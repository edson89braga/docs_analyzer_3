# src/flet_ui/views/llm_settings_view.py

import flet as ft
from typing import Optional, List, Dict, Any
import time

from src.services.firebase_client import FirebaseClientFirestore, _to_firestore_value, _from_firestore_value
from src.services import credentials_manager
from src.flet_ui.components import (
    show_snackbar,
    show_loading_overlay,
    hide_loading_overlay,
    CardWithHeader,
    wrapper_cotainer_1
)
from src.flet_ui import theme
from src.flet_ui.theme import WIDTH_CONTAINER_CONFIGS

import logging
logger = logging.getLogger(__name__)

# --- Constantes para Firestore ---
from src.settings import (USER_LLM_PREFERENCES_COLLECTION,
                          KEY_SESSION_ANALYSIS_SETTINGS, KEY_SESSION_USER_LLM_PREFERENCES, KEY_SESSION_LOADED_LLM_PROVIDERS, FALLBACK_ANALYSIS_SETTINGS)


class LLMConfigCard(CardWithHeader):
    """
    Representa um card de configuração para um provedor de LLM específico,
    permitindo ao usuário gerenciar a chave API associada.
    """
    def __init__(
        self,
        page: ft.Page,
        provider_data: Dict[str, Any], # Nova estrutura do provedor
        firestore_manager: FirebaseClientFirestore,
        on_key_status_change: Optional[callable] = None # Callback para notificar a view principal
    ):
        """
        Inicializa um LLMConfigCard.

        Args:
            page (ft.Page): A página Flet atual.
            provider_data (Dict[str, Any]): Dicionário contendo os dados do provedor LLM,
                                             incluindo 'name_display', 'system_name', 'api_url' e 'models'.
            firestore_manager (FirebaseClientFirestore): Instância do gerenciador Firestore para
                                                         interagir com o banco de dados.
            on_key_status_change (Optional[callable]): Callback a ser chamado quando o status
                                                       da chave API do provedor mudar.
        """
        super().__init__( # Chama o __init__ de CardWithHeader
             title=provider_data.get('name_display', 'Provedor Desconhecido'), # Título do card
             content=ft.Column([], spacing=10), # Conteúdo será preenchido abaixo
             card_elevation=2,
             header_bgcolor=ft.Colors.with_opacity(0.05, theme.PRIMARY)
        )

        self.page = page
        self.provider_data = provider_data
        self.firestore_manager = firestore_manager
        self.on_key_status_change = on_key_status_change # Para atualizar a view principal se necessário

        self.system_name = provider_data.get('system_name', 'unknown_provider')
        #self.display_name = provider_data.get('name_display', 'Provedor Desconhecido')
        self.api_url_default = provider_data.get('api_url', '')
        self.models_list = provider_data.get('models', [])

        # --- Controles do Card ---
        self.status_text = ft.Text("Verificando chave...", size=14, italic=True, color=theme.COLOR_INFO)
        self.api_key_field = ft.TextField(
            label=f"Chave API para {self.title_text.value}", # self.display_name
            password=True,
            can_reveal_password=True,
            hint_text="Cole sua chave API aqui",
            expand=True
        )
        self.key_configured_icon = ft.Icon(name=ft.Icons.HELP_OUTLINE, color=theme.COLOR_WARNING, tooltip="Status da chave desconhecido")

        save_button = ft.ElevatedButton("Salvar Chave", icon=ft.Icons.SAVE, on_click=self._handle_save_api_key)
        clear_button = ft.ElevatedButton("Limpar Chave", icon=ft.Icons.DELETE_OUTLINE, on_click=self._handle_clear_api_key, color=ft.Colors.WHITE, bgcolor=theme.COLOR_ERROR)

        # Simulação de um campo para a URL da API, mas por ora é read-only
        api_url_display = ft.TextField(label="URL Base da API", value=self.api_url_default, read_only=True, border=ft.InputBorder.NONE, text_size=11)

        self.main_content.controls.extend([ # main_content é o ft.Column do CardWithHeader
                api_url_display,
                ft.Row([self.api_key_field, self.key_configured_icon], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                self.status_text,
                ft.Row([clear_button, save_button], alignment=ft.MainAxisAlignment.END, spacing=10),
                ft.Divider(height=1, color=ft.Colors.TRANSPARENT),
            ]
        )

    def did_mount(self):
        logger.debug(f"LLMConfigCard para {self.system_name} did_mount. Carregando status da chave API.")
        self.load_api_key_status()

    def update_card_content_status(self, status_msg: str, status_color: str, key_icon: str, key_icon_color: str, key_icon_tooltip: str, api_key_hint: str):
        """
        Atualiza o conteúdo visual do card de status da chave API.

        Args:
            status_msg (str): Mensagem de status a ser exibida.
            status_color (str): Cor da mensagem de status (ex: ft.Colors.RED, theme.COLOR_SUCCESS).
            key_icon (str): Nome do ícone Flet para o status da chave (ex: ft.Icons.CHECK_CIRCLE_OUTLINE).
            key_icon_color (str): Cor do ícone de status da chave.
            key_icon_tooltip (str): Texto de dica para o ícone de status.
            api_key_hint (str): Texto de dica para o campo de entrada da chave API.
        """
        self.status_text.value = status_msg
        self.status_text.color = status_color
        self.key_configured_icon.name = key_icon
        self.key_configured_icon.color = key_icon_color
        self.key_configured_icon.tooltip = key_icon_tooltip
        self.api_key_field.hint_text = api_key_hint
        self.api_key_field.value = "" # Sempre limpa o campo de input

        if self.page and self.uid:
            self.status_text.update()
            self.key_configured_icon.update()
            self.api_key_field.update()

    def _get_session_key_for_decrypted_api_key(self) -> str:
        """
        Gera a chave de sessão usada para armazenar a chave API descriptografada.

        Returns:
            str: A chave de sessão única para a chave API descriptografada.
        """
        return f"decrypted_api_key_{self.system_name}" # Simplificado, system_name já deve ser único

    def _get_current_user_context(self) -> Optional[tuple[str, str]]:
        """
        Obtém o token de ID e o ID do usuário da sessão, garantindo que o token esteja atualizado.

        Returns:
            Optional[tuple[str, str]]: Uma tupla contendo (id_token, user_id) se o usuário estiver
                                       autenticado e o token for válido, caso contrário, None.
        """
        from src.flet_ui.app import check_and_refresh_token_if_needed
        if not check_and_refresh_token_if_needed(self.page):
            return None
        id_token = self.page.session.get("auth_id_token")
        user_id = self.page.session.get("auth_user_id")
        if id_token and user_id:
            return id_token, user_id
        logger.error(f"Contexto do usuário (token/ID) não encontrado para {self.system_name}.")
        # Não redireciona daqui, a view principal pode tratar
        return None

    def load_api_key_status(self):
        """
        Carrega o status da chave API para o provedor atual, verificando a sessão e o Firestore.
        Atualiza a UI do card com o status correspondente.
        """
        logger.info(f"Carregando status da chave API salva para {self.system_name}...")
        self.update_card_content_status("Verificando...", theme.COLOR_INFO, ft.Icons.HOURGLASS_EMPTY, theme.COLOR_INFO, "Verificando status...", "Aguarde...")

        context = self._get_current_user_context()
        if not context:
            self.update_card_content_status("Erro de sessão.", theme.COLOR_ERROR, ft.Icons.ERROR_OUTLINE, theme.COLOR_ERROR, "Erro de sessão", "Erro de sessão")
            if self.on_key_status_change: self.on_key_status_change(self.system_name, False) # Notifica falha
            return

        id_token, user_id = context
        session_key_decrypted = self._get_session_key_for_decrypted_api_key()

        if self.page.session.contains_key(session_key_decrypted):
            logger.info(f"Chave API para {self.system_name} encontrada descriptografada na sessão (cache).")
            self.update_card_content_status(
                "Chave API configurada e pronta (em cache).", theme.COLOR_SUCCESS,
                ft.Icons.CHECK_CIRCLE_OUTLINE, theme.COLOR_SUCCESS, "Chave API configurada",
                "Chave API configurada. Preencha para alterar."
            )
            if self.on_key_status_change: self.on_key_status_change(self.system_name, True)
            return

        try:
            encrypted_key_bytes = self.firestore_manager.get_user_api_key_client(
                id_token, user_id, self.system_name
            )
            if encrypted_key_bytes:
                logger.info(f"Chave API criptografada encontrada para {self.system_name} no Firestore.")
                # TENTAR DESCRIPTOGRAFAR E SALVAR NA SESSÃO AQUI
                decrypted_key = credentials_manager.decrypt(encrypted_key_bytes)
                if decrypted_key:
                    logger.info(f"Chave API para {self.system_name} descriptografada com sucesso.")
                    self.page.session.set(session_key_decrypted, decrypted_key)
                    self.update_card_content_status(
                        "Chave API configurada e pronta.", theme.COLOR_SUCCESS, # Mensagem mais direta
                        ft.Icons.CHECK_CIRCLE_OUTLINE, theme.COLOR_SUCCESS, "Chave API configurada e carregada na sessão",
                        "Chave API configurada. Preencha para alterar."
                    )
                    if self.on_key_status_change: self.on_key_status_change(self.system_name, True)
                else:
                    logger.error(f"Falha ao descriptografar chave API para {self.system_name} do Firestore.")
                    self.update_card_content_status(
                        "Chave API salva, mas falha ao acessar.", theme.COLOR_ERROR, # Mensagem ajustada
                        ft.Icons.LOCK_ALERT_OUTLINED, theme.COLOR_ERROR, "Chave API salva, mas erro ao descriptografar",
                        "Erro ao acessar a chave. Tente salvá-la novamente."
                    )
                    if self.on_key_status_change: self.on_key_status_change(self.system_name, False)
            else:
                logger.info(f"Nenhuma chave API encontrada para {self.system_name} no Firestore.")
                self.update_card_content_status(
                    "Nenhuma chave API configurada.", theme.COLOR_WARNING,
                    ft.Icons.WARNING_AMBER_OUTLINED, theme.COLOR_WARNING, "Chave API não configurada",
                    "Nenhuma chave API configurada para este serviço."
                )
                if self.on_key_status_change: self.on_key_status_change(self.system_name, False)
        except Exception as e:
            logger.error(f"Erro ao carregar/descriptografar chave API para {self.system_name}: {e}", exc_info=True)
            self.update_card_content_status(
                "Erro ao carregar configuração da chave.", theme.COLOR_ERROR,
                ft.Icons.ERROR_OUTLINE, theme.COLOR_ERROR, "Erro ao carregar",
                "Erro ao carregar configuração da chave."
            )
            if self.on_key_status_change: self.on_key_status_change(self.system_name, False)
            
    def _handle_save_api_key(self, e: ft.ControlEvent):
        """
        Manipula o evento de clique do botão "Salvar Chave".
        Criptografa a chave API fornecida e a salva no Firestore para o usuário atual.

        Args:
            e (ft.ControlEvent): O evento de controle que disparou a função.
        """
        new_api_key_value = self.api_key_field.value
        if not new_api_key_value:
            show_snackbar(self.page, "O campo da Chave API está vazio.", color=theme.COLOR_WARNING)
            return

        logger.info(f"Tentando salvar chave API para {self.system_name}.")
        context = self._get_current_user_context()
        if not context: return
        id_token, user_id = context

        encrypted_key_bytes: Optional[bytes] = None
        try:
            if not credentials_manager.get_encryption_key():
                logger.error("Chave de criptografia Fernet local não encontrada.")
                show_snackbar(self.page, "Erro de configuração: Chave de criptografia principal ausente.", color=theme.COLOR_ERROR)
                self.update_card_content_status("Erro: Chave de criptografia local ausente.", theme.COLOR_ERROR, ft.Icons.ERROR, theme.COLOR_ERROR, "Erro", "Erro")
                return
            encrypted_key_bytes = credentials_manager.encrypt(new_api_key_value)
        except Exception as enc_ex:
            logger.error(f"Falha ao criptografar chave API: {enc_ex}", exc_info=True)
            show_snackbar(self.page, "Erro ao proteger a chave API.", color=theme.COLOR_ERROR)
            return

        if not encrypted_key_bytes:
            show_snackbar(self.page, "Falha ao preparar a chave API para salvamento.", color=theme.COLOR_ERROR)
            return

        show_loading_overlay(self.page, f"Salvando chave para {self.title_text.value}...")
        try:
            success = self.firestore_manager.save_user_api_key_client(
                id_token, user_id, self.system_name, encrypted_key_bytes
            )
            hide_loading_overlay(self.page)
            
            session_key_decrypted = self._get_session_key_for_decrypted_api_key()
            if success:
                logger.info(f"Chave API para {self.system_name} salva com sucesso.")
                self.page.session.set(session_key_decrypted, new_api_key_value)
                show_snackbar(self.page, "Chave API salva com sucesso!", color=theme.COLOR_SUCCESS)
                self.load_api_key_status() # Recarrega o status para refletir a mudança
            else:
                if self.page.session.get("auth_id_token"):
                    show_snackbar(self.page, "Não foi possível salvar a chave API.", color=theme.COLOR_ERROR)
                if self.page.session.contains_key(session_key_decrypted):
                    self.page.session.remove(session_key_decrypted)
                logger.error(f"Falha ao salvar chave API para {self.system_name} no Firestore.")
                self.load_api_key_status() # Recarrega o status
        except Exception as ex:
            hide_loading_overlay(self.page)
            logger.error(f"Erro inesperado ao salvar chave API: {ex}", exc_info=True)
            if self.page.session.contains_key(self._get_session_key_for_decrypted_api_key()):
                self.page.session.remove(self._get_session_key_for_decrypted_api_key())
            show_snackbar(self.page, "Ocorreu um erro inesperado ao salvar a chave.", color=theme.COLOR_ERROR)
            self.load_api_key_status()

    def _handle_clear_api_key(self, e: ft.ControlEvent):
        """
        Manipula o evento de clique do botão "Limpar Chave".
        Remove a chave API do provedor atual do Firestore e da sessão.

        Args:
            e (ft.ControlEvent): O evento de controle que disparou a função.
        """
        logger.info(f"Tentando limpar chave API para {self.system_name}.")
        context = self._get_current_user_context()
        if not context: return
        id_token, user_id = context

        empty_encrypted_key = credentials_manager.encrypt("") # Chave vazia criptografada
        if empty_encrypted_key is None:
             show_snackbar(self.page, "Erro ao preparar limpeza da chave.", color=theme.COLOR_ERROR)
             return

        show_loading_overlay(self.page, f"Limpando chave para {self.title_text.value}...") # Corrigido
        session_key_decrypted = self._get_session_key_for_decrypted_api_key()
        if self.page.session.contains_key(session_key_decrypted):
            self.page.session.remove(session_key_decrypted)

        try:
            # Salvar uma chave "vazia" (string vazia criptografada) efetivamente limpa a chave útil.
            # O ideal seria um método `delete_user_api_key_field` no `FirebaseClientFirestore`
            # que usasse a operação `FieldValue.delete()` do Firestore, mas salvar bytes
            # vazios é uma alternativa se esse método não existir.
            success = self.firestore_manager.save_user_api_key_client(
                id_token, user_id, self.system_name, empty_encrypted_key
            )
            hide_loading_overlay(self.page)
            if success:
                logger.info(f"Chave API para {self.system_name} limpa/removida.")
                show_snackbar(self.page, "Chave API removida com sucesso!", color=theme.COLOR_SUCCESS)
            else:
                logger.error(f"Falha ao limpar chave API para {self.system_name} no Firestore (retorno False).")
        except Exception as ex:
            hide_loading_overlay(self.page)
            logger.error(f"Erro inesperado ao limpar chave API: {ex}", exc_info=True)
            show_snackbar(self.page, "Ocorreu um erro inesperado ao limpar a chave.", color=theme.COLOR_ERROR)
        finally:
            self.load_api_key_status()

class LLMSettingsViewContent(ft.Column):
    """
    Conteúdo principal da view de configurações de LLM, incluindo gerenciamento
    de chaves API e preferências de provedor/modelo padrão.
    """
    def __init__(self, page: ft.Page):
        """
        Inicializa o conteúdo da view de configurações de LLM.

        Args:
            page (ft.Page): A página Flet atual.
        """
        super().__init__(spacing=20, width=WIDTH_CONTAINER_CONFIGS,
                         horizontal_alignment=ft.CrossAxisAlignment.CENTER) # expand=True, scroll=ft.ScrollMode.ADAPTIVE
        self.page = page
        self.firestore_manager = FirebaseClientFirestore()
        self.provider_cards_map: Dict[str, LLMConfigCard] = {} # system_name -> card instance
        #self.loaded_providers_data: List[Dict[str, Any]] = [] obtém da sessão
        self._last_pref_error_message = "" # Para armazenar mensagens de erro de preferências

        # Controles para seleção de provedor e modelo padrão
        self.default_provider_dropdown = ft.Dropdown(
            label="Provedor Padrão",
            hint_text="Selecione o provedor padrão para análises",
            options=[],
            on_change=self._handle_default_provider_change,
            width=300
        )
        self.default_model_dropdown = ft.Dropdown(
            label="Modelo Padrão",
            hint_text="Selecione o modelo padrão",
            options=[],
            disabled=True, # Habilita após selecionar provedor
            width=300,
            on_change=self._handle_model_change # Adicionado para habilitar save_preferences_button
        )
        self.save_preferences_button = ft.ElevatedButton(
            "Salvar Preferências",
            icon=ft.Icons.SETTINGS_APPLICATIONS_SHARP, # CHECK_CIRCLE_OUTLINE
            on_click=self._handle_save_preferences,
            disabled=True # Habilita após alguma mudança
        )
        self.status_preferences_text = ft.Text("", size=12, italic=True)

        if self.status_preferences_text.value and "Erro" in self.status_preferences_text.value:
            self.status_preferences_text.color = theme.COLOR_ERROR
        elif self.status_preferences_text.value:
            self.status_preferences_text.color = theme.COLOR_SUCCESS

        self.cards_container = ft.Column(spacing=15, width = WIDTH_CONTAINER_CONFIGS, 
                                         alignment=ft.MainAxisAlignment.START, 
                                         horizontal_alignment=ft.CrossAxisAlignment.CENTER)

        self.controls = [
            ft.Text("Configurações de Provedores e Modelos LLM", size=28, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
            ft.Text(
                "Gerencie suas chaves de API e defina o provedor/modelo padrão para as análises.\n"
                "As chaves API são criptografadas localmente antes de serem salvas.",
                size=14, color=ft.Colors.with_opacity(0.8, ft.Colors.ON_SURFACE), text_align=ft.TextAlign.CENTER
            ),
            ft.Divider(height=10),
            CardWithHeader(
                title="Preferências Padrão de Análise",
                content=ft.Column(
                    [
                        ft.Row([self.default_provider_dropdown, self.default_model_dropdown], spacing=20, alignment=ft.MainAxisAlignment.CENTER),
                        ft.Row([self.save_preferences_button], alignment=ft.MainAxisAlignment.CENTER),
                        ft.Row([self.status_preferences_text], alignment=ft.MainAxisAlignment.CENTER, spacing=5)
                    ], spacing=15
                ),
                header_bgcolor=ft.Colors.with_opacity(0.05, theme.PRIMARY),
                card_elevation=1,
                width = WIDTH_CONTAINER_CONFIGS
            ),
            ft.Divider(height=12,
            ),
            ft.Text("Chaves de API por Provedor", style=ft.TextThemeStyle.TITLE_MEDIUM, text_align=ft.TextAlign.CENTER),
            self.cards_container,
            # Botão para adicionar novo provedor (funcionalidade futura, gerenciada pelo Admin)
            # ft.ElevatedButton("Adicionar Novo Provedor LLM (Admin)", icon=ft.Icons.ADD_CIRCLE_OUTLINE, disabled=True)
        ]

    def _get_loaded_providers(self) -> List[Dict[str, Any]]:
        """
        Obtém a lista de provedores LLM carregados da sessão da página.

        Returns:
            List[Dict[str, Any]]: Uma lista de dicionários, onde cada dicionário
                                  representa um provedor LLM configurado.
        """
        return self.page.session.get(KEY_SESSION_LOADED_LLM_PROVIDERS) or []

    def _get_user_preferences(self) -> Dict[str, Any]:
        """
        Obtém as preferências de LLM do usuário da sessão da página.

        Returns:
            Dict[str, Any]: Um dicionário contendo as preferências do usuário,
                            como o provedor e modelo padrão.
        """
        return self.page.session.get(KEY_SESSION_USER_LLM_PREFERENCES) or {}
    
    def _update_status_preferences_display(self):
        """
        Atualiza o texto de status que exibe as preferências de LLM padrão salvas.
        """
        user_preferences = self._get_user_preferences()
        if user_preferences.get("default_provider_system_name") and user_preferences.get("default_model_id"):
            provider_key = user_preferences["default_provider_system_name"]
            model_key = user_preferences["default_model_id"]
            provider_text = self._get_dropdown_option_text(self.default_provider_dropdown, provider_key)
            
            model_text = model_key # Fallback
            loaded_providers = self._get_loaded_providers()
            provider_config = next((p for p in loaded_providers if p.get('system_name') == provider_key), None)
            if provider_config:
                model_config = next((m for m in provider_config.get('models', []) if m.get('id') == model_key), None)
                if model_config:
                    model_text = model_config.get('name', model_key)

            self.status_preferences_text.value = f"Padrões salvos: {provider_text} / {model_text}"
            self.status_preferences_text.color = theme.COLOR_SUCCESS
        elif hasattr(self, '_last_pref_error_message') and self._last_pref_error_message:
             self.status_preferences_text.value = self._last_pref_error_message
             self.status_preferences_text.color = theme.COLOR_ERROR
        else:
            self.status_preferences_text.value = "Nenhuma preferência LLM padrão foi salva ainda."
            self.status_preferences_text.color = theme.COLOR_INFO

        if self.page and self.status_preferences_text.uid : # Garante que o controle existe e está na página
            self.status_preferences_text.update()

    def did_mount(self):
        """
        Método chamado quando o controle LLMSettingsViewContent é montado na página.
        Carrega os dados dos provedores e preferências da sessão e atualiza a UI.
        """
        logger.info("LLMSettingsViewContent did_mount. Carregando dados dos provedores e preferências da sessão.")
        # Os dados já devem ter sido carregados para a sessão por app.py
        self._update_provider_cards_from_session()
        self._update_preference_dropdowns_from_session()
        self._update_status_preferences_display() # Atualiza com base no que foi carregado na sessão
        #self.load_providers_and_preferences()
    
    def _handle_key_status_change(self, provider_system_name: str, is_configured: bool):
        """
        Callback chamado quando o status da chave API de um provedor muda.
        Atualiza o estado do botão de salvar preferências.

        Args:
            provider_system_name (str): O nome do sistema do provedor cuja chave mudou.
            is_configured (bool): True se a chave estiver configurada, False caso contrário.
        """
        self.save_preferences_button.disabled = self._are_preferences_unchanged()
        if self.page and self.save_preferences_button.uid :
            self.save_preferences_button.update()

    def _update_provider_cards_from_session(self): # Renomeado
        """
        Atualiza os cards de configuração de provedores LLM com base nos dados da sessão.
        Cria um LLMConfigCard para cada provedor carregado.
        """
        self.cards_container.controls.clear()
        self.provider_cards_map.clear()
        loaded_providers = self._get_loaded_providers()

        if not loaded_providers:
            self.cards_container.controls.append(ft.Text("Nenhum provedor LLM configurado no sistema (ou falha ao carregar).", italic=True, color=theme.COLOR_WARNING))
        else:
            for provider_conf in loaded_providers:
                system_name = provider_conf.get('system_name')
                if system_name:
                    # Passa a instância do FirebaseClientFirestore para o card
                    card = LLMConfigCard(self.page, provider_conf, self.firestore_manager, on_key_status_change=self._handle_key_status_change)
                    self.cards_container.controls.append(card)
                    self.provider_cards_map[system_name] = card
        if self.page: self.cards_container.update()

    def _update_preference_dropdowns_from_session(self): # Renomeado
        """
        Atualiza os dropdowns de seleção de provedor e modelo padrão com base
        nos dados dos provedores carregados e nas preferências do usuário da sessão.
        """
        loaded_providers = self._get_loaded_providers()
        user_preferences = self._get_user_preferences()

        provider_options = [
            ft.dropdown.Option(key=p_data['system_name'], text=p_data.get('name_display', p_data['system_name']))
            for p_data in loaded_providers if p_data.get('system_name')
        ]
        self.default_provider_dropdown.options = provider_options
        
        selected_provider_system_name = user_preferences.get("default_provider_system_name")
        if selected_provider_system_name and any(opt.key == selected_provider_system_name for opt in provider_options):
            self.default_provider_dropdown.value = selected_provider_system_name
            self._populate_models_for_selected_provider(update_ui=False) # Popula antes de definir valor do modelo
            
            selected_model_id = user_preferences.get("default_model_id")
            if selected_model_id and any(opt.key == selected_model_id for opt in self.default_model_dropdown.options):
                self.default_model_dropdown.value = selected_model_id
            elif self.default_model_dropdown.options: # Se modelo salvo não existe, mas há opções
                # Não seleciona automaticamente, deixa o usuário escolher ou o _populate_models pode ter uma lógica de default
                pass
        else:
            self.default_provider_dropdown.value = None
            self.default_model_dropdown.options = []
            self.default_model_dropdown.value = None
            self.default_model_dropdown.disabled = True

        self.save_preferences_button.disabled = self._are_preferences_unchanged()
        if self.page:
            self.default_provider_dropdown.update()
            self.default_model_dropdown.update()
            self.save_preferences_button.update()

    def _populate_models_for_selected_provider(self, update_ui: bool = True):
        """
        Popula o dropdown de modelos com os modelos disponíveis para o provedor selecionado.

        Args:
            update_ui (bool): Se True, força a atualização da UI dos dropdowns.
        """
        selected_provider_key = self.default_provider_dropdown.value
        self.default_model_dropdown.options = []
        # self.default_model_dropdown.value = None # Não reseta o valor aqui ainda
        self.default_model_dropdown.disabled = True
        loaded_providers = self._get_loaded_providers()

        if selected_provider_key:
            provider_data = next((p for p in loaded_providers if p.get('system_name') == selected_provider_key), None)
            if provider_data and provider_data.get('models'):
                model_options = [
                    ft.dropdown.Option(key=model['id'], text=model.get('name', model['id']))
                    for model in provider_data['models'] if model.get('id')
                ]
                self.default_model_dropdown.options = model_options
                self.default_model_dropdown.disabled = False
                
                # Tenta manter o valor atual do dropdown de modelo se ele ainda for válido para o novo provedor
                current_model_value = self.default_model_dropdown.value
                if current_model_value and any(opt.key == current_model_value for opt in model_options):
                    # O modelo atual ainda é válido, não precisa mudar
                    pass
                elif model_options : # Modelo atual não é válido ou não havia, mas há opções
                    self.default_model_dropdown.value = None # Força o usuário a re-selecionar ou seleciona o primeiro
                    # self.default_model_dropdown.value = model_options[0].key # Descomente para auto-selecionar o primeiro
        
        if update_ui and self.page:
            self.default_model_dropdown.update()

    def _handle_default_provider_change(self, e: ft.ControlEvent):
        """
        Manipula a mudança de seleção no dropdown de provedor padrão.
        Popula os modelos para o provedor selecionado e atualiza o estado do botão de salvar.

        Args:
            e (ft.ControlEvent): O evento de controle que disparou a função.
        """
        self._populate_models_for_selected_provider()
        # Habilita o botão salvar se a seleção mudou
        self.save_preferences_button.disabled = self._are_preferences_unchanged()
        if self.page: self.save_preferences_button.update()

    def _handle_model_change(self, e: ft.ControlEvent):
        """
        Manipula a mudança de seleção no dropdown de modelo padrão.
        Atualiza o estado do botão de salvar preferências.

        Args:
            e (ft.ControlEvent): O evento de controle que disparou a função.
        """
        # Habilita o botão salvar se a seleção mudou
        self.save_preferences_button.disabled = self._are_preferences_unchanged()
        if self.page: self.save_preferences_button.update()

    def _are_preferences_unchanged(self) -> bool:
        """
        Verifica se as preferências de provedor e modelo selecionadas na UI
        são as mesmas que as preferências salvas na sessão do usuário.

        Returns:
            bool: True se as preferências na UI forem idênticas às salvas, False caso contrário.
        """
        current_provider_ui = self.default_provider_dropdown.value
        current_model_ui = self.default_model_dropdown.value
        user_preferences = self._get_user_preferences()
        saved_provider = user_preferences.get("default_provider_system_name")
        saved_model = user_preferences.get("default_model_id")
        return current_provider_ui == saved_provider and current_model_ui == saved_model

    def _get_dropdown_option_text(self, dropdown: ft.Dropdown, key_value: Optional[str]) -> str:
        """
        Retorna o texto de exibição de uma opção de dropdown com base na sua chave (valor).

        Args:
            dropdown (ft.Dropdown): A instância do dropdown a ser pesquisada.
            key_value (Optional[str]): A chave (valor) da opção desejada.

        Returns:
            str: O texto da opção correspondente, "N/A" se a chave for None,
                 ou a própria chave se o texto não for encontrado.
        """
        if key_value is None:
            return "N/A"
        for option in dropdown.options:
            if option.key == key_value:
                return option.text
        return str(key_value) # Retorna a chave se o texto não for encontrado (fallback)
    
    def _handle_save_preferences(self, e: ft.ControlEvent):
        """
        Manipula o evento de clique do botão "Salvar Preferências".
        Salva as preferências de provedor e modelo LLM padrão do usuário no Firestore
        e as atualiza na sessão.

        Args:
            e (ft.ControlEvent): O evento de controle que disparou a função.
        """
        logger.info("Salvando preferências de LLM do usuário...")
        self._last_pref_error_message = ""
        from src.flet_ui.app import check_and_refresh_token_if_needed

        if not check_and_refresh_token_if_needed(self.page): context = None
        else:
            id_token_session = self.page.session.get("auth_id_token")
            user_id_session = self.page.session.get("auth_user_id")
            if id_token_session and user_id_session: context = (id_token_session, user_id_session)
            else: context = None

        if not context:
            show_snackbar(self.page, "Erro de sessão ao salvar preferências.", theme.COLOR_ERROR)
            self._last_pref_error_message = "Erro de sessão ao salvar."
            self._update_status_preferences_display()
            return

        id_token, user_id = context

        if not self.page.session.get("is_admin"):
            show_snackbar(self.page, "Apenas administradores podem alterar as preferências padrão de LLM.", color=theme.COLOR_WARNING, duration=5000)
            logger.warning(f"Usuário não-admin (ID: {self.page.session.get('auth_user_id')}) tentou salvar preferências de LLM.")
            # Opcional: Reverter a seleção na UI para refletir as preferências salvas
            self._update_preference_dropdowns_from_session()
            return

        selected_provider = self.default_provider_dropdown.value
        selected_model = self.default_model_dropdown.value

        if not selected_provider or not selected_model:
            show_snackbar(self.page, "Selecione um provedor e um modelo padrão.", theme.COLOR_WARNING)
            return

        loaded_providers = self._get_loaded_providers()
        provider_config = next((p for p in loaded_providers if p.get("system_name") == selected_provider), None)
        if not provider_config:
            show_snackbar(self.page, f"Provedor '{selected_provider}' inválido ou não carregado.", theme.COLOR_ERROR)
            return
        model_config = next((m for m in provider_config.get("models", []) if m.get("id") == selected_model), None)
        if not model_config:
            show_snackbar(self.page, f"Modelo '{selected_model}' inválido para o provedor '{selected_provider}'.", theme.COLOR_ERROR)
            return

        key_for_selected_provider_in_session = f"decrypted_api_key_{selected_provider}"
        if not self.page.session.contains_key(key_for_selected_provider_in_session):
            card_instance = self.provider_cards_map.get(selected_provider)
            if card_instance:
                # Força o card a tentar carregar/descriptografar a chave para a sessão
                card_instance.load_api_key_status() # Isso tentará popular a sessão se a chave estiver no Firestore
                # Re-verifica a sessão após a tentativa do card
                if not self.page.session.contains_key(key_for_selected_provider_in_session):
                    provider_display_name = self._get_dropdown_option_text(self.default_provider_dropdown, selected_provider)
                    show_snackbar(self.page, f"A chave API para o provedor '{provider_display_name}' não está configurada ou acessível. Salve-a primeiro.", theme.COLOR_WARNING, duration=6000)
                    return
            else:
                show_snackbar(self.page, "Erro interno: Card de configuração do provedor não encontrado.", theme.COLOR_ERROR)
                return

        new_preferences = {
            "default_provider_system_name": selected_provider,
            "default_model_id": selected_model,
            "updated_at": time.time()
        }
        pref_doc_path = f"{USER_LLM_PREFERENCES_COLLECTION}/{user_id}"
        firestore_payload = {"fields": {k: _to_firestore_value(v) for k, v in new_preferences.items()}}

        show_loading_overlay(self.page, "Salvando suas preferências LLM...")
        try:
            self.firestore_manager._make_firestore_request(
                method="PATCH", user_token=id_token, document_path=pref_doc_path, json_data=firestore_payload
            )
            hide_loading_overlay(self.page)
            
            self.page.session.set(KEY_SESSION_USER_LLM_PREFERENCES, new_preferences)
            
            current_analysis_settings = self.page.session.get(KEY_SESSION_ANALYSIS_SETTINGS) or FALLBACK_ANALYSIS_SETTINGS.copy()
            current_analysis_settings["llm_provider"] = selected_provider
            current_analysis_settings["llm_model"] = selected_model
            self.page.session.set(KEY_SESSION_ANALYSIS_SETTINGS, current_analysis_settings)
            logger.info(f"Preferências de LLM salvas e aplicadas à sessão atual para usuário {user_id}: {new_preferences}")

            self.save_preferences_button.disabled = True
            if self.page and self.save_preferences_button.uid: self.save_preferences_button.update()
            self._update_status_preferences_display()
            show_snackbar(self.page, "Preferências de LLM padrão salvas com sucesso!", color=theme.COLOR_SUCCESS)

        except Exception as e:
            hide_loading_overlay(self.page)
            logger.error(f"Erro ao salvar preferências LLM do usuário {user_id}: {e}", exc_info=True)
            self._last_pref_error_message = "Erro ao salvar preferências."
            self._update_status_preferences_display()
            show_snackbar(self.page, "Não foi possível salvar suas preferências de LLM.", theme.COLOR_ERROR)


def create_llm_settings_view(page: ft.Page) -> ft.Control:
    """
    Cria e retorna o conteúdo da view de Configurações de LLM.

    Args:
        page (ft.Page): A página Flet atual.

    Returns:
        ft.Control: O conteúdo principal da view de Configurações de LLM.
    """
    logger.info("Criando o conteúdo da view de Configurações LLM.")

    if not page.session.get("auth_id_token"):
        logger.warning("Usuário não autenticado tentou acessar Configurações LLM.")
        # O router deve ter redirecionado. Se chegar aqui, é um fallback.
        return ft.Text("Erro: Autenticação necessária. Você será redirecionado.", color=theme.COLOR_ERROR)

    llm_settings_form = LLMSettingsViewContent(page)

    return wrapper_cotainer_1(llm_settings_form)

    return ft.Container( # Container para centralizar e aplicar padding geral
        content=llm_settings_form,
        alignment=ft.alignment.top_center,
        padding=ft.padding.symmetric(vertical=20, horizontal=15),
        expand=True
    )

