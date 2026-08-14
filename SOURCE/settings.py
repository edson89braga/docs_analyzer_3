import logging
logger = logging.getLogger(__name__)

from time import perf_counter
start_time = perf_counter()
logger.info(f"[DEBUG] {start_time:.4f}s - Iniciando settings.py")
print(f"[DEBUG] {start_time:.4f}s - Iniciando settings.py")

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
APP_NAME = "Sist_Opera"
APP_TITLE = "ÓPERA - IA Assistente" # Análise de Documentos
APP_VERSION = "0.5.2" 
ALLOWED_EMAIL_DOMAINS = ["pf.gov.br", "dpf.gov.br"]
KEY_NAME_FLET_SECRET_KEY = "flet_secret_key"

# Calcula o diretório de dados da aplicação:
# Em modo server, respeita variável de ambiente para montagem de volume (ex: /app/data)
if os.getenv("APP_MODE") == "server":
    APP_DATA_DIR = os.getenv("SERVER_DATA_DIR", "/app/data")
else:
    if os.name == 'nt':
        APP_DATA_DIR = os.path.join(os.getenv('APPDATA', ''), APP_NAME)
    else:
        APP_DATA_DIR = os.path.join(os.path.expanduser('~'), f".{APP_NAME}_data")

os.makedirs(APP_DATA_DIR, exist_ok=True)

ENCRYPTED_SERVICE_KEY_FILENAME = "firebase_service_key.enc"
ENCRYPTED_SERVICE_KEY_PATH = os.path.join(APP_DATA_DIR, ENCRYPTED_SERVICE_KEY_FILENAME)

# --- Configurações do Firebase -------------------------------------------------------------------------------
FIREBASE_WEB_API_KEY = os.getenv("FIREBASE_WEB_API_KEY", "AIzaSyDuRGIubM32TMjAQEvpl55tf4sGIWULKpk")

if FIREBASE_WEB_API_KEY == "SUA_FIREBASE_WEB_API_KEY_AQUI":
    logger.warning(
        "A variável FIREBASE_WEB_API_KEY não foi definida. "
        "A autenticação NÃO funcionará. "
        "Defina-a no arquivo 'SOURCE/config/settings.py' ou como variável de ambiente."
    )

PROJECT_ID = "docs-analyzer-a7430"
FB_STORAGE_BUCKET = "docs-analyzer-a7430.firebasestorage.app"
#FIREBASE_DB_URL = 'https://app-scripts-sec-default-rtdb.firebaseio.com/'

# Caminhos de configuração do FIRESTORE -----------------------------------
APP_DEFAULT_SETTINGS_COLLECTION = "app_default_settings"
ANALYZE_PDF_DEFAULTS_DOC_ID = "analyze_pdf_defaults"
CHAT_DOCS_DEFAULTS_DOC_ID = "chat_docs_defaults"
LLM_PROVIDERS_CONFIG_COLLECTION = "llm_providers_config" # Já existe como PROVIDERS_COLLECTION em llm_settings_view
LLM_PROVIDERS_DEFAULT_DOC_ID = "default_list"          # Já existe como DEFAULT_PROVIDERS_DOC_ID em llm_settings_view
LLM_EMBEDDINGS_CONFIG_COLLECTION = "llm_providers_config" # Pode ser a mesma coleção dos provedores
LLM_EMBEDDINGS_DEFAULT_DOC_ID = "model_embeddings_list" # Documento com a lista de custos

PROMPTS_COLLECTION = "prompt_templates"
PROMPTS_DOCUMENT_ID = "initial_analysis_v1"

# --- Chaves de sessão relacionadas às configurações das views ---
KEY_SESSION_NC_ANALYZE_SETTINGS = "app_nc_analyze_settings"
KEY_SESSION_CHAT_SETTINGS = "app_chat_settings"
#KEY_SESSION_ANALYSIS_SETTINGS = "app_analysis_settings" # Configurações atuais da sessão

# Chaves de sessão relacionadas ao Firebase ---------------------------------
KEYRING_SERVICE_FIREBASE = f"{APP_NAME}_Firebase"
KEYRING_USER_ENCRYPTION_KEY = "encryption_key" # Chave Fernet
KEY_SESSION_LOADED_LLM_PROVIDERS = "app_loaded_llm_providers" # Lista de dicts dos provedores
KEY_SESSION_CLOUD_ANALYSIS_DEFAULTS = "app_cloud_analysis_defaults" # Padrões carregados da nuvem (nc_analyze)
KEY_SESSION_CLOUD_CHAT_DEFAULTS = "app_cloud_chat_defaults" # Padrões carregados da nuvem, já mesclados com overrides de chat_docs_defaults
KEY_SESSION_TOKENS_EMBEDDINGS = "app_tokens_embeddings"
KEY_SESSION_MODEL_EMBEDDINGS_LIST = "app_model_embeddings_list"

# --- Configurações do Banco de Dados Local (SQLite) ---
DB_APP_SETTINGS_TABLE = "app_settings"

# --- Configurações de Cloud Logger ---------------------------------------------
CLOUD_LOGGER_FOLDER = "logs/"        # Pasta no CloudStorage
CLOUD_LOGGER_UPLOAD_INTERVAL = 120   # Tempo de intervalo entre uploads (segundos)
CLOUD_LOGGER_MAX_BUFFER_SIZE = 1000  # Tamanho máximo do buffer (número de linhas)
CLOUD_LOGGER_MAX_RETRIES = 3         # Número máximo de tentativas de upload
CLOUD_LOGGER_RETRY_DELAY = 12        # Tempo de espera entre as tentativas (segundos)


# --- Configurações de PDF_PROCESSOR e LLM -------------------------------------------------
DEFAULT_LLM_SERVICE = "llm_pf"  # "openai" # Exemplo
DEFAULT_LLM_PROVIDER = "llm_pf" # "openai"
DEFAULT_LLM_MODEL = "Qwen3.5-35B-A3B-FP8"  # "gpt-5-nano" # Modelo inicial padrão
DEFAULT_TEMPERATURE = 0.2 # Baixa temperatura para respostas mais factuais/consistentes

# Endpoint interno da PF (provider "llm_pf") -----------------------------------------------
# Modelo fixo servido em http://llm.pf.gov.br:31893/v1, independente do modelo selecionado na UI.
LLM_PF_MODEL_ID = "Qwen3.5-35B-A3B-FP8"  # Janela de contexto: 128k tokens (substituiu Qwen3-8B-AWQ, 32k)
# Teto de tokens de saída solicitado ao endpoint; sem isso, a resposta é truncada em 4096 tokens.
# NÃO usar um valor próximo da janela de contexto: a API valida (tokens_de_entrada + max_tokens) contra
# a janela total, então pedir "todo o espaço restante" faz a requisição encostar no teto por construção e
# qualquer subestimação do input (tiktoken vs. tokenizer real do Qwen) vira erro 400. Valor dimensionado
# pelo que a resposta de fato consome. Vale para o modo SEM raciocínio (a análise completa da NC
# consome ~2.300 tokens de JSON).
LLM_PF_MAX_OUTPUT_TOKENS = 16_000

# Teto de saída quando enable_thinking=True. Medição no endpoint (13/08/2026): o raciocínio do
# Qwen3.5 é longo e NÃO é limitável — 'chat_template_kwargs.thinking_budget' e o parâmetro
# 'reasoning_effort' são aceitos pela API e ignorados pelo modelo; num prompt trivial de 48 tokens o
# raciocínio já consome ~2.700 tokens. Com o teto de 16k, uma análise de lote grande gastava todo o
# orçamento raciocinando e terminava em finish_reason='length' com 'content' vazio, sem nunca chegar
# a emitir o JSON. O valor é aplicado apenas ao max_tokens da requisição (ver
# compute_llm_pf_max_output_tokens) e continua limitado ao espaço que sobra na janela; a reserva
# usada na truncagem de entrada segue sendo LLM_PF_MAX_OUTPUT_TOKENS, para não reduzir a quantidade
# de páginas analisáveis.
LLM_PF_MAX_OUTPUT_TOKENS_THINKING = 32_000

# Truncagem automática de tokens de entrada (nc_analyzer e chat) ---------------------------
# Usadas para calcular quantas páginas de documento cabem no contexto, quando o usuário
# deixa 'Limite Tokens Input' vazio no drawer de configurações (modo automático).
# A reserva de saída usada no cálculo é o próprio LLM_PF_MAX_OUTPUT_TOKENS acima — o orçamento de
# input é o que sobra da janela depois de garantir esse teto (ver compute_llm_pf_auto_token_limit).
LLM_PF_CONTEXT_WINDOW = 128_000            # janela total do modelo
LLM_PF_CHAT_HISTORY_RESERVE_TOKENS = 20_000  # reserva extra p/ chat: o document_context fixo não pode
                                              # consumir o espaço que os próximos turnos da conversa vão precisar
LLM_PF_TOKEN_SAFETY_MARGIN = 0.10          # ~10%, calibrado no drift medido entre tiktoken e o tokenizer real do Qwen (~7,9%)

# Fallback Default Analysis Settings (se Firestore falhar)
FALLBACK_ANALYSIS_SETTINGS = {
    "pdf_extractor": "PyMuPdf-fitz",
    "vectorization_model": "tfidf_vectorizer", # "all-MiniLM-L6-v2",
    "similarity_threshold": 0.97, # 0.87
    "language_detector": "langdetect",
    "token_counter": "tiktoken",
    "tfidf_analyzer": "sklearn",
    "llm_provider": "llm_pf",
    "llm_model": "Qwen3.5-35B-A3B-FP8",
    "llm_input_token_limit": None,  # None = truncagem automática (calculada em runtime p/ llm_pf)
    "llm_output_format": "Padrão",
    "llm_max_output_length": "Padrão",
    "llm_temperature": 0.2,
    "prompt_structure": "prompt_unico",
    "reasoning_effort": "low",
    "verbosity_level": "medium"
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


# --- Chaves de Sessão Compartilhadas entre Views ---
KEY_SESSION_SHARED_FILES_ORDERED = "shared_files_ordered"
KEY_SESSION_SHARED_DOCUMENT_CONTEXT = "shared_document_context"
KEY_SESSION_SHARED_PROCESSING_METADATA = "shared_processing_metadata"

# --- Configurações de NC_ANALYZE_VIEW --------------------------------------------------------------------------
# Chaves de Sessão (mantidas e podem ser expandidas) apv: Refere-se a "Analyze PDF View"
KEY_SESSION_CURRENT_BATCH_NAME = "apv_current_batch_name"
KEY_SESSION_PROMPTS_FINAL = "app_prompts_from_firestore_1"
KEY_SESSION_PROMPTS_DICT = "app_prompts_from_firestore_2"
KEY_SESSION_LIST_TO_PROMPTS = "app_list_to_prompts_from_firestore"

# --- Configurações de CHAT_VIEW --------------------------------------------------------------------------
KEY_SESSION_CHAT_PROMPT_STRICT = "chat_prompt_strict"
KEY_SESSION_CHAT_PROMPT_FLEXIBLE = "chat_prompt_flexible"
KEY_SESSION_CHAT_PROMPT_CUSTOM = "chat_prompt_custom"
KEY_SESSION_CHAT_PROMPT_ACTIVE_KEY = "chat_prompt_active_key"
CHAT_PROMPTS_DEFAULTS_DOC_ID = "chat_prompts_defaults"

# -----------------------------------------------------------------------------------------------------------------

# --- Configurações do Atualizador Automático ---
VERSION_INFO_URL = "https://raw.githubusercontent.com/edson89braga/docs_analyzer_3/refs/heads/master/release_info/version.json" # json original

# --- Configurações do Motor de ML Local ---
ML_ENGINE_VERSION = "1.0" # Versão local do motor de ML
ML_ENGINE_API_URL = "http://127.0.0.1:8001"

execution_time = perf_counter() - start_time
logger.info(f"[DEBUG] Carregado SETTINGS em {execution_time:.4f}s")
print(f"[DEBUG] Carregado SETTINGS em {execution_time:.4f}s")