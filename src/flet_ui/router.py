# src/flet_ui/router.py
import logging
logger = logging.getLogger(__name__)

from time import perf_counter
start_time = perf_counter()
logger.debug(f"{start_time:.4f}s - Iniciando router.py")

import flet as ft
import threading
from typing import Optional, Dict, Callable, Any
from pathlib import Path

from src.settings import UPLOAD_TEMP_DIR 

from .theme import COLOR_WARNING, COLOR_ERROR, PADDING_L 
from .layout import create_app_bar, _find_nav_index_for_route, icones_navegacao

#from .views.login_view import create_login_view
#from .views.signup_view import create_signup_view 
#from .views.home_view import create_home_view2
#from .views.profile_view import create_profile_view
#from .views.proxy_settings_view import create_proxy_settings_content
#from .views.llm_settings_view import create_llm_settings_view
#from .views.nc_analyze_view import create_analyze_pdf_content
#from .views.others_view import create_chat_pdf_content

## Mapeamento de rotas para funções que criam o *conteúdo* (não a View inteira)
## route_content_mapping
#_content_creators = {
#    "/login": create_login_view,
#    "/signup": create_signup_view, 
#    "/home": create_home_view2,
#    "/profile": create_profile_view,
#    "/settings/proxy": create_proxy_settings_content,
#    "/settings/llm": create_llm_settings_view,
#    "/analyze_pdf": create_analyze_pdf_content, 
#    "/chat_pdf": create_chat_pdf_content, 
#    "/knowledge_base": create_knowledge_base_content,    
#    "/wiki_rotinas": create_wiki_rotinas_content,
#    "/correicao_processos": create_correicao_processos_content,
#    "/roteiro_investigacoes": create_roteiro_investigacoes_content,
#}
_content_creators = {}

# Em vez disso, vamos mapear as rotas para o CAMINHO do módulo e o NOME da função.
_view_module_map = {
    "/login": ("src.flet_ui.views.login_view", "create_login_view"),
    "/signup": ("src.flet_ui.views.signup_view", "create_signup_view"),
    "/home": ("src.flet_ui.views.home_view", "create_home_view2"),
    "/profile": ("src.flet_ui.views.profile_view", "create_profile_view"),
    #"/settings/proxy": ("src.flet_ui.views.proxy_settings_view", "create_proxy_settings_content"),
    "/settings/llm": ("src.flet_ui.views.llm_settings_view", "create_llm_settings_view"),
    "/analyze_pdf": ("src.flet_ui.views.nc_analyze_view", "create_analyze_pdf_content"),
    "/chat_pdf": ("src.flet_ui.views.others_view", "create_chat_pdf_content"),
    "/knowledge_base": ("src.flet_ui.views.others_view", "create_knowledge_base_content"),
    "/wiki_rotinas": ("src.flet_ui.views.others_view", "create_wiki_rotinas_content"),
    "/correicao_processos": ("src.flet_ui.views.others_view", "create_correicao_processos_content"),
    "/roteiro_investigacoes": ("src.flet_ui.views.others_view", "create_roteiro_investigacoes_content"),
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
    """
    Verifica se o usuário está autenticado.

    Procura por um token de ID válido na sessão da página ou no armazenamento do cliente.

    Args:
        page (ft.Page): A instância da página Flet.

    Returns:
        bool: True se o usuário estiver autenticado, False caso contrário.
    """
    token = page.session.get("auth_id_token") or (page.client_storage.get("auth_id_token") if page.client_storage else None)
    logger.debug(f"is_user_authenticated: {bool(token)}")
    return bool(token)

def app_router(page: ft.Page, route: str):
    # Função NÃO utilizada nesta aplicação.
    """
    Gerencia a navegação e a exibição das views corretas no aplicativo Flet.

    Esta função é responsável por:
    1. Limpar a pilha de views existente.
    2. Lidar com a lógica de autenticação e redirecionamento para rotas públicas/privadas.
    3. Construir e exibir a view apropriada para a rota solicitada.
    4. Adicionar elementos de layout padrão (AppBar) para rotas autenticadas.
    5. Tratar erros na criação da view, exibindo uma mensagem de erro.

    Args:
        page (ft.Page): A instância da página Flet.
        route (str): A rota para a qual o aplicativo está navegando.
    """
    logger.info(f"Navegando para rota: '{route}'")
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

def OLD_route_change_content_only(
    page: ft.Page,
    app_bar: ft.AppBar,
    navigation_rail: ft.NavigationRail,
    content_container_for_main_layout: ft.Container,
    route: str
):
    """
    [DEPRECATED] Gerencia a navegação e a atualização do conteúdo principal da página.

    Esta função é uma versão mais antiga da lógica de roteamento que atualiza
    diretamente o conteúdo de um container na página, em vez de manipular a pilha de views.
    Inclui lógica de autenticação e tratamento de rotas de arquivo.

    Args:
        page (ft.Page): A instância da página Flet.
        app_bar (ft.AppBar): A barra de aplicativo principal.
        navigation_rail (ft.NavigationRail): O componente de navegação lateral.
        content_container_for_main_layout (ft.Container): O container onde o conteúdo principal será carregado.
        route (str): A rota para a qual o aplicativo está navegando.
    """
    logger.info(f"Navegando para rota (OLD_content_only): '{route}'")

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

def route_change_content_only(
    page: ft.Page,
    app_bar: ft.AppBar,
    navigation_rail: ft.NavigationRail,
    content_container_for_main_layout: ft.Container,
    route: str
):
    """
    Gerencia a navegação com carregamento assíncrono de conteúdo.

    Esta função atualiza a UI imediatamente com um indicador de progresso e,
    em uma thread de background, carrega o módulo da view e suas dependências.
    Quando o conteúdo real está pronto, ele substitui o indicador.

    Args:
        page (ft.Page): A instância da página Flet.
        app_bar (ft.AppBar): A barra de aplicativo principal.
        navigation_rail (ft.NavigationRail): O componente de navegação lateral.
        content_container_for_main_layout (ft.Container): O container onde o conteúdo principal será carregado.
        route (str): A rota para a qual o aplicativo está navegando.
    """
    logger.info(f"Navegando para rota (content_only): '{route}'")

    # Ignora rotas de ação de autenticação do Firebase para que o SDK JS do cliente possa lidar com elas.
    if "/__/auth/action" in route:
        logger.debug("Rota de ação do Firebase detectada. Ignorando para manipulação pelo cliente.")
        return
    
    # --- 1. Validações e Redirecionamento ---
    upload_dir_base_url_path = f"/{Path(UPLOAD_TEMP_DIR).name}/"
    if route.startswith(upload_dir_base_url_path):
        logger.debug(f"Rota de arquivo '{route}'. Deixando Flet servir o arquivo.")
        return

    authenticated = is_user_authenticated(page)
    if not authenticated and route not in PUBLIC_ROUTES:
        logger.warning(f"Usuário não autenticado tentando acessar '{route}'. Redirecionando para /login.")
        page.go("/login")
        return
    if authenticated and route in PUBLIC_ROUTES:
        logger.info(f"Usuário já autenticado na página '{route}'. Redirecionando para /home.")
        page.go("/home")
        return

    # Obtém o lock global. Se não existir, a operação não será protegida.
    update_lock = page.data.get("global_update_lock")

    def _execute_ui_update(update_callable: Callable):
        """
        Função auxiliar para executar atualizações de UI de forma segura com um lock.

        Garante que as atualizações da UI sejam feitas de forma thread-safe,
        utilizando um lock global se disponível.

        Args:
            update_callable (Callable): A função a ser executada para atualizar a UI.
        """
        if update_lock:
            with update_lock:
                update_callable()
                page.update()
        else:
            # Fallback se o lock não for encontrado (menos seguro, mas evita deadlock)
            logger.warning("Lock de atualização da GUI não encontrado. Atualizando GUI sem proteção de lock.")
            update_callable()
            page.update()
        logger.debug("Procedido: _execute_ui_update")

    # --- 2. Atualização Imediata da Estrutura da UI ---
    def _setup_layout_and_placeholder():
        page.controls.clear()
        placeholder = ft.Column(
            [ft.ProgressRing(), ft.Container(height=10), ft.Text("1º Carregamento...", style=ft.TextThemeStyle.BODY_LARGE)],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True
        )

        if route in ROUTES_WITHOUT_NAV_RAIL:
            page.appbar = None
            page.add(placeholder)
        else:
            page.appbar = app_bar
            page.appbar.visible = True
            navigation_rail.visible = True
            current_nav_index = _find_nav_index_for_route(route)
            if navigation_rail.selected_index != current_nav_index:
                navigation_rail.selected_index = current_nav_index
            
            content_container_for_main_layout.content = placeholder
            content_container_for_main_layout.padding = 0  # Centraliza o placeholder
            
            page.add(
                ft.Row(
                    [navigation_rail, ft.VerticalDivider(width=1), content_container_for_main_layout],
                    expand=True
                )
            )
        logger.debug("Procedido: _setup_layout_and_placeholder")

    _execute_ui_update(_setup_layout_and_placeholder)

    # --- 3. Carregamento do Conteúdo Real em Background ---
    def _load_and_set_view(page_ref: ft.Page, target_route: str):
        """
        Carrega o conteúdo da view em uma thread separada e atualiza a UI.

        Esta função é executada em uma thread de background para carregar
        dinamicamente o módulo e a função criadora da view, evitando bloquear a UI.
        Após o carregamento, agenda a atualização da UI na thread principal.

        Args:
            page_ref (ft.Page): Referência à instância da página Flet.
            target_route (str): A rota para a qual o conteúdo está sendo carregado.
        """
        logger.debug(f"Thread: Iniciando carregamento do conteúdo para a rota '{target_route}'.")
        final_content: Optional[ft.Control] = None

        try:
            # --- LÓGICA DE IMPORTAÇÃO DINÂMICA ---
            if target_route in _view_module_map:
                import importlib
                module_path, function_name = _view_module_map[target_route]
                
                # O import pesado acontece aqui!
                view_module = importlib.import_module(module_path)
                creator_func = getattr(view_module, function_name)
                
                final_content = creator_func(page_ref)
            else:
                raise ValueError(f"Nenhum criador de conteúdo encontrado para a rota: {target_route}")
            
            logger.debug("Procedido: _load_and_set_view")
            #creator_func = _content_creators.get(target_route)
            #if creator_func:
            #    final_content = creator_func(page_ref)
            #else:
            #    raise ValueError(f"Nenhum criador de conteúdo encontrado para a rota: {target_route}")

        except Exception as e:
            # ... (código de tratamento de erro para final_content) ...
            logger.error(f"Erro ao criar conteúdo para rota '{target_route}': {e}", exc_info=True)
            final_content = ft.Column(
                [
                    ft.Icon(ft.Icons.ERROR_OUTLINE, color=COLOR_ERROR, size=48),
                    ft.Text(f"Erro ao carregar a página: {target_route}", size=20, weight=ft.FontWeight.BOLD),
                    ft.Text(f"Detalhes: {e}", selectable=True, font_family="monospace"),
                    ft.Container(height=20),
                    ft.ElevatedButton("Voltar para o Início", on_click=lambda _: page_ref.go("/home"))
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
                spacing=15
            )

        def _update_ui_with_new_content():
            """
            Função que será executada na thread da GUI para substituir o placeholder.
            Esta função é agora protegida pelo lock em _execute_ui_update.
            """
            logger.debug(f"Thread: Conteúdo para '{target_route}' carregado. Atualizando GUI.")
            if target_route in ROUTES_WITHOUT_NAV_RAIL:
                page_ref.controls.clear()
                page_ref.add(final_content)
            else:
                content_container_for_main_layout.content = final_content
                content_container_for_main_layout.padding = PADDING_L
            logger.debug("Procedido: _update_ui_with_new_content")
        
        # Agenda a atualização da UI na thread principal
        page_ref.run_thread(lambda: _execute_ui_update(_update_ui_with_new_content))

    # Inicia a thread de carregamento
    threading.Thread(target=_load_and_set_view, args=(page, route), daemon=True).start()


execution_time = perf_counter() - start_time
logger.debug(f"Carregado ROUTER.py em {execution_time:.4f}s")
