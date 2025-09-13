# run_chat_test.py
import flet as ft
import sys, os


# Adiciona o diretório raiz ao path para encontrar o pacote 'src' ...
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from src.flet_ui.views.chat_view import create_chat_view_content
from src.flet_ui import theme
from src.settings import UPLOAD_TEMP_DIR, ASSETS_DIR

import logging
logger = logging.getLogger(__name__)

try:
    from src.logger.logger import LoggerSetup
    LoggerSetup.initialize(
        routine_name="DocsAnalyzer3",
        dev_mode = True, 
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

def main(page: ft.Page):
    """
    Função principal para executar a view de chat de forma isolada para testes.
    """
    page.title = "Teste - Chat com Documentos"
    page.theme = theme.APP_THEME
    page.dark_theme = theme.APP_DARK_THEME
    page.theme_mode = ft.ThemeMode.LIGHT

    # --- Inicialização de Componentes Globais (simula o app.py) ---
    # Essencial para que ManagedFilePicker e show_loading_overlay funcionem.
    if page.data is None:
        page.data = {}

    # FilePicker global
    global_file_picker = ft.FilePicker()
    page.overlay.append(global_file_picker)
    page.data["global_file_picker"] = global_file_picker

    # Loading Overlay global
    page_loading_text = ft.Text("", size=16, weight=ft.FontWeight.BOLD)
    page_loading_overlay = ft.Container(
        content=ft.Column([ft.ProgressRing(), ft.Container(height=10), page_loading_text]),
        alignment=ft.alignment.center, expand=True,
        bgcolor=ft.Colors.with_opacity(0.5, ft.Colors.BLACK), visible=False
    )
    page.overlay.append(page_loading_overlay)
    page.data["global_loading_overlay"] = page_loading_overlay
    page.data["global_loading_text"] = page_loading_text
    
    # SnackBar global
    page_snackbar = ft.SnackBar(content=ft.Text(""), show_close_icon=True)
    page.overlay.append(page_snackbar)
    page.data["global_snackbar"] = page_snackbar

    # Cria e adiciona o conteúdo da view de chat à página
    chat_view = create_chat_view_content(page)
    page.add(chat_view)

if __name__ == "__main__":
    os.environ['FLET_SECRET_KEY'] = 'secret_key_test_aleatoria_dadlksan@#$4fkjdk'
    ft.app(
        target=main,
        view=ft.AppView.WEB_BROWSER,
        assets_dir=ASSETS_DIR,
        upload_dir=UPLOAD_TEMP_DIR
    )
    os.environ['FLET_SECRET_KEY'] = ''  # Limpa a variável de ambiente após o uso
    