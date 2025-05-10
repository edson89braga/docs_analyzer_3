# src/flet_ui/views/signup_view.py

import flet as ft
from typing import Optional

from src.services.firebase_client import FbManagerAuth
from src.flet_ui.components import show_snackbar, show_loading_overlay, hide_loading_overlay, ValidatedTextField
from src.flet_ui import theme
from src.logger.logger import LoggerSetup

_logger = LoggerSetup.get_logger(__name__)

# Validadores (podem ser movidos para um utils_validators.py se usados em mais lugares)
def email_validator(email: str) -> Optional[str]:
    if not email: return "O email não pode estar vazio."
    if "@" not in email or "." not in email: return "Formato de email inválido."
    return None

def password_validator(password: str) -> Optional[str]:
    if not password: return "A senha não pode estar vazia."
    if len(password) < 6: return "A senha deve ter pelo menos 6 caracteres."
    return None

def display_name_validator(name: str) -> Optional[str]:
    if not name: return "O nome de exibição não pode estar vazio."
    if len(name) < 3: return "O nome de exibição deve ter pelo menos 3 caracteres."
    return None

def create_signup_view(page: ft.Page) -> ft.View:
    """
    Cria e retorna a ft.View para a tela de criação de conta (signup).
    """
    _logger.info("Criando a view de Signup.")
    auth_manager = FbManagerAuth()

    display_name_field = ValidatedTextField(
        label="Nome de Exibição",
        hint_text="Como você gostaria de ser chamado?",
        validator=display_name_validator,
        autofocus=True,
        capitalization=ft.TextCapitalization.WORDS
    )

    email_field = ValidatedTextField(
        label="Email",
        hint_text="Digite seu email",
        keyboard_type=ft.KeyboardType.EMAIL,
        validator=email_validator,
        #capitalization=ft.TextCapitalization.
    )

    password_field = ValidatedTextField(
        label="Senha",
        hint_text="Crie uma senha (mín. 6 caracteres)",
        password=True,
        can_reveal_password=True,
        validator=password_validator
    )

    confirm_password_field = ValidatedTextField(
        label="Confirmar Senha",
        hint_text="Digite a senha novamente",
        password=True,
        can_reveal_password=True,
        validator=lambda val: "As senhas não coincidem." if val != password_field.value else None
    )

    def handle_signup_click(e: ft.ControlEvent):
        _logger.info("Botão de signup clicado.")
        page.update()

        is_display_name_valid = display_name_field.validate(show_error=True)
        is_email_valid = email_field.validate(show_error=True)
        is_password_valid = password_field.validate(show_error=True)
        is_confirm_password_valid = confirm_password_field.validate(show_error=True) # Valida se coincide

        if not all([is_display_name_valid, is_email_valid, is_password_valid, is_confirm_password_valid]):
            show_snackbar(page, "Por favor, corrija os erros no formulário.", color=theme.COLOR_ERROR)
            _logger.warning("Tentativa de signup com formulário inválido.")
            return

        display_name = display_name_field.value or ""
        email = email_field.value or ""
        password = password_field.value or ""

        show_loading_overlay(page, "Criando conta...")
        _logger.info(f"Tentando criar conta para: {email} com nome {display_name}")

        try:
            creation_response = auth_manager.create_user(email, password, display_name)
            hide_loading_overlay(page)

            if creation_response and creation_response.get("localId"): # Sucesso se tem localId
                _logger.info(f"Conta criada com sucesso para {email}. User ID: {creation_response['localId']}")
                show_snackbar(page, "Conta criada com sucesso! Você será redirecionado para o login.", color=theme.COLOR_SUCCESS, duration=5000)
                # Opcional: Fazer login automático aqui e ir para /home,
                # ou redirecionar para /login para o usuário entrar.
                # Redirecionar para login é mais simples por agora.
                page.go("/login")
            else:
                error_message = "Não foi possível criar a conta."
                if isinstance(creation_response, dict) and creation_response.get("error"):
                    api_error = creation_response["error"].get("message", "ERRO_DESCONHECIDO_API")
                    if api_error == "EMAIL_EXISTS":
                        error_message = "Este email já está em uso."
                    elif api_error.startswith("WEAK_PASSWORD"):
                        error_message = "A senha é muito fraca (mínimo 6 caracteres)."
                    else:
                        error_message = f"Erro ao criar conta: {api_error}"
                
                _logger.warning(f"Falha na criação da conta para {email}. Erro: {error_message}")
                show_snackbar(page, error_message, color=theme.COLOR_ERROR, duration=7000)

        except Exception as ex:
            hide_loading_overlay(page)
            _logger.error(f"Erro inesperado durante o signup: {ex}", exc_info=True)
            show_snackbar(page, "Ocorreu um erro inesperado. Tente novamente.", color=theme.COLOR_ERROR)

    signup_button = ft.ElevatedButton(
        text="Criar Conta",
        on_click=handle_signup_click,
        icon=ft.icons.PERSON_ADD,
        width=200,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
    )

    login_link_button = ft.TextButton(
        "Já tem uma conta? Faça login",
        on_click=lambda _: page.go("/login")
    )

    signup_card_content = ft.Column(
        [
            ft.Text("Criar Nova Conta", size=28, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
            ft.Container(height=20),
            display_name_field,
            email_field,
            password_field,
            confirm_password_field,
            ft.Container(height=20),
            ft.Row([signup_button], alignment=ft.MainAxisAlignment.CENTER),
            ft.Container(height=10),
            ft.Row([login_link_button], alignment=ft.MainAxisAlignment.CENTER),
        ],
        width=400,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        spacing=10
    )

    signup_card = ft.Card(
        content=ft.Container(
            content=signup_card_content,
            padding=ft.padding.symmetric(vertical=30, horizontal=25)
        ),
        elevation=8,
    )

    return ft.View(
        route="/signup",
        controls=[
            ft.Container(
                content=signup_card,
                alignment=ft.alignment.center,
                expand=True,
            )
        ],
        vertical_alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        padding=20
    )

