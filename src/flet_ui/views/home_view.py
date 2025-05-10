# src/flet_ui/views/home_view.py

import flet as ft
from src.logger.logger import LoggerSetup

_logger = LoggerSetup.get_logger(__name__)

def create_home_view(page: ft.Page) -> ft.View:
    """
    Cria e retorna a ft.View para a tela inicial (home) após o login.
    """
    _logger.info("Criando a view Home.")

    # Recupera informações do usuário da sessão ou client_storage
    display_name = page.session.get("auth_display_name") or \
                   (page.client_storage.get("auth_display_name") if page.client_storage else "Usuário")
    user_email = page.session.get("auth_user_email") or \
                 (page.client_storage.get("auth_user_email") if page.client_storage else "N/A")

    welcome_text = ft.Text(f"Bem-vindo(a) à Página Inicial, {display_name}!", size=24, weight=ft.FontWeight.BOLD)
    email_text = ft.Text(f"Seu email registrado: {user_email}", size=16)
    
    # Conteúdo principal da página Home
    main_content = ft.Column(
        [
            welcome_text,
            email_text,
            ft.Container(height=20),
            ft.Text("Este é o conteúdo principal da sua aplicação após o login."),
            ft.Text("Você pode adicionar aqui os componentes da sua dashboard ou funcionalidade principal."),
            # Exemplo de como poderia ser um link para outra seção (requer rota e view)
            # ft.ElevatedButton("Ir para Produtos", on_click=lambda _: page.go("/products"))
        ],
        alignment=ft.MainAxisAlignment.START,
        horizontal_alignment=ft.CrossAxisAlignment.START,
        spacing=15,
        expand=True # Para ocupar o espaço disponível na coluna
    )
    
    # A view de home usará o layout padrão (AppBar, NavigationDrawer, etc.)
    # que é adicionado pelo router.
    return ft.View(
        route="/home",
        controls=[
            ft.Container( # Container para o conteúdo principal com padding
                content=main_content,
                padding=ft.padding.all(20), # Adiciona padding em volta do conteúdo
                expand=True # Garante que o container do conteúdo expanda
            )
        ]
        # AppBar, Drawer, etc., são adicionados pelo router
    )

