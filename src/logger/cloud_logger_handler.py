import logging, atexit, os, re
from threading import Thread, Lock, Event
from typing import Any, List, Optional
from datetime import datetime
from pathlib import Path
from time import sleep

from src.settings import (PATH_LOGS, CLOUD_LOGGER_FOLDER, CLOUD_LOGGER_UPLOAD_INTERVAL, CLOUD_LOGGER_MAX_BUFFER_SIZE, 
CLOUD_LOGGER_MAX_RETRIES, CLOUD_LOGGER_RETRY_DELAY)

from src.services.firebase_client import FirebaseClientStorage
from src.services.firebase_manager import FbManagerStorage
from abc import ABC, abstractmethod

class LogUploaderStrategy(ABC):
    @abstractmethod
    def upload_logs(self, logs_batch: List[str], base_log_folder: Path, log_filename: str) -> bool:
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
        
        # O storage_path_suffix é relativo a users/{uid}/
        # base_log_folder já contém o username_full e version_app
        # Ex: base_log_folder = CLOUD_LOGGER_FOLDER / username_full / version_app
        #     log_filename = username_full_YYYY-MM-DD.txt
        # Precisamos remover a parte "users/{uid}/" que é adicionada por upload_text_user
        # O path completo no bucket seria: users/{uid}/{base_log_folder_sem_users_uid_prefixo}/{log_filename}
        # No entanto, o client_storage.get_text_user espera o path *após* users/{uid}
        
        # Correção: client_storage espera o path relativo à pasta do usuário.
        # base_log_folder é CLOUD_LOGGER_FOLDER / username_full / version_app
        # Se CLOUD_LOGGER_FOLDER é "logs_app", e username_full é "pcuser_appuser",
        # e version_app é "v1", então o path no bucket será:
        # users/UID_DO_USUARIO/logs_app/pcuser_appuser/v1/pcuser_appuser_data.txt
        # O que get_text_user precisa é: "logs_app/pcuser_appuser/v1/pcuser_appuser_data.txt"
        
        # `base_log_folder` é como `logs/username_app/version_app`
        # `log_filename` é `username_app_data.txt`
        # O `storage_path_suffix` para `get_text_user` deve ser `base_log_folder_relativa / log_filename`
        # onde `base_log_folder_relativa` é `CLOUD_LOGGER_FOLDER / username_full / version_app`
        # mas `CLOUD_LOGGER_FOLDER` já está no `base_log_folder`.
        
        # Simplificando: o `storage_path_suffix` deve ser o path a partir de `users/{uid}/`
        # Se `base_log_folder` é `logs_gerais/NomeUsuarioApp/VersaoApp`
        # e `log_filename` é `NomeUsuarioApp_Data.txt`,
        # então o `storage_path_suffix_for_client` seria `logs_gerais/NomeUsuarioApp/VersaoApp/NomeUsuarioApp_Data.txt`
        
        path_suffix = (base_log_folder / log_filename).as_posix()

        try:
            return self.client_storage.get_text_user(
                self._current_user_token, self._current_user_id, path_suffix
            ) or ""
        except Exception as e:
            self.logger.warning(f"ClientLogUploader: Erro ao obter log existente: {e}")
            return ""

    def upload_logs(self, logs_batch: List[str], base_log_folder: Path, log_filename: str) -> bool:
        if not self.client_storage or not self._current_user_token or not self._current_user_id:
            self.logger.warning("ClientLogUploader: Contexto de usuário ou cliente ausente para upload.")
            return False

        path_suffix = (base_log_folder / log_filename).as_posix()
        existing_data = self.get_existing_logs(base_log_folder, log_filename)
        if existing_data and not existing_data.endswith("\n"):
            existing_data += "\n"
        
        log_data_to_upload = existing_data + "\n".join(logs_batch) + "\n"

        return self.client_storage.upload_text_user(
            self._current_user_token, self._current_user_id, log_data_to_upload, path_suffix
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

    def upload_logs(self, logs_batch: List[str], base_log_folder: Path, log_filename: str) -> bool:
        if not self.admin_storage: return False
        
        cloud_path = (base_log_folder / log_filename).as_posix()
        existing_data = self.get_existing_logs(base_log_folder, log_filename)
        if existing_data and not existing_data.endswith("\n"):
             existing_data += "\n"

        log_data_to_upload = existing_data + "\n".join(logs_batch) + "\n"
        try:
            self.admin_storage.upload_text(log_data_to_upload, cloud_path)
            return True
        except Exception as e:
            self.logger.error(f"AdminLogUploader: Falha no upload para {cloud_path}: {e}")
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
                 username_app: str,
                 version_app: str,
                 uploader_strategy: LogUploaderStrategy, # Estratégia de upload injetada
                 level=logging.INFO):
        super().__init__(level=level)
        self.username_app = username_app
        self.version_app = version_app
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
                logger.info("CloudLogHandler: Thread de upload global iniciada.")

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
        logger.info("CloudLogHandler: Thread de upload (estática, com instância) rodando.")
        while not CloudLogHandler.stop_thread_flag:
            signaled = CloudLogHandler.upload_event.wait(CLOUD_LOGGER_UPLOAD_INTERVAL)
            if CloudLogHandler.stop_thread_flag:
                logger.info("CloudLogHandler: Sinal de parada recebido na thread (estática).")
                break

            current_logs_batch = []
            with CloudLogHandler.buffer_lock:
                if CloudLogHandler.log_buffer:
                    current_logs_batch = CloudLogHandler.log_buffer[:]
                    CloudLogHandler.log_buffer.clear()
            
            if signaled: CloudLogHandler.upload_event.clear()

            if current_logs_batch:
                try:
                    # Usa o uploader da instância do handler passada
                    handler_instance._perform_upload(current_logs_batch)
                except Exception as e:
                    logger.error(f"Erro no upload de logs pela thread (estática): {e}", exc_info=True)
        logger.info("CloudLogHandler: Thread de upload (estática) encerrada.")

    def _perform_upload(self, logs_batch: List[str]) -> bool:
        """Método de instância que usa a estratégia de upload configurada."""
        if not logs_batch: return True

        # --- Construção do Path (comum) ---
        try:
            username_pc = os.getlogin()
        except OSError:
            username_pc = "unknown_pc"
        
        username_pc_safe = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', username_pc)
        username_app_safe = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', self.username_app) # Usa da instância
        username_full = username_pc_safe if (username_app_safe in username_pc_safe) else f"{username_pc_safe}_{username_app_safe}"
        username_full = re.sub(r'[^\w\s\d_\-\.]', '', username_full).strip()
        username_full = re.sub(r'\s+', '_', username_full).strip('_') or "default_user"
         # Correção regex para múltiplos underscores/hífens/pontos
        username_full = re.sub(r'[_.-]+', '_', username_full)


        # O base_log_folder agora é relativo ao CLOUD_LOGGER_FOLDER
        # e não inclui o 'users/{uid}' que o client uploader espera.
        # O `base_log_folder` é o que vai *depois* de `users/{uid}/` para o cliente,
        # ou o que vai *depois* do bucket para o admin.
        # Para o ClientUploader, o path no bucket será: `users/{uid}/{CLOUD_LOGGER_FOLDER}/{username_full}/{version_app}/{log_filename}`
        # Para o AdminUploader, o path no bucket será: `{CLOUD_LOGGER_FOLDER}/{username_full}/{version_app}/{log_filename}`
        #
        # Vamos definir `base_log_folder_for_strategy` que é o caminho DENTRO do "diretório" do CLOUD_LOGGER_FOLDER
        # e o `log_filename_for_strategy`.
        # O `uploader.upload_logs` receberá estes dois.
        
        # `base_log_folder_in_cloud` é o caminho a partir da raiz do bucket (para admin)
        # ou a partir de `users/{uid}/` (para cliente).
        # Se CLOUD_LOGGER_FOLDER = "app_logs"
        # base_log_folder_in_cloud = Path("app_logs") / username_full / self.version_app
        base_log_folder_in_cloud = Path(CLOUD_LOGGER_FOLDER) / username_full / self.version_app
        log_filename_in_cloud = f"{username_full}_{datetime.now().strftime('%Y-%m-%d')}.txt"
        
        full_cloud_path_info_for_backup = (base_log_folder_in_cloud / log_filename_in_cloud).as_posix()


        success = False
        for attempt in range(CLOUD_LOGGER_MAX_RETRIES):
            try:
                if self.uploader.upload_logs(logs_batch, base_log_folder_in_cloud, log_filename_in_cloud):
                    self.logger.info(f"CloudLogHandler: Lote de {len(logs_batch)} logs enviado via {self.uploader.__class__.__name__} para pasta base {base_log_folder_in_cloud}")
                    success = True
                    break
                else: # Uploader retornou False explicitamente
                    self.logger.warning(f"CloudLogHandler: Tentativa {attempt + 1} de upload falhou (uploader retornou False).")
            except Exception as e:
                self.logger.error(f"CloudLogHandler: Exceção na tentativa {attempt + 1} de upload via {self.uploader.__class__.__name__}: {e}", exc_info=True)
            
            if not success and attempt < CLOUD_LOGGER_MAX_RETRIES - 1:
                sleep(CLOUD_LOGGER_RETRY_DELAY)
        
        if not success:
            self.logger.error(f"CloudLogHandler: Falha final no upload para CloudStorage via {self.uploader.__class__.__name__}.")
            self._backup_logs_local(logs_batch, full_cloud_path_info_for_backup)
        return success  

    def _backup_logs_local(self, logs_batch: List[str], cloud_path_info: str):
        backup_dir = PATH_LOGS / "logs_backup_cloud_failed"
        backup_dir.mkdir(exist_ok=True)
        backup_file = backup_dir / f"cloud_fail_{self.username_app}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
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
            logger.info("CloudLogHandler: Aguardando thread de upload (estática) encerrar...")
            upload_thread.join(timeout=max(1, CLOUD_LOGGER_UPLOAD_INTERVAL // 2))
            if upload_thread.is_alive():
                logger.warning("CloudLogHandler: WARNING - Timeout ao aguardar thread (estática).")
            else:
                logger.info("CloudLogHandler: Thread de upload (estática) encerrada.")
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

