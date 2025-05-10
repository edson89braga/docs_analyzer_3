# src/flet_ui/layout.py
"""
Define elementos de layout reutilizáveis como AppBar e NavigationRail.
"""
import flet as ft
from typing import List, Dict, Any, Optional, Callable

# Importa definições de tema se necessário (ex: para padding ou cores)
from src.flet_ui import theme

def create_app_bar(page: ft.Page, app_title) -> ft.AppBar:
    """Cria a AppBar padrão para a aplicação."""
    
    def toggle_theme_mode(e):
        if page.theme_mode == ft.ThemeMode.LIGHT:
            page.theme_mode = ft.ThemeMode.DARK
        elif page.theme_mode == ft.ThemeMode.DARK:
            page.theme_mode = ft.ThemeMode.LIGHT
        else:
            page.theme_mode = ft.ThemeMode.DARK
        # Atualiza a cor da appbar explicitamente se necessário
        # page.appbar.bgcolor = ... # Se o tema não atualizar automaticamente
        page.update()

    # Recupera o nome do usuário para exibir na AppBar, se logado
    user_display_name = page.session.get("auth_display_name") or \
                        (page.client_storage.get("auth_display_name") if page.client_storage else None)
    
    user_greeting_or_empty = []
    if user_display_name:
        user_greeting_or_empty.append(
            ft.Text(f"Olá, {user_display_name.split(' ')[0]}", # Pega o primeiro nome
                    size=14,
                    font_family="Roboto", # Garante uma fonte consistente
                    weight=ft.FontWeight.NORMAL,
                    opacity=0.8, # Um pouco mais sutil
                    italic=True) 
        )
        user_greeting_or_empty.append(ft.Container(width=10)) # Pequeno espaçador

    app_bar_actions = [
        *user_greeting_or_empty, # Desempacota a lista (pode ser vazia)
        ft.IconButton(
            ft.icons.BRIGHTNESS_4_OUTLINED, # Ícone para tema
            tooltip="Mudar tema",
            padding = ft.padding.only(left=theme.PADDING_XL, right=theme.PADDING_XL),
            on_click=toggle_theme_mode,
        ),
        ft.PopupMenuButton(
            tooltip="Opções do Usuário",
            icon=ft.icons.ACCOUNT_CIRCLE_OUTLINED,
            padding = ft.padding.only(left=theme.PADDING_XL, right=theme.PADDING_XL),
            items=[
                ft.PopupMenuItem(text="Meu Perfil", icon=ft.icons.PERSON_OUTLINE, on_click=lambda _: page.go("/profile")), # Rota de perfil
                ft.PopupMenuItem(text="Configurações", icon=ft.icons.SETTINGS_OUTLINED, on_click=lambda _: page.go("/settings")), # Rota de configurações
                ft.PopupMenuItem(),  # Divisor
                ft.PopupMenuItem(text="Sair", icon=ft.icons.LOGOUT, on_click=lambda _: handle_logout(page)) # Ação de Logout
            ]
        )
    ]

    return ft.AppBar(
        title=ft.Text(app_title),
        center_title=False,
        actions=app_bar_actions
    )

# Módulos e seus ícones/rotas para a navegação
# Definido aqui para ser acessível globalmente por este módulo
icones_navegacao: List[Dict[str, Any]] = [
    {
        "label": "Início",
        "icon": ft.Icons.HOME_OUTLINED,
        "selected_icon": ft.Icons.HOME,
        "route": "/home"
    },
    {
        "label": "Perfil",
        "icon": ft.Icons.ACCOUNT_CIRCLE_OUTLINED,
        "selected_icon": ft.Icons.ACCOUNT_CIRCLE,
        "route": "/profile"
    },
    {
        "label": "Produtos",
        "icon": ft.Icons.CATEGORY_OUTLINED,
        "selected_icon": ft.Icons.CATEGORY,
        "route": "/products" # Rota base para a seção de produtos
    },
    {
        "label": "Pedidos",
        "icon": ft.Icons.SHOPPING_CART_OUTLINED,
        "selected_icon": ft.Icons.SHOPPING_CART,
        "route": "/orders" # Rota base para a seção de pedidos
    },
    {
        "label": "Análises",
        "icon": ft.Icons.INSIGHTS_OUTLINED,
        "selected_icon": ft.Icons.INSIGHTS,
        "route": "/analytics" # Rota base para a seção de análises
    },
    {
        "label": "Ajuda",
        "icon": ft.Icons.HELP_OUTLINE,
        "selected_icon": ft.Icons.HELP,
        "route": "/help/faq" # Exemplo de rota direta para uma sub-seção
    },
    {
        "label": "Configurações",
        "icon": ft.Icons.SETTINGS_OUTLINED,
        "selected_icon": ft.Icons.SETTINGS,
        "route": "/settings/application" # Rota base para a seção de configurações
    },
]

# REESCRITA DA SEÇÃO: route_to_base_nav_index
# Mapeamento inverso para destacar o item correto na NavRail principal
route_to_base_nav_index: Dict[str, int] = {
    # Raiz do app, geralmente redireciona para /home ou /dashboard
    "/": 0, # Mapeia para "Início" (índice 0)
    "/home": 0,

    "/profile": 1,
    "/profile/edit": 1,
    "/profile/security": 1,

    "/products": 2, # Rota base para produtos
    "/products/list": 2,
    "/products/new": 2,
    "/products/categories": 2,
    "/products/detail/123": 2, # Exemplo com parâmetro

    "/orders": 3, # Rota base para pedidos
    "/orders/list": 3,
    "/orders/pending": 3,
    "/orders/detail/456": 3, # Exemplo com parâmetro

    "/analytics": 4, # Rota base para análises
    "/analytics/sales": 4,
    "/analytics/users": 4,

    "/help": 5, # Rota base para ajuda
    "/help/faq": 5,
    "/help/contact": 5,

    "/settings": 6, # Rota base para configurações
    "/settings/application": 6,
    "/settings/user": 6,
    "/settings/notifications": 6,
}

def _find_nav_index_for_route(route: str) -> int:
    """Encontra o índice da NavigationRail para uma dada rota (incluindo sub-rotas)."""
    selected_index = 0 # Default Dashboard
    best_match_len = 0
    # Rota base "/" deve ter prioridade baixa se outra rota mais específica corresponder
    if route == "/":
        best_match_len = 1 # Define um comprimento mínimo para a raiz

    for base_route, index in route_to_base_nav_index.items():
        # Ignora a rota raiz "/" na checagem de prefixo se a rota atual for diferente dela
        if base_route == "/" and route != "/":
            continue

        # Verifica se a rota atual é exatamente a rota base ou começa com a rota base + '/'
        is_exact_match = (route == base_route)
        # Garante que a rota base não seja apenas "/" para a checagem de prefixo
        is_prefix_match = (base_route != "/" and route.startswith(base_route + "/"))

        if is_exact_match or is_prefix_match:
            # Comprimento da rota base encontrada
            current_match_len = len(base_route)
            # Se esta rota base for mais longa (mais específica) que a melhor encontrada até agora
            if current_match_len > best_match_len:
                best_match_len = current_match_len
                selected_index = index
            # Caso especial: Se a rota atual for EXATAMENTE igual a uma rota base de mesmo comprimento
            # que a melhor encontrada (improvável com a estrutura atual, mas defensivo),
            # prioriza a correspondência exata.
            elif current_match_len == best_match_len and is_exact_match and selected_index != index:
                 selected_index = index

    return selected_index

def create_navigation_rail(page: ft.Page, selected_route: str) -> ft.NavigationRail:
    """Cria a NavigationRail, marcando o índice correto com base na rota.

    A NavigationRail (ou NavigationDrawer) é o painel lateral que contém os links
    para as diferentes seções do aplicativo. Aqui, criamos essa NavigationRail e
    fazemos com que ela seja configurada para marcar a seção correta com base na
    rota atual.

    :param page: A página atual do Flet (usada apenas para obter a rota atual)
    :param selected_route: A rota atual (usada para determinar o índice selecionado)
    :return: A NavigationRail configurada e pronta para uso
    """

    # Encontra o índice da NavigationRail para a rota atual
    selected_index = _find_nav_index_for_route(selected_route)

    # Define uma função que será executada quando a NavigationRail for alterada
    # (ou seja, quando o usuário clicar em um item diferente)
    def navigate(e):
        # Obtém o índice do item selecionado na NavigationRail
        target_index = e.control.selected_index
        # Obtém a rota para o item selecionado
        target_route = icones_navegacao[target_index]["route"]
        # Navega para a rota selecionada
        page.go(target_route)

    # Cria a NavigationRail com base nos dados de icones_navegacao
    # e configura o evento de mudança para a função navigate
    return ft.NavigationRail(
        selected_index=selected_index,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=100,
        min_extended_width=200,
        destinations=[
            ft.NavigationRailDestination(
                icon=modulo["icon"],
                selected_icon=modulo["selected_icon"],
                label=modulo["label"]
            ) for modulo in icones_navegacao
        ],
        on_change=navigate
    )

def create_navigation_drawer(page: ft.Page, selected_route: str) -> ft.NavigationDrawer:
    """Cria a NavigationDrawer."""
    selected_index = _find_nav_index_for_route(selected_route)

    def navigate_and_close_drawer(e):
        # target_index = e.control.selected_index # Drawer não tem selected_index no evento on_change
        # Precisamos encontrar o índice pelo label ou outra propriedade se o evento não der o índice
        # Para simplificar, vamos assumir que o controle do evento é o NavigationDrawerDestination
        # e podemos pegar a rota do seu label ou de um atributo data.
        # Flet pode passar o controle do destino clicado.
        # No entanto, o `on_change` do NavigationDrawer é mais simples e não retorna o destino clicado.
        # Uma abordagem mais robusta é usar o `data` de cada destino.

        # A forma mais direta é fechar o drawer e então navegar.
        # O on_change do drawer em si não é ideal para navegação direta
        # porque ele dispara antes de um destino ser 'selecionado'
        # É melhor que cada destino tenha seu próprio on_click.
        page.drawer.open = False # Fecha o drawer
        page.update()
        # A navegação real deve ser feita pelo on_click de cada tile/destino

    # Dentro do Drawer, usamos controles como ft.NavigationDrawerDestination
    # ou ft.ListTile para criar os itens navegáveis.
    
    drawer_destinations = []
    for i, modulo in enumerate(icones_navegacao):
        drawer_destinations.append(
            ft.NavigationDrawerDestination(
                icon_content=ft.Icon(modulo["icon"]),
                selected_icon_content=ft.Icon(modulo["selected_icon"]),
                label=modulo["label"],
            )
        )
        # O NavigationDrawerDestination em si não tem um evento on_click fácil
        # para navegação direta. Frequentemente se usa ListTile dentro do drawer.

    # Alternativa usando ListTile para melhor controle do clique
    drawer_tiles = []
    for i, modulo in enumerate(icones_navegacao):
        is_selected = (selected_index == i)
        drawer_tiles.append(
            ft.ListTile(
                title=ft.Text(modulo["label"]),
                leading=ft.Icon(modulo["selected_icon"] if is_selected else modulo["icon"]),
                on_click=lambda _, route=modulo["route"]: (
                    setattr(page.drawer, 'open', False), # Fecha o drawer
                    page.go(route) # Navega
                ),
                selected=is_selected,
                # Para o tema do ListTile selecionado funcionar bem,
                # você pode precisar envolver o NavigationDrawer em um Container com um tema
                # ou ajustar o tema global.
            )
        )

    return ft.NavigationDrawer(
        controls=drawer_tiles, # Usando os ListTiles
        # selected_index=selected_index # Isso ajuda a destacar visualmente
        # on_change=navigate_and_close_drawer # on_change pode ser usado para outras lógicas
    )

def create_footer(page: ft.Page) -> ft.BottomAppBar:
    """Cria um rodapé simples para a aplicação."""
    return ft.BottomAppBar(
        content=ft.Row(
            [
                ft.Text(f"© {theme.APP_YEAR} ERP BRG. Todos os direitos reservados."),
                ft.Container(expand=True), # Espaçador
                ft.TextButton("Suporte"),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
        ),
        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE), # Exemplo de cor
        padding=ft.padding.symmetric(horizontal=theme.PADDING_M)
    )

from src.logger.logger import LoggerSetup # Adicionado
_logger_layout = LoggerSetup.get_logger(__name__)

def handle_logout(page: ft.Page):
    """Limpa o estado de autenticação e redireciona para a tela de login."""
    user_id_logged_out = page.session.get("auth_user_id") or \
                         (page.client_storage.get("auth_user_id") if page.client_storage else "Desconhecido")
    _logger_layout.info(f"Usuário {user_id_logged_out} deslogando.")

    # Limpa do client_storage se existir
    if page.client_storage:
        if page.client_storage.contains_key("auth_id_token"): # Verifica antes de remover
            page.client_storage.remove("auth_id_token")
        if page.client_storage.contains_key("auth_user_id"):
            page.client_storage.remove("auth_user_id")
        if page.client_storage.contains_key("auth_user_email"):
            page.client_storage.remove("auth_user_email")
        if page.client_storage.contains_key("auth_display_name"):
            page.client_storage.remove("auth_display_name")
        _logger_layout.debug("Dados de autenticação removidos do client_storage (se existiam).")
    
    keys_to_remove_session = ["auth_id_token", "auth_user_id", "auth_user_email", "auth_display_name"]
    for key in keys_to_remove_session:
        if page.session.contains_key(key):
            page.session.remove(key) 
    _logger_layout.debug("Dados de autenticação removidos da sessão Flet.")
    
    LoggerSetup.set_cloud_user_context(None, None) # Limpa contexto do logger de nuvem
    _logger_layout.info("Contexto do logger de nuvem limpo.")
    
    page.go("/login")
    # Opcional: Mostrar um snackbar de logout bem-sucedido na página de login
    # Isso é um pouco mais complexo porque o snackbar precisa ser mostrado *após* o redirecionamento.
    # Uma forma seria passar um parâmetro na rota: page.go("/login?logout=true")
    # E a view de login verificaria esse parâmetro para mostrar o snackbar.
