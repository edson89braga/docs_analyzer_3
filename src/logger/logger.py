import os, shutil, logging, atexit, re
from sys import version
from time import time, sleep
from threading import Thread, Lock, Event
from pathlib import Path
from logging.handlers import RotatingFileHandler
from rich.logging import RichHandler
from datetime import datetime, timedelta
from typing import List, Optional, Any

from src.settings import (PATH_LOGS, CLOUD_LOGGER_FOLDER, CLOUD_LOGGER_UPLOAD_INTERVAL, CLOUD_LOGGER_MAX_BUFFER_SIZE, 
CLOUD_LOGGER_MAX_RETRIES, CLOUD_LOGGER_RETRY_DELAY)

# Cria o diretório de logs se não existir
log_dir = Path(PATH_LOGS)
log_dir.mkdir(exist_ok=True)

modules_to_log = []

class ModuleFilter(logging.Filter):
    """Filtro para registrar logs apenas de módulos específicos."""
    
    def __init__(self, modules: List[str]):
        super().__init__()
        self.modules = modules
    
    def filter(self, record: logging.LogRecord) -> bool:
        return record.module in self.modules

class CloudLogHandler(logging.Handler):
    """
    Handler personalizado para enviar logs para o CloudStorage.
    Gerencia um buffer interno e uma thread para upload periódico/em lote.
    """
    
    # Atributos de classe para gerenciar buffer e thread compartilhados
    log_buffer = []
    upload_thread = None
    stop_thread = False # Flag para controlar a thread de upload

    buffer_lock = Lock()
    upload_event = Event()
    _instance = None # Para rastrear a instância única para atexit

    def __init__(self, fb_manager: Any, username_app: str, version_app: str):
        """
        Inicializa o Handler.

        Args:
            fb_manager: Instância do gerenciador de storage (ex: FirebaseManager).
            username_app: Nome do usuário/aplicação para identificação no log.
            version_app: Versão da aplicação para identificação no log.
        """
        super().__init__()
        self.fb_manager = fb_manager
        self.username_app = username_app
        self.version_app = version_app

        # --- Gerenciamento da Thread e Registro Atexit ---
        with CloudLogHandler.buffer_lock: # Lock para criação segura da thread
            if CloudLogHandler.upload_thread is None or not CloudLogHandler.upload_thread.is_alive():
                CloudLogHandler.stop_thread_flag = False
                CloudLogHandler.upload_event.clear()
                # Passa self para que a thread possa chamar métodos da instância se necessário
                # (embora estejamos usando classmethod para upload agora)
                CloudLogHandler.upload_thread = Thread(target=self._upload_logs_thread_target, daemon=True)
                CloudLogHandler.upload_thread.start()
                print("CloudLogHandler: Thread de upload iniciada.")

            # Registra o método de cleanup da *instância* no atexit, apenas uma vez.
            if not CloudLogHandler._instance:
                # _force_upload_on_exit é um método de instância, correto para atexit
                atexit.register(self._force_upload_on_exit)
                CloudLogHandler._instance = True
                print("CloudLogHandler: Método de cleanup registrado no atexit.")

    def emit(self, record: logging.LogRecord):
        """Adiciona um registro formatado ao buffer e sinaliza para upload se cheio."""
        # Ignora logs do próprio handler para evitar recursão (opcional)
        if record.name == __name__:
             return
        try:
            log_message = self.format(record)
            try:
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

    def _upload_logs_thread_target(self):
        """Método alvo da thread. Aguarda sinal/timeout e dispara upload."""
        print("CloudLogHandler: Thread de upload rodando.")
        while not CloudLogHandler.stop_thread_flag:
            # Espera pelo evento ou pelo timeout
            signaled = CloudLogHandler.upload_event.wait(CLOUD_LOGGER_UPLOAD_INTERVAL)

            if CloudLogHandler.stop_thread_flag:
                print("CloudLogHandler: Sinal de parada recebido na thread.")
                break

            current_logs = []
            with CloudLogHandler.buffer_lock:
                if CloudLogHandler.log_buffer:
                    current_logs = CloudLogHandler.log_buffer[:]
                    CloudLogHandler.log_buffer.clear()

            # Reseta evento *após* processar, caso tenha sido sinalizado
            if signaled:
                CloudLogHandler.upload_event.clear()

            if current_logs:
                try:
                    # Chama o método de classe para realizar o upload
                    CloudLogHandler.upload_logs_batch_static(
                        current_logs, self.fb_manager, self.username_app, self.version_app
                    )
                except Exception as e:
                    print(f"Erro no upload de logs pela thread: {e}")
                    # Considerar adicionar logs de volta ao buffer ou salvar localmente aqui também
                    # Ex: with CloudLogHandler.buffer_lock: CloudLogHandler.log_buffer[:0] = current_logs

        print("CloudLogHandler: Thread de upload encerrada.")

    @classmethod
    def upload_logs_batch_static(cls, logs_batch: List[str], fb_manager: Any, username_app: str, version_app: str):
        """
        (@classmethod) Faz upload de um lote de logs para o CloudStorage com retries.

        Args:
            logs_batch: Lista de strings de log para upload.
            fb_manager: Instância do gerenciador de storage.
            username_app: Nome do usuário/aplicação.
            version_app: Versão da aplicação.

        Returns:
            bool: True se o upload foi bem-sucedido, False caso contrário.
        """
        if not logs_batch or not fb_manager:
            return True # Nada a fazer ou sem manager

        # --- Sanitização e Construção do Path ---
        try:
            username_pc = os.getlogin()
        except OSError:
            username_pc = "unknown_pc" # Fallback

        username_pc_safe = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', username_pc)
        username_app_safe = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', username_app)
        # Lógica original de combinação e limpeza
        username_full = username_pc_safe if (username_app_safe in username_pc_safe) else f"{username_pc_safe}_{username_app_safe}"
        username_full = re.sub(r'[^\w\s\d_\-\.]', '', username_full)
        username_full = re.sub(r'\s+', '_', username_full)
        username_full = re.sub(r'[_\-\.]+', '_', username_full)
        username_full = re.sub(r'^_|_$', '', username_full).strip() or "default_user"

        log_folder_user = Path(CLOUD_LOGGER_FOLDER) / username_full / version_app
        log_filename = f"{username_full}_{datetime.now().strftime('%Y-%m-%d')}.txt"
        cloud_path = log_folder_user / log_filename
        cloud_path_str = cloud_path.as_posix() # Caminho estilo Unix para storage

        # --- Lógica de Upload com Retry e Append ---
        log_data_to_upload = ""
        success = False
        for attempt in range(CLOUD_LOGGER_MAX_RETRIES):
            try:
                try:
                    existing_data = fb_manager.get_text(cloud_path_str)
                    if existing_data and not existing_data.endswith("\n"):
                        existing_data += "\n"
                except Exception: # Captura falha ao buscar (ex: arquivo não existe)
                    existing_data = ""

                log_data_to_upload = existing_data + "\n".join(logs_batch) + "\n"
                fb_manager.upload_text(log_data_to_upload, cloud_path_str)
                # print(f"CloudLogHandler: Lote de {len(logs_batch)} logs enviado para {cloud_path_str}") # Debug
                success = True
                break # Sai do loop de retry

            except Exception as e:
                print(f"Erro no upload (tentativa {attempt + 1}/{CLOUD_LOGGER_MAX_RETRIES}) para '{cloud_path_str}': {e}")
                if attempt < CLOUD_LOGGER_MAX_RETRIES - 1:
                    sleep(CLOUD_LOGGER_RETRY_DELAY)
                else:
                    print(f"Falha final no upload para CloudStorage após {CLOUD_LOGGER_MAX_RETRIES} tentativas.")
                    # --- Backup Local ---
                    backup_dir = Path("logs_backup")
                    backup_dir.mkdir(exist_ok=True)
                    backup_file = backup_dir / f"cloud_fail_{username_full}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
                    try:
                        with open(backup_file, 'w', encoding='utf-8') as f:
                            f.write(f"# Falha no upload para: {cloud_path_str}\n")
                            f.write(f"# Data/Hora da falha: {datetime.now()}\n\n")
                            f.write("\n".join(logs_batch) + "\n")
                        print(f"Logs não enviados salvos localmente em: {backup_file}")
                    except Exception as be:
                        print(f"Erro crítico ao salvar backup local: {be}")
                    success = False # Garante que retornará False
        return success

    def _force_upload_on_exit(self):
        """Método de instância chamado por atexit para upload final e cleanup."""
        print("CloudLogHandler: Executando upload final antes de encerrar...")

        # 1. Sinaliza a thread para parar
        CloudLogHandler.stop_thread_flag = True
        CloudLogHandler.upload_event.set() # Acorda a thread caso esteja esperando

        # 2. Pega logs restantes do buffer
        final_logs = []
        with CloudLogHandler.buffer_lock:
            if CloudLogHandler.log_buffer:
                final_logs = CloudLogHandler.log_buffer[:]
                CloudLogHandler.log_buffer.clear()
                print(f"CloudLogHandler: {len(final_logs)} logs do buffer para upload final.")

        # 3. Tenta upload final (usa método de classe)
        if final_logs:
            try:
                CloudLogHandler.upload_logs_batch_static(
                    final_logs, self.fb_manager, self.username_app, self.version_app
                )
            except Exception as e:
                print(f"Erro durante upload final do buffer: {e}")
                # Considerar salvar localmente aqui também

        # 4. Espera a thread terminar (com timeout)
        upload_thread = CloudLogHandler.upload_thread # Ref local
        if upload_thread and upload_thread.is_alive():
            print("CloudLogHandler: Aguardando thread de upload encerrar...")
            upload_thread.join(timeout=max(1, CLOUD_LOGGER_UPLOAD_INTERVAL // 2)) # Timeout razoável
            if upload_thread.is_alive():
                 print("CloudLogHandler: WARNING - Timeout ao aguardar thread. Pode não ter finalizado.")
            else:
                 print("CloudLogHandler: Thread de upload encerrada.")

        print("CloudLogHandler: Processo de encerramento do logger da nuvem concluído.")

    def flush(self):
        """Força o envio imediato do buffer de logs atual."""
        current_logs = []
        with CloudLogHandler.buffer_lock:
            if CloudLogHandler.log_buffer:
                current_logs = CloudLogHandler.log_buffer[:]
                CloudLogHandler.log_buffer.clear()

        if current_logs:
            try:
                CloudLogHandler.upload_logs_batch_static(
                    current_logs, self.fb_manager, self.username_app, self.version_app
                )
            except Exception as e:
                print(f"Erro durante flush manual de logs: {e}")
                # Decide se adiciona de volta ao buffer ou não
                # with CloudLogHandler.buffer_lock: CloudLogHandler.log_buffer[:0] = current_logs

class LoggerSetup:
    """Classe responsável pela configuração e setup de loggers."""
    
    ### Formats: 
    # Formato detalhado para o arquivo de log, com informações de data, hora, nível, módulo, função, linha, mensagem
    formatter_detailed = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Formato resumido para a saída padrão, sem data e hora
    formatter_resumed = logging.Formatter( # Retirado %(asctime)s pois já vem embutido no RichHandler
        fmt='%(message)s', 
        datefmt='%H:%M:%S'
    )
    
    _instance: Optional[logging.Logger] = None
    _initialized = False
    _loggers = {}  # Dicionário para rastrear todos os loggers criados
    _cloud_handler_instance: Optional[CloudLogHandler] = None # Instância única do handler cloud
    
    logging.getLogger('httpx').setLevel(logging.WARNING)
    
    @classmethod
    def _create_file_handler(cls, log_file, formatter, level=logging.DEBUG):
        handler = RotatingFileHandler(
            filename=log_file,
            maxBytes=10*1024*1024,
            backupCount=6,
            encoding='utf-8',
            delay=True
        )
        handler.setLevel(level)
        handler.setFormatter(formatter)
        return handler

    @classmethod
    def _create_console_handler(cls, formatter, level=logging.INFO):
        handler = RichHandler(
            level=level,
            show_level=False,
            rich_tracebacks=True,
            tracebacks_show_locals=False,
            markup=True,
            keywords=["INFO", "WARNING", "ERROR", "CRITICAL"]
        )
        handler.setFormatter(formatter)
        return handler

    @classmethod
    def _create_cloud_logger_handler(cls, formatter, fb_manager, username_app, version_app, level=logging.INFO):
        if not fb_manager:
             print("LoggerSetup: fb_manager não fornecido. Cloud logging desabilitado.")
             return None
        # Cria a instância apenas uma vez
        if cls._cloud_handler_instance is None:
             try:
                 print("LoggerSetup: Criando instância do CloudLogHandler...")
                 cls._cloud_handler_instance = CloudLogHandler(fb_manager, username_app, version_app)
                 cls._cloud_handler_instance.setLevel(level)
                 cls._cloud_handler_instance.setFormatter(formatter)
                 print("LoggerSetup: CloudLogHandler criado com sucesso.")
             except Exception as e:
                 print(f"LoggerSetup: Erro ao inicializar CloudLogHandler: {e}. Cloud logging desabilitado.")
                 cls._cloud_handler_instance = None # Garante estado consistente

        return cls._cloud_handler_instance
    
    @classmethod
    def _setup_temporary_logger(cls, logger_name):
        """Configura um logger temporário básico antes da inicialização completa."""
        global log_dir
        logger = logging.getLogger(logger_name)
        if not logger.handlers:            
            # Adiciona console handler
            console_handler = cls._create_console_handler(cls.formatter_resumed, logging.INFO)
            logger.addHandler(console_handler)
            
            # Adiciona file handler
            file_handler = cls._create_file_handler(
                log_dir / "Root_temp.log",
                cls.formatter_detailed, 
                logging.DEBUG
            )
            logger.addHandler(file_handler)
                        
            logger.setLevel(logging.INFO)
            logger.propagate = True

    @classmethod
    def _rotate_log_file(cls, base_log_file, dated_log_file):
        """Executa a rotação de um arquivo de log."""
        try:
            if base_log_file.exists() and not dated_log_file.exists():
                try:
                    shutil.copy2(base_log_file, dated_log_file)
                    base_log_file.unlink()
                except (OSError, IOError) as e:
                    print(f"Erro ao copiar arquivo de log: {e}")
        except Exception as e:
            print(f"Erro ao rotacionar arquivo de log: \n{e}")

    @classmethod
    def _apply_module_filter(cls, logger, modules_to_log):
        """Aplica o filtro de módulos de forma consistente."""
        if not modules_to_log:
            return
            
        module_filter = ModuleFilter(modules_to_log)
        logger.addFilter(module_filter) 

    @classmethod
    def initialize(cls, 
                   routine_name: str,
                   fb_manager: Any,
                   username_app: str,
                   version_app: str,
                   modules_to_log: Optional[List[str]] = None, # None para desabilitar filtro
                   custom_handler: Optional[logging.Handler] = None,) -> None:
        """
        Inicializa o logger global. Deve ser chamado uma vez no início do programa.
        
        Args:
            routine_name: Nome da rotina para o arquivo de log.
            modules_to_log: Lista de módulos para filtrar os logs.
            custom_handler: Handler personalizado para ser adicionado ao logger.
        """   
        global log_dir
        ### file_handler:
        # Cria o nome do arquivo de log com base no nome da rotina
        safe_routine_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in routine_name)
        
        # Cria o nome do arquivo de log com a data atual
        current_date = datetime.now().strftime('%Y-%m-%d')
        base_log_file = log_dir / f"{safe_routine_name}.log"
        dated_log_file = log_dir / f"{safe_routine_name}_{current_date}.log"

        try:
            # Se o arquivo de log existir, renomeia-o para o nome com data
            if base_log_file.exists():
                if not dated_log_file.exists():
                    try:
                        shutil.copy2(base_log_file, dated_log_file)
                        base_log_file.unlink()
                    except (OSError, IOError):
                        pass
        except Exception as e:
            print(f"Erro ao rotacionar arquivo de log: \n{e}")

        # --- Limit the number of dated log files ---
        cls._cleanup_old_log_files(log_dir, safe_routine_name, days_to_keep=7)  # Keep only 7 days of logs

        # Cria o file_handler com o nome do arquivo de log
        file_handler = cls._create_file_handler(
                base_log_file,
                cls.formatter_detailed, 
                logging.DEBUG
            )
        cls._apply_module_filter(file_handler, modules_to_log)

        ### console_handler: 
        # Cria o console_handler com o formato resumido
        console_handler = cls._create_console_handler(cls.formatter_resumed, logging.INFO)

        ### Logger Root:
        # Cria o logger root
        logger = logging.getLogger('root')
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()

        # Aplica o filtro de módulos ao logger root se especificado
        cls._apply_module_filter(logger, modules_to_log)

        ### Add handlers:
        # Adiciona os handlers ao logger root
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        # Adiciona o handler para CloudStorage
        cloud_log_handler = cls._create_cloud_logger_handler(cls.formatter_detailed, fb_manager, username_app, version_app, level=logging.INFO)
        logger.addHandler(cloud_log_handler)

        # Adiciona o handler personalizado, se fornecido: Usado para handler que imprime no componente do Flet
        if custom_handler:
            logger.addHandler(custom_handler)

        #logger.propagate = True
        # Armazena o logger root como instância da classe
        cls._instance = logger
        cls._initialized = True
        
        # Atualiza todos os loggers já criados
        cls._update_existing_loggers()
    
    @classmethod
    def _update_existing_loggers(cls):
        """Atualiza todos os loggers já criados com a nova configuração."""
        for name, logger in cls._loggers.items():
            # Remove handlers antigos
            logger.handlers.clear()
            # Configura o novo logger com base no root logger
            if name != 'root':
                logger.parent = cls._instance
    
    @classmethod
    def get_logger(cls, name: str = None) -> logging.Logger:
        """
        Retorna um logger configurado para o módulo especificado.
        
        Args:
            name: Nome do módulo (geralmente __name__)
            
        Returns:
            logging.Logger: Logger configurado
        """
        logger_name = name if name else 'root'
        
        if logger_name in cls._loggers:
            return cls._loggers[logger_name]
            
        logger = logging.getLogger(logger_name)
        
        if cls._initialized:
            logger.parent = cls._instance
        else:
            cls._setup_temporary_logger(logger_name)
                    
        cls._loggers[logger_name] = logger
        return logger
    
    @classmethod
    def _cleanup_old_log_files(cls, log_dir: Path, routine_name: str, days_to_keep: int):
        """Removes dated log files older than `days_to_keep`."""
        today = datetime.today()
        cutoff_date = today - timedelta(days=days_to_keep)
        for file in log_dir.glob(f"{routine_name}_*.log"):
            try:
                file_date_str = file.stem.split("_")[-1]  # Extract YYYY-MM-DD
                file_date = datetime.strptime(file_date_str, "%Y-%m-%d")
                if file_date < cutoff_date:
                    file.unlink()  # Delete the old file
            except (ValueError, IndexError):
                pass  # Skip files that don't match the date pattern

# ======================================================================
# Função de Teste Manual para Cloud Logging (Somente para Devs)
# ======================================================================

def test_cloud_logging(test_identifier: str, fb_manager_instance: Optional[Any]):
    """
    Executa um teste manual do LoggerSetup com CloudLogHandler.

    1. Inicializa o LoggerSetup com CloudHandler.
    2. Gera algumas mensagens de log em diferentes níveis.
    3. Força o upload dos logs (simulando o fim do programa).
    4. Tenta baixar o log do Firebase Storage.
    5. Verifica se as mensagens de teste estão no arquivo baixado.
    6. (Opcional) Deleta o arquivo de log do Storage.

    Args:
        test_identifier: String única para identificar esta execução de teste nos logs.
        fb_manager_instance: Instância configurada do FirebaseManager (ou similar).
    """
    print(f"\n--- Iniciando Teste Cloud Logging: {test_identifier} ---")

    if not fb_manager_instance:
        print("ERRO TESTE: Instância do Firebase Manager não fornecida. Abortando teste.")
        return

    # --- Configuração do Teste ---
    test_routine_name = f"TestRoutine_{test_identifier}"
    test_username = f"TestUser_{test_identifier}"
    test_version = "0.0.1-test"
    # Mensagens únicas para procurar no log baixado
    log_marker_info = f"[INFO_TEST_MARKER_{test_identifier}]"
    log_marker_warning = f"[WARN_TEST_MARKER_{test_identifier}]"
    log_marker_debug = f"[DEBUG_TEST_MARKER_{test_identifier}]" # Deve ir pro arquivo, não nuvem (por padrão)

    cloud_handler_instance = None # Para referência posterior
    expected_cloud_path_str = ""

    try:
        # --- 1. Inicialização do Logger ---
        print("Passo 1: Inicializando LoggerSetup...")
        LoggerSetup.initialize(
            routine_name=test_routine_name,
            fb_manager=fb_manager_instance,
            username_app=test_username,
            version_app=test_version
        )
        print("LoggerSetup inicializado.")

        # Guarda a instância do handler para chamar métodos diretamente
        cloud_handler_instance = LoggerSetup._cloud_handler_instance
        if not cloud_handler_instance:
             print("AVISO TESTE: Cloud handler não foi criado. Teste pode não funcionar como esperado.")
             # O teste pode continuar para verificar logs locais, mas a parte da nuvem falhará.

        # Define o caminho esperado no cloud (precisa ser calculado como no handler)
        # Replicando a lógica de path do CloudLogHandler.upload_logs_batch_static
        username_pc = os.getlogin() if os.name != 'posix' else os.getenv('USER', 'unknown_posix') # Adaptação simples getlogin
        username_pc_safe = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', username_pc)
        username_app_safe = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', test_username)
        username_full = username_pc_safe if (username_app_safe in username_pc_safe) else f"{username_pc_safe}_{username_app_safe}"
        username_full = re.sub(r'[^\w\s\d_\-\.]', '', username_full)
        username_full = re.sub(r'\s+', '_', username_full)
        username_full = re.sub(r'[_\-\.]+', '_', username_full)
        username_full = re.sub(r'^_|_$', '', username_full).strip() or "default_user"

        log_folder_user = Path(CLOUD_LOGGER_FOLDER) / username_full / test_version
        log_filename = f"{username_full}_{datetime.now().strftime('%Y-%m-%d')}.txt"
        cloud_path = log_folder_user / log_filename
        expected_cloud_path_str = cloud_path.as_posix()
        print(f"Caminho esperado no Cloud Storage: {expected_cloud_path_str}")

        # --- 2. Geração de Logs ---
        print("\nPasso 2: Gerando logs de teste...")
        logger = LoggerSetup.get_logger("test_module")

        logger.debug(f"Mensagem de DEBUG. {log_marker_debug}") # Não deve ir para a nuvem
        logger.info(f"Mensagem de INFO. {log_marker_info}")
        logger.warning(f"Mensagem de WARNING. {log_marker_warning}")
        logger.error("Mensagem de ERRO (sem marcador único).")
        print("Logs gerados.")

        # --- 3. Forçar Upload ---
        print("\nPasso 3: Forçando upload final (simulando saída)...")
        if cloud_handler_instance:
            # Chama o método que `atexit` chamaria
            cloud_handler_instance._force_upload_on_exit()
            # Dê um tempo extra para garantir que o upload HTTP possa concluir
            print("Aguardando alguns segundos para o upload completar...")
            sleep(10) # Ajuste conforme necessário (depende da latência)
        else:
            print("Cloud handler não existe, pulando upload forçado.")


        # --- 4. Verificação no Firebase ---
        print("\nPasso 4: Verificando o log no Firebase Storage...")
        if not cloud_handler_instance:
             print("Cloud handler não existe, pulando verificação no Firebase.")
             raise RuntimeError("Teste incompleto: Cloud Handler não foi instanciado.")

        downloaded_content = ""
        try:
            print(f"Tentando baixar: {expected_cloud_path_str}")
            downloaded_content = fb_manager_instance.get_text(expected_cloud_path_str)
            print("Log baixado com sucesso do Firebase Storage.")
        except Exception as e:
            print(f"ERRO TESTE: Falha ao baixar o log do Firebase Storage: {e}")
            print("Verifique se o caminho está correto, se as credenciais são válidas e se o arquivo existe no bucket.")
            raise # Re-levanta a exceção para indicar falha no teste

        # --- 5. Assertivas ---
        print("\nPasso 5: Validando conteúdo do log baixado...")
        assert log_marker_info in downloaded_content, f"ERRO TESTE: Marcador INFO '{log_marker_info}' não encontrado no log!"
        print(f"OK: Marcador INFO '{log_marker_info}' encontrado.")

        assert log_marker_warning in downloaded_content, f"ERRO TESTE: Marcador WARNING '{log_marker_warning}' não encontrado no log!"
        print(f"OK: Marcador WARNING '{log_marker_warning}' encontrado.")

        assert log_marker_debug not in downloaded_content, f"ERRO TESTE: Marcador DEBUG '{log_marker_debug}' foi encontrado no log da nuvem (não deveria)!"
        print(f"OK: Marcador DEBUG '{log_marker_debug}' corretamente ausente.")

        print("\n*** SUCESSO: Teste de Cloud Logging concluído com êxito! ***")

    except Exception as e:
        print(f"\n--- FALHA no Teste Cloud Logging: {test_identifier} ---")
        print(f"Erro: {e}")
        import traceback
        traceback.print_exc()
        print("---------------------------------------------------------")
        return # Retorna em caso de falha

    finally:
        # --- 6. Limpeza (Opcional) ---
        print("\nPasso 6: Limpeza (Removendo log de teste do Storage)...")
        input("Pressione Enter para prosseguir...")
        # ATENÇÃO: Habilite com cuidado. Garanta que `expected_cloud_path_str` está correto.
        cleanup_enabled = True # Mude para False para manter o log no bucket após o teste
        if cleanup_enabled and expected_cloud_path_str and fb_manager_instance:
            try:
                print(f"Tentando deletar: {expected_cloud_path_str}")
                fb_manager_instance.delete_file(expected_cloud_path_str) # Supondo que seu manager tenha delete_file
                print("Log de teste removido do Firebase Storage.")
            except Exception as e:
                print(f"AVISO TESTE: Falha ao deletar log de teste '{expected_cloud_path_str}' do Storage: {e}")
        elif not cleanup_enabled:
             print("Limpeza desabilitada. O arquivo de log permanecerá no Storage.")
        else:
             print("Limpeza não realizada (sem path esperado ou sem fb_manager).")

        print(f"--- Fim do Teste Cloud Logging: {test_identifier} ---")

# Executar o teste
# A partir de >>> python -i teste.py
# from src.services import firebase_manager
# fb_manager = firebase_manager.FirebaseManagerStorage()
# from src.logger.logger import test_cloud_logging
# test_cloud_logging(test_identifier='TESTE-123', fb_manager_instance=fb_manager)