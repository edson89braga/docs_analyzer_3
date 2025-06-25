# src/flet_ui/views/proxy_settings_view.py

### Por ora, módulo DESCONTINUADO para voltar a usar o show_proxy_settings_dialog em dialog.py.

import flet as ft
from typing import Optional

from src.flet_ui.components import (
    show_snackbar,
    ValidatedTextField,
    CardWithHeader, 
    wrapper_cotainer_1
)
from src.flet_ui import theme
from src.flet_ui.theme import WIDTH_CONTAINER_CONFIGS
from src.config_manager import get_proxy_settings, save_proxy_settings
from src.settings import (
    K_PROXY_ENABLED, K_PROXY_PASSWORD_SAVED, K_PROXY_IP_URL,
    K_PROXY_PORT, K_PROXY_USERNAME, K_PROXY_PASSWORD,
    PROXY_URL_DEFAULT, PROXY_PORT_DEFAULT
)

import logging
logger = logging.getLogger(__name__)

# --- Funções de Validação (podem ser movidas para um local comum se usadas em mais lugares) ---
def host_validator(value: str) -> Optional[str]:
    """
    Valida o valor de um host (IP ou nome de domínio).

    Args:
        value (str): O valor do host a ser validado.

    Returns:
        Optional[str]: Uma mensagem de erro se o host for inválido, caso contrário, None.
    """
    if not value:
        return "O host não pode estar vazio se o proxy estiver habilitado."
    # Validação mais robusta de IP/hostname pode ser adicionada aqui se necessário
    return None

def port_validator(value: str) -> Optional[str]:
    """
    Valida o valor de uma porta de rede.

    Args:
        value (str): O valor da porta a ser validado.

    Returns:
        Optional[str]: Uma mensagem de erro se a porta for inválida, caso contrário, None.
    """
    if not value:
        return "A porta não pode estar vazia se o proxy estiver habilitado."
    if not value.isdigit() or not (1 <= int(value) <= 65535):
        return "Porta inválida (deve ser um número entre 1 e 65535)."
    return None

# --- Elementos da UI e Lógica ---
class ProxySettingsContent(ft.Column):
    """
    Conteúdo principal da view de configurações de proxy, permitindo ao usuário
    habilitar/desabilitar, configurar e salvar as definições de proxy.
    """
    def __init__(self, page: ft.Page):
        """
        Inicializa o conteúdo da view de configurações de proxy.

        Args:
            page (ft.Page): A página Flet atual.
        """
        super().__init__(spacing=20, width=WIDTH_CONTAINER_CONFIGS, horizontal_alignment=ft.CrossAxisAlignment.CENTER) # expand=True, scroll=ft.ScrollMode.ADAPTIVE
        self.page = page

        # Carregar configurações iniciais
        self.current_settings = get_proxy_settings()

        # --- Controles da UI ---
        self.proxy_enabled_switch = ft.Switch(
            label="Habilitar Proxy",
            value=self.current_settings.get(K_PROXY_ENABLED, False),
            on_change=self._toggle_fields_enabled
        )
        self.proxy_host_field = ValidatedTextField(
            label="Host do Proxy",
            value=self.current_settings.get(K_PROXY_IP_URL, PROXY_URL_DEFAULT),
            validator=host_validator,
            hint_text="ex: proxy.dpf.gov.br ou 10.0.0.1",
            disabled=True if not self.proxy_enabled_switch.value else False
        )
        self.proxy_port_field = ValidatedTextField(
            label="Porta do Proxy",
            value=str(self.current_settings.get(K_PROXY_PORT, PROXY_PORT_DEFAULT)),
            validator=port_validator,
            keyboard_type=ft.KeyboardType.NUMBER,
            disabled=True if not self.proxy_enabled_switch.value else False
        )
        self.proxy_user_field = ft.TextField(
            label="Usuário Proxy",
            value=self.current_settings.get(K_PROXY_USERNAME, ""),
            disabled=True if not self.proxy_enabled_switch.value else False
        )
        self.proxy_password_field = ft.TextField(
            label="Senha Proxy (deixe em branco se não mudou)",
            hint_text="Preencha apenas para definir/alterar a senha",
            password=True,
            can_reveal_password=True,
            disabled=True if not self.proxy_enabled_switch.value else False,
            expand=True
        )
        self.save_password_checkbox = ft.Checkbox(
            label="Salvar Senha",
            value=self.current_settings.get(K_PROXY_PASSWORD_SAVED, False),
            tooltip="Salva a senha no Keyring do sistema operacional.",
            disabled=True if not self.proxy_enabled_switch.value else False
        )
        self.security_warning_text = ft.Text(
            "Atenção: As configurações de proxy, incluindo o nome de usuário, são salvas localmente. "
            "\nSe 'Salvar Senha' estiver marcado, a senha também será armazenada de forma segura no Keyring do sistema. "
            "\nSe este NÃO é seu computador pessoal, desmarque 'Salvar Senha' ou remova as configurações ao sair.",
            size=12,
            italic=True,
            color=ft.colors.with_opacity(0.7, ft.colors.ON_SURFACE),
            #width=550 # Para quebrar linha
        )

        self.save_button = ft.ElevatedButton(
            "Salvar Configurações",
            icon=ft.icons.SAVE,
            on_click=self._handle_save_settings,
            width=200
        )
        self.delete_button = ft.ElevatedButton(
            "Remover Tudo",
            icon=ft.icons.DELETE_SWEEP_OUTLINED,
            on_click=self._handle_delete_settings,
            tooltip="Limpa todas as configurações de proxy salvas.",
            width=200,
            color=ft.colors.WHITE,
            bgcolor=theme.COLOR_ERROR
        )

        # --- Layout com CardWithHeader ---
        settings_card = CardWithHeader(
            title="Configurações de Conexão Proxy",
            content=ft.Column(
                [
                    self.proxy_enabled_switch,
                    self.proxy_host_field,
                    self.proxy_port_field,
                    self.proxy_user_field,
                    ft.Row([self.proxy_password_field, self.save_password_checkbox], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Divider(height=5, color=ft.colors.TRANSPARENT),
                    self.security_warning_text,
                    ft.Divider(height=15, color=ft.colors.TRANSPARENT),
                    ft.Row(
                        [self.delete_button, self.save_button],
                        alignment=ft.MainAxisAlignment.END,
                        spacing=10
                    ),
                    ft.Divider(height=1, color=ft.colors.TRANSPARENT),
                ],
                spacing=15,
            ),
            card_elevation=2,
            width = WIDTH_CONTAINER_CONFIGS,
            header_bgcolor=ft.colors.with_opacity(0.1, theme.PRIMARY) # Um pouco diferente do padrão
        )

        self.controls = [
            ft.Text("Gerenciar Configurações de Proxy", size=28, weight=ft.FontWeight.BOLD),
            ft.Text(
                "Se necessário, Configure as definições de proxy para acesso à internet pela aplicação. "
                "\nAs configurações são armazenadas de forma segura no seu sistema.",
                size=14, color=ft.colors.with_opacity(0.8, ft.colors.ON_SURFACE)
            ),
            ft.Divider(height=20),
            settings_card
        ]

    def _toggle_fields_enabled(self, e: Optional[ft.ControlEvent] = None):
        """
        Alterna o estado de habilitação/desabilitação dos campos de entrada do proxy
        com base no estado do switch 'Habilitar Proxy'.

        Args:
            e (Optional[ft.ControlEvent]): O evento de controle que disparou a função (opcional).
        """
        is_enabled = self.proxy_enabled_switch.value
        self.proxy_host_field.disabled = not is_enabled
        self.proxy_port_field.disabled = not is_enabled
        self.proxy_user_field.disabled = not is_enabled
        self.proxy_password_field.disabled = not is_enabled
        self.save_password_checkbox.disabled = not is_enabled
        
        # Limpar erros se desabilitado
        if not is_enabled:
            self.proxy_host_field.text_field.error_text = None
            self.proxy_port_field.text_field.error_text = None
        
        self.proxy_host_field.update()
        self.proxy_port_field.update()
        self.proxy_user_field.update()
        self.proxy_password_field.update()
        self.save_password_checkbox.update()

    def _load_settings_to_ui(self):
        """
        Carrega as configurações de proxy salvas (do config_manager) para os campos da UI.
        Atualiza o estado dos campos e a UI.
        """
        self.current_settings = get_proxy_settings()
        self.proxy_enabled_switch.value = self.current_settings.get(K_PROXY_ENABLED, False)
        self.proxy_host_field.value = self.current_settings.get(K_PROXY_IP_URL, PROXY_URL_DEFAULT)
        self.proxy_port_field.value = str(self.current_settings.get(K_PROXY_PORT, PROXY_PORT_DEFAULT))
        self.proxy_user_field.value = self.current_settings.get(K_PROXY_USERNAME, "")
        self.proxy_password_field.value = "" # Senha nunca é pré-preenchida
        self.save_password_checkbox.value = self.current_settings.get(K_PROXY_PASSWORD_SAVED, False)
        self._toggle_fields_enabled() # Atualiza o estado de 'disabled' dos campos
        self.update() # Atualiza toda a coluna (ProxySettingsContent)

    def _handle_save_settings(self, e: ft.ControlEvent):
        """
        Manipula o evento de clique do botão "Salvar Configurações".
        Valida os campos de proxy e salva as configurações no sistema.

        Args:
            e (ft.ControlEvent): O evento de controle que disparou a função.
        """
        logger.info("Tentando salvar configurações de proxy.")
        is_enabled = self.proxy_enabled_switch.value
        host_valid = True
        port_valid = True

        if is_enabled:
            host_valid = self.proxy_host_field.validate(show_error=True)
            port_valid = self.proxy_port_field.validate(show_error=True)
        else:
            self.proxy_host_field.text_field.error_text = None
            self.proxy_port_field.text_field.error_text = None
            self.proxy_host_field.update()
            self.proxy_port_field.update()

        if not host_valid or not port_valid:
            show_snackbar(self.page, "Corrija os erros no formulário.", color=theme.COLOR_ERROR)
            return

        new_settings = {
            K_PROXY_ENABLED: is_enabled,
            K_PROXY_IP_URL: self.proxy_host_field.value if is_enabled else PROXY_URL_DEFAULT,
            K_PROXY_PORT: self.proxy_port_field.value if is_enabled else PROXY_PORT_DEFAULT,
            K_PROXY_USERNAME: self.proxy_user_field.value if is_enabled else "",
            K_PROXY_PASSWORD_SAVED: self.save_password_checkbox.value if is_enabled else False
        }
        # A senha só é incluída no dict se for fornecida (não vazia)
        if self.proxy_password_field.value:
            new_settings[K_PROXY_PASSWORD] = self.proxy_password_field.value
        
        if save_proxy_settings(new_settings):
            logger.info("Configurações de proxy salvas com sucesso.")
            show_snackbar(self.page, "Configurações de proxy salvas com sucesso!", color=theme.COLOR_SUCCESS)
            self.proxy_password_field.value = "" # Limpa campo de senha após salvar
            self.proxy_password_field.update()
        else:
            logger.error("Falha ao salvar configurações de proxy.")
            show_snackbar(self.page, "Erro ao salvar configurações de proxy.", color=theme.COLOR_ERROR)

    def _handle_delete_settings(self, e: ft.ControlEvent):
        """
        Manipula o evento de clique do botão "Remover Tudo".
        Limpa todas as configurações de proxy salvas e atualiza a UI.

        Args:
            e (ft.ControlEvent): O evento de controle que disparou a função.
        """
        logger.info("Tentando remover todas as configurações de proxy.")
        # Define configurações para desabilitar e limpar tudo
        settings_to_delete = {
            K_PROXY_ENABLED: False,
            K_PROXY_IP_URL: PROXY_URL_DEFAULT,
            K_PROXY_PORT: PROXY_PORT_DEFAULT,
            K_PROXY_USERNAME: "",
            K_PROXY_PASSWORD: "", # Importante para que a função delete_proxy_settings seja efetiva
            K_PROXY_PASSWORD_SAVED: False
        }
        if save_proxy_settings(settings_to_delete): # save_proxy_settings lida com a deleção se username for vazio
            logger.info("Configurações de proxy removidas com sucesso.")
            show_snackbar(self.page, "Todas as configurações de proxy foram removidas.", color=theme.COLOR_INFO)
            # Recarrega os valores padrão na UI
            self._load_settings_to_ui()
        else:
            logger.error("Falha ao remover configurações de proxy.")
            show_snackbar(self.page, "Erro ao remover configurações de proxy.", color=theme.COLOR_ERROR)

def create_proxy_settings_content(page: ft.Page) -> ft.Control:
    """
    Cria e retorna o conteúdo principal para a view de configurações de proxy.

    Args:
        page (ft.Page): A página Flet atual.

    Returns:
        ft.Control: O conteúdo principal da view de configurações de proxy.
    """
    logger.info("View Configurações de Proxy: Iniciando criação.")
    
    proxy_settings_form = ProxySettingsContent(page)
    
    return wrapper_cotainer_1(proxy_settings_form)

    return ft.Container(
        content=proxy_settings_form,
        alignment=ft.alignment.top_center, # Alinha o conteúdo ao topo e centro
        padding=ft.padding.symmetric(vertical=20, horizontal=15), # Padding geral da view
        expand=True
    )