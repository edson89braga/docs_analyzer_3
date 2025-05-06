# src/flet_ui/app.py
import flet as ft
from typing import Dict, Any

from ..settings import APP_TITLE

from .layout import create_app_bar, create_navigation_rail
#from .components import ...
from .router import route_change 

from . import theme
error_color = theme.COLOR_ERROR if hasattr(theme, 'COLOR_ERROR') else ft.colors.RED

# Importa o logger
from src.logger.logger import LoggerSetup
logger = LoggerSetup.get_logger(__name__)


def main(page: ft.Page):
    """
    Função principal da aplicação Flet.
    Configura a página, inicializa DB/Serviços, define layout persistente e conecta o router.
    """
    page.title = APP_TITLE
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.horizontal_alignment = ft.CrossAxisAlignment.START

    # --- Aplicar Temas ---
    page.theme = theme.APP_THEME
    page.dark_theme = theme.APP_DARK_THEME
    page.theme_mode = ft.ThemeMode.SYSTEM # Define como o tema inicial será escolhido (SYSTEM usa a preferência do OS)
    
    # page.data pode ser usado, mas page.client_data é mais adequado para dados da sessão
    # page.client_data = {}
            
    # --- Definição dos Elementos Persistentes do Layout ---
    app_bar = create_app_bar(page)
    
    # Cria a NavigationRail (será passada para o router para atualização)
    navigation_rail = create_navigation_rail(page, page.route or "/") # Usa "/" se page.route for None inicial
    
    # Container para o conteúdo dinâmico que será atualizado pelo router
    content_container = ft.Container(
        content=ft.ProgressRing(), # Mostra um loading inicial
        expand=True,
        padding=theme.PADDING_L # Padding geral para a área de conteúdo
    )

    # --- Conectar o Roteador ---
    # Passa o content_container e navigation_rail para a função route_change
    page.on_route_change = lambda route_event: route_change(page, content_container, navigation_rail, route_event.route)
    # page.on_view_pop não é mais necessário com esta abordagem, pois não usamos a pilha de Views

    # --- Estrutura Principal da Página ---
    page.clean() # Limpa a página
    page.appbar = app_bar # AppBar global
    page.add(
        ft.Row(
            [
                navigation_rail, # Navegação persistente
                ft.VerticalDivider(width=1),
                content_container # Container para o conteúdo dinâmico
            ],
            expand=True,
        )
    )

    # --- Limpeza ao Fechar (Opcional mas recomendado) ---
    def on_disconnect(e):
        logger.info("Cliente desconectado ou aplicação Flet fechando...")
        if page.data and page.data.get("db_session"):
            logger.info("Fechando sessão SQLAlchemy...")
            try:
                page.data["db_session"].close()
                logger.info("Sessão SQLAlchemy fechada.")
            except Exception as close_err:
                logger.error(f"Erro ao fechar a sessão SQLAlchemy: {close_err}")

    page.on_disconnect = on_disconnect

    # --- Navegar para a Rota Inicial ---
    # Força a atualização inicial da rota "/" ou a rota atual se já houver uma
    initial_route = page.route if page.route and page.route != "" and page.route != "/" else "/dashboard"
    logger.info(f"Navegando para a rota inicial: {initial_route}")
    page.go(initial_route)
    # O on_route_change será chamado e preencherá o content_container

