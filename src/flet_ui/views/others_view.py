# src/flet_ui/views/knowledge_base_view.py (NOVO ARQUIVO)
import flet as ft
from src.flet_ui.components import show_snackbar
from src.flet_ui import theme # Para COLOR_WARNING

from src.flet_ui.theme import COLOR_WARNING

from src.settings import KEY_SESSION_CURRENT_BATCH_NAME

import logging
logger = logging.getLogger(__name__)


def create_chat_pdf_content(page: ft.Page) -> ft.Control:
    """
    Cria e retorna o conteúdo placeholder para a view "Chat com PDF".
    Esta funcionalidade ainda não está implementada.

    Args:
        page (ft.Page): A página Flet atual.

    Returns:
        ft.Control: O conteúdo placeholder da view.
    """
    logger.info("Criando conteúdo da view Chat com PDF.")

    current_pdf_name = page.session.get(KEY_SESSION_CURRENT_BATCH_NAME)
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

def OLD_create_knowledge_base_content(page: ft.Page) -> ft.Control:
    """
    Cria e retorna o conteúdo placeholder para a view "Banco de Pareceres".
    Esta função é uma versão antiga e será substituída por create_placeholder_content.

    Args:
        page (ft.Page): A página Flet atual.

    Returns:
        ft.Control: O conteúdo placeholder da view.
    """
    logger.info("Acessando conteúdo placeholder para Banco de Pareceres.")

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

def create_placeholder_content(page: ft.Page, module_name: str) -> ft.Control:
    """
    Cria e retorna um conteúdo placeholder genérico para módulos ainda não implementados.

    Args:
        page (ft.Page): A página Flet atual.
        module_name (str): O nome do módulo para o qual o placeholder está sendo criado.

    Returns:
        ft.Control: O conteúdo placeholder genérico.
    """
    logger.info(f"Acessando conteúdo placeholder para: {module_name}")
    show_snackbar(
        page,
        f"{module_name}: Módulo ainda não programado.",
        color=COLOR_WARNING,
        duration=3000
    )
    return ft.Column( # Retorna um Column para consistência com outras content_creators
        [
            ft.Text(f"{module_name}", style=ft.TextThemeStyle.HEADLINE_MEDIUM),
            ft.Text("Esta funcionalidade será implementada em versões futuras."),
            ft.Icon(ft.icons.CONSTRUCTION, size=50, opacity=0.5)
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True,
        spacing=20
    )

def create_knowledge_base_content(page: ft.Page) -> ft.Control:
    """
    Cria e retorna o conteúdo para a view "Banco de Pareceres", utilizando o placeholder genérico.

    Args:
        page (ft.Page): A página Flet atual.

    Returns:
        ft.Control: O conteúdo da view "Banco de Pareceres".
    """
    return create_placeholder_content(page, "Banco de Pareceres")

def create_wiki_rotinas_content(page: ft.Page) -> ft.Control:
    """
    Cria e retorna o conteúdo para a view "Wiki PF - Rotinas", utilizando o placeholder genérico.

    Args:
        page (ft.Page): A página Flet atual.

    Returns:
        ft.Control: O conteúdo da view "Wiki PF - Rotinas".
    """
    return create_placeholder_content(page, "Wiki PF - Rotinas")

def create_correicao_processos_content(page: ft.Page) -> ft.Control:
    """
    Cria e retorna o conteúdo para a view "Correição de Flagrantes e IPLs", utilizando o placeholder genérico.

    Args:
        page (ft.Page): A página Flet atual.

    Returns:
        ft.Control: O conteúdo da view "Correição de Flagrantes e IPLs".
    """
    return create_placeholder_content(page, "Correição de Flagrantes e IPLs")

def create_roteiro_investigacoes_content(page: ft.Page) -> ft.Control:
    """
    Cria e retorna o conteúdo para a view "Roteiros de Investigações", utilizando o placeholder genérico.

    Args:
        page (ft.Page): A página Flet atual.

    Returns:
        ft.Control: O conteúdo da view "Roteiros de Investigações".
    """
    return create_placeholder_content(page, "Roteiros de Investigações")