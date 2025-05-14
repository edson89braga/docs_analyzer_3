# src/flet_ui/views/profile_view.py

from turtle import bgcolor
import flet as ft
from typing import Optional

from src.services.firebase_client import FbManagerAuth
from src.flet_ui.components import (
    show_snackbar, 
    show_loading_overlay, 
    hide_loading_overlay,
    show_confirmation_dialog,
    ValidatedTextField,
    CardWithHeader
)
from src.flet_ui import theme

from src.logger.logger import LoggerSetup
_logger = LoggerSetup.get_logger(__name__)

# Validador de senha (reutilizado)
def password_validator(password: str) -> Optional[str]:
    if not password: return "A senha não pode estar vazia."
    if len(password) < 6: return "A senha deve ter pelo menos 6 caracteres."
    return None

def display_name_validator(name: str) -> Optional[str]: # Reutilizado do signup
    if not name: return "O nome de exibição não pode estar vazio."
    if len(name) < 3: return "O nome de exibição deve ter pelo menos 3 caracteres."
    return None

def create_profile_view(page: ft.Page) -> ft.View:
    """
    Cria e retorna a ft.View para a tela de perfil do usuário.
    """
    _logger.info("Criando a view de Perfil.")
    auth_manager = FbManagerAuth()

    # Recupera informações do usuário da sessão
    user_id_token_initial  = page.session.get("auth_id_token")
    current_display_name  = page.session.get("auth_display_name") or "N/A"
    user_email = page.session.get("auth_user_email") or "N/A"

    if not user_id_token_initial :
        _logger.error("Token de usuário não encontrado na sessão ao tentar criar view de perfil. Redirecionando para login.")
        # Idealmente, o router já deveria ter bloqueado isso.
        # Mas como uma salvaguarda, podemos forçar o redirecionamento.
        page.go("/login") 
        # Retorna uma view vazia ou com mensagem de erro, pois page.go() é assíncrono.
        return ft.View(
            route="/profile", 
            controls=[ft.Text("Erro: Usuário não autenticado. Redirecionando...")]
        )

    def handle_delete_account_click(e):
        _logger.info("Botão 'Excluir Conta' clicado.")

        show_confirmation_dialog(
            page,
            title="Confirmar Exclusão de Conta",
            content=ft.Column([
                ft.Text("Esta ação é irreversível! Todos os seus dados associados à conta serão perdidos."),
                ft.Text("Você tem certeza que deseja excluir sua conta permanentemente?")
            ]),
            confirm_text="Sim, Excluir Minha Conta",
            on_confirm=confirm_delete_account
        )

    def handle_change_password(e):
        
        _logger.info("Tentando alterar senha do perfil.")
        if not new_password_field.validate(show_error=True) or \
           not confirm_new_password_field.validate(show_error=True):
            show_snackbar(page, "Por favor, corrija os erros no formulário de senha.", color=theme.COLOR_ERROR)
            return

        new_password = new_password_field.value or ""
        
        show_loading_overlay(page, "Alterando senha...")
        try:
            # Agora auth_manager.change_password recebe 'page'
            success_or_error_dict = auth_manager.change_password(page, new_password)
            hide_loading_overlay(page)

            if success_or_error_dict is True: # Sucesso direto
                show_snackbar(page, "Senha alterada com sucesso!", color=theme.COLOR_SUCCESS)
                # ... (limpar campos como antes) ...
                new_password_field.value = "" 
                confirm_new_password_field.value = ""
                new_password_field.text_field.error_text = None 
                confirm_new_password_field.text_field.error_text = None
                page.update() 
                _logger.info(f"Senha alterada para usuário {page.session.get('auth_user_id')}")
            elif isinstance(success_or_error_dict, dict) and success_or_error_dict.get("error"):
                error_type = success_or_error_dict.get("error")
                if error_type == "CREDENTIAL_TOO_OLD_RELOGIN_REQUIRED":
                    # O método change_password já deve ter mostrado o snackbar e chamado handle_logout
                    _logger.warning("Alteração de senha requer re-login (tratado por change_password).")
                elif error_type == "REFRESH_FAILED_LOGOUT" or error_type == "NO_TOKEN_SESSION_LOGOUT":
                    # O logout já foi forçado
                     _logger.warning("Alteração de senha falhou devido a problema de token/sessão (logout forçado).")
                else:
                    # Outros erros da API ou falhas
                    show_snackbar(page, f"Não foi possível alterar a senha: {success_or_error_dict.get('details', error_type)}", color=theme.COLOR_ERROR)
                    _logger.warning(f"Falha ao alterar senha via API: {error_type}")
            else: # Caso inesperado de retorno
                show_snackbar(page, "Não foi possível alterar a senha. Resposta inesperada.", color=theme.COLOR_ERROR)
                _logger.error(f"Retorno inesperado de auth_manager.change_password: {success_or_error_dict}")

        except Exception as ex: # Captura exceções não HTTPError levantadas por _execute_sensitive_action
            hide_loading_overlay(page)
            _logger.error(f"Erro geral ao alterar senha: {ex}", exc_info=True)
            show_snackbar(page, "Ocorreu um erro ao tentar alterar a senha.", color=theme.COLOR_ERROR)

    def handle_update_profile(e: ft.ControlEvent): # Reescrita integral
        _logger.info("Botão 'Salvar Novo Nome' clicado.")
        
        if not edit_display_name_field.validate(show_error=True):
            show_snackbar(page, "Por favor, corrija os erros no nome de exibição.", color=theme.COLOR_ERROR)
            return

        new_name = edit_display_name_field.value or ""
        current_session_display_name = page.session.get("auth_display_name")

        if new_name == current_session_display_name:
            show_snackbar(page, "Nenhuma alteração detectada no nome de exibição.", color=theme.COLOR_INFO)
            return

        show_loading_overlay(page, "Atualizando perfil...")
        _logger.info(f"Tentando atualizar nome de exibição para '{new_name}'.")
        try:
            # auth_manager é instanciado no início de create_profile_view
            # Chamada ao método de FbManagerAuth que agora recebe 'page'
            success_or_error_dict = auth_manager.update_profile(page, display_name=new_name)
            hide_loading_overlay(page)

            if success_or_error_dict is True:
                show_snackbar(page, "Nome de exibição atualizado com sucesso!", color=theme.COLOR_SUCCESS)
                _logger.info(f"Nome de exibição atualizado para '{new_name}' para usuário {page.session.get('auth_user_id')}")
                
                # Atualizar na sessão e client_storage (se usado)
                page.session.set("auth_display_name", new_name)
                if page.client_storage and page.client_storage.contains_key("auth_display_name"): # Preserva o "lembrar de mim"
                    page.client_storage.set("auth_display_name", new_name)
                
                display_name_text_control.value = f"Nome: {new_name}" # Atualiza UI local
                # A AppBar será atualizada na próxima navegação ou se houver um mecanismo de pub/sub
                page.update()
            elif isinstance(success_or_error_dict, dict) and success_or_error_dict.get("error"):
                error_type = success_or_error_dict.get("error")
                error_details = success_or_error_dict.get("details", error_type)
                _logger.warning(f"Falha ao atualizar perfil (nome): {error_type} - {error_details}")

                if error_type in ["CREDENTIAL_TOO_OLD_RELOGIN_REQUIRED", "REFRESH_FAILED_LOGOUT", "NO_TOKEN_SESSION_LOGOUT"]:
                    # O método em FbManagerAuth já deve ter lidado com o snackbar e o logout.
                    # Apenas logamos aqui.
                    _logger.info(f"Atualização de perfil falhou devido a {error_type}, logout foi/deveria ter sido tratado.")
                else: # Outros erros da API ou falhas genéricas
                    show_snackbar(page, f"Não foi possível atualizar o nome: {error_details}", color=theme.COLOR_ERROR)
            else: # Caso inesperado de retorno
                show_snackbar(page, "Não foi possível atualizar o nome. Resposta inesperada.", color=theme.COLOR_ERROR)
                _logger.error(f"Retorno inesperado de auth_manager.update_profile: {success_or_error_dict}")

        except Exception as ex:
            hide_loading_overlay(page)
            _logger.error(f"Erro geral ao atualizar perfil (nome): {ex}", exc_info=True)
            show_snackbar(page, "Ocorreu um erro ao tentar atualizar o perfil.", color=theme.COLOR_ERROR)

    def confirm_delete_account(): 
        _logger.warning(f"Usuário {page.session.get('auth_user_id')} confirmou a exclusão da conta. Executando ação...")
        
        show_loading_overlay(page, "Excluindo conta...")
        try:
            # auth_manager é instanciado no início de create_profile_view
            # Chamada ao método de FbManagerAuth que agora recebe 'page'
            success_or_error_dict = auth_manager.delete_user_account(page)
            hide_loading_overlay(page)

            if success_or_error_dict is True:
                # O método delete_user_account em FbManagerAuth não força mais o logout se _execute_sensitive_action
                # for bem sucedido e retornar True. O logout agora é responsabilidade da UI após sucesso.
                show_snackbar(page, "Conta excluída com sucesso. Você será desconectado.", color=theme.COLOR_SUCCESS, duration=5000)
                _logger.info(f"Conta do usuário {page.session.get('auth_user_id')} marcada para exclusão pela API.")
                
                # Forçar logout AGORA que a operação foi confirmada como sucesso pela API
                from src.flet_ui.layout import handle_logout # Import tardio e local
                handle_logout(page)

            elif isinstance(success_or_error_dict, dict) and success_or_error_dict.get("error"):
                error_type = success_or_error_dict.get("error")
                error_details = success_or_error_dict.get("details", error_type)
                _logger.error(f"Falha ao excluir conta: {error_type} - {error_details}")

                if error_type in ["CREDENTIAL_TOO_OLD_RELOGIN_REQUIRED", "REFRESH_FAILED_LOGOUT", "NO_TOKEN_SESSION_LOGOUT"]:
                    # O método em FbManagerAuth já deve ter lidado com o snackbar e o logout.
                    _logger.info(f"Exclusão de conta falhou devido a {error_type}, logout foi/deveria ter sido tratado.")
                else: # Outros erros da API ou falhas genéricas
                    show_snackbar(page, f"Não foi possível excluir a conta: {error_details}", color=theme.COLOR_ERROR)
            else: # Caso inesperado de retorno
                show_snackbar(page, "Não foi possível excluir a conta. Resposta inesperada.", color=theme.COLOR_ERROR)
                _logger.error(f"Retorno inesperado de auth_manager.delete_user_account: {success_or_error_dict}")

        except Exception as ex:
            hide_loading_overlay(page)
            _logger.error(f"Erro geral ao excluir conta: {ex}", exc_info=True)
            show_snackbar(page, "Ocorreu um erro ao tentar excluir a conta.", color=theme.COLOR_ERROR)

    # --- Elementos da UI ---
    display_name_text_control  = ft.Text(f"Nome: {current_display_name }", size=18, weight=ft.FontWeight.BOLD)
    email_text = ft.Text(f"Email: {user_email}", size=16)

    new_password_field = ValidatedTextField(
        label="Nova Senha",
        password=True,
        can_reveal_password=True,
        validator=password_validator
    )
    confirm_new_password_field = ValidatedTextField(
        label="Confirmar Nova Senha",
        password=True,
        can_reveal_password=True,
        validator=lambda val: "As senhas não coincidem." if val != new_password_field.value else None
    )

    edit_display_name_field = ValidatedTextField(
        label="Novo Nome de Exibição",
        value=current_display_name if current_display_name != "N/A" else "",
        validator=display_name_validator,
        capitalization=ft.TextCapitalization.WORDS
    )

    update_profile_button = ft.ElevatedButton("Salvar Novo Nome", on_click=handle_update_profile)

    edit_profile_section = CardWithHeader(
        title="Editar Informações do Perfil",
        content=ft.Column(
            [
                edit_display_name_field,
                ft.Container(height=10),
                ft.Row([update_profile_button], alignment=ft.MainAxisAlignment.END)
            ],
            spacing=15
        ),
        card_elevation=2,
        header_bgcolor=ft.colors.with_opacity(0.3, theme.COLOR_INFO)
    )

    change_password_button = ft.ElevatedButton("Alterar Senha", on_click=handle_change_password)

    change_password_section = CardWithHeader(
        title="Alterar Senha",
        content=ft.Column(
            [
                new_password_field,
                confirm_new_password_field,
                ft.Container(height=10),
                ft.Row([change_password_button], alignment=ft.MainAxisAlignment.END)
            ],
            spacing=15
        ),
        card_elevation=2,
        header_bgcolor=ft.colors.with_opacity(0.3, theme.COLOR_WARNING)
    )

    delete_account_button = ft.ElevatedButton(
        "Excluir Minha Conta",
        on_click=handle_delete_account_click,
        color=ft.colors.WHITE, # Texto branco
        bgcolor=theme.COLOR_ERROR, # Fundo vermelho
        icon=ft.icons.DELETE_FOREVER
    )

    danger_zone_section = CardWithHeader(
        title="Zona de Perigo",
        content=ft.Column(
            [
                ft.Text("Ações nesta seção podem ter consequências permanentes.", size=12, italic=True),
                ft.Divider(height=10, color=ft.colors.TRANSPARENT),
                ft.Row([delete_account_button], alignment=ft.MainAxisAlignment.START)
            ],
            spacing=10
        ),
        card_elevation=2,
        header_bgcolor=ft.colors.with_opacity(0.3, theme.COLOR_ERROR) # Cabeçalho com tom de perigo
    )

    # --- Layout Principal da View de Perfil ---
    profile_content_column  = ft.Column(
        [
            ft.Text("Meu Perfil", size=32, weight=ft.FontWeight.BOLD),
            ft.Divider(),
            display_name_text_control ,
            email_text,
            ft.Container(height=5),
            edit_profile_section, 
            ft.Container(height=8),
            change_password_section,
            ft.Container(height=8),
            danger_zone_section,
        ],
        spacing=20,
        width=700, # Definir uma largura máxima para o conteúdo do perfil
        scroll=ft.ScrollMode.ADAPTIVE
        # alignment=ft.MainAxisAlignment.START, # Coluna já alinha no topo
        # horizontal_alignment=ft.CrossAxisAlignment.CENTER # Centraliza a coluna na página
    )

    return ft.Container(content=ft.Column( # Container para centralizar e aplicar padding
                [profile_content_column] ,
                alignment=ft.MainAxisAlignment.START, # Coluna já alinha no topo
                horizontal_alignment=ft.CrossAxisAlignment.CENTER, # Centraliza a coluna na página
                expand=True, scroll=ft.ScrollMode.ADAPTIVE
            ),
            padding=ft.padding.symmetric(vertical=30, horizontal=20),
            alignment=ft.alignment.top_center, expand=True, 
            border=ft.border.all(1, ft.colors.with_opacity(0.3, theme.COLOR_INFO))
        )

    return ft.View(
        route="/profile",
        controls=[
            ft.Container( # Container para centralizar e aplicar padding
                content=profile_content_column ,
                alignment=ft.alignment.top_center, # Alinha o CardWithHeader no centro
                padding=ft.padding.symmetric(vertical=30, horizontal=20),
                expand=True
            )
        ],
        scroll=ft.ScrollMode.ADAPTIVE # Permite scroll se o conteúdo for maior que a tela
    )

