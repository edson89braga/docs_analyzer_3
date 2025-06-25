# run.py
import logging
logger = logging.getLogger(__name__)

from time import perf_counter
start_time = perf_counter()
logger.info(f"{start_time:.4f}s - Iniciando run.py")

DEBUG_LEVEL = False # Constam outras constantes de inicialização em app.py e pdf_processor.py

import logging, os, sys
from src.logger.logger import LoggerSetup

try:
    LoggerSetup.initialize(
        routine_name="DocsAnalyzer3",
        dev_mode = DEBUG_LEVEL, 
        #firebase_client_storage=_client_storage_for_logger,
        #fb_manager_storage_admin=_admin_storage_for_logger
    )
    # Logger para o próprio run.py
    logger = LoggerSetup.get_logger(__name__)
    logger.info("Logger inicializado a partir de run.py.")
except Exception as e:
    logger.critical(f"Falha CRÍTICA ao inicializar o logger em run.py: {e}", exc_info=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.error("Logger principal falhou ao inicializar. Usando fallback básico.")
    # Não levantar exceção aqui para permitir que a app Flet tente iniciar mesmo assim.

# =====================================================================================================================================
# Tratamentos preventivos para PyInstaller
import secrets, base64, keyring
import keyring.backends.Windows
# Sem pyi_splash

# ===============================================================================
# 1. CONFIGURAÇÕES INICIAIS PARA AMBIENTE FROZEN
def setup_frozen_environment():
    """Configura o ambiente quando executado via PyInstaller"""
    if getattr(sys, 'frozen', False):
        # Fix para keyring no Windows
        if sys.platform.startswith('win'):
            os.environ['PYTHON_KEYRING_BACKEND'] = 'keyring.backends.Windows.WinVaultKeyring'
        
        # Fix para paths de recursos
        application_path = os.path.dirname(sys.executable)
        
        # Ajusta sys.path para bibliotecas
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller cria uma pasta temporária e armazena o caminho em _MEIPASS
            bundle_dir = sys._MEIPASS
        else:
            bundle_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Adiciona o diretório do bundle ao path
        sys.path.insert(0, bundle_dir)
        
# ===============================================================================
# 2. GERENCIAMENTO DE FLET_SECRET_KEY
def get_or_create_secret_key():
    """
    Obtém ou cria a FLET_SECRET_KEY seguindo a hierarquia:
    1. Variável de ambiente (administrador/usuário avançado)
    2. Keyring (persistência local)
    3. Gera nova chave e salva no Keyring
    """
    APP_NAME = "DocsAnalyzerPF_FletKey"  #
    KEY_NAME = "flet_secret_key"
    
    try:
        # 1. Primeiro, tenta ler da variável de ambiente
        secret_key = os.getenv('FLET_SECRET_KEY')
        if secret_key:
            logger.info("FLET_SECRET_KEY carregada da variável de ambiente")
            return secret_key
        
        # 2. Tenta ler do Keyring
        try:
            secret_key = keyring.get_password(APP_NAME, KEY_NAME)
            if secret_key:
                logger.info("FLET_SECRET_KEY carregada do Keyring")
                return secret_key
        except Exception as e:
            logger.warning(f"Erro ao acessar Keyring: {e}")
        
        # 3. Gera nova chave se não encontrou
        secret_key = base64.b64encode(secrets.token_bytes(32)).decode('utf-8')
        
        # Tenta salvar no Keyring para futuras sessões
        try:
            keyring.set_password(APP_NAME, KEY_NAME, secret_key)
            logger.info("Nova FLET_SECRET_KEY gerada e salva no Keyring")
        except Exception as e:
            logger.warning(f"Não foi possível salvar no Keyring: {e}")
            logger.info("Nova FLET_SECRET_KEY gerada (apenas para esta sessão)")
        
        return secret_key
        
    except Exception as e:
        logger.error(f"Erro crítico ao gerenciar FLET_SECRET_KEY: {e}")
        # Fallback: gera chave temporária
        return base64.b64encode(secrets.token_bytes(32)).decode('utf-8')
    
    # os.environ["FLET_SECRET_KEY"] = get_or_create_flet_secret_key()

# ===============================================================================
# 3. TRATAMENTOS PARA BIBLIOTECAS ESPECÍFICAS
def setup_library_fixes():
    """Aplica fixes específicos para bibliotecas em ambiente frozen"""
    
    # Fix para requests/urllib3 - certificados SSL
    if getattr(sys, 'frozen', False):
        import ssl
        import certifi
        
        # Garante que o certifi encontre os certificados
        os.environ['SSL_CERT_FILE'] = certifi.where()
        os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
    
    # Fix para PIL/Pillow - plugins de imagem
    try:
        from PIL import Image
        # Força o carregamento de plugins essenciais
        Image.preinit()
    except ImportError:
        pass
    
    # Fix para matplotlib (se usado)
    # ...

# ===============================================================================
# 4. GERENCIAMENTO DE RECURSOS E ASSETS
# get_resource_path -> movido para utils.py

# ===============================================================================
# 5. CONFIGURAÇÕES DE REDE E PROXY
def setup_network_config():
    """Configura settings de rede para ambiente corporativo"""
    if getattr(sys, 'frozen', False):
        # Em ambiente frozen, pode ser necessário configurar proxy
        # Verifica se há configurações de proxy no ambiente
        proxy_settings = {
            'http_proxy': os.getenv('HTTP_PROXY'),
            'https_proxy': os.getenv('HTTPS_PROXY'),
            'no_proxy': os.getenv('NO_PROXY')
        }
        
        # Aplica configurações se existirem
        for key, value in proxy_settings.items():
            if value:
                os.environ[key.upper()] = value

# ===============================================================================
# 6. TRATAMENTO DE EXCEÇÕES GLOBAIS
def setup_global_exception_handler():
    """Configura handler global para exceções não tratadas"""
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        logger.critical(
            "Exceção não tratada",
            exc_info=(exc_type, exc_value, exc_traceback)
        )
        
        # Em ambiente frozen, pode mostrar dialog de erro amigável
        if getattr(sys, 'frozen', False):
            import tkinter as tk
            from tkinter import messagebox
            
            root = tk.Tk()
            root.withdraw()  # Esconde janela principal
            
            messagebox.showerror(
                "Erro",
                "Ocorreu um erro inesperado. Verifique o arquivo de log."
            )
            root.destroy()
    
    sys.excepthook = handle_exception

# ===============================================================================
# 7. FUNÇÃO PRINCIPAL DE INICIALIZAÇÃO
def initialize_app():
    """Inicializa todas as configurações necessárias"""
    # Sem pyi_splash

    # 1. Configura ambiente frozen
    setup_frozen_environment()
    
    # 2. Aplica fixes de bibliotecas
    setup_library_fixes()
    
    # 3. Configura rede
    setup_network_config()
    
    # 4. Configura handler de exceções
    setup_global_exception_handler()
    
    # 5. Configura FLET_SECRET_KEY
    secret_key = get_or_create_secret_key()
    os.environ['FLET_SECRET_KEY'] = secret_key
    
    logger.info("Aplicação inicializada com sucesso")

# ===============================================================================
# 8. PONTO DE ENTRADA
# =====================================================================================================================================

import threading
def load_to_utils():
    # Antecipando, sob load_progressing_gui, outros imports que serão utilizados em utils.py:
    start_time_l = perf_counter()
    logger.info("[DEBUG] Start func.: load_to_utils")
    import unicodedata
    import pdfplumber, fitz
    from unidecode import unidecode
    from sentence_transformers import SentenceTransformer
    execution_time_l = perf_counter() - start_time_l
    logger.info(f"[DEBUG] Finish func.: load_to_utils em {execution_time_l:.4f}s")

threading.Thread(target=load_to_utils, daemon=True).start()

import flet as ft
# Importa a função 'main' do módulo app dentro de flet_gui
from src.flet_ui.app import main
from src.settings import UPLOAD_TEMP_DIR, ASSETS_DIR_ABS, WEB_TEMP_EXPORTS_SUBDIR 
from src.utils import register_temp_files_cleanup

# Verifica se este script está sendo executado diretamente
if __name__ == "__main__":
    
    if getattr(sys, 'frozen', False):
        # Em modo compilado (PyInstaller), os assets estão na pasta temporária
        base_path = sys._MEIPASS
        final_assets_dir = os.path.join(base_path, "assets")
    else:
        # Em modo de desenvolvimento, usa o caminho absoluto
        final_assets_dir = ASSETS_DIR_ABS

    register_temp_files_cleanup(UPLOAD_TEMP_DIR)

    temp_exports_full_path = os.path.join(ASSETS_DIR_ABS, WEB_TEMP_EXPORTS_SUBDIR)
    os.makedirs(temp_exports_full_path, exist_ok=True) 
    register_temp_files_cleanup(temp_exports_full_path)

    execution_time = perf_counter() - start_time
    logger.info(f"[DEBUG] Carregado RUN em {execution_time:.4f}s")

    # Configura e inicia a aplicação Flet
    ft.app(
        target=main,                 # Função principal a ser executada
        view=ft.AppView.WEB_BROWSER, # Executa como uma aplicação web no navegador padrão
        port=8550,                   # Porta em que a aplicação será servida (ex: http://localhost:8550)
        assets_dir=final_assets_dir, # Descomente se você tiver uma pasta 'assets' na raiz
        upload_dir=UPLOAD_TEMP_DIR
    )

    # >>> python run.py  ou
    # >>> flet run -w run.py
    # >>> flet run run.py -d -r --ignore-dirs=logs,__pycache__,.git,.pytest_cache,storage --web -p 8550

