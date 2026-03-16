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

from SOURCE.settings import UPLOAD_TEMP_DIR 

from .theme import COLOR_WARNING, COLOR_ERROR, PADDING_L 
from .layout import create_app_bar, _find_nav_index_for_route, route_to_base_nav_index, icones_navegacao

_content_creators = {}

_view_module_map = {
    "/login": ("SOURCE.flet_ui.views.login_view", "create_login_view"),
    "/signup": ("SOURCE.flet_ui.views.signup_view", "create_signup_view"),
    "/home": ("SOURCE.flet_ui.views.home_view", "create_home_view2"),
    "/profile": ("SOURCE.flet_ui.views.profile_view", "create_profile_view"),
    "/settings/llm": ("SOURCE.flet_ui.views.llm_settings_view", "create_llm_settings_view"),
    "/analyze_pdf": ("SOURCE.flet_ui.views.nc_analyze_view", "create_analyze_pdf_content"),
    "/chat_docs": ("SOURCE.flet_ui.views.chat_view", "create_chat_view_content"),
    "/knowledge_base": ("SOURCE.flet_ui.views.others_view", "create_knowledge_base_content"),
    "/wiki_rotinas": ("SOURCE.flet_ui.views.others_view", "create_wiki_rotinas_content"),
    "/correicao_processos": ("SOURCE.flet_ui.views.others_view", "create_correicao_processos_content"),
    "/roteiro_investigacoes": ("SOURCE.flet_ui.views.others_view", "create_roteiro_investigacoes_content"),
    "/session-taken-over": ("SOURCE.flet_ui.views.others_view", "create_session_taken_over_view"),    
}

_parameterized_content_creators: Dict[str, Callable[[ft.Page, Any], Any]] = {}

PUBLIC_ROUTES = ["/login", "/signup", "/session-taken-over"]
ROUTES_WITHOUT_NAV_RAIL = ["/login", "/signup", "/session-taken-over"]

# ── FIX 3: Rotas stateful que NÃO devem ser cacheadas ───────────────────────
# Views com estado interno rico (uploads, histórico de chat, resultados de análise).
# Recriá-las a cada visita evita que state stale cause comportamento errático
# ou que callbacks internos referenciem objetos já desconectados da árvore de UI.
NO_CACHE_ROUTES = {"/analyze_pdf", "/chat_docs"}

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
    page.views.clear()

    current_view_creator: Optional[callable] = None
    route_params = None

    if route in _content_creators:
        current_view_creator = _content_creators[route]

    authenticated = is_user_authenticated(page)

    public_routes = ["/login", "/signup"]
    if not authenticated and route not in public_routes:
        logger.warning(f"Usuário não autenticado tentando acessar '{route}'. Redirecionando para /login.")
        page.go("/login") # Força o redirecionamento
        # A chamada page.go irá disparar o app_router novamente com a nova rota.
        # É importante que a view de login seja construída sem Appbar/Navrail.
        return # Interrompe o processamento da rota atual

    if authenticated and route in public_routes:
        logger.info("Usuário já autenticado na página de login. Redirecionando para /home.")
        page.go("/home")
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
    else:
        logger.warning(f"Nenhuma view encontrada para a rota: {route}")
        page.views.append(
            ft.View(
                route=route,
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


# ── FIX 4: Reset de sessão ───────────────────────────────────────────────────

def _handle_session_reset(page: ft.Page):
    """
    Desbloqueio de emergência da sessão Flet. Acessível via /reset.

    Não toca em tokens de autenticação nem em dados do usuário — apenas reseta
    o estado da UI (lock, cache de views, controles), suficiente para destravar
    os três tipos de congelamento identificados.
    """
    logger.warning(f"[RESET] Sessão {page.session_id} solicitou reset de UI.")

    try:
        if page.data is None:
            page.data = {}

        # 1. Recria o lock global, liberando qualquer deadlock pendente
        old_lock = page.data.get("global_update_lock")
        page.data["global_update_lock"] = threading.Lock()
        if old_lock:
            acquired = old_lock.acquire(blocking=False)
            if acquired:
                old_lock.release()
                logger.info("[RESET] Lock anterior estava livre — reset preventivo.")
            else:
                logger.warning("[RESET] Lock anterior estava TRAVADO — deadlock confirmado e resolvido.")

        # 2. Limpa o cache de views (força recriação limpa)
        try:
            from SOURCE.utils import get_user_cache
            user_cache = get_user_cache(page)
            cleared = len(user_cache.get('view_cache', {}))
            user_cache['view_cache'] = {}
            logger.info(f"[RESET] Cache de {cleared} view(s) limpo.")
        except Exception as e:
            logger.warning(f"[RESET] Não foi possível limpar cache de views: {e}")

        # 3. Incrementa o nav_token, descartando threads de carregamento em andamento
        page.data["_nav_token"] = page.data.get("_nav_token", 0) + 1
        logger.info(f"[RESET] Nav token incrementado para {page.data['_nav_token']}.")

        # 4. Limpa os controles da página
        try:
            page.controls.clear()
            page.update()
        except Exception as e:
            logger.warning(f"[RESET] Erro ao limpar controles: {e}")

    except Exception as e:
        logger.error(f"[RESET] Erro durante o reset: {e}", exc_info=True)

    # 5. Redireciona para destino seguro
    target = "/home" if is_user_authenticated(page) else "/login"
    logger.info(f"[RESET] Redirecionando para '{target}' após reset.")
    page.go(target)


def route_change_content_only(
    page: ft.Page,
    app_bar: ft.AppBar,
    navigation_rail: ft.NavigationRail,
    content_container_for_main_layout: ft.Container,
    route: str,
    admin_routes: bool = False,
    route_to_base_nav_index = route_to_base_nav_index,
    content_creators = _content_creators,
    view_module_map = _view_module_map,
    initial_route = '/home'
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
        logger.debug("Rota de ação do Firebase detectada. Ignorando.")
        return

    # Intercepta a rota raiz e redireciona para a página inicial (evita ValueError)
    if route == "/":
        logger.debug(f"Rota raiz acessada. Redirecionando para {initial_route}.")
        page.go(initial_route)
        return

    # ── FIX 4: Intercepta /reset antes de qualquer outra lógica ─────────────
    if route == "/reset":
        _handle_session_reset(page)
        return

    # --- 1. Validações e Redirecionamento ---
    upload_dir_base_url_path = f"/{Path(UPLOAD_TEMP_DIR).name}/"
    if route.startswith(upload_dir_base_url_path):
        logger.debug(f"Rota de arquivo '{route}'. Deixando Flet servir o arquivo.")
        return

    if not admin_routes:
        authenticated = is_user_authenticated(page)
        if not authenticated and route not in PUBLIC_ROUTES:
            logger.warning(f"Usuário não autenticado tentando acessar '{route}'. Redirecionando para /login.")
            page.go("/login")
            return
        # Redireciona para /home APENAS se um usuário autenticado tentar acessar as páginas de login/signup.
        if authenticated and route in ["/login", "/signup"]:
            logger.info(f"Usuário já autenticado na página '{route}'. Redirecionando para /home.")
            page.go("/home")
            return

    # ── FIX 1: Versão corrigida de _execute_ui_update ───────────────────────
    # page.update() agora fica FORA do `with update_lock`.
    # O lock protege apenas a mutação do estado dos controles. Manter page.update()
    # dentro do lock causava deadlock quando a thread da GUI recebia o callable via
    # page.run_thread() enquanto outro evento já aguardava o mesmo lock.
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
            # ← page.update() FORA do lock (correção crítica)
            page.update()
        else:
            # Fallback se o lock não for encontrado (menos seguro, mas evita deadlock)
            logger.warning("Lock de atualização da GUI não encontrado. Atualizando sem lock.")
            update_callable()
            page.update()
        logger.debug("Procedido: _execute_ui_update")

    # --- 2. Atualização Imediata da Estrutura da UI ---
    def _setup_layout_and_placeholder():
        page.controls.clear()
        placeholder = ft.Column(
            [ft.ProgressRing(), ft.Container(height=10), ft.Text("Carregando...", style=ft.TextThemeStyle.BODY_LARGE)],
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
            current_nav_index = _find_nav_index_for_route(route, route_to_base_nav_index=route_to_base_nav_index)
            if navigation_rail.selected_index != current_nav_index:
                navigation_rail.selected_index = current_nav_index
            
            content_container_for_main_layout.content = placeholder
            content_container_for_main_layout.padding = 0
            
            page.add(
                ft.Row(
                    [navigation_rail, ft.VerticalDivider(width=1), content_container_for_main_layout],
                    expand=True
                )
            )
        logger.debug("Procedido: _setup_layout_and_placeholder")

    _execute_ui_update(_setup_layout_and_placeholder)

    # ── FIX 2: Incrementa o nav_token ANTES de lançar a thread ──────────────
    # Qualquer thread de carregamento anterior que ainda esteja rodando verá
    # que seu token não corresponde mais ao atual e descartará o resultado,
    # evitando que uma thread lenta sobrescreva o conteúdo da rota correta.
    if page.data is None:
        page.data = {}
    page.data["_nav_token"] = page.data.get("_nav_token", 0) + 1
    nav_token = page.data["_nav_token"]

    # --- 3. Carregamento do Conteúdo Real em Background ---
    def _load_and_set_view(page_ref: ft.Page, target_route: str, token: int):
        """
        Carrega o conteúdo da view em uma thread separada e atualiza a UI.

        Esta função é executada em uma thread de background para carregar
        dinamicamente o módulo e a função criadora da view, evitando bloquear a UI.
        Após o carregamento, agenda a atualização da UI na thread principal.

        Args:
            page_ref (ft.Page): Referência à instância da página Flet.
            target_route (str): A rota para a qual o conteúdo está sendo carregado.
        """
        logger.debug(f"Thread [{token}]: Iniciando carregamento para '{target_route}'.")
        final_content: Optional[ft.Control] = None

        try:
            from SOURCE.utils import get_user_cache
            user_cache = get_user_cache(page_ref)

            if 'view_cache' not in user_cache:
                user_cache['view_cache'] = {}
            
            # FIX 3: Não cacheia views stateful
            use_cache = target_route not in NO_CACHE_ROUTES
            cached_view = user_cache['view_cache'].get(target_route) if use_cache else None

            if cached_view:
                logger.info(f"[{token}] View '{target_route}' do cache.")
                final_content = cached_view

            if content_creators:
                creator_func = content_creators.get(target_route)
                if creator_func and not cached_view:
                    logger.info(f"[{token}] Criando nova view '{target_route}' via content_creators.")
                    final_content = creator_func(page_ref)
                    if use_cache:
                        user_cache['view_cache'][target_route] = final_content
                elif not cached_view:
                    raise ValueError(f"Nenhum criador de conteúdo encontrado para: {target_route}")
            
            elif view_module_map and not cached_view:
                logger.info(f"[{token}] Criando nova view '{target_route}' via import dinâmico.")
                # --- LÓGICA DE IMPORTAÇÃO DINÂMICA ---
                if target_route in view_module_map:
                    import importlib
                    module_path, function_name = view_module_map[target_route]

                    # O import pesado acontece aqui!
                    view_module = importlib.import_module(module_path)
                    creator_func = getattr(view_module, function_name)

                    final_content = creator_func(page_ref)
                    if use_cache:
                        user_cache['view_cache'][target_route] = final_content
                else:
                    raise ValueError(f"Nenhum criador de conteúdo para: {target_route}")

            logger.debug(f"[{token}] Conteúdo criado para '{target_route}'.")

        except Exception as e:
            logger.error(f"[{token}] Erro ao criar conteúdo para '{target_route}': {e}", exc_info=True)
            final_content = ft.Column(
                [
                    ft.Icon(ft.Icons.ERROR_OUTLINE, color=COLOR_ERROR, size=48),
                    ft.Text(f"Erro ao carregar a página: {target_route}", size=20, weight=ft.FontWeight.BOLD),
                    ft.Text(f"Detalhes: {e}", selectable=True, font_family="monospace"),
                    ft.Container(height=20),
                    ft.ElevatedButton("Voltar para o Início", on_click=lambda _: page_ref.go(initial_route))
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
                spacing=15
            )

        # FIX 2: Verifica se esta ainda é a navegação atual (primeiro check, antes de run_thread)
        current_token = page_ref.data.get("_nav_token", 0)
        if token != current_token:
            logger.info(f"[{token}] Navegação obsoleta para '{target_route}' descartada (token atual: {current_token}).")
            return

        def _update_ui_with_new_content():
            """
            Função que será executada na thread da GUI para substituir o placeholder.
            Esta função é agora protegida pelo lock em _execute_ui_update.
            """
            # FIX 2: Double-check dentro da GUI thread
            if token != page_ref.data.get("_nav_token", 0):
                logger.debug(f"[{token}] Double-check: descartando update obsoleto para '{target_route}'.")
                return
            logger.debug(f"[{token}] Aplicando conteúdo para '{target_route}'.")
            if target_route in ROUTES_WITHOUT_NAV_RAIL:
                page_ref.controls.clear()
                page_ref.add(final_content)
            else:
                content_container_for_main_layout.content = final_content
                content_container_for_main_layout.padding = PADDING_L
        
        # Agenda a atualização da UI na thread principal
        page_ref.run_thread(lambda: _execute_ui_update(_update_ui_with_new_content))

    threading.Thread(target=_load_and_set_view, args=(page, route, nav_token), daemon=True).start()


execution_time = perf_counter() - start_time
logger.debug(f"Carregado ROUTER.py em {execution_time:.4f}s")