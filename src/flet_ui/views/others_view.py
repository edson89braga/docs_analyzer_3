# src/flet_ui/views/knowledge_base_view.py (NOVO ARQUIVO)
import flet as ft
from src.flet_ui.components import show_snackbar
from src.flet_ui import theme # Para COLOR_WARNING

from src.flet_ui.views.analyze_pdf_view1 import KEY_SESSION_CURRENT_PDF_NAME

from src.logger.logger import LoggerSetup
_logger = LoggerSetup.get_logger(__name__)


def create_chat_pdf_content(page: ft.Page) -> ft.Control:
    _logger.info("Criando conteúdo da view Chat com PDF.")

    current_pdf_name = page.session.get(KEY_SESSION_CURRENT_PDF_NAME)
    processed_text_for_chat = None

    show_snackbar(
        page,
        "Chat com PDFs: Seção ainda não programada.",
        color=theme.COLOR_WARNING, # Ou uma cor neutra/informativa
        duration=5000
    )

    main_content = ft.Column(
        [
            ft.Icon(ft.Icons.CONSTRUCTION, size=80, opacity=0.3),
            ft.Text(
                "Chat com PDFs",
                style=ft.TextThemeStyle.HEADLINE_MEDIUM,
                text_align=ft.TextAlign.CENTER,
                opacity=0.7
            ),
            ft.Text(
                "Esta funcionalidade estará disponível na próxima versão.",
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

    #aggregated_info = page.session.get(KEY_SESSION_PDF_AGGREGATED_TEXT_INFO)
    
    #if aggregated_info:
    #    # A ordem na tupla é (str_pages_considered, aggregated_text, tokens_antes, tokens_depois)
    #    processed_text_for_chat = aggregated_info[1] 

    #if not current_pdf_name or not processed_text_for_chat:
    #    info_text = ft.Text(
    #        "Nenhum PDF carregado para o chat. Por favor, vá para a seção 'Análise PDF', "
    #        "carregue e analise um documento primeiro.",
    #        style=ft.TextThemeStyle.TITLE_MEDIUM,
    #        text_align=ft.TextAlign.CENTER
    #    )
    #    go_to_analyze_button = ft.ElevatedButton(
    #        "Ir para Análise PDF",
    #        icon=ft.Icons.FIND_IN_PAGE,
    #        on_click=lambda _: page.go("/analyze_pdf")
    #    )
    #    return ft.Column(
    #        [info_text, ft.Container(height=20), go_to_analyze_button],
    #        alignment=ft.MainAxisAlignment.CENTER,
    #        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    #        expand=True,
    #        spacing=20
    #    )

    # --- Conteúdo da view Chat com PDF (se PDF estiver carregado) ---
    if current_pdf_name and processed_text_for_chat:
        title = ft.Row([ft.Text(f"Chat com: {current_pdf_name}", style=ft.TextThemeStyle.HEADLINE_SMALL)], alignment=ft.MainAxisAlignment.START)
        
        # Placeholder para a interface de chat (será implementada na Fase 2 - Objetivo 2.5)
        chat_placeholder = ft.Column(
            [
                ft.Icon(ft.Icons.CHAT_BUBBLE_OUTLINE, size=80, opacity=0.3),
                ft.Text(
                    "Funcionalidade de Chat com PDF",
                    style=ft.TextThemeStyle.HEADLINE_MEDIUM,
                    text_align=ft.TextAlign.CENTER,
                    opacity=0.7
                ),
                ft.Text(
                    "Esta seção será implementada na Fase 2 (RAG e Interação com PDF).",
                    style=ft.TextThemeStyle.BODY_LARGE,
                    text_align=ft.TextAlign.CENTER,
                    opacity=0.7
                ),
                ft.Text(
                    f"O texto processado do PDF '{current_pdf_name}' estará disponível para esta funcionalidade.",
                    italic=True,
                    opacity=0.5,
                    text_align=ft.TextAlign.CENTER
                ),
                ft.ProgressRing(width=30, height=30, opacity=0.5) # Simula trabalho futuro
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True,
            spacing=20
        )

        return ft.Column(
            [
                title,
                ft.Divider(),
                chat_placeholder
            ],
            alignment=ft.MainAxisAlignment.START,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True, #spacing=15,
        )
    
    return main_content


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