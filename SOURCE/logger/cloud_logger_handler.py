import logging, time
logger = logging.getLogger(__name__)

from time import sleep
from time import perf_counter
start_time = perf_counter()
logger.debug(f"{start_time:.4f}s - Iniciando cloud_logger_handler.py")

import atexit, os, re
from threading import Thread, Lock, Event
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from pathlib import Path

from SOURCE.settings import (PATH_LOGS_DIR, CLOUD_LOGGER_FOLDER, CLOUD_LOGGER_UPLOAD_INTERVAL, CLOUD_LOGGER_MAX_BUFFER_SIZE, 
CLOUD_LOGGER_MAX_RETRIES, CLOUD_LOGGER_RETRY_DELAY, APP_VERSION)

from SOURCE.services.firebase_client import FirebaseClientStorage
from SOURCE.services.firebase_manager import FbManagerStorage
from abc import ABC, abstractmethod
import contextvars
from pathlib import Path
PATH_LOGS_DIR = Path(PATH_LOGS_DIR)

# Variáveis de contexto para manter isolamento entre requisições concorrentes
user_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("user_id_ctx", default="anonymous_user")
user_email_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("user_email_ctx", default=None)

class LogUploaderStrategy(ABC):
    @abstractmethod
    def upload_logs(self, logs_batch: List[str], full_cloud_path: str) -> bool:
        """
        Tenta fazer upload de um lote de logs.
        Retorna True em sucesso, False em falha.
        """
        pass

    @abstractmethod
    def get_existing_logs(self, base_log_folder: Path, log_filename: str) -> str:
        """
        Tenta obter o conteúdo de logs existentes para append.
        Retorna o conteúdo ou string vazia.
        """
        pass

class AdminLogUploader(LogUploaderStrategy):
    def __init__(self, admin_storage: FbManagerStorage): # Forward reference
        self.admin_storage = admin_storage

    def get_existing_logs(self, base_log_folder: Path, log_filename: str) -> str:
        if not self.admin_storage: return ""
        cloud_path = (base_log_folder / log_filename).as_posix()
        try:
            return self.admin_storage.get_text(cloud_path) or ""
        except Exception as e:
            logger.warning(f"AdminLogUploader: Erro ao obter log existente ({cloud_path}): {e}")
            return ""

    def upload_logs(self, logs_batch: List[str], full_cloud_path: str) -> bool:
        if not self.admin_storage: return False
        
        #existing_data = self.get_existing_logs(full_cloud_path)
        #if existing_data and not existing_data.endswith("\n"):
        #    existing_data += "\n"

        log_data_to_upload = "\n".join(logs_batch) + "\n"
        try:
            self.admin_storage.upload_text(log_data_to_upload, full_cloud_path)
            return True
        except Exception as e:
            logger.error(f"AdminLogUploader: Falha no upload para {full_cloud_path}: {e}")
            return False

class CloudLogHandler(logging.Handler):
    """
    Handler personalizado para enviar logs para o CloudStorage.
    Gerencia um buffer interno e uma thread para upload periódico/em lote.
    """
    # Dicionário para isolar buffers por usuário: { "user_id": {"token": str, "logs": List[str]} }
    log_buffers: Dict[str, Dict[str, Any]] = {}    
    upload_thread: Optional[Thread] = None
    stop_thread_flag: bool = False
    buffer_lock: Lock = Lock()
    upload_event: Event = Event()
    _atexit_registered: bool = False # Para registrar atexit apenas uma vez globalmente
    
    # Informações da aplicação e uploader agora são de instância
    def __init__(self,
                 uploader_strategy: LogUploaderStrategy, # Estratégia de upload injetada
                 level=logging.INFO):
        super().__init__(level=level)
        self.uploader = uploader_strategy # Uploader strategy

        # Gerenciamento da thread (pode ser iniciado uma vez globalmente ou por instância)
        # Para simplificar, vamos manter uma thread global controlada por flags de classe.
        with CloudLogHandler.buffer_lock:
            if CloudLogHandler.upload_thread is None or not CloudLogHandler.upload_thread.is_alive():
                CloudLogHandler.stop_thread_flag = False
                CloudLogHandler.upload_event.clear()
                # Passamos a instância do handler para a thread ter acesso aos seus atributos
                CloudLogHandler.upload_thread = Thread(target=CloudLogHandler._upload_logs_thread_target_static,
                                                       args=(self,), daemon=True)
                CloudLogHandler.upload_thread.start()
                logger.debug("CloudLogHandler: Thread de upload global iniciada.")

            if not CloudLogHandler._atexit_registered:
                atexit.register(CloudLogHandler._force_upload_on_exit_static, self) # Passa a instância
                CloudLogHandler._atexit_registered = True
                logger.debug("CloudLogHandler: Método de cleanup global registrado no atexit.")
             
    def emit(self, record: logging.LogRecord):
        """Adiciona um registro formatado ao buffer e sinaliza para upload se cheio."""
        # Ignora logs do próprio handler para evitar recursão (opcional)
        if record.name == __name__ or record.module == "cloud_logger_handler":
            return
        try:
            try:
                log_message = self.format(record)
                log_message_utf8 = log_message.encode('utf-8', errors='replace').decode('utf-8')
            except UnicodeError:
                log_message_utf8 = repr(log_message) # Fallback extremo

            if not log_message_utf8.strip():
                return # Ignora mensagens vazias

            with CloudLogHandler.buffer_lock:
                uid = user_id_ctx.get() or "anonymous_user"
                
                if uid not in CloudLogHandler.log_buffers:
                    CloudLogHandler.log_buffers[uid] = {"logs": []}
                    
                CloudLogHandler.log_buffers[uid]["logs"].append(log_message_utf8)
                buffer_size = sum(len(data["logs"]) for data in CloudLogHandler.log_buffers.values())

            if buffer_size >= CLOUD_LOGGER_MAX_BUFFER_SIZE:
                CloudLogHandler.upload_event.set() # Sinaliza a thread fora do lock

        except Exception:
            self.handleError(record) # Usa o tratamento de erro padrão do Handler
        
    @staticmethod 
    def _upload_logs_thread_target_static(handler_instance: 'CloudLogHandler'):
        """Método alvo da thread. Aguarda sinal/timeout e dispara upload."""
        logger.debug("CloudLogHandler: Thread de upload (estática, com instância) rodando.")
        while not CloudLogHandler.stop_thread_flag:
            signaled = CloudLogHandler.upload_event.wait(CLOUD_LOGGER_UPLOAD_INTERVAL)
            if CloudLogHandler.stop_thread_flag:
                logger.debug("CloudLogHandler: Sinal de parada recebido na thread (estática).")
                break

            snapshot_buffers = {}
            with CloudLogHandler.buffer_lock:
                if CloudLogHandler.log_buffers:
                    # Faz uma cópia rasa do estado atual e limpa o global
                    snapshot_buffers = CloudLogHandler.log_buffers.copy()
                    CloudLogHandler.log_buffers.clear()
            
            if signaled: CloudLogHandler.upload_event.clear()

            for uid, data in snapshot_buffers.items():
                current_logs_batch = data["logs"]
                
                if not current_logs_batch:
                    continue
                try:
                    # Injeta o contexto da thread original na thread de background temporariamente
                    user_id_ctx.set(uid)
                    
                    success = handler_instance._perform_upload(current_logs_batch)
                    
                    if not success:
                        logger.warning(f"CloudLogHandler: Falha no upload para uid={uid[:8]}...")

                except Exception as e:
                    logger.error(f"Erro no upload de logs do usuário {uid} pela thread: {e}", exc_info=True)
        logger.debug("CloudLogHandler: Thread de upload (estática) encerrada.")

    def _perform_upload(self, logs_batch: List[str]) -> bool:
        """Método de instância que usa a estratégia de upload configurada."""
        if not logs_batch: return True

        # --- Construção do Path (comum) ---
        try: username_pc = os.getlogin()
        except OSError: username_pc = "unknown_pc"
        
        # Limpeza do nome do PC
        username_pc_safe = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', username_pc)
        username_pc_safe = re.sub(r'[^\w\s\d_\-\.]', '', username_pc_safe).strip()
        username_pc_safe = re.sub(r'\s+', '_', username_pc_safe).strip('_') or "default_user"
         # Correção regex para múltiplos underscores/hífens/pontos
        username_pc_safe = re.sub(r'[_.-]+', '_', username_pc_safe)

        # Identificação pelo username do email (ex: "joao.silva" de "joao.silva@pf.gov.br")
        raw_email = user_email_ctx.get() or ""
        if raw_email and "@" in raw_email:
            email_username = raw_email.split("@")[0]
        else:
            uid = user_id_ctx.get() or "anonymous"
            email_username = uid[:8]  # fallback: prefixo do uid se email indisponível
        user_label = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', email_username) 

        # Estrutura de pasta baseada em data
        now = datetime.now(timezone.utc)
        # Diretório único por data, nome do arquivo identifica o usuário
        base_log_folder_in_cloud = Path(CLOUD_LOGGER_FOLDER) / now.strftime('%Y/%m/%d')
        log_filename_in_cloud = f"{user_label}_{now.strftime('%H%M%S')}_{username_pc_safe}.log"
        # Caminho completo do objeto no Storage
        full_cloud_path = (base_log_folder_in_cloud / log_filename_in_cloud).as_posix()

        success = False
        
        for attempt in range(CLOUD_LOGGER_MAX_RETRIES):
            try:
                if self.uploader.upload_logs(logs_batch, full_cloud_path):
                    logger.info(
                        f"CloudLogHandler: Lote de {len(logs_batch)} logs enviado para "
                        f"{full_cloud_path}"
                    )
                    success = True
                    break
                else:
                    logger.warning(
                        f"CloudLogHandler: Tentativa {attempt + 1}/{CLOUD_LOGGER_MAX_RETRIES} "
                        f"falhou para {full_cloud_path}."
                    )
            except Exception as e:
                logger.error(
                    f"CloudLogHandler: Exceção na tentativa {attempt + 1}: {e}", exc_info=True
                )
            if not success and attempt < CLOUD_LOGGER_MAX_RETRIES - 1:
                sleep(CLOUD_LOGGER_RETRY_DELAY)

        if not success:        
            logger.error(f"CloudLogHandler: Falha final no upload para CloudStorage via {self.uploader.__class__.__name__}.")
            self._backup_logs_local(logs_batch, full_cloud_path)
            
        return success  

    def _backup_logs_local(self, logs_batch: List[str], cloud_path_info: str):
        backup_dir = PATH_LOGS_DIR / "logs_backup_cloud_failed"
        backup_dir.mkdir(exist_ok=True)
        backup_file = backup_dir / f"cloud_fail_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        try:
            with open(backup_file, 'w', encoding='utf-8') as f:
                f.write(f"# Falha no upload para nuvem. Uploader: {self.uploader.__class__.__name__}\n")
                f.write(f"# Path/Info no Cloud: {cloud_path_info}\n")
                f.write(f"# Data/Hora da falha: {datetime.now()}\n\n")
                f.write("\n".join(logs_batch) + "\n")
            logger.debug(f"Logs não enviados salvos localmente em: {backup_file}")
        except Exception as be:
            logger.error(f"Erro crítico ao salvar backup local de logs da nuvem: {be}", exc_info=True)

    @staticmethod
    def _force_upload_on_exit_static(handler_instance: 'CloudLogHandler'):
        """Método de instância chamado por atexit para upload final e cleanup."""
        logger.debug("CloudLogHandler: Executando upload final (estático, com instância) antes de encerrar...")
        CloudLogHandler.stop_thread_flag = True
        CloudLogHandler.upload_event.set()

        final_logs = []
        with CloudLogHandler.buffer_lock:
            if CloudLogHandler.log_buffer:
                final_logs = CloudLogHandler.log_buffer[:]
                CloudLogHandler.log_buffer.clear()
                logger.debug(f"CloudLogHandler: {len(final_logs)} logs do buffer para upload final.")
        
        if final_logs:
            try:
                handler_instance._perform_upload(final_logs)
            except Exception as e:
                logger.error(f"Erro durante upload final do buffer (estático): {e}", exc_info=True)

        upload_thread = CloudLogHandler.upload_thread
        if upload_thread and upload_thread.is_alive():
            # ... (lógica de join como antes)
            logger.debug("CloudLogHandler: Aguardando thread de upload (estática) encerrar...")
            upload_thread.join(timeout=max(1, CLOUD_LOGGER_UPLOAD_INTERVAL // 2))
            if upload_thread.is_alive():
                logger.warning("CloudLogHandler: WARNING - Timeout ao aguardar thread (estática).")
            else:
                logger.debug("CloudLogHandler: Thread de upload (estática) encerrada.")
        logger.debug("CloudLogHandler: Processo de encerramento do logger da nuvem (estático) concluído.")

    def flush(self):
        """Força o envio imediato do buffer de logs atual."""
        current_logs = []
        with CloudLogHandler.buffer_lock:
            if CloudLogHandler.log_buffer:
                current_logs = CloudLogHandler.log_buffer[:]
                CloudLogHandler.log_buffer.clear()

        if current_logs:
            self._perform_upload(current_logs)


execution_time = perf_counter() - start_time
logger.debug(f"Carregado CLOUD_LOGGER em {execution_time:.4f}s")
