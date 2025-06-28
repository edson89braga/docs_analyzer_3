# src/flet_ui/views/login_view.py

import flet as ft
import time, threading, jwt
from typing import Optional, Dict, Any

from src.settings import PATH_IMAGE_LOGO_DEPARTAMENTO, APP_TITLE, APP_VERSION

from src.services.firebase_client import FbManagerAuth # Ajuste o caminho se FbManagerAuth estiver em outro lugar
#from src.flet_ui.layout import show_proxy_settings_dialog
from src.flet_ui.components import show_snackbar, show_loading_overlay, hide_loading_overlay, ValidatedTextField
from src.flet_ui import theme # Para cores de erro, etc.
from src.logger.logger import LoggerSetup

import logging
logger = logging.getLogger(__name__)


# Validador simples de email (pode ser mais robusto)
def email_validator(email: str) -> Optional[str]:
    """
    Valida o formato de um endereço de email.

    Args:
        email (str): O endereço de email a ser validado.

    Returns:
        Optional[str]: Uma mensagem de erro se o email for inválido, caso contrário, None.
    """
    if not email:
        return "O email não pode estar vazio."
    if "@" not in email or "." not in email: # Validação muito básica
        return "Formato de email inválido."
    return None

# Validador de senha
def password_validator(password: str) -> Optional[str]:
    """
    Valida a complexidade de uma senha.

    Args:
        password (str): A senha a ser validada.

    Returns:
        Optional[str]: Uma mensagem de erro se a senha for inválida, caso contrário, None.
    """
    if not password:
        return "A senha não pode estar vazia."
    if len(password) < 6:
        return "A senha deve ter pelo menos 6 caracteres."
    return None


def create_login_view(page: ft.Page) -> ft.View:
    """
    Cria e retorna a ft.View para a tela de login, incluindo campos para email e senha,
    opções de "Lembrar de mim", e links para redefinição de senha e criação de conta.

    Args:
        page (ft.Page): A página Flet atual.

    Returns:
        ft.View: A view completa da tela de login.
    """
    from src.services.firebase_client import FirebaseClientStorage
    logger.info("Criando a view de Login.")

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

    #proxy_settings_button = ft.ElevatedButton(
    #    "Configurações de Proxy",
    #    icon=ft.Icons.NETWORK_CHECK_ROUNDED,
    #    #icon=ft.Icons.SETTINGS_ETHERNET_ROUNDED,
    #    on_click=lambda _: show_proxy_settings_dialog(page)
    #)

    def _resend_verification_email(id_token: str):
        """
        Reenvia o email de verificação para o usuário.

        Args:
            id_token (str): O ID token do usuário autenticado.
        """
        show_loading_overlay(page, "Reenviando email de verificação...")
        success = auth_manager.send_verification_email(id_token)
        hide_loading_overlay(page)
        if success:
            show_snackbar(page, "Novo email de verificação enviado. Verifique sua caixa de entrada.", color=theme.COLOR_SUCCESS, duration=8000)
        else:
            show_snackbar(page, "Não foi possível reenviar o email de verificação. Tente novamente mais tarde.", color=theme.COLOR_ERROR)

    # --- Função de Callback para o Botão de Login ---
    def handle_login_click(e: ft.ControlEvent):
        """
        Manipula o evento de clique do botão de login.
        Realiza a validação dos campos, autentica o usuário e gerencia o estado da sessão.

        Args:
            e (ft.ControlEvent): O evento de controle que disparou a função.
        """
        logger.info("Botão de login clicado.")
        page.update()

        is_email_valid = email_field.validate(show_error=True)
        is_password_valid = password_field.validate(show_error=True)

        if not is_email_valid or not is_password_valid:
            show_snackbar(page, "Por favor, corrija os erros no formulário.", color=theme.COLOR_ERROR)
            logger.warning("Tentativa de login com formulário inválido.")
            return

        email = email_field.value or ""
        password = password_field.value or ""

        show_loading_overlay(page, "Autenticando...")
        logger.info(f"Tentando autenticar usuário: {email}")

        try:
            auth_response: Optional[Dict[str, Any]] = auth_manager.authenticate_user_get_all_data(email, password)
            hide_loading_overlay(page)
            logger.debug(f"Resposta da autenticação: {auth_response}")
            if auth_response and auth_response.get("idToken") and auth_response.get("localId"):
                
                #is_email_verified = auth_response.get("emailVerified", False)
                id_token = auth_response["idToken"]
                
                decoded_and_verified_token = auth_manager.verify_id_token(id_token)
                if not decoded_and_verified_token:
                    logger.error("Falha na verificação da assinatura do token de autenticação. Login abortado por segurança.")
                    show_snackbar(page, "Falha na verificação de segurança da sessão. Tente novamente.", color=theme.COLOR_ERROR)
                    return # Bloqueia o login
                
                is_email_verified = decoded_and_verified_token.get("email_verified", False)
                
                is_admin = decoded_and_verified_token.get("admin", False)
                logger.info(f"Status de Administrador do usuário verificado: {is_admin}")

                #try:
                #    # Decodifica o JWT sem verificar a assinatura (apenas para extrair dados)
                #    # Em produção, você pode querer verificar a assinatura
                #    decoded_token = jwt.decode(id_token, options={"verify_signature": False})
                #    is_email_verified = decoded_token.get("email_verified", False)
                #    _logger.info(f"Email verificado (do token JWT): {is_email_verified}")
                #except Exception as jwt_error:
                #    _logger.error(f"Erro ao decodificar token JWT: {jwt_error}")
                #    # Fallback: usar o valor da resposta da API (se disponível)
                #    is_email_verified = auth_response.get("emailVerified", False)

                if not is_email_verified:
                    logger.warning(f"Tentativa de login bloqueada para {email}: email não verificado.")

                    # Usa o SnackBar global de forma mais avançada
                    snackbar_instance = page.data.get("global_snackbar")
                    if snackbar_instance:
                        snackbar_instance.content = ft.Text(
                            "Sua conta ainda não foi ativada. Verifique seu email para continuar."
                        )
                        snackbar_instance.bgcolor = theme.COLOR_WARNING
                        snackbar_instance.duration = 8000
                        # Adiciona o botão de ação
                        id_token_for_resend = auth_response.get("idToken")
                        if id_token_for_resend:
                            snackbar_instance.action = "REENVIAR EMAIL"
                            snackbar_instance.on_action = lambda _: _resend_verification_email(id_token_for_resend)
                        else:
                            snackbar_instance.action = None
                            snackbar_instance.on_action = None

                        snackbar_instance.open = True
                        page.update()
                    else: # Fallback se o snackbar global não for encontrado
                        show_snackbar(page, "Sua conta ainda não foi ativada. Verifique seu email.", color=theme.COLOR_WARNING, duration=12000)

                    return # Bloqueia o login
            
                id_token = auth_response["idToken"]
                user_id = auth_response["localId"]
                refresh_token = auth_response.get("refreshToken") 
                expires_in = int(auth_response.get("expiresIn", 3600)) # Segundos, default 1h
                id_token_expires_at = time.time() + expires_in - 60 # Timestamp UTC, -60s de buffer

                user_email_from_auth = auth_response.get("email", email) # Email confirmado pela auth
                display_name = auth_response.get("displayName", user_email_from_auth)

                logger.info(f"Usuário {user_id} ({display_name}) autenticado com sucesso.")
                show_snackbar(page, f"Bem-vindo, {display_name}!", color=theme.COLOR_SUCCESS)

                # Limpar dados de autenticação antigos antes de definir novos
                auth_keys_to_clear = [
                    "auth_id_token", "auth_user_id", "auth_user_email", 
                    "auth_display_name", "auth_refresh_token", "auth_id_token_expires_at",
                    "is_admin"
                ]

                if page.client_storage:
                    for key in auth_keys_to_clear:
                        if page.client_storage.contains_key(key): page.client_storage.remove(key)

                for key in auth_keys_to_clear:
                    if page.session.contains_key(key): page.session.remove(key)

                # Armazenar na sessão Flet por padrão
                logger.info("Armazenando token e ID do usuário na sessão Flet.")
                page.session.set("auth_id_token", id_token)
                page.session.set("auth_user_id", user_id)
                page.session.set("is_admin", is_admin)                
                if refresh_token: 
                    page.session.set("auth_refresh_token", refresh_token) 
                page.session.set("auth_id_token_expires_at", id_token_expires_at)
                page.session.set("auth_user_email", user_email_from_auth)
                page.session.set("auth_display_name", display_name)

                # Se "Lembrar de mim" estiver marcado e client_storage disponível,
                # também armazena no client_storage.
                if remember_me_checkbox.value and page.client_storage:
                    logger.info("Opção 'Lembrar de mim' ativa. Armazenando também no client_storage.")
                    page.client_storage.set("auth_id_token", id_token)
                    page.client_storage.set("auth_user_id", user_id)
                    page.client_storage.set("is_admin", is_admin)
                    if refresh_token: 
                        page.client_storage.set("auth_refresh_token", refresh_token)
                    page.client_storage.set("auth_id_token_expires_at", id_token_expires_at)
                    page.client_storage.set("auth_user_email", user_email_from_auth)
                    page.client_storage.set("auth_display_name", display_name)
                elif remember_me_checkbox.value and not page.client_storage:
                    logger.warning("Opção 'Lembrar de mim' ativa, mas client_storage não está disponível (app não é Web/Desktop?).")

                # Chama a função de carregamento de configurações em uma thread
                load_settings_func = page.data.get("load_settings_func")
                if load_settings_func:
                    logger.info("Disparando carregamento de configurações de usuário em background após login.")
                    threading.Thread(target=load_settings_func, args=(page,), daemon=True).start()
                else:
                    logger.error("Função 'load_settings_func' não encontrada em page.data! As configurações do usuário podem não ser carregadas.")

                LoggerSetup.set_cloud_user_context(id_token, user_id)
                # TENTA ADICIONAR CLOUD LOGGING AQUI
                try:
                    if not LoggerSetup._active_cloud_handler_instance:
                        LoggerSetup.add_cloud_logging(
                            user_token_for_client=id_token,
                            user_id_for_client=user_id
                        )
                        logger.info("Cloud logging (cliente) configurado após restaurar sessão.")
                except Exception as e_rcl:
                    logger.error(f"Falha ao configurar cloud logging (cliente) após restaurar sessão: {e_rcl}")

                logger.info(f"Contexto do logger de nuvem atualizado para usuário {user_id}.")

                from src.utils import check_app_version
                check_app_version()

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
                
                logger.warning(f"Falha na autenticação para {email}. Erro: {error_message}")
                show_snackbar(page, error_message, color=theme.COLOR_ERROR, duration=7000)

        except Exception as ex:
            hide_loading_overlay(page)
            logger.error(f"Erro inesperado durante o login: {ex}", exc_info=True)
            show_snackbar(page, "Ocorreu um erro inesperado. Tente novamente.", color=theme.COLOR_ERROR)

    login_button = ft.ElevatedButton(
        text="Entrar",
        on_click=handle_login_click,
        icon=ft.Icons.LOGIN,
        width=200, # Largura do botão
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
    )

    # Link para "Esqueci minha senha" (implementação futura)
    def handle_forgot_password_click(e: ft.ControlEvent):
        """
        Manipula o evento de clique do link "Esqueci minha senha".
        Solicita o envio de um email de redefinição de senha para o email fornecido.

        Args:
            e (ft.ControlEvent): O evento de controle que disparou a função.
        """
        email_val = email_field.value or ""
        if not email_val or not email_validator(email_val) is None:
            show_snackbar(page, "Por favor, digite um email válido no campo Email para redefinir a senha.", color=theme.COLOR_WARNING, duration=5000)
            email_field.focus()
            return

        show_loading_overlay(page, "Enviando email de redefinição...")
        logger.info(f"Solicitando redefinição de senha para: {email_val}")
        try:
            success = auth_manager.send_password_reset_email(email_val)
            hide_loading_overlay(page)
            if success:
                show_snackbar(page, f"Email de redefinição enviado para {email_val}. Verifique sua caixa de entrada.", color=theme.COLOR_SUCCESS, duration=7000)
            else:
                show_snackbar(page, "Não foi possível enviar o email de redefinição. Verifique o email ou tente mais tarde.", color=theme.COLOR_ERROR, duration=7000)
        except Exception as ex_reset:
            hide_loading_overlay(page)
            logger.error(f"Erro ao solicitar redefinição de senha para {email_val}: {ex_reset}", exc_info=True)
            show_snackbar(page, "Ocorreu um erro ao solicitar a redefinição.", color=theme.COLOR_ERROR)

    forgot_password_button = ft.TextButton(
        "Esqueci minha senha",
        on_click=handle_forgot_password_click
    )

    # Link para "Criar conta" (implementação futura)
    def handle_create_account_click(e: ft.ControlEvent):
        """
        Manipula o evento de clique do link "Criar conta".
        Redireciona o usuário para a página de cadastro (/signup).

        Args:
            e (ft.ControlEvent): O evento de controle que disparou a função.
        """
        logger.info("Botão 'Criar conta' clicado. Navegando para /signup.")
        page.go("/signup")

    create_account_button = ft.TextButton(
        "Não tem conta? Crie uma aqui",
        on_click=handle_create_account_click
    )

    # --- Seção Superior: Identidade Visual (reutilizada da home_view) ---
    try:
        department_logo = ft.Image(
            src=PATH_IMAGE_LOGO_DEPARTAMENTO, width=150, height=150,
            fit=ft.ImageFit.CONTAIN,
        )
    except Exception:
        department_logo = ft.Container()

    welcome_title = ft.Text(
        f"Bem-vindo à {APP_TITLE}",
        style=ft.TextThemeStyle.HEADLINE_SMALL, text_align=ft.TextAlign.CENTER,
        weight=ft.FontWeight.BOLD, color=theme.PRIMARY
    )
    version_text = ft.Text(
        f"Versão: {APP_VERSION}",
        style=ft.TextThemeStyle.BODY_MEDIUM,
        text_align=ft.TextAlign.CENTER,
        italic=True,
        color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE)
    )
    header_section = ft.Column(
        [
            department_logo,
            ft.Container(height=15),
            welcome_title,
            ft.Container(height=5),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=5
    )

    # --- Layout da View de Login ---
    login_card_content = ft.Column(
        [
            ft.Text("Login", size=28, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
            ft.Container(height=20), # Espaçador
            email_field,
            password_field,
            ft.Row([remember_me_checkbox], alignment=ft.MainAxisAlignment.START),
            ft.Container(height=15),
            ft.Row([login_button], alignment=ft.MainAxisAlignment.CENTER),
            ft.Container(height=10),
            ft.Row([forgot_password_button], alignment=ft.MainAxisAlignment.CENTER),
            ft.Row([create_account_button], alignment=ft.MainAxisAlignment.CENTER),
            #ft.Container(height=15),
            #ft.Row([proxy_settings_button], alignment=ft.MainAxisAlignment.CENTER),
        ],
        width=400, # Largura do card de login
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        spacing=10, scroll=ft.ScrollMode.ADAPTIVE
    )

    login_card = ft.Card(
        content=ft.Container(
            content=login_card_content,
            padding=ft.padding.symmetric(vertical=30, horizontal=25)
        ),
        elevation=8,
        # margin=20 # Margem em volta do card
    )

    main_layout = ft.Column(
        [
            ft.Container(expand=True), # Espaçador superior para empurrar para o centro
            header_section,
            ft.Container(height=30),
            login_card,
            ft.Container(height=40, expand=True), # Espaçador inferior
            version_text
        ],
        expand=True,
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=0,
        scroll=ft.ScrollMode.ADAPTIVE # Permite scroll se o conteúdo exceder a tela
    )

    return main_layout

    return ft.Container( # Container para centralizar o card
                content=login_card,
                alignment=ft.alignment.center,
                expand=True, # Ocupa todo o espaço disponível
                # bgcolor=ft.Colors.BLUE_GREY_50 # Um fundo suave, opcional
            )

    return ft.View(
        route="/login",
        controls=[
            ft.Container( # Container para centralizar o card
                content=login_card,
                alignment=ft.alignment.center,
                expand=True, # Ocupa todo o espaço disponível
                # bgcolor=ft.Colors.BLUE_GREY_50 # Um fundo suave, opcional
            )
        ],
        vertical_alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        padding=20
    )

