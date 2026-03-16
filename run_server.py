# run_server.py
import logging
import os
import threading
from time import perf_counter

start_time = perf_counter()

# Força o modo servidor caso não esteja setado no ambiente
os.environ["APP_MODE"] = "server"

from SOURCE.logger.logger import LoggerSetup
from SOURCE.settings import ASSETS_DIR, UPLOAD_TEMP_DIR

# 1. Configuração de Logging para Servidor
try:
    LoggerSetup.initialize(
        routine_name="DocsAnalyzer3_Server",
        dev_mode=False
    )
    logger = LoggerSetup.get_logger(__name__)
    logger.info("Logger inicializado no modo Servidor.")
except Exception as e:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.error(f"Falha ao inicializar o logger principal: {e}")
    logger = logging.getLogger(__name__)

# 2. Garantia de Chave Secreta
# No servidor, é mandatório que a chave venha do ambiente (ex: Docker ENV)
flet_secret_key = os.getenv('FLET_SECRET_KEY')
if not flet_secret_key:
    logger.warning("FLET_SECRET_KEY não encontrada no ambiente! Usando chave temporária (não recomendado para produção).")
    import secrets, base64
    flet_secret_key = base64.b64encode(secrets.token_bytes(32)).decode('utf-8')
    os.environ['FLET_SECRET_KEY'] = flet_secret_key

# 3. Pré-carregamento Assíncrono (Opcional, para aquecer o servidor)
def preload_heavy_modules():
    logger.info("Carregando módulos pesados sincronamente para o servidor (Warm-up)...")
    try:
        import SOURCE.utils
        from SOURCE.core import prompts, pdf_processor, ai_orchestrator, doc_generator, chat_llm_orchestrator
        from SOURCE.flet_ui.views import nc_analyze_view, chat_view
        from SOURCE import app_cache
        app_cache.heavy_imports_loading_event.set()
        logger.info("Módulos pré-carregados com sucesso.")
    except Exception as e:
        logger.error(f"Erro no pré-carregamento: {e}")

preload_heavy_modules()

# 4. Inicialização do Flet
import flet as ft
from SOURCE.flet_ui.app import main

def server_main(page: ft.Page):
    """
    Wrapper simplificado para o servidor. 
    Apenas repassa para a lógica principal do app Flet,
    sem travas de singleton ou atualizadores locais.
    """
    logger.info(f"Nova sessão web iniciada: {page.session_id}")
    
    # Repassa para o main real do app
    main(page)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8550))
    logger.info(f"Iniciando servidor Flet na porta {port}...")
    
    execution_time = perf_counter() - start_time
    logger.info(f"Setup do servidor concluído em {execution_time:.4f}s")

    # Garante o diretório de uploads e define permissões 777 (necessário para Flet Web)
    if not os.path.exists(UPLOAD_TEMP_DIR):
        os.makedirs(UPLOAD_TEMP_DIR, exist_ok=True)
    try:
        os.chmod(UPLOAD_TEMP_DIR, 0o777)
    except Exception as e:
        logger.warning(f"Não foi possível aplicar chmod 777 na pasta de upload: {e}")
    
    ft.app(
        target=server_main,
        view=ft.AppView.WEB_BROWSER,
        port=port,
        host="0.0.0.0", # Permite acesso externo ao container
        assets_dir=ASSETS_DIR, 
        upload_dir=UPLOAD_TEMP_DIR
        #, web_renderer=ft.WebRenderer.HTML
    )