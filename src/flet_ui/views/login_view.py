# src/flet_ui/views/login_view.py

import flet as ft
from typing import Optional, Dict, Any

from src.services.firebase_client import FbManagerAuth # Ajuste o caminho se FbManagerAuth estiver em outro lugar
from src.flet_ui.components import show_snackbar, show_loading_overlay, hide_loading_overlay, ValidatedTextField
from src.flet_ui import theme # Para cores de erro, etc.
from src.logger.logger import LoggerSetup

# Obtém uma instância de logger para este módulo
# A inicialização do LoggerSetup deve ocorrer em run.py ou app.py antes daqui
_logger = LoggerSetup.get_logger(__name__)


# Validador simples de email (pode ser mais robusto)
def email_validator(email: str) -> Optional[str]:
    if not email:
        return "O email não pode estar vazio."
    if "@" not in email or "." not in email: # Validação muito básica
        return "Formato de email inválido."
    return None

# Validador de senha
def password_validator(password: str) -> Optional[str]:
    if not password:
        return "A senha não pode estar vazia."
    if len(password) < 6:
        return "A senha deve ter pelo menos 6 caracteres."
    return None


def create_login_view(page: ft.Page) -> ft.View:
    """
    Cria e retorna a ft.View para a tela de login.
    """
    _logger.info("Criando a view de Login.")

    auth_manager = FbManagerAuth() # Instancia o gerenciador de autenticação

    email_field = ValidatedTextField(
        label="Email",
        hint_text="Digite seu email",
        keyboard_type=ft.KeyboardType.EMAIL,
        validator=email_validator,
        autofocus=True,
        #capitalization=ft.TextCapitalization.
    )

    password_field = ValidatedTextField(
        label="Senha",
        hint_text="Digite sua senha",
        password=True,
        can_reveal_password=True,
        validator=password_validator,
        on_submit = lambda e: handle_login_click(e)
    )

    remember_me_checkbox = ft.Checkbox(label="Lembrar de mim", value=True) # Default True

    # --- Função de Callback para o Botão de Login ---
    def handle_login_click(e: ft.ControlEvent):
        _logger.info("Botão de login clicado.")
        page.update() 

        is_email_valid = email_field.validate(show_error=True)
        is_password_valid = password_field.validate(show_error=True)

        if not is_email_valid or not is_password_valid:
            show_snackbar(page, "Por favor, corrija os erros no formulário.", color=theme.COLOR_ERROR)
            _logger.warning("Tentativa de login com formulário inválido.")
            return

        email = email_field.value or ""
        password = password_field.value or ""

        show_loading_overlay(page, "Autenticando...")
        _logger.info(f"Tentando autenticar usuário: {email}")

        try:
            auth_response: Optional[Dict[str, Any]] = auth_manager.authenticate_user_get_all_data(email, password)
            hide_loading_overlay(page)

            if auth_response and auth_response.get("idToken") and auth_response.get("localId"):
                id_token = auth_response["idToken"]
                user_id = auth_response["localId"]
                user_email_from_auth = auth_response.get("email", email) # Email confirmado pela auth
                display_name = auth_response.get("displayName", user_email_from_auth)

                _logger.info(f"Usuário {user_id} ({display_name}) autenticado com sucesso.")
                show_snackbar(page, f"Bem-vindo, {display_name}!", color=theme.COLOR_SUCCESS)

                # Limpar dados de autenticação antigos antes de definir novos
                if page.client_storage: # Verifica se client_storage está disponível
                    page.client_storage.remove("auth_id_token")
                    page.client_storage.remove("auth_user_id")
                    page.client_storage.remove("auth_user_email")
                    page.client_storage.remove("auth_display_name")
                
                if page.session.contains_key("auth_id_token"):
                    page.session.remove("auth_id_token")
                if page.session.contains_key("auth_user_id"):
                    page.session.remove("auth_user_id")
                if page.session.contains_key("auth_user_email"):
                    page.session.remove("auth_user_email")
                if page.session.contains_key("auth_display_name"):
                    page.session.remove("auth_display_name")

                # Armazenar na sessão Flet por padrão
                _logger.info("Armazenando token e ID do usuário na sessão Flet.")
                page.session.set("auth_id_token", id_token)
                page.session.set("auth_user_id", user_id)
                page.session.set("auth_user_email", user_email_from_auth)
                page.session.set("auth_display_name", display_name)

                # Se "Lembrar de mim" estiver marcado e client_storage disponível,
                # também armazena no client_storage.
                if remember_me_checkbox.value and page.client_storage:
                    _logger.info("Opção 'Lembrar de mim' ativa. Armazenando também no client_storage.")
                    page.client_storage.set("auth_id_token", id_token)
                    page.client_storage.set("auth_user_id", user_id)
                    page.client_storage.set("auth_user_email", user_email_from_auth)
                    page.client_storage.set("auth_display_name", display_name)
                elif remember_me_checkbox.value and not page.client_storage:
                    _logger.warning("Opção 'Lembrar de mim' ativa, mas client_storage não está disponível (app não é Web/Desktop?).")


                LoggerSetup.set_cloud_user_context(id_token, user_id)
                _logger.info(f"Contexto do logger de nuvem atualizado para usuário {user_id}.")

                page.go("/home")

            else: # Falha na autenticação
                # ... (lógica de mensagem de erro como antes) ...
                error_message = "Email ou senha inválidos."
                if isinstance(auth_response, dict) and auth_response.get("error"):
                    api_error = auth_response["error"].get("message", "ERRO_DESCONHECIDO_API")
                    if api_error == "EMAIL_NOT_FOUND" or api_error == "INVALID_PASSWORD" or api_error == "INVALID_LOGIN_CREDENTIALS":
                        pass 
                    elif api_error == "USER_DISABLED":
                        error_message = "Esta conta de usuário foi desabilitada."
                    else: 
                        error_message = f"Erro de autenticação: {api_error}"
                
                _logger.warning(f"Falha na autenticação para {email}. Erro: {error_message}")
                show_snackbar(page, error_message, color=theme.COLOR_ERROR, duration=7000)

        except Exception as ex:
            hide_loading_overlay(page)
            _logger.error(f"Erro inesperado durante o login: {ex}", exc_info=True)
            show_snackbar(page, "Ocorreu um erro inesperado. Tente novamente.", color=theme.COLOR_ERROR)

    login_button = ft.ElevatedButton(
        text="Entrar",
        on_click=handle_login_click,
        icon=ft.icons.LOGIN,
        width=200, # Largura do botão
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
    )

    # Link para "Esqueci minha senha" (implementação futura)
    def handle_forgot_password_click(e):
        email_val = email_field.value or ""
        if not email_val or not email_validator(email_val) is None:
            show_snackbar(page, "Por favor, digite um email válido no campo Email para redefinir a senha.", color=theme.COLOR_WARNING, duration=5000)
            email_field.focus()
            return

        show_loading_overlay(page, "Enviando email de redefinição...")
        _logger.info(f"Solicitando redefinição de senha para: {email_val}")
        try:
            success = auth_manager.send_password_reset_email(email_val)
            hide_loading_overlay(page)
            if success:
                show_snackbar(page, f"Email de redefinição enviado para {email_val}. Verifique sua caixa de entrada.", color=theme.COLOR_SUCCESS, duration=7000)
            else:
                show_snackbar(page, "Não foi possível enviar o email de redefinição. Verifique o email ou tente mais tarde.", color=theme.COLOR_ERROR, duration=7000)
        except Exception as ex_reset:
            hide_loading_overlay(page)
            _logger.error(f"Erro ao solicitar redefinição de senha para {email_val}: {ex_reset}", exc_info=True)
            show_snackbar(page, "Ocorreu um erro ao solicitar a redefinição.", color=theme.COLOR_ERROR)


    forgot_password_button = ft.TextButton(
        "Esqueci minha senha",
        on_click=handle_forgot_password_click
    )

    # Link para "Criar conta" (implementação futura)
    def handle_create_account_click(e):
        _logger.info("Botão 'Criar conta' clicado. Navegando para /signup.")
        page.go("/signup") 

    create_account_button = ft.TextButton(
        "Não tem conta? Crie uma aqui",
        on_click=handle_create_account_click
    )

    # --- Layout da View de Login ---
    login_card_content = ft.Column(
        [
            ft.Text("Login", size=28, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
            ft.Container(height=20), # Espaçador
            email_field,
            password_field,
            ft.Row([remember_me_checkbox], alignment=ft.MainAxisAlignment.START),
            ft.Container(height=10),
            ft.Row([login_button], alignment=ft.MainAxisAlignment.CENTER),
            ft.Container(height=10),
            ft.Row([forgot_password_button], alignment=ft.MainAxisAlignment.CENTER),
            ft.Row([create_account_button], alignment=ft.MainAxisAlignment.CENTER),
        ],
        width=400, # Largura do card de login
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        spacing=10
    )

    login_card = ft.Card(
        content=ft.Container(
            content=login_card_content,
            padding=ft.padding.symmetric(vertical=30, horizontal=25)
        ),
        elevation=8,
        # margin=20 # Margem em volta do card
    )

    # A view de login não terá AppBar ou NavigationRail, geralmente é centralizada.
    return ft.View(
        route="/login",
        controls=[
            ft.Container( # Container para centralizar o card
                content=login_card,
                alignment=ft.alignment.center,
                expand=True, # Ocupa todo o espaço disponível
                # bgcolor=ft.colors.BLUE_GREY_50 # Um fundo suave, opcional
            )
        ],
        vertical_alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        padding=20
    )

