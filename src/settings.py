import logging
logger = logging.getLogger(__name__)

from time import perf_counter
start_time = perf_counter()
logger.info(f"[DEBUG] {start_time:.4f}s - Iniciando settings.py")
print(f"[DEBUG] {start_time:.4f}s - Iniciando settings.py")

# --- Variáveis de Teste/Exemplo (Remover em produção) -----------------------------------------------------------------------
# TODO: DELETE:
api_key_test = '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'

# --- Outras Variáveis globais temporárias (Remover em produção?)--------------------------------------------------------------
cotacao_dolar_to_real = 6

import os, sys

# --- Configurações de Diretórios e Arquivos -------------------------------------------------------------------------------
SRC_DIR = os.path.dirname(os.path.abspath(__file__))

def get_resource_path(relative_path=''):
    """
    Obtém o caminho correto para recursos/assets tanto em desenvolvimento
    quanto em ambiente frozen
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller cria uma pasta temporária
        base_path = os.path.dirname(sys.executable)
    else:
        # Desenvolvimento
        base_path = os.path.dirname(SRC_DIR)
    
    return os.path.join(base_path, relative_path)

APP_ROOT_DIR = get_resource_path()

ASSETS_DIR = os.path.join(APP_ROOT_DIR, "assets")
UPLOAD_TEMP_DIR = os.path.join(APP_ROOT_DIR, "uploads_temp")
PATH_LOGS_DIR = os.path.join(APP_ROOT_DIR, "logs")

for pth in [UPLOAD_TEMP_DIR, ASSETS_DIR, PATH_LOGS_DIR]:
    if not os.path.exists(pth):
        os.makedirs(pth)

# --- Paths relativos à pasta Assets (flet):
PATH_IMAGE_LOGO_DEPARTAMENTO = "logo_pf_orgao.png" 
TEMPLATES_DOCX_SUBDIR = "templates_docx"
WEB_TEMP_EXPORTS_SUBDIR = "temp_docx_exports"

# --- Configurações Gerais da Aplicação -------------------------------------------------------------------------------
APP_NAME = "DocsAnalyzerPF"
APP_VERSION = "0.2" # Versão inicial do MVP
APP_TITLE = "IA Assistente - COR/SR/PF/SP" # Análise de Documentos
ALLOWED_EMAIL_DOMAINS = ["pf.gov.br", "dpf.gov.br"]
KEY_NAME_FLET_SECRET_KEY = "flet_secret_key"

# Calcula o diretório de dados da aplicação:
try:
    assert os.name == 'nt' # Windows
    APP_DATA_DIR = os.path.join(os.getenv('APPDATA', ''), APP_NAME)
    os.makedirs(APP_DATA_DIR, exist_ok=True) # Garante que exista
except Exception as e:
    logger.critical(f"Erro crítico ao determinar/criar o diretório de dados da aplicação: {e}", exc_info=True)
    # Define um fallback para o diretório atual se tudo mais falhar, mas loga criticamente
    APP_DATA_DIR = os.path.join(os.getcwd(), f".{APP_NAME}_data")
    os.makedirs(APP_DATA_DIR, exist_ok=True)
    logger.warning(f"Usando diretório de dados fallback: {APP_DATA_DIR}")

ENCRYPTED_SERVICE_KEY_FILENAME = "firebase_service_key.enc"
ENCRYPTED_SERVICE_KEY_PATH = os.path.join(APP_DATA_DIR, ENCRYPTED_SERVICE_KEY_FILENAME)

# --- Configurações do Firebase -------------------------------------------------------------------------------
FIREBASE_WEB_API_KEY = os.getenv("FIREBASE_WEB_API_KEY", "AIzaSyDuRGIubM32TMjAQEvpl55tf4sGIWULKpk")

if FIREBASE_WEB_API_KEY == "SUA_FIREBASE_WEB_API_KEY_AQUI":
    logger.warning(
        "A variável FIREBASE_WEB_API_KEY não foi definida. "
        "A autenticação NÃO funcionará. "
        "Defina-a no arquivo 'src/config/settings.py' ou como variável de ambiente."
    )

PROJECT_ID = "docs-analyzer-a7430"
FB_STORAGE_BUCKET = "docs-analyzer-a7430.firebasestorage.app"
#FIREBASE_DB_URL = 'https://app-scripts-sec-default-rtdb.firebaseio.com/'

# Caminhos de configuração do FIRESTORE -----------------------------------
APP_DEFAULT_SETTINGS_COLLECTION = "app_default_settings"
ANALYZE_PDF_DEFAULTS_DOC_ID = "analyze_pdf_defaults"
LLM_PROVIDERS_CONFIG_COLLECTION = "llm_providers_config" # Já existe como PROVIDERS_COLLECTION em llm_settings_view
LLM_PROVIDERS_DEFAULT_DOC_ID = "default_list"          # Já existe como DEFAULT_PROVIDERS_DOC_ID em llm_settings_view
USER_LLM_PREFERENCES_COLLECTION = "user_llm_preferences"
LLM_EMBEDDINGS_CONFIG_COLLECTION = "llm_providers_config" # Pode ser a mesma coleção dos provedores
LLM_EMBEDDINGS_DEFAULT_DOC_ID = "model_embeddings_list" # Documento com a lista de custos

PROMPTS_COLLECTION = "prompt_templates"
PROMPTS_DOCUMENT_ID = "initial_analysis_v1"

# Chaves de sessão relacionadas ao Firebase ---------------------------------
KEYRING_SERVICE_FIREBASE = f"{APP_NAME}_Firebase"
KEYRING_USER_ENCRYPTION_KEY = "encryption_key" # Chave Fernet
KEY_SESSION_LOADED_LLM_PROVIDERS = "app_loaded_llm_providers" # Lista de dicts dos provedores
KEY_SESSION_USER_LLM_PREFERENCES = "app_user_llm_preferences" # Dict com default_provider e default_model
KEY_SESSION_ANALYSIS_SETTINGS = "app_analysis_settings" # Configurações atuais da sessão
KEY_SESSION_CLOUD_ANALYSIS_DEFAULTS = "app_cloud_analysis_defaults" # Padrões carregados da nuvem
KEY_SESSION_TOKENS_EMBEDDINGS = "app_tokens_embeddings"
KEY_SESSION_MODEL_EMBEDDINGS_LIST = "app_model_embeddings_list"

# --- Configurações de Cloud Logger ---------------------------------------------
CLOUD_LOGGER_FOLDER = "logs/"        # Pasta no CloudStorage
CLOUD_LOGGER_UPLOAD_INTERVAL = 120   # Tempo de intervalo entre uploads (segundos)
CLOUD_LOGGER_MAX_BUFFER_SIZE = 1000  # Tamanho máximo do buffer (número de linhas)
CLOUD_LOGGER_MAX_RETRIES = 3         # Número máximo de tentativas de upload
CLOUD_LOGGER_RETRY_DELAY = 12        # Tempo de espera entre as tentativas (segundos)


# --- Configurações de PDF_PROCESSOR e LLM -------------------------------------------------
DEFAULT_LLM_SERVICE = "openai" # Exemplo
DEFAULT_LLM_PROVIDER = "openai"
DEFAULT_LLM_MODEL = "gpt-4.1-mini" # Modelo inicial padrão
DEFAULT_TEMPERATURE = 0.3 # Baixa temperatura para respostas mais factuais/consistentes

# Fallback Default Analysis Settings (se Firestore falhar)
FALLBACK_ANALYSIS_SETTINGS = {
    "pdf_extractor": "PyMuPdf-fitz",
    "vectorization_model": "all-MiniLM-L6-v2",
    "similarity_threshold": 0.87,
    "language_detector": "langdetect",
    "token_counter": "tiktoken",
    "tfidf_analyzer": "sklearn",
    "llm_provider": "openai",
    "llm_model": "gpt-4.1-mini",
    "llm_input_token_limit": 180000,
    "llm_output_format": "Padrão",
    "llm_max_output_length": "Padrão",
    "llm_temperature": 0.2,
    "prompt_structure": "prompt_unico",
}


# --- Configurações de Proxy -------------------------------------------------------------------------
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

def show_data_k(keyring):
    """
    Função de depuração para exibir dados de proxy armazenados no Keyring.
    ATENÇÃO: Esta função é apenas para fins de depuração e não deve ser usada em produção.
    """
    logger.debug(f"Proxy Enabled: {keyring.get_password(PROXY_KEYRING_SERVICE, K_PROXY_ENABLED)}")
    logger.debug(f"Proxy IP URL: {keyring.get_password(PROXY_KEYRING_SERVICE, K_PROXY_IP_URL)}")
    logger.debug(f"Proxy Username: {keyring.get_password(PROXY_KEYRING_SERVICE, K_PROXY_USERNAME)}")
    logger.debug(f"Proxy Password: *** ") # {keyring.get_password(PROXY_KEYRING_SERVICE, K_PROXY_PASSWORD)}


# --- Configurações de NC_ANALYZE_VIEW --------------------------------------------------------------------------
# Chaves de Sessão (mantidas e podem ser expandidas) apv: Refere-se a "Analyze PDF View"
KEY_SESSION_CURRENT_BATCH_NAME = "apv_current_batch_name"
KEY_SESSION_PDF_FILES_ORDERED = "apv_pdf_files_ordered"
KEY_SESSION_PROCESSING_METADATA = "apv_processing_metadata"
KEY_SESSION_LLM_METADATA = "apv_llm_metadata"
KEY_SESSION_FEEDBACK_COLLECTED_FOR_CURRENT_ANALYSIS = "apv_feedback_collected"  # Flag para indicar se o feedback já foi coletado.
KEY_SESSION_LLM_REANALYSIS = "apv_llm_reanalysis_flag"

# Dados a ficar em _SERVER_SIDE_CACHE:
KEY_SESSION_PDF_AGGREGATED_TEXT_INFO = "apv_pdf_aggregated_text_info" # (str_pages, aggregated_text, tokens_antes, tokens_depois)
KEY_SESSION_PDF_LLM_RESPONSE = "apv_pdf_llm_response"                                           # Resposta original da IA
KEY_SESSION_PDF_LLM_RESPONSE_ACTUAL = "apv_pdf_llm_response_actual"                             # Resposta na GUI (que pode ter sido editada pelo usuário) # LLMStructuredResultDisplay.get_current_form_data()
KEY_SESSION_PDF_LLM_RESPONSE_SNAPSHOT_FOR_FEEDBACK = "apv_llm_response_snapshot_for_feedback"   # Cópia da resposta original p/ fins de comparação com a respota editada pelo usuário.

KEY_SESSION_PROMPTS_FINAL = "app_prompts_from_firestore_1"
KEY_SESSION_PROMPTS_DICT = "app_prompts_from_firestore_2"
KEY_SESSION_LIST_TO_PROMPTS = "app_list_to_prompts_from_firestore"

# -----------------------------------------------------------------------------------------------------------------

execution_time = perf_counter() - start_time
logger.info(f"[DEBUG] Carregado SETTINGS em {execution_time:.4f}s")
print(f"[DEBUG] Carregado SETTINGS em {execution_time:.4f}s")