# src/flet_ui/app.py
import flet as ft
from typing import Dict, Any

from ..settings import APP_TITLE, APP_VERSION

#from .layout import create_app_bar, create_navigation_rail
#from .components import ...
from .router import app_router 

from . import theme
error_color = theme.COLOR_ERROR if hasattr(theme, 'COLOR_ERROR') else ft.colors.RED

# Importa o logger
from src.logger.logger import LoggerSetup
logger = LoggerSetup.get_logger(__name__)


# Função para carregar o estado de autenticação (exemplo)
def load_auth_state_from_storage(page: ft.Page):
    """
    Carrega o estado de autenticação do client_storage (se "Lembrar de mim" foi usado)
    para a sessão Flet da página atual.
    """
    if page.client_storage and page.client_storage.contains_key("auth_id_token"):
        logger.info("Restaurando estado de autenticação do client_storage para a sessão Flet.")
        # Pega todos os valores do client_storage e define na sessão
        id_token = page.client_storage.get("auth_id_token")
        user_id = page.client_storage.get("auth_user_id")
        user_email = page.client_storage.get("auth_user_email")
        display_name = page.client_storage.get("auth_display_name")

        if id_token and user_id: # Garante que os dados essenciais existem
            page.session.set("auth_id_token", id_token)
            page.session.set("auth_user_id", user_id)
            if user_email: # Email e display name são opcionais no client_storage
                 page.session.set("auth_user_email", user_email)
            if display_name:
                 page.session.set("auth_display_name", display_name)
            
            LoggerSetup.set_cloud_user_context(id_token, user_id)
            logger.info(f"Contexto do logger de nuvem restaurado para usuário {user_id} do client_storage.")
        else:
            logger.warning("Dados de autenticação no client_storage estavam incompletos. Não restaurados para a sessão.")
            # Opcional: Limpar chaves incompletas do client_storage aqui
            page.client_storage.remove("auth_id_token") # etc.
    else:
        logger.info("Nenhum estado de autenticação persistente encontrado no client_storage.")


def main(page: ft.Page):
    logger.info(f"Aplicação Flet '{APP_TITLE}' v{APP_VERSION} iniciando...")
    page.title = APP_TITLE
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.horizontal_alignment = ft.CrossAxisAlignment.START

    # --- Aplicar Temas ---
    page.theme = theme.APP_THEME
    page.dark_theme = theme.APP_DARK_THEME
    page.theme_mode = ft.ThemeMode.SYSTEM
    
    # Tenta carregar o estado de autenticação persistido
    load_auth_state_from_storage(page)

    # --- Conectar o Roteador ---
    page.on_route_change = lambda route_event: app_router(page, route_event.route)
    
    # --- Limpeza ao Fechar ---
    def on_disconnect(e):
        logger.info("Cliente desconectado ou aplicação Flet fechando...")
        # Limpar contexto do logger de nuvem ao desconectar
        LoggerSetup.set_cloud_user_context(None, None)
        logger.info("Contexto do logger de nuvem limpo ao desconectar.")
        # ... (outras limpezas como fechar sessão DB, se houver) ...

    page.on_disconnect = on_disconnect
    
    # --- Navegar para a Rota Inicial ---
    # O router agora lida com o redirecionamento para /login se não autenticado.
    # Se a rota for / ou vazia, o router pode decidir para onde ir (ex: /home se logado, /login se não).
    initial_route = page.route
    if not initial_route or initial_route == "/":
        # O app_router decidirá se vai para /login ou /home baseado na autenticação
        initial_route = "/home" # Ou deixe o router decidir implicitamente indo para "/"
                                 # e sendo redirecionado.
                                 # Mas page.go("/") pode ser mais explícito.

    logger.info(f"Disparando navegação inicial para: {initial_route}")
    page.go(initial_route) # Dispara o on_route_change


def Other_main(page: ft.Page):
    """
    Função principal da aplicação Flet.
    Configura a página, inicializa DB/Serviços, define layout persistente e conecta o router.
    """
    create_app_bar, route_change = [None]*2

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
    app_bar = create_app_bar(page, APP_TITLE)
    
    # --- Conectar o Roteador ---
    # Passa o content_container e navigation_rail para a função route_change
    page.on_route_change = lambda route_event: route_change(page, route_event.route)
    # page.on_view_pop não é mais necessário com esta abordagem, pois não usamos a pilha de Views

    # --- Estrutura Principal da Página ---
    page.clean() # Limpa a página
    page.appbar = app_bar # AppBar global

    ...

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
    initial_route = page.route if page.route and page.route != "" and page.route != "/" else "/login"
    logger.info(f"Navegando para a rota inicial: {initial_route}")
    page.go(initial_route)


