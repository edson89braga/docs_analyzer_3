from time import perf_counter
start_time = perf_counter()
print(f"{start_time:.4f}s - Iniciando logger.py")

import os, shutil, re
from time import sleep

from pathlib import Path
from logging.handlers import RotatingFileHandler
from rich.logging import RichHandler
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Any, TYPE_CHECKING

from .cloud_logger_handler import CloudLogHandler, ClientLogUploader, AdminLogUploader
from src.settings import (PATH_LOGS, CLOUD_LOGGER_FOLDER, APP_VERSION)

from src.services.firebase_manager import FbManagerStorage
from src.services.firebase_client import FirebaseClientStorage

if TYPE_CHECKING:
    from .cloud_logger_handler import LogUploaderStrategy

modules_to_log = []

import logging
logger = logging.getLogger(__name__)

class ModuleFilter(logging.Filter):
    """
    Filtro para permitir logs apenas de módulos que começam com um
    dos prefixos especificados.
    """
    def __init__(self, prefixes: List[str]):
        """
        Inicializa o filtro.
        Args:
            prefixes: Uma lista de prefixos de nome de módulo a serem permitidos.
                      Ex: ['src', 'meu_outro_modulo_raiz']
        """
        super().__init__()
        self.prefixes = tuple(prefixes)

    def filter(self, record: logging.LogRecord) -> bool:
        """Permite a passagem do log se o nome do logger começar com algum dos prefixos."""
        # record.name contém o nome completo do logger (ex: 'src.flet_ui.views.home_view')
        return record.name.startswith(self.prefixes)

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
        fmt='%(levelname)-8s | %(message)s', 
        datefmt='%H:%M:%S'
    )
    
    _instance: Optional[logging.Logger] = None
    _initialized = False
    _loggers = {}  # Dicionário para rastrear todos os loggers criados

    _client_uploader_instance: Optional[ClientLogUploader] = None
    _admin_uploader_instance: Optional[AdminLogUploader] = None
    _active_cloud_handler_instance: Optional[CloudLogHandler] = None # Para referência
    
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
    def _create_cloud_logger_handler(
        cls,
        formatter,
        level=logging.INFO
    ) -> Optional[CloudLogHandler]:
        
        # Decide qual uploader usar ou se cria um handler.
        # Se o client_uploader tem contexto, priorize-o. Senão, use admin se disponível.
        uploader_to_use: Optional['LogUploaderStrategy'] = None
        
        if cls._client_uploader_instance:
            uploader_to_use = cls._client_uploader_instance
            print("LoggerSetup: Usando ClientLogUploader para CloudLogHandler (usuário autenticado).")
        elif cls._admin_uploader_instance:
            uploader_to_use = cls._admin_uploader_instance
            print("LoggerSetup: Usando AdminLogUploader para CloudLogHandler (fallback ou sem usuário).")
        else:
            print("WARNING: LoggerSetup: Nenhum uploader (cliente ou admin) configurado/disponível para CloudLogHandler.")
            return None

        # Cria uma nova instância do CloudLogHandler com a estratégia decidida
        # CloudLogHandler não é mais um singleton no LoggerSetup, mas a thread de upload é global.
        try:
            cloud_handler = CloudLogHandler(
                uploader_strategy=uploader_to_use
            )
            cloud_handler.setLevel(level)
            cloud_handler.setFormatter(formatter)
            cls._active_cloud_handler_instance = cloud_handler # Guarda a referência da última instância criada
            print(f"LoggerSetup: CloudLogHandler criado com uploader {uploader_to_use.__class__.__name__}.")
            return cloud_handler
        except Exception as e:
            print(f"ERROR: LoggerSetup: Erro ao criar CloudLogHandler: {e}", exc_info=True)
            return None
    
    @classmethod
    def set_cloud_user_context(cls, user_token: Optional[str], user_id: Optional[str]):
        """
        Define o contexto do usuário (token e ID) para o ClientLogUploader.
        """
        if cls._client_uploader_instance:
            cls._client_uploader_instance.set_user_context(user_token, user_id)
            # Se o CloudLogHandler ativo estiver usando o ClientUploader, ele refletirá a mudança.
            # Se um novo CloudLogHandler for criado (ex: se o logger for reinicializado),
            # ele pegará o uploader com o contexto mais recente.
        # else: Não imprime warning aqui, add_cloud_logging cuidará da criação.
        #    print("WARNING: ClientLogUploader não inicializado. Contexto do usuário não pode ser definido.")

    @classmethod
    def _setup_temporary_logger(cls, logger_name):
        """Configura um logger temporário básico antes da inicialização completa."""
        logger = logging.getLogger(logger_name)
        if not logger.handlers:            
            # Adiciona console handler
            console_handler = cls._create_console_handler(cls.formatter_resumed, logging.INFO)
            logger.addHandler(console_handler)
            
            # Adiciona file handler
            file_handler = cls._create_file_handler(
                PATH_LOGS / "Root_temp.log",
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
    def OLD_initialize(cls,
                   routine_name: str,
                   #firebase_client_storage: Optional['FirebaseClientStorage'] = None,
                   #fb_manager_storage_admin: Optional['FbManagerStorage'] = None,
                   modules_to_log: Optional[List[str]] = None,
                   custom_handler: Optional[logging.Handler] = None,
                   dev_mode: bool = False) -> None:
        """
        Inicializa o logger global. Deve ser chamado uma vez no início do programa.
        
        Args:
            routine_name: Nome da rotina para o arquivo de log.
            modules_to_log: Lista de módulos para filtrar os logs.
            custom_handler: Handler personalizado para ser adicionado ao logger.
        """   
        if cls._initialized and not dev_mode: 
            return
        
        if cls._initialized and dev_mode and cls._instance and cls._instance.name == "dev_minimal_logger":
            return
        
        if dev_mode:
            # Configuração mínima para dev_mode
            logger = logging.getLogger('dev_minimal_logger') # Usa um nome diferente para evitar conflitos
            logger.handlers.clear() # Limpa handlers anteriores se houver
            console_handler = cls._create_console_handler(cls.formatter_resumed, logging.DEBUG) # DEBUG para dev
            logger.addHandler(console_handler)
            logger.setLevel(logging.DEBUG)
            logger.propagate = False # Não propaga para o logger root padrão, pois este é o nosso "root" em dev_mode
            cls._instance = logger
            cls._initialized = True
            # current_internal_logger.info("LoggerSetup inicializado em MODO DE DESENVOLVIMENTO (mínimo).")
            # cls._update_existing_loggers() # Garante que loggers filhos usem este
            return
        
        global PATH_LOGS
        
        # A responsabilidade de criar e adicionar o CloudLogHandler ficará totalmente com add_cloud_logging
        #if firebase_client_storage:
        #    cls._client_uploader_instance = ClientLogUploader(firebase_client_storage)
        #    print("LoggerSetup: Instância de ClientLogUploader criada.")
        #if fb_manager_storage_admin:
        #    cls._admin_uploader_instance = AdminLogUploader(fb_manager_storage_admin)
        #    print("LoggerSetup: Instância de AdminLogUploader criada.")

        ### file_handler:
        # Cria o nome do arquivo de log com base no nome da rotina
        safe_routine_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in routine_name)
        
        # Cria o nome do arquivo de log com a data atual
        current_date = datetime.now().strftime('%Y-%m-%d')
        base_log_file = PATH_LOGS / f"{safe_routine_name}.log"
        dated_log_file = PATH_LOGS / f"{safe_routine_name}_{current_date}.log"

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
        cls._cleanup_old_log_files(PATH_LOGS, days_to_keep=7)  # Keep only 7 days of logs

        # Cria o file_handler com o nome do arquivo de log
        file_handler = cls._create_file_handler(
                base_log_file,
                cls.formatter_detailed, 
                logging.DEBUG
            )

        ### console_handler: 
        # Cria o console_handler com o formato resumido
        console_handler = cls._create_console_handler(cls.formatter_resumed, logging.INFO)

        ### Logger Root:
        # Cria o logger root
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()

        ### Add handlers:
        # Adiciona os handlers ao logger root
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        #if firebase_client_storage or fb_manager_storage_admin:
        #    # Adiciona o handler para CloudStorage
        #    cloud_log_handler = cls._create_cloud_logger_handler(cls.formatter_detailed, level=logging.INFO)
        #    if cloud_log_handler:
        #        cls._apply_module_filter(cloud_log_handler, modules_to_log)
        #        logger.addHandler(cloud_log_handler)
        #else:
        #    print("LoggerSetup: Nenhum Firebase storage manager fornecido para o logger da nuvem. Cloud logging desabilitado.")

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
    def initialize(cls,
                   routine_name: str,
                   modules_to_log: Optional[List[str]] = None, # Mantido, mas a nova lógica usa o prefixo 'src'
                   custom_handler: Optional[logging.Handler] = None,
                   dev_mode: bool = False) -> None:
        """
        Inicializa o logger global. Deve ser chamado uma vez no início do programa.
        
        Args:
            routine_name: Nome da rotina para o arquivo de log.
            modules_to_log: Lista de prefixos de módulos para filtrar os logs no console. Se None, usa ['src'].
            custom_handler: Handler personalizado para ser adicionado ao logger.
            dev_mode: Se True, define o nível do console para DEBUG.
        """
        if cls._initialized:
            # Se já inicializado, apenas loga uma mensagem e retorna para evitar reconfiguração.
            if cls._instance:
                cls._instance.debug("LoggerSetup.initialize chamado novamente, mas já inicializado. Ignorando.")
            return

        # Define o nível do console com base no modo de desenvolvimento
        console_level = logging.DEBUG if dev_mode else logging.INFO

        # Usamos ['src'] como padrão para filtrar apenas os módulos do seu projeto.
        allowed_prefixes = modules_to_log if modules_to_log is not None else ['src', '__main__']

        # Cria o nome do arquivo de log com base no nome da rotina
        safe_routine_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in routine_name)
        
        # Rotaciona o log antigo
        current_date = datetime.now().strftime('%Y-%m-%d')
        base_log_file = PATH_LOGS / f"{safe_routine_name}.log"
        dated_log_file = PATH_LOGS / f"{safe_routine_name}_{current_date}.log"
        cls._rotate_log_file(base_log_file, dated_log_file)

        # Limpa logs mais antigos
        cls._cleanup_old_log_files(PATH_LOGS, days_to_keep=7)

        # --- Cria Handlers ---
        file_handler = cls._create_file_handler(
            base_log_file,
            cls.formatter_detailed, 
            logging.DEBUG  # Arquivo sempre em DEBUG
        )
        console_handler = cls._create_console_handler(cls.formatter_resumed, console_level)

        if dev_mode and allowed_prefixes:
            module_filter = ModuleFilter(prefixes=allowed_prefixes)
            console_handler.addFilter(module_filter)
            print(f"Filtro de log do console ativado para prefixos: {allowed_prefixes}")

        # --- Silencia Loggers de Bibliotecas de Terceiros ---
        # Define um nível mais alto para loggers específicos para reduzir o ruído geral.
        # Isso afeta tanto o console quanto o arquivo, o que é bom.
        logging.getLogger("flet_core").setLevel(logging.WARNING)
        logging.getLogger("flet_runtime").setLevel(logging.WARNING)
        logging.getLogger("flet_web").setLevel(logging.WARNING)
        logging.getLogger("flet").setLevel(logging.WARNING)
        logging.getLogger("websockets").setLevel(logging.WARNING)
        logging.getLogger("watchdog").setLevel(logging.WARNING)
        logging.getLogger("uvicorn").setLevel(logging.INFO)
        logging.getLogger("uvicorn.error").setLevel(logging.INFO)
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("starlette").setLevel(logging.WARNING)
        logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)
        logging.getLogger("asyncio").setLevel(logging.INFO)
        logging.getLogger("keyring.backend").setLevel(logging.INFO)

        # --- Configura o Logger Raiz ---
        logger = logging.getLogger() # Pega o logger raiz
        logger.setLevel(logging.DEBUG) # O logger raiz deve ter o nível mais baixo
        logger.handlers.clear() # Limpa handlers pré-existentes do raiz

        # Adiciona os novos handlers
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        if custom_handler:
            logger.addHandler(custom_handler)

        cls._instance = logger
        cls._initialized = True
        
        # Atualiza loggers que possam ter sido criados antes da inicialização
        cls._update_existing_loggers()

        # Loga a mensagem de inicialização
        init_mode = "MODO DE DESENVOLVIMENTO (DEBUG no console)" if dev_mode else "MODO DE PRODUÇÃO (INFO no console)"
        logger.info(f"LoggerSetup inicializado com sucesso em {init_mode}.")

    @classmethod
    def add_cloud_logging(
        cls,
        user_token_for_client: Optional[str] = None, # Para passar o token no momento da adição
        user_id_for_client: Optional[str] = None      # Para passar o user_id no momento da adição
    ) -> bool:
        """
        Adiciona o CloudLogHandler ao logger raiz, se não já adicionado.
        Cria os uploaders se necessário.
        """
        if not cls._initialized:
            print("LoggerSetup ERROR: Logger não inicializado. Chame LoggerSetup.initialize() primeiro.")
            return False
        if not cls._instance: # Logger raiz não configurado
            print("LoggerSetup ERROR: Logger raiz não está configurado.")
            return False

        # Verifica se um CloudLogHandler já existe para evitar duplicação
        if cls._active_cloud_handler_instance and cls._active_cloud_handler_instance in cls._instance.handlers:
            print("LoggerSetup: CloudLogHandler já está ativo. Verificando contexto do uploader.")
            # Se já existe, apenas garante que o contexto do client_uploader está atualizado
            #if cls._client_uploader_instance and (user_token_for_client or user_id_for_client):
            #    cls._client_uploader_instance.set_user_context(user_token_for_client, user_id_for_client)
            if isinstance(cls._active_cloud_handler_instance.uploader, ClientLogUploader):
                cls._active_cloud_handler_instance.uploader.set_user_context(user_token_for_client, user_id_for_client)
            return True

        # Cria o ClientUploader se não existir e se tokens forem fornecidos
        if not cls._client_uploader_instance and (user_token_for_client and user_id_for_client):
            # Tenta obter o FirebaseClientStorage. Se não estiver disponível em run.py,
            # precisará ser instanciado aqui ou de alguma forma acessível.
            # Por ora, assumimos que se chegamos aqui, run.py já pode ter instanciado
            # e não o passou para initialize, então add_cloud_logging é a primeira chance.
            # Se este for o caso, e você não quer instanciar FirebaseClientStorage globalmente
            # ou passá-lo de run.py, esta parte precisa de um design cuidadoso.
            # Temporariamente, vamos instanciar aqui se não existir.
            try:
                _fcs_temp = FirebaseClientStorage() # Instancia se necessário
                cls._client_uploader_instance = ClientLogUploader(_fcs_temp)
                print("LoggerSetup: Instância de ClientLogUploader criada dinamicamente em add_cloud_logging.")
                cls._client_uploader_instance.set_user_context(user_token_for_client, user_id_for_client)
            except Exception as e_fcs:
                print(f"LoggerSetup: Erro ao criar FirebaseClientStorage para ClientUploader: {e_fcs}")
                # Não prosseguir com client uploader se falhar
        
        # Cria o AdminUploader se não existir (se não houver contexto de cliente ou como fallback)
        if not cls._admin_uploader_instance and not (user_token_for_client and user_id_for_client) :
            try:
                _fms_temp = FbManagerStorage() # Instancia se necessário
                cls._admin_uploader_instance = AdminLogUploader(_fms_temp)
                print("LoggerSetup: Instância de AdminLogUploader criada dinamicamente em add_cloud_logging.")
            except Exception as e_fms:
                print(f"LoggerSetup: Erro ao criar FbManagerStorage para AdminLogUploader: {e_fms}")

        cloud_log_handler = cls._create_cloud_logger_handler(
            cls.formatter_detailed,
            level=logging.INFO
        )

        if cloud_log_handler:
            cls._instance.addHandler(cloud_log_handler)
            print("LoggerSetup: CloudLogHandler adicionado ao logger raiz.")
            return True
        else:
            print("LoggerSetup: Falha ao criar CloudLogHandler. Logging na nuvem não será ativado.")
            return False
        
    @classmethod
    def _update_existing_loggers(cls):
        """Atualiza todos os loggers já criados com a nova configuração."""
        for name, logger in cls._loggers.items():
            # Remove handlers antigos
            logger.handlers.clear()
            # Configura o novo logger com base no root logger
            if name is not None:
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
        logger_name = name 
        
        if logger_name in cls._loggers:
            return cls._loggers[logger_name]
            
        logger = logging.getLogger(logger_name)
        
        # Sets Logs específicos:
        logging.getLogger("pdfminer").setLevel(logging.ERROR)

        if cls._initialized:
            logger.parent = cls._instance
        else:
            cls._setup_temporary_logger(logger_name)
                    
        cls._loggers[logger_name] = logger
        return logger
    
    @classmethod
    def _cleanup_old_log_files(cls, log_dir: Path, days_to_keep: int):
        """
        Remove recursivamente arquivos .log e .txt mais antigos que 'days_to_keep'
        do diretório de logs especificado.
        """
        if not log_dir.is_dir():
            print(f"Diretório de logs '{log_dir}' não encontrado para limpeza.")
            return

        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        files_removed_count = 0
        #logger = cls.get_logger(__name__) # Usa o próprio logger para registrar a ação
        cleanup_logger = logging.getLogger(__name__)
        
        cleanup_logger.info(f"Iniciando limpeza de logs antigos (mais de {days_to_keep} dias) em '{log_dir}'...")

        # Usa rglob para encontrar arquivos em subdiretórios também
        for file_path in log_dir.rglob('*'):
            # Verifica se é um arquivo e tem a extensão desejada
            if file_path.is_file() and file_path.suffix.lower() in ['.log', '.txt']:
                try:
                    file_mod_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_mod_time < cutoff_date:
                        file_path.unlink()
                        #logger.info(f"Arquivo de log antigo removido: {file_path}")
                        files_removed_count += 1
                except FileNotFoundError:
                    # O arquivo pode ter sido removido por outro processo entre o rglob e o stat/unlink
                    cleanup_logger.debug(f"Arquivo '{file_path}' não encontrado durante a limpeza (concorrência?).")
                except Exception as e:
                    cleanup_logger.error(f"Erro ao tentar remover o arquivo de log antigo '{file_path}': {e}", exc_info=False)
        
        cleanup_logger.info(f"Limpeza de logs antigos concluída. {files_removed_count} arquivo(s) removido(s).")

    @classmethod
    def cleanup_cloud_logs(cls, storage_manager: FbManagerStorage, days_to_keep: int, dry_run: bool = False):
        """
        Remove ou lista logs do Firebase Storage de forma recursiva a partir do prefixo CLOUD_LOGGER_FOLDER,
        deletando arquivos mais antigos que 'days_to_keep'.
        """
        logger = cls.get_logger(__name__)
        
        if not CLOUD_LOGGER_FOLDER.endswith('/'):
            cloud_log_prefix = f"{CLOUD_LOGGER_FOLDER}/"
        else:
            cloud_log_prefix = CLOUD_LOGGER_FOLDER

        logger.info(f"Iniciando verificação de logs antigos na nuvem (prefixo: '{cloud_log_prefix}', retenção: {days_to_keep} dias)...")
        
        try:
            # list_blobs com um prefixo já itera por todos os objetos que começam com esse prefixo,
            # efetivamente fazendo uma listagem recursiva.
            blobs_iterator = storage_manager.bucket.list_blobs(prefix=cloud_log_prefix)
            
            # A data/hora do blob.updated é 'timezone-aware' (UTC). Precisamos comparar com UTC.
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
            
            files_to_remove = []
            
            for blob in blobs_iterator:
                # Ignora "pastas vazias" que o Firebase Storage pode criar.
                # São blobs de 0 bytes cujo nome termina com '/'.
                if blob.name.endswith('/') and blob.size == 0:
                    continue

                if blob.updated and blob.updated < cutoff_date:
                    files_to_remove.append(blob)
            
            if not files_to_remove:
                logger.info("Nenhum log antigo encontrado para remover na nuvem.")
                return

            logger.warning(f"Encontrados {len(files_to_remove)} logs antigos para remover:")
            for blob in files_to_remove:
                # Formata a data para melhor legibilidade no log
                mod_time_str = blob.updated.strftime('%Y-%m-%d %H:%M:%S %Z')
                logger.warning(f"  - A REMOVER: {blob.name} (Última modificação: {mod_time_str})")

            if dry_run:
                logger.info("DRY RUN concluído. Nenhuma ação de deleção foi executada.")
                return

            logger.info("Prosseguindo com a deleção real dos arquivos na nuvem...")
            files_removed_count = 0
            for blob in files_to_remove:
                try:
                    storage_manager.delete_file(blob.name)
                    files_removed_count += 1
                except Exception as e_del:
                    logger.error(f"Erro ao tentar remover o log da nuvem '{blob.name}': {e_del}")
            
            logger.info(f"Deleção concluída. {files_removed_count} de {len(files_to_remove)} arquivo(s) removido(s) com sucesso.")

        except Exception as e:
            logger.error(f"Falha geral ao executar a limpeza de logs da nuvem: {e}", exc_info=True)
            
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
            fb_manager_storage_admin=fb_manager_instance,
        )
        print("LoggerSetup inicializado.")

        # Guarda a instância do handler para chamar métodos diretamente
        cloud_handler_instance = LoggerSetup._active_cloud_handler_instance
        if not cloud_handler_instance:
             print("AVISO TESTE: Cloud handler não foi criado. Teste pode não funcionar como esperado.")
             # O teste pode continuar para verificar logs locais, mas a parte da nuvem falhará.

        # Define o caminho esperado no cloud (precisa ser calculado como no handler)
        # Replicando a lógica de path do CloudLogHandler.upload_logs_batch_static
        username_pc = os.getlogin() if os.name != 'posix' else os.getenv('USER', 'unknown_posix') # Adaptação simples getlogin
        username_pc_safe = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', username_pc)
        username_full = username_pc_safe 
        username_full = re.sub(r'[^\w\s\d_\-\.]', '', username_full)
        username_full = re.sub(r'\s+', '_', username_full)
        username_full = re.sub(r'[_\-\.]+', '_', username_full)
        username_full = re.sub(r'^_|_$', '', username_full).strip() or "default_user"

        log_folder_user = Path(CLOUD_LOGGER_FOLDER) / username_full / APP_VERSION
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
            cloud_handler_instance._force_upload_on_exit_static(cloud_handler_instance)
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
# fb_manager = firebase_manager.FbManagerStorage()
# from src.logger.logger import test_cloud_logging
# test_cloud_logging(test_identifier='TESTE-456', fb_manager_instance=fb_manager)



execution_time = perf_counter() - start_time
print(f"Carregado LOGGER em {execution_time:.4f}s")
