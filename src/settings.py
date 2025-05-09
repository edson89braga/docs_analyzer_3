# src/config/settings.py

import os, logging
from pathlib import Path

logger = logging.getLogger(__name__)

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

# --- Outras Configurações (Podem ser adicionadas futuramente) ---
APP_VERSION = "0.1.0" # Versão inicial do MVP
DEFAULT_LLM_SERVICE = "openai" # Exemplo

# (Pode adicionar mais configurações conforme necessário)

APP_TITLE = "IA AssiStente - Análise de Documentos - COR/SR/PF/SP"

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