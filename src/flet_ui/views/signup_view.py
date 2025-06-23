# src/flet_ui/views/signup_view.py

import flet as ft
from typing import Optional

from src.settings import ALLOWED_EMAIL_DOMAINS
from src.services.firebase_client import FbManagerAuth
from src.flet_ui.components import show_snackbar, show_loading_overlay, hide_loading_overlay, ValidatedTextField
from src.flet_ui import theme

import logging
logger = logging.getLogger(__name__)

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
    logger.info("Criando a view de Signup.")
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
        logger.info("Botão de signup clicado.")
        page.update()

        is_display_name_valid = display_name_field.validate(show_error=True)
        is_email_valid = email_field.validate(show_error=True)
        is_password_valid = password_field.validate(show_error=True)
        is_confirm_password_valid = confirm_password_field.validate(show_error=True) # Valida se coincide

        # Se a validação básica do formato de email já falhou, não prossiga.
        if not is_email_valid:
            show_snackbar(page, "Por favor, corrija os erros no formulário.", color=theme.COLOR_ERROR)
            return
        
        email = email_field.value or ""

        try:
            domain = email.split('@')[1]
            if domain.lower() not in [d.lower() for d in ALLOWED_EMAIL_DOMAINS]:
                error_msg = f"Cadastro permitido apenas para emails do(s) domínio(s): {', '.join(ALLOWED_EMAIL_DOMAINS)}"
                show_snackbar(page, error_msg, color=theme.COLOR_ERROR, duration=7000)
                email_field.text_field.error_text = "Domínio de email não permitido."
                email_field.text_field.update()
                logger.warning(f"Tentativa de cadastro com domínio não permitido: {domain}")
                return
            else:
                # Limpa o erro de domínio se o usuário corrigiu
                email_field.text_field.error_text = None
                email_field.text_field.update()
        except IndexError:
            # O validador de formato de email já deve pegar isso, mas é uma segurança extra.
            show_snackbar(page, "Formato de email inválido.", color=theme.COLOR_ERROR)
            return
        
        if not all([is_display_name_valid, is_password_valid, is_confirm_password_valid]):
            show_snackbar(page, "Por favor, corrija os erros no formulário.", color=theme.COLOR_ERROR)
            logger.warning("Tentativa de signup com formulário inválido.")
            return

        display_name = display_name_field.value or ""
        email = email_field.value or ""
        password = password_field.value or ""

        show_loading_overlay(page, "Criando conta...")
        logger.info(f"Tentando criar conta para: {email} com nome {display_name}")

        try:
            creation_response = auth_manager.create_user(email, password, display_name)
            hide_loading_overlay(page)

            if creation_response and creation_response.get("localId"): # Sucesso
                logger.info(f"Conta criada com sucesso para {email}. User ID: {creation_response['localId']}")
                success_message = (
                    "Conta criada com sucesso! Um email de verificação foi enviado para "
                    f"{email}. Verifique sua caixa de entrada para ativar a conta."
                )
                show_snackbar(page, success_message, color=theme.COLOR_SUCCESS, duration=12000)
                page.go("/login")
            
            elif creation_response and creation_response.get("error"): # Falha da API Firebase
                api_error_code = creation_response.get("error", "UNKNOWN_ERROR")
                
                # Mapeia códigos de erro da API para mensagens amigáveis
                if api_error_code == "EMAIL_EXISTS":
                    error_message = "Este email já está em uso por outra conta."
                elif api_error_code.startswith("WEAK_PASSWORD"):
                    error_message = "A senha é muito fraca. Tente uma senha mais forte."
                elif api_error_code == "INVALID_EMAIL":
                    error_message = "O formato do email fornecido é inválido."
                else:
                    error_message = "Não foi possível criar a conta. Por favor, tente novamente."
                    logger.error(f"Erro não mapeado da API de signup: {api_error_code}")
                
                logger.warning(f"Falha na criação da conta para {email}. Erro: {api_error_code}")
                show_snackbar(page, error_message, color=theme.COLOR_ERROR, duration=7000)

            elif creation_response and creation_response.get("error_type"): # Falha de conexão/requisição
                error_type = creation_response.get("error_type")
                if error_type == "CONNECTION_ERROR":
                    show_snackbar(page, "Erro de conexão. Verifique sua internet/proxy e tente novamente.", color=theme.COLOR_ERROR, duration=7000)
                else:
                    show_snackbar(page, "Ocorreu um erro de comunicação. Tente novamente mais tarde.", color=theme.COLOR_ERROR, duration=7000)

            else: # Outro tipo de falha
                show_snackbar(page, "Não foi possível criar a conta. Resposta inesperada do servidor.", color=theme.COLOR_ERROR, duration=7000)
                logger.error(f"Resposta inesperada ao criar usuário: {creation_response}")

        except Exception as ex:
            hide_loading_overlay(page)
            logger.error(f"Erro inesperado durante o signup: {ex}", exc_info=True)
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

    return ft.Container(
                content=signup_card,
                alignment=ft.alignment.center,
                expand=True,
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

