# run_chat_test.py
import flet as ft
import sys
import os

# Adiciona o diretório raiz ao path para encontrar o pacote 'src'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from src.flet_ui.views.chat_view import create_chat_view_content
from src.flet_ui import theme

def main(page: ft.Page):
    """
    Função principal para executar a view de chat de forma isolada para testes.
    """
    page.title = "Teste - Chat com Documentos"
    page.theme = theme.APP_THEME
    page.dark_theme = theme.APP_DARK_THEME
    page.theme_mode = ft.ThemeMode.LIGHT

    # Cria e adiciona o conteúdo da view de chat à página
    chat_view = create_chat_view_content(page)
    page.add(chat_view)

if __name__ == "__main__":
    ft.app(
        target=main,
        view=ft.AppView.WEB_BROWSER
    )
    