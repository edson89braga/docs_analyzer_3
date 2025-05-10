# src/flet_ui/router.py
import flet as ft
import re
from typing import Optional

from .theme import COLOR_ERROR, PADDING_L 
from .layout import create_app_bar, create_navigation_rail, create_navigation_drawer, create_footer, _find_nav_index_for_route, icones_navegacao

from .views.login_view import create_login_view
from .views.signup_view import create_signup_view 
from .views.home_view import create_home_view 

from src.logger.logger import LoggerSetup
logger = LoggerSetup.get_logger(__name__)


# Mapeamento de rotas para funções que criam o *conteúdo* (não a View inteira)
# route_content_mapping
_view_creators = {
    "/login": create_login_view,
    "/signup": create_signup_view, 
    "/home": create_home_view,
}

# Mapeamento para rotas parametrizadas (usando regex simples)
# A chave é um padrão regex, o valor é a função que recebe page e os grupos capturados
# route_parameter_mapping 
_parameterized_view_creators  = {
    #r"/cadastros/materiais/chapa/(.+)$": lambda p, m: 'create_form_chapa_content'(p, m.group(1)), # Captura o ID da chapa
    # Adicionar outras rotas parametrizadas aqui (ex: /compras/<id>)
}

# Função auxiliar para verificar se o usuário está autenticado
def is_user_authenticated(page: ft.Page) -> bool:
    """Verifica se há um token de ID válido na sessão ou client_storage."""
    token = page.session.get("auth_id_token") or (page.client_storage.get("auth_id_token") if page.client_storage else None)
    # TODO: Idealmente, verificar a validade/expiração do token aqui.
    # Por agora, apenas a presença é verificada.
    # if token:
    #     try:
    #         # decoded_token = firebase_admin.auth.verify_id_token(token) # Requer Admin SDK
    #         # Ou, se você tiver a lógica de decodificação JWT e verificação de expiração:
    #         # payload = jwt.decode(token, options={"verify_signature": False}) # Simples para expiração
    #         # expiration_timestamp = payload.get("exp")
    #         # current_timestamp = time.time()
    #         # if expiration_timestamp and expiration_timestamp < current_timestamp:
    #         #     _logger.warning("Token de autenticação expirado.")
    #         #     page.session.remove("auth_id_token") # Limpa token expirado
    #         #     # Limpar outros dados de sessão e client_storage
    #         #     if page.client_storage: page.client_storage.remove("auth_id_token")
    #         #     return False
    #         return True
    #     except Exception as e:
    #         _logger.error(f"Erro ao verificar token: {e}. Considerando não autenticado.")
    #         return False
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
    if route in _view_creators:
        current_view_creator = _view_creators[route]
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
                        ft.Icon(ft.icons.ERROR_OUTLINE, color=COLOR_ERROR, size=48),
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
                    ft.Icon(ft.icons.ERROR_OUTLINE, color=COLOR_ERROR, size=48),
                    ft.Text(f"Página não encontrada: {route}", size=24, weight=ft.FontWeight.BOLD),
                    ft.ElevatedButton("Voltar ao Início", on_click=lambda _: page.go("/home"))
                ],
                vertical_alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER
            )
        )
    
    page.update()


def route_change(page: ft.Page, content_container: ft.Container, navigation_rail: ft.NavigationRail, route: str) -> None:
    """
    Chamado quando a rota da página muda.
    Atualiza o conteúdo principal e garante o índice correto da NavigationRail.
    """
    route_content_mapping = None
    route_parameter_mapping = None

    current_nav_index = _find_nav_index_for_route(route)
    if navigation_rail.selected_index != current_nav_index:
        navigation_rail.selected_index = current_nav_index
    
    # Limpa o container de conteúdo antigo
    content_container.content = None
    # Mostra um indicador de carregamento enquanto busca o novo conteúdo
    content_container.content = ft.Column(
        [ft.ProgressRing()],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True
    )
    page.update() # Mostra o loading
   
    content_creator = None
    parameter_match = None

    # 1. Tenta encontrar rota estática primeiro
    content_creator = route_content_mapping.get(route)

    # 2. Se não achou estática, tenta as parametrizadas
    if not content_creator:
        for pattern, creator_func in route_parameter_mapping.items():
            match = re.match(pattern, route)
            if match:
                content_creator = creator_func
                parameter_match = match # Guarda o objeto match para passar os grupos
                break # Para no primeiro match parametrizado

    if content_creator:
        try:
            if parameter_match:
                # Chama a função passando page e o objeto match
                new_content = content_creator(page, parameter_match)
            else:
                # Chama a função passando apenas page (rotas estáticas/novo)
                new_content = content_creator(page)
            content_container.content = new_content
        except Exception as e:
            # ... (tratamento de erro como antes) ...
            content_container.content = ft.Column([
                 ft.Icon(ft.icons.ERROR_OUTLINE, color=COLOR_ERROR, size=30),
                 ft.Text(f"Erro ao carregar conteúdo para {route}:", weight=ft.FontWeight.BOLD),
                 ft.Text(f"{e}", selectable=True),
            ], spacing=PADDING_L, alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
            # Logar o erro também
            logger.error(f"Erro ao criar conteúdo para rota '{route}'", exc_info=True)
    else:
        # ... (conteúdo de rota não encontrada como antes) ...
         content_container.content = ft.Column([
             ft.Text(f"Recurso não encontrado: {route}", size=20)
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True)

    page.update()