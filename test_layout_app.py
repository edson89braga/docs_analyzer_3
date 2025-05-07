# test_layout_app.py (coloque na raiz do projeto Repo/ ou em uma pasta tests/)

import flet as ft
import sys
import os

# --- Configuração do Caminho para Importação ---
# Adiciona o diretório 'src' ao Python path para encontrar os módulos.
# Isso é útil se você executar este script de um local diferente da raiz do projeto.
# Se 'test_layout_app.py' estiver na raiz do projeto 'Repo/', esta seção pode ser mais simples.

# Obtém o diretório do script atual
script_dir = os.path.dirname(os.path.abspath(__file__))

# Assume que a pasta 'src' está no mesmo nível que a pasta onde 'test_layout_app.py' está,
# ou um nível acima se 'test_layout_app.py' estiver em 'Repo/tests/'.
# Ajuste 'project_root_candidate' conforme a sua estrutura.
# Se test_layout_app.py está em Repo/:
project_root_candidate = script_dir
# Se test_layout_app.py está em Repo/tests/:
# project_root_candidate = os.path.dirname(script_dir)

src_path = os.path.join(project_root_candidate, "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)
# --- Fim da Configuração do Caminho ---

# Agora podemos importar os módulos do seu projeto
from src.flet_ui import layout  # Importa seu módulo layout.py
from src.flet_ui import theme as app_theme # Importa seu módulo theme.py

# Variável global para a área de conteúdo principal da view (para facilitar a atualização)
main_content_area = ft.Column(
    controls=[ft.Text("Bem-vindo! Navegue usando o menu lateral ou superior.")],
    alignment=ft.MainAxisAlignment.START,
    horizontal_alignment=ft.CrossAxisAlignment.START,
    expand=True,
    spacing=20,
    #padding=app_theme.PADDING_M # Usa padding do tema
)

def update_main_content_for_route(page: ft.Page, route: str):
    """
    Atualiza a área de conteúdo principal com base na rota atual.
    Também demonstra como a navegação para sub-rotas pode ser testada.
    """
    main_content_area.controls.clear()
    main_content_area.controls.append(
        ft.Text(f"Conteúdo da Rota: {route}", size=24, weight=ft.FontWeight.BOLD)
    )
    main_content_area.controls.append(
        ft.Text(f"Índice de navegação base detectado: {layout._find_nav_index_for_route(route)}")
    )

    # Adiciona botões para testar a navegação para sub-rotas específicas
    if route.startswith("/products"):
        main_content_area.controls.append(
            ft.ElevatedButton("Ir para /products/list", on_click=lambda _: page.go("/products/list"))
        )
        main_content_area.controls.append(
            ft.ElevatedButton("Ir para /products/detail/123", on_click=lambda _: page.go("/products/detail/123"))
        )
    elif route.startswith("/settings"):
        main_content_area.controls.append(
            ft.ElevatedButton("Ir para /settings/user", on_click=lambda _: page.go("/settings/user"))
        )
        main_content_area.controls.append(
            ft.ElevatedButton("Ir para /settings/application", on_click=lambda _: page.go("/settings/application"))
        )
    #main_content_area.update()


def main_test_layout(page: ft.Page):
    """Função principal para configurar e exibir a página de teste do layout."""
    page.title = "Teste de Layout e Navegação Flet"
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.horizontal_alignment = ft.CrossAxisAlignment.START

    # 1. Aplica o tema global à página
    app_theme.configure_theme(page)

    def app_router(route_event: ft.RouteChangeEvent):
        """
        Manipulador de rotas. Reconstrói a view principal com base na rota atual.
        Isso garante que a NavigationRail e o NavigationDrawer reflitam o estado correto.
        """
        current_route = page.route # A rota já foi atualizada pelo Flet
        print(f"Navegando para: {current_route}")

        page.views.clear() # Limpa as views anteriores (estratégia de navegação com Views)

        # 2. Cria a AppBar
        # A função create_app_bar já está no seu layout.py
        app_bar = layout.create_app_bar(page, app_title="Demonstração do Layout")

        # 3. Cria e atribui o NavigationDrawer à página
        # A função create_navigation_drawer também está no seu layout.py
        # Ela usa _find_nav_index_for_route para definir o item selecionado.
        page.drawer = layout.create_navigation_drawer(page, current_route)

        # Adiciona um botão de "menu" à AppBar para abrir o NavigationDrawer
        if page.drawer: # Se um drawer foi criado
            app_bar.leading = ft.IconButton(
                ft.Icons.MENU,
                tooltip="Abrir menu de navegação",
                on_click=lambda _: setattr(page.drawer, "open", True) # Abre o drawer
            )
            app_bar.leading_width = 50 # Ajusta o espaço para o ícone do menu

        # 4. Cria a NavigationRail
        # A função create_navigation_rail está no seu layout.py
        # Ela também usa _find_nav_index_for_route para o selected_index.
        nav_rail = layout.create_navigation_rail(page, current_route)

        # Atualiza o conteúdo da área principal com base na rota
        update_main_content_for_route(page, current_route)

        # Monta a View principal
        page.views.append(
            ft.View(
                route=current_route, # Define a rota da view
                controls=[
                    ft.Row(
                        [
                            nav_rail, # NavigationRail à esquerda
                            ft.VerticalDivider(width=1),
                            main_content_area, # Conteúdo dinâmico à direita
                        ],
                        expand=True,
                        vertical_alignment=ft.CrossAxisAlignment.START, # Alinha NavRail e conteúdo no topo
                    )
                ],
                appbar=app_bar,
                drawer=page.drawer, # Associa o drawer à view
                bottom_appbar=layout.create_footer(page) # 5. Cria o Footer
            )
        )
        page.update()

    # Define o manipulador de rotas e a rota inicial
    page.on_route_change = app_router
    # Define uma rota inicial. Se page.route for None (primeira carga), usa "/home".
    initial_route = page.route if page.route and page.route != "/" else "/home"
    page.go(initial_route)


def run_test_desktop():
    """Inicia o aplicativo de teste em modo Desktop."""
    print("Iniciando teste em modo Desktop...")
    ft.app(
        target=main_test_layout,
        # assets_dir="assets" # Descomente se você tiver assets (fontes, imagens)
    )

def run_test_web(port_number=8550):
    """Inicia o aplicativo de teste em modo Web."""
    print(f"Iniciando teste em modo Web. Acesse http://localhost:{port_number}")
    ft.app(
        target=main_test_layout,
        view=ft.WEB_BROWSER,
        port=port_number,
        # assets_dir="assets" # Descomente se você tiver assets
    )

if __name__ == "__main__":
    print("Selecione o modo de execução do teste de layout:")
    print("  1. Modo Desktop")
    print("  2. Modo Web")
    choice = input("Digite sua escolha (1 ou 2): ")

    if choice == "1":
        run_test_desktop()
    elif choice == "2":
        # Você pode alterar o número da porta se necessário
        run_test_web(port_number=8551)
    else:
        print("Escolha inválida. Encerrando.")