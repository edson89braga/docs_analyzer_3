# src/flet_ui/views/knowledge_base_view.py (NOVO ARQUIVO)
import flet as ft
from src.flet_ui.components import show_snackbar
from src.flet_ui import theme # Para COLOR_WARNING
from src.logger.logger import LoggerSetup

_logger = LoggerSetup.get_logger(__name__)

def create_knowledge_base_content(page: ft.Page) -> ft.Control:
    _logger.info("Acessando conteúdo placeholder para Banco de Pareceres.")

    # Exibe o snackbar imediatamente ao carregar o conteúdo desta "view"
    # O show_snackbar já chama page.update()
    show_snackbar(
        page,
        "Banco de Pareceres: Seção ainda não programada.",
        color=theme.COLOR_WARNING, # Ou uma cor neutra/informativa
        duration=5000
    )

    # Conteúdo principal (placeholder)
    main_content = ft.Column(
        [
            ft.Icon(ft.icons.CONSTRUCTION, size=80, opacity=0.3),
            ft.Text(
                "Chat com Banco de Pareceres",
                style=ft.TextThemeStyle.HEADLINE_MEDIUM,
                text_align=ft.TextAlign.CENTER,
                opacity=0.7
            ),
            ft.Text(
                "Esta funcionalidade estará disponível em versões futuras.",
                style=ft.TextThemeStyle.BODY_LARGE,
                text_align=ft.TextAlign.CENTER,
                opacity=0.7
            ),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True,
        spacing=20
    )
    return main_content