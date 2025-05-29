# src/config/settings.py

import os, logging
from pathlib import Path

logger = logging.getLogger(__name__)

#TODO: DELETE:
api_key_test = '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'

cotacao_dolar_to_real = 6

# --- Firebase Settings ---
# ATENÇÃO: Obtenha esta chave no Console do Firebase -> Configurações do Projeto -> Geral -> Seus apps -> Configuração do SDK
# Esta chave é considerada pública e segura para ser incluída no código do cliente (como este app desktop).
# Ela identifica seu projeto Firebase para os serviços de Autenticação, Firestore (com regras de segurança), etc.
# NÃO confunda com a Chave de Serviço (Admin SDK JSON), que é secreta.
FIREBASE_WEB_API_KEY = os.getenv("FIREBASE_WEB_API_KEY", "AIzaSyDuRGIubM32TMjAQEvpl55tf4sGIWULKpk")

if FIREBASE_WEB_API_KEY == "SUA_FIREBASE_WEB_API_KEY_AQUI":
    logger.warning(
        "A variável FIREBASE_WEB_API_KEY não foi definida. "
        "A autenticação NÃO funcionará. "
        "Defina-a no arquivo 'src/config/settings.py' ou como variável de ambiente."
    )

# --- Constantes de Configuração (Centralizadas aqui) ---
# É importante que estas sejam consistentes com o uso em outros lugares (FirebaseBackend)
# Idealmente, seriam carregadas de uma config central, mas por ora definimos aqui.
APP_NAME = "DocsAnalyzerPF"
KEYRING_SERVICE_FIREBASE = f"{APP_NAME}_Firebase"
KEYRING_USER_ENCRYPTION_KEY = "encryption_key" # Chave Fernet

# Calcula o diretório de dados da aplicação
try:
    if os.name == 'nt': # Windows
        APP_DATA_DIR = os.path.join(os.getenv('APPDATA', ''), APP_NAME)
    elif sys.platform == 'darwin': # macOS
        APP_DATA_DIR = os.path.join(os.path.expanduser('~/Library/Application Support'), APP_NAME)
    else: # Linux e outros
        APP_DATA_DIR = os.path.join(os.path.expanduser('~/.config'), APP_NAME)
    os.makedirs(APP_DATA_DIR, exist_ok=True) # Garante que exista
except Exception as e:
    logger.critical(f"Erro crítico ao determinar/criar o diretório de dados da aplicação: {e}", exc_info=True)
    # Define um fallback para o diretório atual se tudo mais falhar, mas loga criticamente
    APP_DATA_DIR = os.path.join(os.getcwd(), f".{APP_NAME}_data")
    os.makedirs(APP_DATA_DIR, exist_ok=True)
    logger.warning(f"Usando diretório de dados fallback: {APP_DATA_DIR}")
    
ENCRYPTED_SERVICE_KEY_FILENAME = "firebase_service_key.enc"
ENCRYPTED_SERVICE_KEY_PATH = os.path.join(APP_DATA_DIR, ENCRYPTED_SERVICE_KEY_FILENAME)

# --- Outras Configurações (Podem ser adicionadas futuramente) ---
APP_VERSION = "0.1.0" # Versão inicial do MVP
DEFAULT_LLM_SERVICE = "openai" # Exemplo

# (Pode adicionar mais configurações conforme necessário)

APP_TITLE = "IA Assistente - COR/SR/PF/SP" # Análise de Documentos

CLOUD_LOGGER_FOLDER = "logs/"        # Pasta no CloudStorage
CLOUD_LOGGER_UPLOAD_INTERVAL = 120   # Tempo de intervalo entre uploads (segundos)
CLOUD_LOGGER_MAX_BUFFER_SIZE = 1000  # Tamanho máximo do buffer (número de linhas)
CLOUD_LOGGER_MAX_RETRIES = 3         # Número máximo de tentativas de upload
CLOUD_LOGGER_RETRY_DELAY = 12        # Tempo de espera entre as tentativas (segundos)

PROJECT_ID = "docs-analyzer-a7430"
FB_STORAGE_BUCKET = "docs-analyzer-a7430.firebasestorage.app"
#FIREBASE_DB_URL = 'https://app-scripts-sec-default-rtdb.firebaseio.com/'

PATH_LOGS = Path("logs") # Pastas locais
PATH_LOGS.mkdir(exist_ok=True) 

# Constantes Keyring Proxy -> rótulos fixos para uso no keyring e também no Dict_resultado config_proxy
PROXY_URL_DEFAULT = 'proxy.dpf.gov.br'
PROXY_PORT_DEFAULT = '8080'
PROXY_KEYRING_SERVICE = f"{APP_NAME}_Proxy"
K_PROXY_ENABLED = "proxy_enabled"
K_PROXY_PASSWORD_SAVED = "password_saved_proxy"
K_PROXY_IP_URL = "ip_address"
K_PROXY_PORT = "port_proxy"
K_PROXY_USERNAME = "username_proxy"
K_PROXY_PASSWORD = "password_proxy" 

def show_data_k():
    keyring = None
    print(keyring.get_password(PROXY_KEYRING_SERVICE, K_PROXY_ENABLED))
    print(keyring.get_password(PROXY_KEYRING_SERVICE, K_PROXY_IP_URL))
    print(keyring.get_password(PROXY_KEYRING_SERVICE, K_PROXY_USERNAME))
    print(keyring.get_password(PROXY_KEYRING_SERVICE, K_PROXY_PASSWORD))
    #keyring.set_password(PROXY_KEYRING_SERVICE, K_PROXY_ENABLED, 'false')


# --- Firebase LLM Providers Config Paths ---
LLM_PROVIDERS_CONFIG_COLLECTION = "llm_providers_config" # Já existe como PROVIDERS_COLLECTION em llm_settings_view
LLM_PROVIDERS_DEFAULT_DOC_ID = "default_list"          # Já existe como DEFAULT_PROVIDERS_DOC_ID em llm_settings_view
USER_LLM_PREFERENCES_COLLECTION = "user_llm_preferences"

# --- Session Keys for LLM Providers and Preferences ---
KEY_SESSION_LOADED_LLM_PROVIDERS = "app_loaded_llm_providers" # Lista de dicts dos provedores
KEY_SESSION_USER_LLM_PREFERENCES = "app_user_llm_preferences" # Dict com default_provider e default_model


# --- Constantes referentes aos modelos de LLM:
DEFAULT_LLM_PROVIDER = "openai"
DEFAULT_LLM_MODEL = "gpt-4.1-nano" # Modelo inicial padrão
DEFAULT_TEMPERATURE = 0.3 # Baixa temperatura para respostas mais factuais/consistentes


SRC_DIR = os.path.dirname(os.path.abspath(__file__))
APP_ROOT_DIR = os.path.dirname(SRC_DIR)
UPLOAD_TEMP_DIR = os.path.join(APP_ROOT_DIR, "uploads_temp") 

ASSETS_DIR_ABS = os.path.join(APP_ROOT_DIR, "assets")

FLET_SECRET_KEY = "minha_chave_secreta_de_teste_temporaria_123"

# Caminho para a imagem (ajuste conforme necessário, pode estar em 'assets')
PATH_IMAGE_LOGO_DEPARTAMENTO = "logo_pf_orgao.png" 

# --- Firebase Default Settings Paths ---
APP_DEFAULT_SETTINGS_COLLECTION = "app_default_settings"
ANALYZE_PDF_DEFAULTS_DOC_ID = "analyze_pdf_defaults"

# --- Session Keys for Analysis Settings ---
KEY_SESSION_ANALYSIS_SETTINGS = "app_analysis_settings" # Configurações atuais da sessão
KEY_SESSION_CLOUD_ANALYSIS_DEFAULTS = "app_cloud_analysis_defaults" # Padrões carregados da nuvem

# --- Fallback Default Analysis Settings (se Firestore falhar) ---
FALLBACK_ANALYSIS_SETTINGS = {
    "pdf_extractor": "PyMuPdf-fitz",
    "embeddings_model": "all-MiniLM-L6-v2",
    "language_detector": "langdetect",
    "token_counter": "tiktoken",
    "tfidf_analyzer": "sklearn",
    "llm_provider": "openai",
    "llm_model": "gpt-4.1-nano",
    "llm_input_token_limit": 180000,
    "llm_output_format": "Padrão",
    "llm_max_output_length": "Padrão",
    "llm_temperature": 0.2,
    "prompt_structure": "prompt_unico",
}

# --- Firebase LLM Embeddings Config Paths ---
LLM_EMBEDDINGS_CONFIG_COLLECTION = "llm_providers_config" # Pode ser a mesma coleção dos provedores
LLM_EMBEDDINGS_DEFAULT_DOC_ID = "model_embeddings_list" # Documento com a lista de custos

# --- Session Keys for Embeddings ---
KEY_SESSION_TOKENS_EMBEDDINGS = "app_tokens_embeddings"
KEY_SESSION_MODEL_EMBEDDINGS_LIST = "app_model_embeddings_list"



