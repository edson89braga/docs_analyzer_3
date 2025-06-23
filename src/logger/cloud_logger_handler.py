from time import perf_counter
start_time = perf_counter()
print(f"{start_time:.4f}s - Iniciando cloud_logger_handler.py")

import logging, atexit, os, re
from threading import Thread, Lock, Event
from typing import List, Optional
from datetime import datetime, timezone
from pathlib import Path
from time import sleep

from src.settings import (PATH_LOGS, CLOUD_LOGGER_FOLDER, CLOUD_LOGGER_UPLOAD_INTERVAL, CLOUD_LOGGER_MAX_BUFFER_SIZE, 
CLOUD_LOGGER_MAX_RETRIES, CLOUD_LOGGER_RETRY_DELAY, APP_VERSION)

from src.services.firebase_client import FirebaseClientStorage
from src.services.firebase_manager import FbManagerStorage
from abc import ABC, abstractmethod

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

class ClientLogUploader(LogUploaderStrategy):
    def __init__(self, client_storage: FirebaseClientStorage): # Forward reference para FirebaseClientStorage
        self.client_storage = client_storage
        self._current_user_token: Optional[str] = None
        self._current_user_id: Optional[str] = None
        self.logger = logging.getLogger(__name__)

    def set_user_context(self, token: Optional[str], user_id: Optional[str]):
        self._current_user_token = token
        self._current_user_id = user_id
        self.logger.info(f"ClientLogUploader: Contexto do usuário atualizado - ID: {'presente' if user_id else 'ausente'}")

    def get_existing_logs(self, base_log_folder: Path, log_filename: str) -> str:
        if not self.client_storage or not self._current_user_token or not self._current_user_id:
            self.logger.warning("ClientLogUploader: Contexto de usuário ou cliente ausente para get_existing_logs.")
            return ""
        
        path_suffix = (base_log_folder / log_filename).as_posix()

        try:
            return self.client_storage.get_text_user(
                self._current_user_token, self._current_user_id, path_suffix
            ) or ""
        except Exception as e:
            self.logger.warning(f"ClientLogUploader: Erro ao obter log existente: {e}")
            return ""

    def upload_logs(self, logs_batch: List[str], full_cloud_path: str) -> bool:
        if not self.client_storage or not self._current_user_token or not self._current_user_id:
            self.logger.warning("ClientLogUploader: Contexto de usuário ou cliente ausente para upload.")
            return False

        # Removemos get_existing_logs porque mudamos a estratégia de salvar um grande arquivo por dia 
        # para salvar múltiplos arquivos pequenos e únicos ao longo do dia.
        #existing_data = self.get_existing_logs(base_log_folder, log_filename)
        #if existing_data and not existing_data.endswith("\n"):
        #    existing_data += "\n" # log_data_to_upload = existing_data + "\n".join(logs_batch) + "\n"
        
        log_data_to_upload = "\n".join(logs_batch) + "\n"

        return self.client_storage.upload_text_user(
            self._current_user_token, self._current_user_id, log_data_to_upload, full_cloud_path
        )

class AdminLogUploader(LogUploaderStrategy):
    def __init__(self, admin_storage: FbManagerStorage): # Forward reference
        self.admin_storage = admin_storage
        self.logger = logging.getLogger(__name__)

    def get_existing_logs(self, base_log_folder: Path, log_filename: str) -> str:
        if not self.admin_storage: return ""
        cloud_path = (base_log_folder / log_filename).as_posix()
        try:
            return self.admin_storage.get_text(cloud_path) or ""
        except Exception as e:
            self.logger.warning(f"AdminLogUploader: Erro ao obter log existente ({cloud_path}): {e}")
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
            self.logger.error(f"AdminLogUploader: Falha no upload para {full_cloud_path}: {e}")
            return False

class CloudLogHandler(logging.Handler):
    """
    Handler personalizado para enviar logs para o CloudStorage.
    Gerencia um buffer interno e uma thread para upload periódico/em lote.
    """
    log_buffer: List[str] = []
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
        logger = logging.getLogger(__name__)
        self.logger = logger

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
                logger.info("CloudLogHandler: Método de cleanup global registrado no atexit.")
             
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
                CloudLogHandler.log_buffer.append(log_message_utf8)
                buffer_size = len(CloudLogHandler.log_buffer)

            if buffer_size >= CLOUD_LOGGER_MAX_BUFFER_SIZE:
                CloudLogHandler.upload_event.set() # Sinaliza a thread fora do lock

        except Exception:
            self.handleError(record) # Usa o tratamento de erro padrão do Handler
        
    @staticmethod 
    def _upload_logs_thread_target_static(handler_instance: 'CloudLogHandler'):
        """Método alvo da thread. Aguarda sinal/timeout e dispara upload."""
        logger = logging.getLogger(__name__)
        logger.debug("CloudLogHandler: Thread de upload (estática, com instância) rodando.")
        while not CloudLogHandler.stop_thread_flag:
            signaled = CloudLogHandler.upload_event.wait(CLOUD_LOGGER_UPLOAD_INTERVAL)
            if CloudLogHandler.stop_thread_flag:
                logger.info("CloudLogHandler: Sinal de parada recebido na thread (estática).")
                break

            current_logs_batch = []
            with CloudLogHandler.buffer_lock:
                if CloudLogHandler.log_buffer:
                    current_logs_batch = CloudLogHandler.log_buffer[:]
                    # CloudLogHandler.log_buffer.clear()
            
            if signaled: CloudLogHandler.upload_event.clear()

            if current_logs_batch:
                upload_completed_successfully = False
                try:
                    upload_completed_successfully = handler_instance._perform_upload(current_logs_batch)

                    if upload_completed_successfully:
                        with CloudLogHandler.buffer_lock: # Limpa o buffer SÓ SE teve sucesso
                            if CloudLogHandler.log_buffer and CloudLogHandler.log_buffer[:len(current_logs_batch)] == current_logs_batch:
                                    CloudLogHandler.log_buffer = CloudLogHandler.log_buffer[len(current_logs_batch):]
                            else: # Se o buffer mudou enquanto processava, seja mais cuidadoso (raro)
                                    logger.warning("CloudLogHandler: Buffer modificado durante upload. Limpeza pode ser imprecisa.")
                                    CloudLogHandler.log_buffer.clear() # Fallback para limpar tudo
                    # Se não teve sucesso (upload_completed_successfully é False),
                    # os logs permanecem no CloudLogHandler.log_buffer para a próxima tentativa.
                    # A lógica de backup local dentro de _perform_upload já cuida dos casos de falha real.

                except Exception as e:
                    logger.error(f"Erro no upload de logs pela thread (estática): {e}", exc_info=True)
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

        # Determina o user_id para o nome do arquivo. Usa "anonymous" se não autenticado.
        user_id_for_filename = "anonymous_user"
        if isinstance(self.uploader, ClientLogUploader) and self.uploader._current_user_id:
            user_id_for_filename = self.uploader._current_user_id
        
        # Estrutura de pasta baseada em data
        now = datetime.now(timezone.utc)
        base_log_folder_in_cloud = Path(CLOUD_LOGGER_FOLDER) / now.strftime('%Y/%m/%d')
        
        # Novo padrão de nome de arquivo
        log_filename_in_cloud = f"{username_pc_safe}_{now.strftime('%H%M%S')}_{user_id_for_filename}.log"
        
        # Caminho completo do objeto no Storage
        full_cloud_path = (base_log_folder_in_cloud / log_filename_in_cloud).as_posix()

        success = False
        initial_upload_attempt_failed_gracefully = False

        # Verifica se o uploader é o ClientLogUploader e se ele tem contexto
        can_attempt_client_upload = isinstance(self.uploader, ClientLogUploader) and \
                                    self.uploader._current_user_token and \
                                    self.uploader._current_user_id

        if isinstance(self.uploader, ClientLogUploader) and not can_attempt_client_upload:
            self.logger.info(f"CloudLogHandler: ClientUploader selecionado, mas sem contexto de usuário. Upload adiado.")
            initial_upload_attempt_failed_gracefully = True # Indica que não devemos fazer retries ou backup agressivo
            # Não retorna True aqui, pois pode haver um fallback para AdminUploader
            # Se não houver fallback, os logs ficarão no buffer.

        if not initial_upload_attempt_failed_gracefully: # Só tenta upload real se não for um "adiamento" do cliente
            for attempt in range(CLOUD_LOGGER_MAX_RETRIES):
                try:
                    upload_successful_this_attempt = False
                    if isinstance(self.uploader, ClientLogUploader):
                        if can_attempt_client_upload:
                            upload_successful_this_attempt = self.uploader.upload_logs(logs_batch, full_cloud_path)
                        # else: não tenta, já tratado por initial_upload_attempt_failed_gracefully
                    elif isinstance(self.uploader, AdminLogUploader): # Se for AdminUploader, sempre tenta
                        upload_successful_this_attempt = self.uploader.upload_logs(logs_batch, full_cloud_path)
                    else: # Estratégia desconhecida
                        self.logger.error(f"CloudLogHandler: Estratégia de uploader desconhecida: {self.uploader.__class__.__name__}")
                        break # Sai do loop de retentativas

                    if upload_successful_this_attempt:
                        self.logger.info(f"CloudLogHandler: Lote de {len(logs_batch)} logs enviado via {self.uploader.__class__.__name__} para pasta base {full_cloud_path}")
                        success = True
                        break
                    else:
                        self.logger.warning(f"CloudLogHandler: Tentativa {attempt + 1} de upload falhou (uploader {self.uploader.__class__.__name__} retornou False).")
                except Exception as e:
                    self.logger.error(f"CloudLogHandler: Exceção na tentativa {attempt + 1} de upload via {self.uploader.__class__.__name__}: {e}", exc_info=True)
                
                if not success and attempt < CLOUD_LOGGER_MAX_RETRIES - 1:
                    sleep(CLOUD_LOGGER_RETRY_DELAY)
        
        # Só faz backup se a tentativa de upload realmente falhou (não se foi adiada por falta de contexto do cliente)
        if not success and not initial_upload_attempt_failed_gracefully:
            self.logger.error(f"CloudLogHandler: Falha final no upload para CloudStorage via {self.uploader.__class__.__name__}.")
            self._backup_logs_local(logs_batch, full_cloud_path)
        elif initial_upload_attempt_failed_gracefully and not success:
            self.logger.info("CloudLogHandler: Upload via cliente adiado, logs permanecem no buffer.")
            pass
        return success  

    def _backup_logs_local(self, logs_batch: List[str], cloud_path_info: str):
        backup_dir = PATH_LOGS / "logs_backup_cloud_failed"
        backup_dir.mkdir(exist_ok=True)
        backup_file = backup_dir / f"cloud_fail_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        try:
            with open(backup_file, 'w', encoding='utf-8') as f:
                f.write(f"# Falha no upload para nuvem. Uploader: {self.uploader.__class__.__name__}\n")
                f.write(f"# Path/Info no Cloud: {cloud_path_info}\n")
                f.write(f"# Data/Hora da falha: {datetime.now()}\n\n")
                f.write("\n".join(logs_batch) + "\n")
            self.logger.info(f"Logs não enviados salvos localmente em: {backup_file}")
        except Exception as be:
            self.logger.error(f"Erro crítico ao salvar backup local de logs da nuvem: {be}", exc_info=True)

    @staticmethod
    def _force_upload_on_exit_static(handler_instance: 'CloudLogHandler'):
        """Método de instância chamado por atexit para upload final e cleanup."""
        logger = logging.getLogger(__name__)
        logger.info("CloudLogHandler: Executando upload final (estático, com instância) antes de encerrar...")
        CloudLogHandler.stop_thread_flag = True
        CloudLogHandler.upload_event.set()

        final_logs = []
        with CloudLogHandler.buffer_lock:
            if CloudLogHandler.log_buffer:
                final_logs = CloudLogHandler.log_buffer[:]
                CloudLogHandler.log_buffer.clear()
                logger.info(f"CloudLogHandler: {len(final_logs)} logs do buffer para upload final.")
        
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
        logger.info("CloudLogHandler: Processo de encerramento do logger da nuvem (estático) concluído.")

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
print(f"Carregado CLOUD_LOGGER em {execution_time:.4f}s")
