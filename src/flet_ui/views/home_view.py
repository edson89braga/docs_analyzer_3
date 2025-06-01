# src/flet_ui/views/home_view.py

import flet as ft
import os
from src.settings import ASSETS_DIR_ABS, PATH_IMAGE_LOGO_DEPARTAMENTO

from src.logger.logger import LoggerSetup
_logger = LoggerSetup.get_logger(__name__)


def create_home_view(page: ft.Page) -> ft.Control: # Retorna ft.Control
    """
    Cria e retorna o *conteúdo* para a tela inicial (home).
    """
    _logger.info("Criando o conteúdo da view Home (imagem departamento).")

    try:
        department_logo = ft.Image(
            src=PATH_IMAGE_LOGO_DEPARTAMENTO,
            width=300, # Ajuste o tamanho conforme necessário
            height=300,
            fit=ft.ImageFit.CONTAIN,
            error_content=ft.Text("Erro ao carregar imagem do logo.", color=ft.colors.RED)
        )
    except Exception as e:
        _logger.error(f"Erro ao tentar carregar a imagem do logo '{PATH_IMAGE_LOGO_DEPARTAMENTO}': {e}")
        department_logo = ft.Container(
            content=ft.Text(f"Não foi possível carregar a imagem do logo em: {PATH_IMAGE_LOGO_DEPARTAMENTO}",
                            color=ft.colors.ORANGE_ACCENT_700, style=ft.TextThemeStyle.BODY_LARGE),
            padding=20,
            alignment=ft.alignment.center
        )

    # Conteúdo principal da página Home (agora apenas a imagem centralizada)
    main_content = ft.Column(
        [
            department_logo
        ],
        alignment=ft.MainAxisAlignment.CENTER, # Centraliza verticalmente
        horizontal_alignment=ft.CrossAxisAlignment.CENTER, # Centraliza horizontalmente
        expand=True
    )

    # Não retorna ft.View, apenas o controle principal do conteúdo
    return main_content


def OLD_create_home_view(page: ft.Page) -> ft.View:
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

