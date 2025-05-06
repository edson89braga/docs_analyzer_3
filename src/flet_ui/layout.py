# src/flet_ui/layout.py
"""
Define elementos de layout reutilizáveis como AppBar e NavigationRail.
"""
import flet as ft
from typing import List, Dict, Any, Optional, Callable

# Importa definições de tema se necessário (ex: para padding ou cores)
from . import theme

def create_app_bar(page: ft.Page) -> ft.AppBar:
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

    return ft.AppBar(
        title=ft.Text("ERP BRG"),
        center_title=False,
        actions=[
             ft.IconButton(
                ft.icons.BRIGHTNESS_4_OUTLINED,
                tooltip="Mudar tema",
                on_click=toggle_theme_mode,
                padding = ft.padding.only(left=theme.PADDING_XL, right=theme.PADDING_XL)
             )
        ]
    )

# --- Variável Global para o SnackBar ---
# Inicializa como None, será criada na primeira chamada a show_snackbar
_global_snackbar_instance: Optional[ft.SnackBar] = None

def show_snackbar(page: ft.Page, message: str, color: str = theme.COLOR_INFO, duration: int = 5000):
    """
    Exibe uma mensagem no SnackBar, adicionando-o temporariamente ao overlay.

    Args:
        page: A instância da página Flet.
        message: A mensagem a ser exibida.
        color: A cor de fundo do SnackBar.
        duration: Duração em milissegundos.
    """
    global _global_snackbar_instance
    
    # Verifica se o SnackBar global já foi criado e adicionado à página
    # Usamos page.client_data para rastrear se já foi adicionado à *página atual*
    snackbar_added_key = "_global_snackbar_added"

    if not page.client_data.get(snackbar_added_key):
        if _global_snackbar_instance is None:
            # Cria a instância global na primeira vez
            _global_snackbar_instance = ft.SnackBar(
                content=ft.Text(""),
                duration=duration,
                show_close_icon = True, # action="OK" Ou "Fechar"
                action_color=ft.colors.WHITE
            )
        # Adiciona a instância global ao overlay da página ATUAL
        # Fazemos isso apenas uma vez por sessão de página (page)
        if _global_snackbar_instance not in page.overlay:
            page.overlay.append(_global_snackbar_instance)
            page.client_data[snackbar_added_key] = True # Marca como adicionado a esta página

    snackbar = _global_snackbar_instance
    if not snackbar:
        print("ERRO: Instância global do SnackBar não está definida!")
        return # Sai se algo deu errado
    
    # Abre o SnackBar
    snackbar.content.value = message
    snackbar.bgcolor = color
    snackbar.duration = duration
    snackbar.open = True
    page.update() # Atualiza para efetivamente mostrar

def show_confirmation_dialog(
    page: ft.Page,
    title: str,
    content: ft.Control | str,
    confirm_text: str = "Confirmar",
    cancel_text: str = "Cancelar",
    on_confirm: Optional[Callable[[], None]] = None # Callback se confirmado
):
    """Exibe um diálogo de confirmação padrão."""
    confirm_dialog = None # Declara antes para ser acessível no close_dialog

    def close_dialog(e):
        confirm_dialog.open = False
        page.update()
        page.overlay.remove(confirm_dialog) # Remove do overlay ao fechar
        if hasattr(e.control, 'data') and e.control.data == "confirm" and on_confirm:
            on_confirm() # Chama o callback de confirmação

    confirm_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text(title),
        content=content if isinstance(content, ft.Control) else ft.Text(content),
        actions=[
            ft.TextButton(confirm_text, on_click=close_dialog, data="confirm"),
            ft.TextButton(cancel_text, on_click=close_dialog, data="cancel"),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    page.overlay.append(confirm_dialog) # Adiciona ao overlay
    confirm_dialog.open = True
    page.update() # Abre o diálogo

# Módulos e seus ícones/rotas para a navegação
# Definido aqui para ser acessível globalmente por este módulo
icones_navegacao: List[Dict[str, Any]] = [
    {"label": "Dashboard", "icon": ft.icons.DASHBOARD_OUTLINED, "selected_icon": ft.icons.DASHBOARD, "route": "/dashboard"},
    #{"label": "Cadastros", "icon": ft.icons.CHECKLIST_OUTLINED, "selected_icon": ft.icons.CHECKLIST_RTL, "route": "/cadastros/materiais"}, 
    {"label": "Cadastros", "icon": ft.icons.CHECKLIST_OUTLINED, "selected_icon": ft.icons.CHECKLIST_RTL, "route": "/cadastros"},
    {"label": "Operações", "icon": ft.icons.ADD_BUSINESS_OUTLINED, "selected_icon": ft.icons.ADD_BUSINESS, "route": "/operacoes/compras"}, # Rota base
    {"label": "Estoque", "icon": ft.icons.INVENTORY_2_OUTLINED, "selected_icon": ft.icons.INVENTORY_2, "route": "/estoque/consultas"},
    {"label": "Financeiro", "icon": ft.icons.CURRENCY_EXCHANGE_OUTLINED, "selected_icon": ft.icons.CURRENCY_EXCHANGE, "route": "/financeiro/lancamentos"}, # Rota base
    {"label": "Contabilidade", "icon": ft.icons.ACCOUNT_BALANCE_OUTLINED, "selected_icon": ft.icons.ACCOUNT_BALANCE, "route": "/contabilidade/lancamentos"}, # Rota base
    {"label": "Configurações", "icon": ft.icons.SETTINGS_OUTLINED, "selected_icon": ft.icons.SETTINGS, "route": "/configuracoes/precos-servicos"}, # Rota base
    # Objetos de teste:
    {"label": "Teste DT", "icon": ft.icons.TABLE_CHART_OUTLINED, "selected_icon": ft.icons.TABLE_CHART, "route": "/test-datatable"},
    {"label": "Teste Sel", "icon": ft.icons.PERSON_SEARCH, "selected_icon": ft.icons.PERSON_SEARCH_SHARP, "route": "/test-selection"},
]

# Mapeamento inverso para destacar o item correto na NavRail principal
route_to_base_nav_index: Dict[str, int] = {
    "/dashboard": 0,
    "/cadastros": 1, # Rota base
    "/cadastros/materiais": 1,
    "/cadastros/crm": 1,
    "/cadastros/produtos": 1,
    "/cadastros/pagamentos": 1, 
    #"/cadastros/financeiro": 1, # Adicionar se/quando criar
    "/operacoes/compras": 2,
    # Adicionar sub-rotas de operações se necessário
    "/estoque/consultas": 3,
    "/financeiro/lancamentos": 4,
    "/contabilidade/lancamentos": 5,
    # Adicionar sub-rotas financeiras
    "/configuracoes/precos-servicos": 6,
    # Adicionar sub-rotas de config...
    "/test-datatable": len(icones_navegacao) - 2, # Ajustar índice
    "/test-selection": len(icones_navegacao) - 1, # Ajustar índice
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

