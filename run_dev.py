# run_dev.py
import flet as ft
import flet.fastapi
from fastapi import FastAPI
import uvicorn
import os
import logging

# Importa a função principal da UI Flet do seu projeto
from src.flet_ui.app import main as create_flet_page_layout # Renomeado para clareza
from src.settings import APP_NAME, UPLOAD_TEMP_DIR, ASSETS_DIR_ABS # Importa o nome da pasta de uploads
from src.logger.logger import LoggerSetup # Para inicializar o logger

# --- Configuração Inicial Essencial (similar ao seu run.py) ---
# Logger (pode ser uma configuração mais simples para dev c/ hot reload)
try:
    # Inicialização básica do logger para run_dev.py
    # Você pode querer uma configuração diferente ou mais leve aqui.
    # A inicialização completa com Firebase pode ser lenta para hot reload.
    # Considere ter uma flag ou um modo "DEV" no seu LoggerSetup.
    LoggerSetup.initialize(
        routine_name=f"{APP_NAME}_DevHotReload",
        # firebase_client_storage=None, # Opcional para dev
        # fb_manager_storage_admin=None # Opcional para dev
    )
    logger = LoggerSetup.get_logger("run_dev")
    logger.info("Logger inicializado para modo de desenvolvimento com hot reload.")
except Exception as e:
    logging.basicConfig(level=logging.INFO) # Fallback básico
    logging.error(f"Falha ao inicializar LoggerSetup em run_dev: {e}")
    logger = logging.getLogger("run_dev_fallback")

# Chave Secreta Flet (lógica adaptada do seu run.py ou da discussão anterior)
import secrets
import keyring

KEYRING_FLET_SECRET_SERVICE = f"{APP_NAME}_FletConfig_Dev" # Nome diferente para dev, se quiser
KEYRING_FLET_SECRET_USER = "FLET_SECRET_KEY_Dev"

flet_secret = os.getenv("FLET_SECRET_KEY_DEV") # Variável de ambiente específica para dev
if not flet_secret:
    try:
        flet_secret = keyring.get_password(KEYRING_FLET_SECRET_SERVICE, KEYRING_FLET_SECRET_USER)
    except Exception: flet_secret = None

    if not flet_secret:
        logger.warning("FLET_SECRET_KEY_DEV não definida. Gerando e salvando no Keyring para dev.")
        flet_secret = secrets.token_hex(32)
        try:
            keyring.set_password(KEYRING_FLET_SECRET_SERVICE, KEYRING_FLET_SECRET_USER, flet_secret)
        except Exception as e_ks:
            logger.error(f"Não foi possível salvar FLET_SECRET_KEY_DEV no Keyring: {e_ks}")
    else:
        logger.info("FLET_SECRET_KEY_DEV carregada do Keyring.")
else:
    logger.info("FLET_SECRET_KEY_DEV carregada da variável de ambiente.")

os.environ["FLET_SECRET_KEY"] = flet_secret

# --- Configuração da Aplicação FastAPI e Flet ---
fast_api_app = FastAPI()

# O page_factory é a sua função `main` de `src.flet_ui.app`
# Ela já faz toda a configuração da página, incluindo layout e roteador.
flet_asgi_app = flet.fastapi.app(
    create_flet_page_layout,
    assets_dir=ASSETS_DIR_ABS,
    upload_dir=UPLOAD_TEMP_DIR
)

fast_api_app.mount("/", flet_asgi_app)

# Variável que Uvicorn usará
app_to_run_dev_mode = fast_api_app

APP_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    host = "127.0.0.1"
    port = 8550 # Pode ser a mesma porta do seu run.py se você só executar um por vez
    
    # Diretórios a serem monitorados pelo Uvicorn para o reload
    # Inclua todos os diretórios relevantes do seu código fonte.
    reload_dirs_watch = [
        os.path.join(APP_ROOT_DIR, "src"), # Monitora toda a pasta src
        APP_ROOT_DIR # Monitora a raiz para run_dev.py, settings.py se estiver lá
    ]
    # Filtra para garantir que os diretórios existem
    reload_dirs_exist = [d for d in reload_dirs_watch if os.path.isdir(d)]
    if not reload_dirs_exist:
        logger.error("Nenhum diretório válido encontrado para monitoramento pelo Uvicorn. Hot reload pode não funcionar.")
        # Fallback para o diretório atual se nenhum for válido
        reload_dirs_exist = ["."]

    logger.info(f"Iniciando servidor de DESENVOLVIMENTO Flet com Uvicorn em http://{host}:{port}")
    logger.info(f"Uvicorn irá monitorar para reload: {reload_dirs_exist}")
    logger.info("Modifique arquivos Python nos diretórios monitorados e salve para testar o hot reload.")
    logger.info("Use o comando: uvicorn run_dev:app_to_run_dev_mode --reload --port 8550 --reload-dir ./src --reload-dir .")
    logger.info("Ou execute este script diretamente: python run_dev.py (Uvicorn será iniciado programaticamente)")

    uvicorn.run(
        "run_dev:app_to_run_dev_mode", # String de importação: modulo_sem_py:nome_da_app_fastapi
        host=host,
        port=port,
        reload=True,
        reload_dirs=reload_dirs_exist # Passa os diretórios que existem
    )


# python run_dev.py  ou
# uvicorn run_dev:app_to_run_dev_mode --reload --port 8550 --reload-dir ./src --reload-dir .

'''
Não funcionou como esperado =( pois tenta atualizar o token de usuário a cada alteração, forçando ter que refazer login
'''
