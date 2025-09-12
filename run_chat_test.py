# run_chat_test.py
import flet as ft
import sys, os, threading
from time import perf_counter

# Adiciona o diretório raiz ao path para encontrar o pacote 'src'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from src.flet_ui.views.chat_view import create_chat_view_content
from src.flet_ui import theme
from src.settings import UPLOAD_TEMP_DIR, ASSETS_DIR
from src import app_cache
from src.logger.logger import LoggerSetup

# --- Instrução Importante para Teste ---
# Para que o RAGOrchestrator funcione, defina sua chave da OpenAI como uma variável de ambiente.
# Exemplo (PowerShell): $env:OPENAI_API_KEY="..."
# Exemplo (CMD): set OPENAI_API_KEY="..."
# Exemplo (Bash/zsh): export OPENAI_API_KEY="..."

# Inicializa o logger para termos visibilidade completa dos erros
LoggerSetup.initialize(routine_name="ChatTestRun", dev_mode=True)
logger = LoggerSetup.get_logger(__name__)

# --- Pré-carregamento do Modelo SentenceTransformer (similar ao run.py) ---
def load_heavy_models_in_background():
    start_time_load = perf_counter()
    logger.info("Iniciando pré-carregamento do modelo SentenceTransformer em background...")

    from sentence_transformers import SentenceTransformer
    
    try:
        model_name = 'all-MiniLM-L6-v2'
        model_local_path = os.path.join(ASSETS_DIR, 'models', model_name)
        logger.info(f"Carregando modelo de: {model_local_path}")
        app_cache.sentence_transformer_model = SentenceTransformer(model_local_path)
        logger.info("Modelo SentenceTransformer pré-carregado e disponível globalmente.")
    except Exception as e:
        logger.critical(f"FALHA CRÍTICA ao pré-carregar o modelo SentenceTransformer: {e}", exc_info=True)
    finally:
        # CRUCIAL: Sinaliza que o processo de carregamento (com sucesso ou falha) terminou.
        app_cache.model_loading_event.set()

    execution_time_load = perf_counter() - start_time_load
    logger.info(f"Pré-carregamento do modelo concluído em {execution_time_load:.4f}s")

threading.Thread(target=load_heavy_models_in_background, daemon=True).start()

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
    