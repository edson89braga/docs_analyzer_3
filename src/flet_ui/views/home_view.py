# src/flet_ui/views/home_view.py

import flet as ft
from src.settings import PATH_IMAGE_LOGO_DEPARTAMENTO, APP_TITLE, APP_VERSION
from src.flet_ui import theme 
from typing import Optional

import logging
logger = logging.getLogger(__name__)


def create_home_view(page: ft.Page) -> ft.Control:
    """
    Cria e retorna a primeira versão da view Home, exibindo informações básicas
    e o logo do departamento.

    Args:
        page (ft.Page): A página Flet atual.

    Returns:
        ft.Control: O conteúdo principal da view Home.
    """
    logger.info("Criando o conteúdo da view Home.")

    try:
        department_logo = ft.Image(
            src=PATH_IMAGE_LOGO_DEPARTAMENTO,
            width=200, # Reduzido para dar espaço ao texto
            height=200,
            fit=ft.ImageFit.CONTAIN,
            error_content=ft.Text("Erro ao carregar imagem do logo.", color=ft.colors.RED)
        )
    except Exception as e:
        logger.error(f"Erro ao tentar carregar a imagem do logo '{PATH_IMAGE_LOGO_DEPARTAMENTO}': {e}")
        department_logo = ft.Container(
            content=ft.Text(f"Não foi possível carregar a imagem do logo.",
                            color=ft.colors.ORANGE_ACCENT_700, style=ft.TextThemeStyle.BODY_LARGE),
            padding=20,
            alignment=ft.alignment.center
        )

    welcome_title = ft.Text(
        f"Bem-vindo à {APP_TITLE}",
        style=ft.TextThemeStyle.HEADLINE_LARGE, # Destaque maior
        text_align=ft.TextAlign.CENTER,
        weight=ft.FontWeight.BOLD,
        color=theme.PRIMARY # Usando a cor primária do tema
    )

    intro_text_1 = ft.Text(
        "Ferramenta inteligente para análise de documentos e otimização de rotinas da Polícia Federal.",
        style=ft.TextThemeStyle.TITLE_MEDIUM, # Tamanho adequado para subtítulo
        text_align=ft.TextAlign.CENTER,
        color=ft.colors.with_opacity(0.85, ft.colors.ON_SURFACE) # Cor suave
    )

    intro_text_2 = ft.Text(
        "Utilize o menu de navegação para acessar as funcionalidades disponíveis, como a Análise Inicial de Notícias-crime,\n"
        "Chats com PDFs ou Banco de Dados, e outros Agentes de IA especializados.",
        style=ft.TextThemeStyle.BODY_LARGE,
        text_align=ft.TextAlign.CENTER,
        width=1000, # Limita a largura para melhor legibilidade
        color=ft.colors.with_opacity(0.75, ft.colors.ON_SURFACE)
    )
    
    version_text = ft.Text(
        f"Versão: {APP_VERSION}",
        style=ft.TextThemeStyle.BODY_MEDIUM,
        text_align=ft.TextAlign.CENTER,
        italic=True,
        color=ft.colors.with_opacity(0.6, ft.colors.ON_SURFACE)
    )

    main_content = ft.Column(
        [
            ft.Container(height=15),
            department_logo,
            ft.Container(height=20), # Espaçador
            welcome_title,
            ft.Container(height=10),
            intro_text_1,
            ft.Container(height=15),
            intro_text_2,
            ft.Container(height=30), # Maior espaçador antes da versão
            version_text,
        ],
        alignment=ft.MainAxisAlignment.START,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True, 
        spacing=5 # Espaçamento geral entre os elementos da coluna
    )

    return main_content


def create_feature_card(page: ft.Page, title: str, description: str, icon: str, route: Optional[str] = None) -> ft.Container:
    """
    Cria um card clicável para destacar uma funcionalidade ou seção do aplicativo.

    Args:
        page (ft.Page): A página Flet atual, usada para navegação.
        title (str): O título do card.
        description (str): Uma breve descrição da funcionalidade.
        icon (str): O nome do ícone Flet a ser exibido no card.
        route (Optional[str]): A rota para a qual o aplicativo navegará ao clicar no card.
                                Se None, o card não será clicável.

    Returns:
        ft.Container: Um container Flet que encapsula o card, tornando-o clicável.
    """
    
    card_content_column = ft.Column( # Renomeado para clareza
        [
            ft.Icon(name=icon, size=36, color=theme.PRIMARY),
            ft.Container(height=8),
            ft.Text(title, weight=ft.FontWeight.BOLD, size=16, text_align=ft.TextAlign.CENTER),
            ft.Text(description, size=13, text_align=ft.TextAlign.CENTER, color=ft.colors.with_opacity(0.8, ft.colors.ON_SURFACE)),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=5,
    )

    actual_card = ft.Card( # O Card em si
        content=ft.Container(
            card_content_column,
            padding=15,
            width=300, 
            height=180,
        ),
        elevation=2,
    )

    # Envolve o Card em um Container para torná-lo clicável
    clickable_container = ft.Container(
        content=actual_card,
        on_click=lambda _: page.go(route) if route else None,
        ink=bool(route), # Efeito visual de clique se houver rota
        shape=ft.RoundedRectangleBorder(radius=10)
    )
    
    return clickable_container


def create_home_view2(page: ft.Page) -> ft.Control:
    """
    Cria e retorna a segunda versão da view Home, apresentando cards de funcionalidades
    e informações sobre o uso responsável da IA.

    Args:
        page (ft.Page): A página Flet atual.

    Returns:
        ft.Control: O conteúdo principal da view Home com cards.
    """
    logger.info("Criando o conteúdo da view Home (com cards).")

    try:
        department_logo = ft.Image(
            src=PATH_IMAGE_LOGO_DEPARTAMENTO,
            width=200,
            height=200,
            fit=ft.ImageFit.CONTAIN,
            error_content=ft.Text("Erro ao carregar imagem do logo.", color=ft.colors.RED)
        )
    except Exception as e:
        logger.error(f"Erro ao tentar carregar a imagem do logo '{PATH_IMAGE_LOGO_DEPARTAMENTO}': {e}")
        department_logo = ft.Container(
            content=ft.Text(f"Não foi possível carregar o logo.",
                            color=ft.colors.ORANGE_ACCENT_700, style=ft.TextThemeStyle.BODY_LARGE),
            padding=20, alignment=ft.alignment.center
        )

    welcome_title = ft.Text(
        f"Bem-vindo à {APP_TITLE}",
        style=ft.TextThemeStyle.HEADLINE_LARGE,
        text_align=ft.TextAlign.CENTER,
        weight=ft.FontWeight.BOLD,
        color=theme.PRIMARY
    )

    intro_text = ft.Text(
        "Plataforma de Agentes de IA especializados e Chats inteligentes\n"
        "para análise de documentos e procedimentos da Polícia Federal.\n"
        "\n"
        "Explore os módulos abaixo:",
        style=ft.TextThemeStyle.TITLE_MEDIUM,
        text_align=ft.TextAlign.CENTER,
        width=1000, # Limita a largura
        color=ft.colors.with_opacity(0.85, ft.colors.ON_SURFACE)
    )

    # Cards de Funcionalidades
    card1 = create_feature_card(
        page,
        "Análise Inicial",
        "Extração de Dados e Produção de resumos de fatos em Notícias-Crime.",
        ft.Icons.FIND_IN_PAGE_OUTLINED,
        "/analyze_pdf"
    )
    card2 = create_feature_card(
        page,
        "Chat com PDF",
        "Chat inteligente com documentos para obtenção de respostas contextuais.",
        ft.Icons.QUESTION_ANSWER_OUTLINED,
        "/chat_pdf"
    )
    card3 = create_feature_card(
        page,
        "Banco de Pareceres",
        "Consulta de pareceres e documentos técnicos relevantes.",
        ft.Icons.LIBRARY_BOOKS_OUTLINED,
        "/knowledge_base"
    )

    feature_cards_row = ft.Row(
        [card1, card2, card3],
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=20,
        wrap=True, # Permite que os cards quebrem linha em telas menores
    )
    
    version_text = ft.Text(
        f"Versão: {APP_VERSION}",
        style=ft.TextThemeStyle.BODY_MEDIUM,
        text_align=ft.TextAlign.CENTER,
        italic=True,
        color=ft.colors.with_opacity(0.6, ft.colors.ON_SURFACE)
    )

    main_content_column = ft.Column(
        [
            department_logo,
            ft.Container(height=15),
            welcome_title,
            ft.Container(height=8),
            intro_text,
            ft.Container(height=18),
            feature_cards_row,
            ft.Container(height=25),
            ft.Container(
                content=ft.Text(
                    "Uso Responsável da IA: Este sistema utiliza Inteligência Artificial como ferramenta de auxílio.\n"
                    "As informações geradas são preliminares e devem ser verificadas por um analista humano.\n"
                    "A responsabilidade final pela correção e uso dos dados é inteiramente do usuário.",
                    size=13,
                    italic=True,
                    text_align=ft.TextAlign.CENTER,
                    color=ft.colors.with_opacity(0.9, ft.colors.ON_SURFACE)
                ),
                width=800, # Limita a largura do aviso
                # padding=ft.padding.only(bottom=20)
                padding=20, border_radius=8,
                # bgcolor=ft.Colors.with_opacity(0.05, theme.COLOR_INFO),
            ),
            ft.Container(height=20, expand=True), # Espaçador flexível para empurrar a versão para baixo
            version_text,
            #ft.Container(height=20, expand=True)
        ],
        alignment=ft.MainAxisAlignment.CENTER, # Tenta centralizar, mas o expand do Container acima ajuda
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True, spacing=5,
        scroll=ft.ScrollMode.ADAPTIVE
    )

    # Container principal para permitir scroll se o conteúdo for muito grande
    # e aplicar padding geral.
    return ft.Container(
        content=main_content_column,
        padding=ft.padding.all(20),
        expand=True,
        alignment=ft.alignment.center # Garante que a coluna esteja centralizada no container
    )

