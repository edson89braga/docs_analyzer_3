import logging
logger = logging.getLogger(__name__)

from time import perf_counter
start_time = perf_counter()
logger.debug(f"{start_time:.4f}s - Iniciando logger.py")

import os, shutil, re
import http.client
import socket
from time import sleep

import requests
import urllib3
from pathlib import Path
from logging.handlers import RotatingFileHandler
from rich.logging import RichHandler
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import List, Optional, Any, TYPE_CHECKING

from .cloud_logger_handler import CloudLogHandler, AdminLogUploader, user_id_ctx, user_email_ctx, session_id_ctx
 
from SOURCE.settings import (PATH_LOGS_DIR, CLOUD_LOGGER_FOLDER, APP_VERSION)

from SOURCE.services.firebase_manager import FbManagerStorage
from SOURCE.services.firebase_client import FirebaseClientStorage

if TYPE_CHECKING:
    from .cloud_logger_handler import LogUploaderStrategy

from pathlib import Path
PATH_LOGS_DIR = Path(PATH_LOGS_DIR)

modules_to_log = []

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

class SessionContextFilter(logging.Filter):
    """
    Filtro que injeta `session_id`, `user_id` (uid Firebase) e `user_short` (parte
    local do e-mail, ex. "edson.eab" de "edson.eab@pf.gov.br" — usado para
    monitoramento visual, ver `scripts/watch_logs.sh`) em cada LogRecord, lendo os
    contextvars correspondentes (propagados manualmente para threads via
    `cloud_logger_handler.context_wrap`, já que `threading.Thread` não herda
    contextvars automaticamente).

    Aplicado apenas aos handlers de arquivo (via `_create_file_handler`) — o
    handler de console permanece sem esses campos.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        """Injeta session_id/user_id/user_short no record e sempre permite a passagem do log."""
        record.session_id = session_id_ctx.get() or "-"
        record.user_id = user_id_ctx.get() or "-"
        user_email = user_email_ctx.get()
        record.user_short = user_email.split("@")[0] if user_email else "-"
        return True

class LoggerSetup:
    """Classe responsável pela configuração e setup de loggers."""
    
    @staticmethod
    def _get_formatter(detailed: bool = True):
        # Formato detalhado para o arquivo de log, com informações de data, hora, nível, módulo, função, linha, mensagem
        tz = dt_timezone(timedelta(hours=-3)) # Fuso de Brasília (UTC-3)

        # Função auxiliar reutilizada pelo RichHandler para gerar o timestamp
        # corretamente no console (Rich não usa o formatter padrão para o tempo)
        @staticmethod
        def _get_brasilia_time() -> datetime:
            return datetime.now(dt_timezone(timedelta(hours=-3)))

        class LocalFormatter(logging.Formatter):
            def formatTime(self, record, datefmt=None):
                dt = datetime.fromtimestamp(record.created, tz)
                return dt.strftime(datefmt or '%Y-%m-%d %H:%M:%S')
        
        # Formato detalhado (arquivo): inclui user_short/session_id/user_id, injetados
        # via SessionContextFilter (anexado apenas aos handlers de arquivo em
        # _create_file_handler, nunca ao console). user_short vem logo após o nível
        # para leitura rápida (ver scripts/watch_logs.sh); session_id/user_id ficam
        # atrás dele para quem precisar do detalhe completo.
        fmt = '%(asctime)s | %(levelname)-8s | %(user_short)s | %(session_id)s | %(user_id)s | %(name)s | %(funcName)s:%(lineno)d | %(message)s' if detailed else '%(message)s'
        return LocalFormatter(fmt=fmt, datefmt='%Y-%m-%d %H:%M:%S')
        
    _instance: Optional[logging.Logger] = None
    _initialized = False
    _loggers = {}  # Dicionário para rastrear todos os loggers criados

    _admin_uploader_instance: Optional[AdminLogUploader] = None
    _active_cloud_handler_instance: Optional[CloudLogHandler] = None # Para referência
    
    logging.getLogger('httpx').setLevel(logging.WARNING)
    # O SDK openai loga em DEBUG o payload completo de cada requisição (openai._base_client.log.debug
    # "Request options: %s"), incluindo as mensagens/prompt inteiros — polui o log em DEBUG sem
    # necessidade prática. WARNING mantém erros de requisição visíveis e corta esse ruído.
    logging.getLogger('openai').setLevel(logging.WARNING)
    
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
        # Injeta session_id/user_id em todo handler de arquivo (nunca no console).
        handler.addFilter(SessionContextFilter())
        return handler

    @classmethod
    def _create_console_handler(cls, formatter, level=logging.INFO):
        tz = dt_timezone(timedelta(hours=-3))
        handler = RichHandler(
            level=level,
            show_level=True,
            show_path=False,
            show_time=True,
            # RichHandler ignora o formatter para o timestamp da coluna [TIME].
            # log_time_format aceita um callable → força UTC-3 (Brasília)
            log_time_format=lambda dt: datetime.now(tz).strftime("%H:%M:%S"),
            rich_tracebacks=True,
            tracebacks_show_locals=False,
            # Suprime os frames internos de bibliotecas de rede (proxy/timeout) para não poluir
            # o console com ~90 linhas repetidas por erro; a causa raiz no código do projeto
            # continua visível normalmente.
            tracebacks_suppress=[urllib3, requests, http.client, socket],
            markup=True,
            keywords=["INFO", "WARNING", "ERROR", "CRITICAL", "DEBUG"]
        )
        handler.setFormatter(formatter)
        return handler

    @classmethod
    def set_cloud_user_context(cls, user_id: Optional[str], user_email: Optional[str]):
        """Define o contexto do usuário (uid + email) para a thread atual."""
        user_id_ctx.set(user_id if user_id else "anonymous_user")
        user_email_ctx.set(user_email)

    @classmethod
    def set_session_context(cls, session_id: Optional[str]) -> None:
        """Define o session_id (sessão Flet) para a thread atual, usado no log de arquivo."""
        session_id_ctx.set(session_id)

    @classmethod
    def _setup_temporary_logger(cls, logger_name):
        """Configura um logger temporário básico antes da inicialização completa."""
        logger = logging.getLogger(logger_name)
        if not logger.handlers:            
            # Adiciona console handler
            console_handler = cls._create_console_handler(cls._get_formatter(detailed=False), logging.INFO)
            logger.addHandler(console_handler)
            
            # Adiciona file handler
            file_handler = cls._create_file_handler(
                PATH_LOGS_DIR / "Root_temp.log",
                cls._get_formatter(detailed=True), 
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
                    logger.debug(f"Erro ao copiar arquivo de log: {e}")
        except Exception as e:
            logger.debug(f"Erro ao rotacionar arquivo de log: \n{e}")

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
        allowed_prefixes = modules_to_log if modules_to_log is not None else ['SOURCE', '__main__']

        # Cria o nome do arquivo de log com base no nome da rotina
        safe_routine_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in routine_name)
        
        # Rotaciona o log antigo
        current_date = datetime.now().strftime('%Y-%m-%d')
        base_log_file = PATH_LOGS_DIR / f"{safe_routine_name}.log"
        dated_log_file = PATH_LOGS_DIR / f"{safe_routine_name}_{current_date}.log"
        cls._rotate_log_file(base_log_file, dated_log_file)

        # Limpa logs mais antigos
        cls._cleanup_old_log_files(PATH_LOGS_DIR, days_to_keep=7)

        logger = logging.getLogger() # Pega o logger raiz
        
        # --- Cria Handlers ---
        file_handler = cls._create_file_handler(
            base_log_file,
            cls._get_formatter(detailed=True), 
            logging.DEBUG  # Arquivo sempre em DEBUG
        )
        console_handler = cls._create_console_handler(cls._get_formatter(detailed=False), console_level)

        if dev_mode and allowed_prefixes:
            module_filter = ModuleFilter(prefixes=allowed_prefixes)
            console_handler.addFilter(module_filter)
            logger.debug(f"Filtro de log do console ativado para prefixos: {allowed_prefixes}")

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
        logger.debug(f"LoggerSetup inicializado com sucesso em {init_mode}.")

    @classmethod
    def add_cloud_logging(
        cls,
        user_token_for_client: Optional[str] = None, # Para passar o token no momento da adição
        user_id_for_client: Optional[str] = None      # Para passar o user_id no momento da adição
    ) -> bool:
        """
        Descontinuado (decisão de 20/08/2026, ver NOTES_persistencia_dados.md): persistência de
        logs de texto no Firebase Storage foi desligada. Toda a persistência de logs passa a ser
        exclusivamente local (RotatingFileHandler em PATH_LOGS_DIR, já sempre ativo em paralelo).
        Função mantida como no-op (em vez de removida) para não quebrar os callers existentes em
        app.py e login_view.py, que já toleram retorno False silenciosamente.
        """
        logger.debug("LoggerSetup: add_cloud_logging() é no-op — upload de logs para o Storage foi descontinuado.")
        return False
    @classmethod
    def _update_existing_loggers(cls):
        """Atualiza todos os loggers já criados com a nova configuração."""
        for name, logger_instance in cls._loggers.items():
            # Remove handlers antigos:
            logger_instance.handlers.clear()
            # Garante que o nível não restrinja mais do que o pai:
            logger_instance.setLevel(logging.DEBUG)
            # Desativa a propagação se você quisesse handlers únicos por logger, mas queremos que eles propaguem para o raiz:
            logger_instance.propagate = True 
        
        logger.debug(f"Reconfigurados {len(cls._loggers)} loggers existentes para usar a nova configuração raiz.")
    
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
        
        logger = logging.getLogger(logger_name)
        if logger_name not in cls._loggers:
            cls._loggers[logger_name] = logger
        
        # Sets Logs específicos:
        logging.getLogger("pdfminer").setLevel(logging.ERROR)

        if cls._initialized:
            logger.parent = cls._instance
        else:
            cls._setup_temporary_logger(logger_name)
                    
        return logger
    
    @classmethod
    def _cleanup_old_log_files(cls, log_dir: Path, days_to_keep: int):
        """
        Remove recursivamente arquivos .log e .txt mais antigos que 'days_to_keep'
        do diretório de logs especificado.
        """
        if not log_dir.is_dir():
            logger.debug(f"Diretório de logs '{log_dir}' não encontrado para limpeza.")
            return

        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        files_removed_count = 0
        #logger = cls.get_logger(__name__) # Usa o próprio logger para registrar a ação
        cleanup_logger = logging.getLogger(__name__)
        
        cleanup_logger.debug(f"Iniciando limpeza de logs antigos (mais de {days_to_keep} dias) em '{log_dir}'...")

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
            cutoff_date = datetime.now(dt_timezone.utc) - timedelta(days=days_to_keep)
            
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
    logger.debug(f"\n--- Iniciando Teste Cloud Logging: {test_identifier} ---")

    if not fb_manager_instance:
        logger.debug("ERRO TESTE: Instância do Firebase Manager não fornecida. Abortando teste.")
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
        logger.debug("Passo 1: Inicializando LoggerSetup...")
        LoggerSetup.initialize(
            routine_name=test_routine_name,
            fb_manager_storage_admin=fb_manager_instance,
        )
        logger.debug("LoggerSetup inicializado.")

        # Guarda a instância do handler para chamar métodos diretamente
        cloud_handler_instance = LoggerSetup._active_cloud_handler_instance
        if not cloud_handler_instance:
             logger.debug("AVISO TESTE: Cloud handler não foi criado. Teste pode não funcionar como esperado.")
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
        logger.debug(f"Caminho esperado no Cloud Storage: {expected_cloud_path_str}")

        # --- 2. Geração de Logs ---
        logger.debug("\nPasso 2: Gerando logs de teste...")
        logger = LoggerSetup.get_logger("test_module")

        logger.debug(f"Mensagem de DEBUG. {log_marker_debug}") # Não deve ir para a nuvem
        logger.info(f"Mensagem de INFO. {log_marker_info}")
        logger.warning(f"Mensagem de WARNING. {log_marker_warning}")
        logger.error("Mensagem de ERRO (sem marcador único).")
        logger.debug("Logs gerados.")

        # --- 3. Forçar Upload ---
        logger.debug("\nPasso 3: Forçando upload final (simulando saída)...")
        if cloud_handler_instance:
            # Chama o método que `atexit` chamaria
            cloud_handler_instance._force_upload_on_exit_static(cloud_handler_instance)
            # Dê um tempo extra para garantir que o upload HTTP possa concluir
            logger.debug("Aguardando alguns segundos para o upload completar...")
            sleep(10) # Ajuste conforme necessário (depende da latência)
        else:
            logger.debug("Cloud handler não existe, pulando upload forçado.")


        # --- 4. Verificação no Firebase ---
        logger.debug("\nPasso 4: Verificando o log no Firebase Storage...")
        if not cloud_handler_instance:
             logger.debug("Cloud handler não existe, pulando verificação no Firebase.")
             raise RuntimeError("Teste incompleto: Cloud Handler não foi instanciado.")

        downloaded_content = ""
        try:
            logger.debug(f"Tentando baixar: {expected_cloud_path_str}")
            downloaded_content = fb_manager_instance.get_text(expected_cloud_path_str)
            logger.debug("Log baixado com sucesso do Firebase Storage.")
        except Exception as e:
            logger.debug(f"ERRO TESTE: Falha ao baixar o log do Firebase Storage: {e}")
            logger.debug("Verifique se o caminho está correto, se as credenciais são válidas e se o arquivo existe no bucket.")
            raise # Re-levanta a exceção para indicar falha no teste

        # --- 5. Assertivas ---
        logger.debug("\nPasso 5: Validando conteúdo do log baixado...")
        assert log_marker_info in downloaded_content, f"ERRO TESTE: Marcador INFO '{log_marker_info}' não encontrado no log!"
        logger.debug(f"OK: Marcador INFO '{log_marker_info}' encontrado.")

        assert log_marker_warning in downloaded_content, f"ERRO TESTE: Marcador WARNING '{log_marker_warning}' não encontrado no log!"
        logger.debug(f"OK: Marcador WARNING '{log_marker_warning}' encontrado.")

        assert log_marker_debug not in downloaded_content, f"ERRO TESTE: Marcador DEBUG '{log_marker_debug}' foi encontrado no log da nuvem (não deveria)!"
        logger.debug(f"OK: Marcador DEBUG '{log_marker_debug}' corretamente ausente.")

        logger.debug("\n*** SUCESSO: Teste de Cloud Logging concluído com êxito! ***")

    except Exception as e:
        logger.debug(f"\n--- FALHA no Teste Cloud Logging: {test_identifier} ---")
        logger.debug(f"Erro: {e}")
        import traceback
        traceback.print_exc()
        logger.debug("---------------------------------------------------------")
        return # Retorna em caso de falha

    finally:
        # --- 6. Limpeza (Opcional) ---
        logger.debug("\nPasso 6: Limpeza (Removendo log de teste do Storage)...")
        input("Pressione Enter para prosseguir...")
        # ATENÇÃO: Habilite com cuidado. Garanta que `expected_cloud_path_str` está correto.
        cleanup_enabled = True # Mude para False para manter o log no bucket após o teste
        if cleanup_enabled and expected_cloud_path_str and fb_manager_instance:
            try:
                logger.debug(f"Tentando deletar: {expected_cloud_path_str}")
                fb_manager_instance.delete_file(expected_cloud_path_str) # Supondo que seu manager tenha delete_file
                logger.debug("Log de teste removido do Firebase Storage.")
            except Exception as e:
                logger.debug(f"AVISO TESTE: Falha ao deletar log de teste '{expected_cloud_path_str}' do Storage: {e}")
        elif not cleanup_enabled:
             logger.debug("Limpeza desabilitada. O arquivo de log permanecerá no Storage.")
        else:
             logger.debug("Limpeza não realizada (sem path esperado ou sem fb_manager).")

        logger.debug(f"--- Fim do Teste Cloud Logging: {test_identifier} ---")

# Executar o teste
# A partir de >>> python -i teste.py
# from src.services import firebase_manager
# fb_manager = firebase_manager.FbManagerStorage()
# from src.logger.logger import test_cloud_logging
# test_cloud_logging(test_identifier='TESTE-456', fb_manager_instance=fb_manager)



execution_time = perf_counter() - start_time
logger.debug(f"Carregado LOGGER em {execution_time:.4f}s")
