# src/flet_ui/router.py
import flet as ft
import re
from typing import Optional, Dict, Callable, Any
from pathlib import Path

from src.settings import UPLOAD_TEMP_DIR 

from .theme import COLOR_WARNING, COLOR_ERROR, PADDING_L 
from .layout import create_app_bar, _find_nav_index_for_route, icones_navegacao
from .components import show_snackbar

from .views.login_view import create_login_view
from .views.signup_view import create_signup_view 
from .views.home_view import create_home_view 
from .views.profile_view import create_profile_view
from .views.proxy_settings_view import create_proxy_settings_content
from .views.llm_settings_view import create_llm_settings_view
from .views.analyze_pdf_view1 import create_analyze_pdf_content
from .views.others_view import create_chat_pdf_content

from src.logger.logger import LoggerSetup
logger = LoggerSetup.get_logger(__name__)


def create_placeholder_content(page: ft.Page, module_name: str) -> ft.Control:
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
    return create_placeholder_content(page, "Banco de Pareceres")

def create_wiki_rotinas_content(page: ft.Page) -> ft.Control:
    return create_placeholder_content(page, "Wiki PF - Rotinas")

def create_correicao_processos_content(page: ft.Page) -> ft.Control:
    return create_placeholder_content(page, "Correição de Flagrantes e IPLs")

def create_roteiro_investigacoes_content(page: ft.Page) -> ft.Control:
    return create_placeholder_content(page, "Roteiros de Investigações")

# Mapeamento de rotas para funções que criam o *conteúdo* (não a View inteira)
# route_content_mapping
_content_creators = {
    "/login": create_login_view,
    "/signup": create_signup_view, 
    "/home": create_home_view,
    "/profile": create_profile_view,
    "/settings/proxy": create_proxy_settings_content,
    "/settings/llm": create_llm_settings_view,
    "/analyze_pdf": create_analyze_pdf_content, 
    "/chat_pdf": create_chat_pdf_content, 
    "/knowledge_base": create_knowledge_base_content,    
    "/wiki_rotinas": create_wiki_rotinas_content,
    "/correicao_processos": create_correicao_processos_content,
    "/roteiro_investigacoes": create_roteiro_investigacoes_content,
}

# Mapeamento para rotas parametrizadas (se houver)
_parameterized_content_creators: Dict[str, Callable[[ft.Page, Any], Any]] = {
    # Ex: r"/products/(\d+)": create_product_detail_content,
}

# Rotas que são consideradas públicas (não exigem autenticação)
PUBLIC_ROUTES = ["/login", "/signup"]
# Rotas que não devem exibir a NavigationRail (ex: login, signup)
ROUTES_WITHOUT_NAV_RAIL = ["/login", "/signup"]

# Função auxiliar para verificar se o usuário está autenticado
def is_user_authenticated(page: ft.Page) -> bool:
    """Verifica se há um token de ID válido na sessão ou client_storage."""
    token = page.session.get("auth_id_token") or (page.client_storage.get("auth_id_token") if page.client_storage else None)
    return bool(token)

def app_router(page: ft.Page, route: str):
    """
    Gerencia a navegação e a exibição das views corretas.
    """
    logger.info(f"Router: Navegando para rota '{route}'")
    page.views.clear() # Limpa a pilha de views atual

    current_view_creator: Optional[callable] = None
    route_params = None

    # Tenta encontrar uma view estática
    if route in _content_creators:
        current_view_creator = _content_creators[route]
    # else: # Lógica para rotas parametrizadas de views, se houver
    #     for pattern, creator_func in _parameterized_view_creators.items():
    #         match = re.fullmatch(pattern, route)
    #         if match:
    #             current_view_creator = creator_func
    #             route_params = match.groups()
    #             break

    # --- Lógica de Autenticação e Redirecionamento ---
    authenticated = is_user_authenticated(page)

    public_routes = ["/login", "/signup"] 
    if not authenticated and route not in public_routes:
        logger.warning(f"Usuário não autenticado tentando acessar '{route}'. Redirecionando para /login.")
        page.go("/login") # Força o redirecionamento
        # A chamada page.go irá disparar o app_router novamente com a nova rota.
        # É importante que a view de login seja construída sem Appbar/Navrail.
        return # Interrompe o processamento da rota atual

    # Se autenticado e tentando acessar /login ou /signup, redireciona para /home
    if authenticated and route in public_routes:
        logger.info("Usuário já autenticado na página de login. Redirecionando para /home.")
        page.go("/home") # Ou sua página principal após login
        return


    # --- Construção da View ---
    if current_view_creator:
        try:
            if route_params:
                view_to_display = current_view_creator(page, *route_params)
            else:
                view_to_display = current_view_creator(page)
            
            # Para rotas que NÃO são de login/públicas, adicionamos o layout padrão
            if route not in public_routes:
                view_title = view_to_display.appbar.title.value if view_to_display.appbar and isinstance(view_to_display.appbar.title, ft.Text) else page.title or "App"
                app_bar = create_app_bar(page, str(view_title)) # Usar page.title se definido pela view
                # create_navigation_drawer com bug de conflito com toggle_theme
                view_to_display.appbar = app_bar

                # Navigation Rail (para telas maiores, geralmente dentro do conteúdo da view)
                # Se você quer um layout com Rail fixo + conteúdo, a estrutura da view precisa acomodar isso.
                # Exemplo: view_to_display.controls = [ft.Row([create_navigation_rail(page,route), ft.VerticalDivider(), main_content_of_view])]
                # Por agora, vamos assumir que a view principal já se estrutura com o Rail se necessário.
                
                # Footer (se aplicável a todas as views autenticadas)
                # view_to_display.bottom_appbar = create_footer(page)

            page.views.append(view_to_display)

        except Exception as e:
            logger.error(f"Erro ao criar view para rota '{route}': {e}", exc_info=True)
            page.views.append(
                ft.View(
                    route=route,
                    controls=[
                        ft.Icon(ft.Icons.ERROR_OUTLINE, color=COLOR_ERROR, size=48),
                        ft.Text(f"Erro ao carregar a página: {route}", size=20, weight=ft.FontWeight.BOLD),
                        ft.Text(f"Detalhes: {e}", selectable=True)
                    ],
                    vertical_alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER
                )
            )
    else: # Rota não encontrada
        logger.warning(f"Nenhuma view encontrada para a rota: {route}")
        page.views.append(
            ft.View(
                route=route, # Mostra a rota não encontrada
                controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE, color=COLOR_ERROR, size=48),
                    ft.Text(f"Página não encontrada: {route}", size=24, weight=ft.FontWeight.BOLD),
                    ft.ElevatedButton("Voltar ao Início", on_click=lambda _: page.go("/home"))
                ],
                vertical_alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER
            )
        )
    
    page.update()

def route_change_content_only(
    page: ft.Page,
    app_bar: ft.AppBar,
    navigation_rail: ft.NavigationRail,
    content_container_for_main_layout: ft.Container, # Renomeado para clareza
    route: str
):
    logger.info(f"Router (content_only): Navegando para rota '{route}'")

    upload_dir_base_url_path = f"/{Path(UPLOAD_TEMP_DIR).name}/" # Ex: "/uploads_temp/"
    if route.startswith(upload_dir_base_url_path):
        logger.info(f"Router: Rota '{route}' parece ser um arquivo do diretório de upload. Deixando o Flet servir o arquivo.")
        return

    authenticated = is_user_authenticated(page)

    # --- Lógica de Autenticação e Redirecionamento ---
    if not authenticated and route not in PUBLIC_ROUTES:
        logger.warning(f"Usuário não autenticado tentando acessar '{route}'. Redirecionando para /login.")
        page.go("/login")
        return
    if authenticated and route in PUBLIC_ROUTES:
        logger.info(f"Usuário já autenticado na página '{route}'. Redirecionando para /home.")
        page.go("/home")
        return

    # --- Seleção do Criador de Conteúdo ---
    current_content_creator: Optional[Callable] = None
    route_params: Optional[Any] = None
    if route in _content_creators:
        current_content_creator = _content_creators[route]
    # ... (lógica para rotas parametrizadas, se houver) ...

    # --- Limpeza e Preparação da Página ---
    page.controls.clear() # Limpa quaisquer controles anteriores da página
    generated_content = None # Conteúdo a ser adicionado à página ou ao container

    # --- Geração do Conteúdo Principal ---
    if current_content_creator:
        try:
            if route_params:
                generated_content = current_content_creator(page, *route_params)
            else:
                generated_content = current_content_creator(page)
        except Exception as e:
            logger.error(f"Erro ao criar conteúdo para rota '{route}': {e}", exc_info=True)
            generated_content = ft.Column([ # Conteúdo de erro
                ft.Icon(ft.Icons.ERROR_OUTLINE, color=COLOR_ERROR, size=48),
                ft.Text(f"Erro ao carregar: {route}", size=20), ft.Text(f"{e}", selectable=True),
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True)
    else:
        logger.warning(f"Nenhum criador de conteúdo encontrado para a rota: {route}")
        generated_content = ft.Column([ # Conteúdo de rota não encontrada
            ft.Icon(ft.Icons.ERROR_OUTLINE, color=COLOR_ERROR, size=48),
            ft.Text(f"Página não encontrada: {route}", size=24),
            ft.ElevatedButton("Voltar ao Início", on_click=lambda _: page.go("/home"))
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True)

    # --- Configuração do Layout da Página (AppBar, NavRail, Conteúdo) ---
    if route in ROUTES_WITHOUT_NAV_RAIL: # Ex: /login, /signup - Tela Cheia
        logger.debug(f"Rota '{route}' é de tela cheia.")
        page.appbar = None # Sem AppBar
        # page.navigation_rail = None # NavigationRail não é um atributo direto de page
        if generated_content:
            page.add(generated_content) # Adiciona o conteúdo de login/signup diretamente
        else: # Segurança, caso generated_content seja None por algum erro não capturado
            page.add(ft.Text("Erro: Conteúdo da página de tela cheia não pôde ser gerado.", color=COLOR_ERROR))
    else: # Rotas que usam o layout principal com AppBar e NavigationRail
        logger.debug(f"Rota '{route}' usa layout principal.")
        page.appbar = app_bar # Define a AppBar global
        page.appbar.visible = True
        navigation_rail.visible = True # Garante que a NavRail esteja visível

        # Atualiza o índice da NavigationRail
        current_nav_index = _find_nav_index_for_route(route)
        if navigation_rail.selected_index != current_nav_index:
            navigation_rail.selected_index = current_nav_index
        
        # Define o conteúdo no container do layout principal
        if generated_content:
            content_container_for_main_layout.content = generated_content
        else: # Segurança
            content_container_for_main_layout.content = ft.Text("Erro: Conteúdo principal não pôde ser gerado.", color=COLOR_ERROR)
        
        content_container_for_main_layout.padding = PADDING_L # Padding padrão

        # Adiciona o layout principal (Row com NavRail e content_container) à página
        page.add(
            ft.Row(
                [
                    navigation_rail,
                    ft.VerticalDivider(width=1),
                    content_container_for_main_layout
                ],
                expand=True,
            )
        )

    page.update() # Atualiza a página inteira com a nova estrutura e conteúdo

