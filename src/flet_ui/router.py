# src/flet_ui/router.py
import flet as ft
import re

from .theme import COLOR_ERROR, PADDING_L 
from .layout import _find_nav_index_for_route

from src.logger.logger import LoggerSetup
logger = LoggerSetup.get_logger(__name__)


# Mapeamento de rotas para funções que criam o *conteúdo* (não a View inteira)
route_content_mapping = {
    "/dashboard": 'create_dashboard_content',
    "/cadastros": 'create_cadastros_index_content', # Rota base para o índice de cadastros
    "/cadastros/materiais": 'create_cad_materiais_content',
    "/cadastros/materiais/chapa/novo": lambda p: 'create_form_chapa_content'(p, None), # Rota para nova chapa
    "/cadastros/materiais/fita/novo": lambda p: 'create_form_fita_content'(p, None),   # Rota para nova fita
    "/test-datatable": 'create_test_datatable_content',
    "/test-selection": 'create_test_selection_dialog_content',
}

# Mapeamento para rotas parametrizadas (usando regex simples)
# A chave é um padrão regex, o valor é a função que recebe page e os grupos capturados
route_parameter_mapping = {
    r"/cadastros/materiais/chapa/(.+)$": lambda p, m: 'create_form_chapa_content'(p, m.group(1)), # Captura o ID da chapa
    r"/cadastros/materiais/fita/(.+)$": lambda p, m: 'create_form_fita_content'(p, m.group(1)),   
    r"/cadastros/composicoes/kit/(.+)$": lambda p, m: 'create_form_kit_content'(p, m.group(1)),
    r"/cadastros/composicoes/movel/(.+)$": lambda p, m: 'create_form_movel_content'(p, m.group(1)), 
    # Adicionar outras rotas parametrizadas aqui (ex: /compras/<id>)
}

def route_change(page: ft.Page, content_container: ft.Container, navigation_rail: ft.NavigationRail, route: str) -> None:
    """
    Chamado quando a rota da página muda.
    Atualiza o conteúdo principal e garante o índice correto da NavigationRail.
    """
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