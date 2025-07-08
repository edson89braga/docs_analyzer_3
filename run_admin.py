# run_admin.py
import logging
logger = logging.getLogger(__name__)

from time import perf_counter
start_time = perf_counter()
logger.info(f"{start_time:.4f}s - Iniciando run_admin.py")

DEBUG_LEVEL = False
from src.logger.logger import LoggerSetup
try:
    LoggerSetup.initialize(
        routine_name="Admin_IAnalista",
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

import flet as ft
import sys, os

# Adiciona o diretório raiz ao path para que Flet encontre o entry point
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.settings import UPLOAD_TEMP_DIR, ASSETS_DIR 
from admin_py.app_admin import main as admin_main

execution_time = perf_counter() - start_time
logger.info(f"[DEBUG] Carregado RUN_ADMIN em {execution_time:.4f}s")

if __name__ == "__main__":
    ft.app(
        target=admin_main,
        port=8551,  # Porta diferente da aplicação principal
        view=ft.AppView.WEB_BROWSER,
        assets_dir=ASSETS_DIR,  # Compartilha os mesmos assets se necessário
    )