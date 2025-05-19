# NOVO ARQUIVO: src/flet_ui/views/llm_settings_view.py

import flet as ft
from typing import Optional, List, Dict, Any
import time # Para simular delays ou timestamps se necessário
import requests

from src.services.firebase_client import FirebaseClientFirestore # Para salvar/carregar chaves
from src.services import credentials_manager # Para criptografia local (encrypt/decrypt)
from src.flet_ui.components import (
    show_snackbar, 
    show_loading_overlay, 
    hide_loading_overlay,
    CardWithHeader,
    wrapper_cotainer_1
)
from src.flet_ui import theme
from src.flet_ui.theme import WIDTH_CONTAINER_CONFIGS

from src.logger.logger import LoggerSetup
_logger = LoggerSetup.get_logger(__name__)

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
    CardWithHeader
)
from src.flet_ui import theme
from src.logger.logger import LoggerSetup

_logger = LoggerSetup.get_logger(__name__)

# --- Dados Mockados/Configuráveis para LLMs (Provisório) ---
# No futuro, isso pode vir do Firestore ou de um arquivo de configuração.
# SUPPORTED_PROVIDERS = {
#     "OpenAI": {
#         "display_name": "OpenAI",
#         "models": [
#             {"id": "gpt-4.1-nano", "name": "GPT-4.1 Nano"}, # 0.10 $ p/1M tokens
#             {"id": "gpt-4.1-mini", "name": "GPT-4.1 Mini"}, # 0.40 $
#             {"id": "o4-mini", "name": "OpenAI o4-mini"},    # 1.10 $
#             {"id": "gpt-4.1", "name": "GPT-4.1"},           # 2.00 $
#         ],
#         "api_url_default": "https://api.openai.com/v1", # Exemplo, pode não ser editável pelo usuário
#         "api_key_field_label": "Chave API OpenAI (sk-...)",
#         "service_name_firestore": "openai_api_key" # Como será salvo no Firestore
#     },
#     # "azure_openai": { ... },
#     # "anthropic": { ... },
# }

# --- Constantes para Firestore ---
PROVIDERS_COLLECTION = "llm_providers_config"  # Coleção para configurações de provedores
DEFAULT_PROVIDERS_DOC_ID = "default_list"       # Documento contendo a lista de provedores padrão
USER_LLM_PREFERENCES_COLLECTION = "user_llm_preferences" # Coleção para preferências do usuário

class LLMConfigCard(CardWithHeader):
    def __init__(
        self,
        page: ft.Page,
        provider_data: Dict[str, Any], # Nova estrutura do provedor
        firestore_manager: FirebaseClientFirestore,
        on_key_status_change: Optional[callable] = None # Callback para notificar a view principal
    ):
        self.page = page
        self.provider_data = provider_data
        self.firestore_manager = firestore_manager
        self.on_key_status_change = on_key_status_change # Para atualizar a view principal se necessário

        self.system_name = provider_data.get('system_name', 'unknown_provider')
        self.display_name = provider_data.get('name_display', 'Provedor Desconhecido')
        self.api_url_default = provider_data.get('api_url', '')
        self.models_list = provider_data.get('models', [])

        # --- Controles do Card ---
        self.api_key_field = ft.TextField(
            label=f"Chave API para {self.display_name}",
            password=True,
            can_reveal_password=True,
            hint_text="Cole sua chave API aqui",
            expand=True
        )
        self.status_text = ft.Text("Verificando chave...", size=14, italic=True, color=theme.COLOR_INFO)
        self.key_configured_icon = ft.Icon(name=ft.icons.HELP_OUTLINE, color=theme.COLOR_WARNING, tooltip="Status da chave desconhecido")

        save_button = ft.ElevatedButton("Salvar Chave", icon=ft.icons.SAVE, on_click=self._handle_save_api_key)
        clear_button = ft.ElevatedButton("Limpar Chave", icon=ft.icons.DELETE_OUTLINE, on_click=self._handle_clear_api_key, color=ft.colors.WHITE, bgcolor=theme.COLOR_ERROR)

        # Simulação de um campo para a URL da API, mas por ora é read-only
        api_url_display = ft.TextField(label="URL Base da API", value=self.api_url_default, read_only=True, border=ft.InputBorder.NONE, text_size=12)

        card_content = ft.Column(
            [
                api_url_display,
                ft.Row([self.api_key_field, self.key_configured_icon], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                self.status_text,
                ft.Row([clear_button, save_button], alignment=ft.MainAxisAlignment.END, spacing=10),
                ft.Divider(height=1, color=ft.colors.TRANSPARENT),
            ],
            spacing=12
        )

        super().__init__(
            title=f"{self.display_name}", # Título do card
            content=card_content,
            card_elevation=2,
            header_bgcolor=ft.colors.with_opacity(0.05, theme.PRIMARY)
        )

    def did_mount(self):
        #_logger.info(f"[DEBUG] LLMConfigCard para {self.system_name} did_mount. Carregando status da chave API.")
        self.load_api_key_status()

    def update_card_content_status(self, status_msg: str, status_color: str, key_icon: str, key_icon_color: str, key_icon_tooltip: str, api_key_hint: str):
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
        return f"decrypted_api_key_{self.system_name}" # Simplificado, system_name já deve ser único

    def _get_current_user_context(self) -> Optional[tuple[str, str]]:
        from src.flet_ui.app import check_and_refresh_token_if_needed
        if not check_and_refresh_token_if_needed(self.page):
            return None
        id_token = self.page.session.get("auth_id_token")
        user_id = self.page.session.get("auth_user_id")
        if id_token and user_id:
            return id_token, user_id
        _logger.error(f"Contexto do usuário (token/ID) não encontrado para {self.system_name}.")
        # Não redireciona daqui, a view principal pode tratar
        return None

    def load_api_key_status(self):
        _logger.info(f"Carregando status da chave API salva para {self.system_name}...")
        self.update_card_content_status("Verificando...", theme.COLOR_INFO, ft.icons.HOURGLASS_EMPTY, theme.COLOR_INFO, "Verificando status...", "Aguarde...")

        context = self._get_current_user_context()
        if not context:
            self.update_card_content_status("Erro de sessão.", theme.COLOR_ERROR, ft.icons.ERROR_OUTLINE, theme.COLOR_ERROR, "Erro de sessão", "Erro de sessão")
            return

        id_token, user_id = context
        session_key_decrypted = self._get_session_key_for_decrypted_api_key()

        if self.page.session.contains_key(session_key_decrypted):
            _logger.info(f"Chave API para {self.system_name} encontrada descriptografada na sessão (cache).")
            self.update_card_content_status(
                "Chave API configurada e pronta (em cache).", theme.COLOR_SUCCESS,
                ft.icons.CHECK_CIRCLE_OUTLINE, theme.COLOR_SUCCESS, "Chave API configurada",
                "Chave API configurada. Preencha para alterar."
            )
            if self.on_key_status_change: self.on_key_status_change(self.system_name, True)
            return

        try:
            encrypted_key_bytes = self.firestore_manager.get_user_api_key_client(
                id_token, user_id, self.system_name # Usa system_name como service_name no Firestore
            )
            if encrypted_key_bytes:
                _logger.info(f"Chave API criptografada encontrada para {self.system_name}.")
                self.update_card_content_status(
                    "Chave API configurada e salva.", theme.COLOR_SUCCESS,
                    ft.icons.LOCK_OUTLINED, theme.COLOR_SUCCESS, "Chave API salva e criptografada",
                    "Chave API configurada. Preencha para alterar."
                )
                if self.on_key_status_change: self.on_key_status_change(self.system_name, True)
            else:
                _logger.info(f"Nenhuma chave API encontrada para {self.system_name}.")
                self.update_card_content_status(
                    "Nenhuma chave API configurada.", theme.COLOR_WARNING,
                    ft.icons.WARNING_AMBER_OUTLINED, theme.COLOR_WARNING, "Chave API não configurada",
                    "Nenhuma chave API configurada para este serviço."
                )
                if self.on_key_status_change: self.on_key_status_change(self.system_name, False)
        except Exception as e:
            _logger.error(f"Erro ao carregar chave API para {self.system_name}: {e}", exc_info=True)
            self.update_card_content_status(
                "Erro ao carregar configuração.", theme.COLOR_ERROR,
                ft.icons.ERROR_OUTLINE, theme.COLOR_ERROR, "Erro ao carregar",
                "Erro ao carregar configuração da chave."
            )
            if self.on_key_status_change: self.on_key_status_change(self.system_name, False)

    def _handle_save_api_key(self, e):
        new_api_key_value = self.api_key_field.value
        if not new_api_key_value:
            show_snackbar(self.page, "O campo da Chave API está vazio.", color=theme.COLOR_WARNING)
            return

        _logger.info(f"Tentando salvar chave API para {self.system_name}.")
        context = self._get_current_user_context()
        if not context: return
        id_token, user_id = context

        encrypted_key_bytes: Optional[bytes] = None
        try:
            if not credentials_manager.get_encryption_key():
                _logger.error("Chave de criptografia Fernet local não encontrada.")
                show_snackbar(self.page, "Erro de configuração: Chave de criptografia principal ausente.", color=theme.COLOR_ERROR)
                self.update_card_content_status("Erro: Chave de criptografia local ausente.", theme.COLOR_ERROR, ft.icons.ERROR, theme.COLOR_ERROR, "Erro", "Erro")
                return
            encrypted_key_bytes = credentials_manager.encrypt(new_api_key_value)
        except Exception as enc_ex:
            _logger.error(f"Falha ao criptografar chave API: {enc_ex}", exc_info=True)
            show_snackbar(self.page, "Erro ao proteger a chave API.", color=theme.COLOR_ERROR)
            return

        if not encrypted_key_bytes:
            show_snackbar(self.page, "Falha ao preparar a chave API para salvamento.", color=theme.COLOR_ERROR)
            return

        show_loading_overlay(self.page, f"Salvando chave para {self.display_name}...")
        try:
            success = self.firestore_manager.save_user_api_key_client(
                id_token, user_id, self.system_name, encrypted_key_bytes
            )
            hide_loading_overlay(self.page)
            
            session_key_decrypted = self._get_session_key_for_decrypted_api_key()
            if success:
                _logger.info(f"Chave API para {self.system_name} salva com sucesso.")
                self.page.session.set(session_key_decrypted, new_api_key_value)
                show_snackbar(self.page, "Chave API salva com sucesso!", color=theme.COLOR_SUCCESS)
                self.load_api_key_status() # Recarrega o status para refletir a mudança
            else:
                if self.page.session.get("auth_id_token"):
                    show_snackbar(self.page, "Não foi possível salvar a chave API.", color=theme.COLOR_ERROR)
                if self.page.session.contains_key(session_key_decrypted):
                    self.page.session.remove(session_key_decrypted)
                _logger.error(f"Falha ao salvar chave API para {self.system_name} no Firestore.")
                self.load_api_key_status() # Recarrega o status
        except Exception as ex:
            hide_loading_overlay(self.page)
            _logger.error(f"Erro inesperado ao salvar chave API: {ex}", exc_info=True)
            if self.page.session.contains_key(self._get_session_key_for_decrypted_api_key()):
                self.page.session.remove(self._get_session_key_for_decrypted_api_key())
            show_snackbar(self.page, "Ocorreu um erro inesperado ao salvar a chave.", color=theme.COLOR_ERROR)
            self.load_api_key_status()

    def _handle_clear_api_key(self, e):
        _logger.info(f"Tentando limpar chave API para {self.system_name}.")
        context = self._get_current_user_context()
        if not context: return
        id_token, user_id = context

        empty_encrypted_key = credentials_manager.encrypt("")
        if empty_encrypted_key is None:
             show_snackbar(self.page, "Erro ao preparar limpeza da chave.", color=theme.COLOR_ERROR)
             return

        show_loading_overlay(self.page, f"Limpando chave para {self.display_name}...")
        session_key_decrypted = self._get_session_key_for_decrypted_api_key()
        if self.page.session.contains_key(session_key_decrypted):
            self.page.session.remove(session_key_decrypted)

        try:
            # Para deletar um campo, o ideal seria uma função delete_field no FirestoreManager
            # ou salvar um valor especial que signifique "deletado" ou null.
            # Por simplicidade, salvar bytes vazios criptografados indica que a chave foi "limpa".
            # No entanto, melhor seria usar save_user_api_key_client para salvar um valor que indique ausência,
            # ou uma função específica delete_user_api_key_field(user_token, user_id, service_name).
            # Vamos assumir que salvar bytes vazios é o "limpar".
            # O ideal é o FirebaseClientFirestore ter um método delete_user_api_key_field
            # que remova o campo do documento. Por ora, simulamos com save de bytes vazios.
            success = self.firestore_manager.save_user_api_key_client(
                id_token, user_id, self.system_name, empty_encrypted_key
            )
            hide_loading_overlay(self.page)
            if success:
                _logger.info(f"Chave API para {self.system_name} limpa/removida.")
                show_snackbar(self.page, "Chave API removida com sucesso!", color=theme.COLOR_SUCCESS)
            else:
                if self.page.session.get("auth_id_token"):
                    show_snackbar(self.page, "Não foi possível limpar a chave API.", color=theme.COLOR_ERROR)
                _logger.error(f"Falha ao limpar chave API para {self.system_name} no Firestore.")
        except Exception as ex:
            hide_loading_overlay(self.page)
            _logger.error(f"Erro inesperado ao limpar chave API: {ex}", exc_info=True)
            show_snackbar(self.page, "Ocorreu um erro inesperado ao limpar a chave.", color=theme.COLOR_ERROR)
        finally:
            self.load_api_key_status() # Recarrega o status após a tentativa

class LLMSettingsViewContent(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__(spacing=25, width=WIDTH_CONTAINER_CONFIGS,
                         horizontal_alignment=ft.CrossAxisAlignment.CENTER) # expand=True, scroll=ft.ScrollMode.ADAPTIVE
        self.page = page
        self.firestore_manager = FirebaseClientFirestore()
        self.loaded_providers_data: List[Dict[str, Any]] = []
        self.provider_cards_map: Dict[str, LLMConfigCard] = {} # system_name -> card instance
        self.user_preferences: Dict[str, Any] = {} # system_name_provider, model_id

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
            icon=ft.icons.SETTINGS_APPLICATIONS_SHARP, # CHECK_CIRCLE_OUTLINE
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
            ft.Text("Configurações de Modelos de Linguagem (LLM)", size=28, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
            ft.Text(
                "Gerencie suas chaves de API e defina o provedor/modelo padrão para as análises.\n"
                "As chaves API são criptografadas localmente antes de serem salvas.",
                size=14, color=ft.colors.with_opacity(0.8, ft.colors.ON_SURFACE), text_align=ft.TextAlign.CENTER
            ),
            ft.Divider(height=10),
            CardWithHeader(
                title="Preferências de Análise",
                content=ft.Column(
                    [
                        ft.Row([self.default_provider_dropdown, self.default_model_dropdown], spacing=20, alignment=ft.MainAxisAlignment.CENTER),
                        ft.Row([self.save_preferences_button], alignment=ft.MainAxisAlignment.CENTER),
                        ft.Row([self.status_preferences_text], alignment=ft.MainAxisAlignment.CENTER)
                    ], spacing=18
                ),
                header_bgcolor=ft.colors.with_opacity(0.05, theme.PRIMARY),
                card_elevation=1,
                width = WIDTH_CONTAINER_CONFIGS
            ),
            ft.Divider(height=10,
            ),
            ft.Text("Chaves de API por Provedor", style=ft.TextThemeStyle.TITLE_MEDIUM, text_align=ft.TextAlign.CENTER),
            self.cards_container,
            # Botão para adicionar novo provedor (funcionalidade futura, gerenciada pelo Admin)
            # ft.ElevatedButton("Adicionar Novo Provedor LLM (Admin)", icon=ft.icons.ADD_CIRCLE_OUTLINE, disabled=True)
        ]

    def _update_status_preferences_display(self):
        """Atualiza o texto de status com base nas user_preferences carregadas."""
        if self.user_preferences.get("default_provider_system_name") and self.user_preferences.get("default_model_id"):
            provider_key = self.user_preferences["default_provider_system_name"]
            model_key = self.user_preferences["default_model_id"]

            # Encontra o texto do provedor
            provider_text = provider_key # Fallback
            for p_opt in self.default_provider_dropdown.options:
                if p_opt.key == provider_key:
                    provider_text = p_opt.text
                    break
            
            # Encontra o texto do modelo (pode precisar carregar as opções do modelo primeiro se não estiverem)
            # Para simplificar, vamos buscar o nome do modelo diretamente dos loaded_providers_data
            model_text = model_key # Fallback
            provider_config = next((p for p in self.loaded_providers_data if p.get('system_name') == provider_key), None)
            if provider_config:
                model_config = next((m for m in provider_config.get('models', []) if m.get('id') == model_key), None)
                if model_config:
                    model_text = model_config.get('name', model_key)

            self.status_preferences_text.value = f"Preferências atuais salvas: {provider_text} / {model_text}"
            self.status_preferences_text.color = theme.COLOR_SUCCESS
        elif hasattr(self, '_last_pref_error_message') and self._last_pref_error_message:
             self.status_preferences_text.value = self._last_pref_error_message # Exibe a última mensagem de erro
             self.status_preferences_text.color = theme.COLOR_ERROR
        else:
            self.status_preferences_text.value = "Nenhuma preferência de LLM padrão foi salva ainda."
            self.status_preferences_text.color = theme.COLOR_INFO # Ou uma cor neutra

        if self.page:
            self.status_preferences_text.update()

    def did_mount(self):
        _logger.info("LLMSettingsViewContent did_mount. Carregando dados...")
        self.load_providers_and_preferences()
    
    def _handle_key_status_change(self, provider_system_name: str, is_configured: bool):
        """Callback do LLMConfigCard para atualizar UI de preferências se necessário."""
        #_logger.info(f"[DEBUG] Status da chave para '{provider_system_name}' mudou para: {is_configured}")
        # Se a chave do provedor padrão foi desconfigurada, podemos querer resetar ou avisar.
        # Por ora, não faremos nada automático aqui, o usuário pode re-salvar preferências.
        # Apenas atualizamos o estado do botão Salvar Preferências.
        self.save_preferences_button.disabled = self._are_preferences_unchanged()

    def _update_provider_cards(self):
        self.cards_container.controls.clear()
        self.provider_cards_map.clear()
        if not self.loaded_providers_data:
            self.cards_container.controls.append(ft.Text("Nenhum provedor LLM configurado no sistema.", italic=True))
        else:
            for provider_conf in self.loaded_providers_data:
                system_name = provider_conf.get('system_name')
                if system_name:
                    card = LLMConfigCard(self.page, provider_conf, self.firestore_manager, on_key_status_change=self._handle_key_status_change)
                    self.cards_container.controls.append(card)
                    self.provider_cards_map[system_name] = card
        if self.page: self.cards_container.update()

    def _update_preference_dropdowns(self):
        # Popula dropdown de provedores
        #_logger.info(f"[DEBUG] Atualizando dropdowns de preferência. Preferências carregadas: {self.user_preferences}")
        provider_options = [
            ft.dropdown.Option(key=p_data['system_name'], text=p_data['name_display'])
            for p_data in self.loaded_providers_data if p_data.get('system_name') and p_data.get('name_display')
        ]
        self.default_provider_dropdown.options = provider_options
        
        # Define valor selecionado para provedor
        selected_provider_system_name = self.user_preferences.get("default_provider_system_name")
        #_logger.info(f"[DEBUG] Provedor padrão salvo: {selected_provider_system_name}")
        if selected_provider_system_name and any(opt.key == selected_provider_system_name for opt in provider_options):
            self.default_provider_dropdown.value = selected_provider_system_name
            #_logger.info(f"[DEBUG] Definindo provedor dropdown para: {selected_provider_system_name}")
            self._populate_models_for_selected_provider(update_ui=False) # Popula modelos para o provedor já selecionado
        else: # Nenhum provedor padrão salvo ou o salvo não existe mais
            self.default_provider_dropdown.value = None
            self.default_model_dropdown.options = []
            self.default_model_dropdown.value = None
            self.default_model_dropdown.disabled = True
            #_logger.info("[DEBUG] Nenhum provedor padrão válido encontrado ou definido. Resetando dropdowns.")

        # Define valor selecionado para modelo (se provedor já estava selecionado)
        if self.default_provider_dropdown.value and self.default_model_dropdown.options:
            selected_model_id = self.user_preferences.get("default_model_id")
            #_logger.info(f"[DEBUG] Tentando definir modelo padrão salvo: {selected_model_id} para provedor {self.default_provider_dropdown.value}")
            if selected_model_id and any(opt.key == selected_model_id for opt in self.default_model_dropdown.options):
                 self.default_model_dropdown.value = selected_model_id
                 #_logger.info(f"[DEBUG] Definindo modelo dropdown para: {selected_model_id}")

        self.save_preferences_button.disabled = self._are_preferences_unchanged() # Verifica se algo mudou em relação ao salvo

        if self.page:
            self.default_provider_dropdown.update()
            self.default_model_dropdown.update()
            self.save_preferences_button.update()

    def _populate_models_for_selected_provider(self, update_ui: bool = True):
        selected_provider_key = self.default_provider_dropdown.value
        self.default_model_dropdown.options = []
        self.default_model_dropdown.value = None
        self.default_model_dropdown.disabled = True
        #_logger.info(f"[DEBUG] Populando modelos para provedor selecionado: {selected_provider_key}")

        if selected_provider_key:
            provider_data = next((p for p in self.loaded_providers_data if p.get('system_name') == selected_provider_key), None)
            if provider_data and provider_data.get('models'):
                model_options = [
                    ft.dropdown.Option(key=model['id'], text=model['name'])
                    for model in provider_data['models'] if model.get('id') and model.get('name')
                ]
                self.default_model_dropdown.options = model_options
                self.default_model_dropdown.disabled = False
                #_logger.info(f"[DEBUG] Modelos para {selected_provider_key}: {len(model_options)} opções. Dropdown de modelo habilitado: {not self.default_model_dropdown.disabled}")
                # Tenta pré-selecionar o modelo se já houver preferência salva
                saved_model_id = self.user_preferences.get("default_model_id")
                saved_provider_pref = self.user_preferences.get("default_provider_system_name")
                saved_model_id_pref = self.user_preferences.get("default_model_id")
                if saved_provider_pref == selected_provider_key and saved_model_id_pref:
                    if any(opt.key == saved_model_id_pref for opt in model_options):
                        self.default_model_dropdown.value = saved_model_id_pref
                        #_logger.info(f"[DEBUG] Modelo '{saved_model_id_pref}' pré-selecionado para provedor '{selected_provider_key}' com base nas preferências salvas.")
                    else:
                        _logger.warning(f"Modelo salvo '{saved_model_id_pref}' não encontrado nas opções do provedor '{selected_provider_key}'.")
                        # Opcional: selecionar o primeiro modelo se o salvo não estiver disponível
                        if model_options:
                            # self.default_model_dropdown.value = model_options[0].key
                            # _logger.info(f"[DEBUG] Selecionando primeiro modelo disponível: {model_options[0].key}")
                            pass # Ou deixar sem seleção para forçar o usuário a escolher
                elif model_options: # Se não há preferência salva ou o provedor mudou, seleciona o primeiro modelo como sugestão
                    # self.default_model_dropdown.value = model_options[0].key # Comentado para não pré-selecionar automaticamente se não for a preferência
                    # _logger.info(f"[DEBUG] Nenhuma preferência de modelo salva para {selected_provider_key} ou provedor diferente. Primeiro modelo {model_options[0].key} disponível (não auto-selecionado).")
                    pass


        if update_ui and self.page: 
            self.default_model_dropdown.update()
        
        #self.save_preferences_button.disabled = self._are_preferences_unchanged()
        #if self.page: self.save_preferences_button.update()

    def _handle_default_provider_change(self, e: ft.ControlEvent):
        self._populate_models_for_selected_provider()
        # Habilita o botão salvar se a seleção mudou
        self.save_preferences_button.disabled = self._are_preferences_unchanged()
        if self.page: self.save_preferences_button.update()

    def _handle_model_change(self, e: ft.ControlEvent):
        # Habilita o botão salvar se a seleção mudou
        self.save_preferences_button.disabled = self._are_preferences_unchanged()
        if self.page: self.save_preferences_button.update()

    def _are_preferences_unchanged(self) -> bool:
        """Verifica se as preferências na UI são diferentes das salvas."""
        current_provider_ui = self.default_provider_dropdown.value
        current_model_ui = self.default_model_dropdown.value

        saved_provider = self.user_preferences.get("default_provider_system_name")
        saved_model = self.user_preferences.get("default_model_id")

        return current_provider_ui == saved_provider and current_model_ui == saved_model

    def load_providers_and_preferences(self):
        _logger.info("Carregando configurações de provedores LLM e preferências do usuário...")
        from src.flet_ui.app import check_and_refresh_token_if_needed
        show_loading_overlay(self.page, "Carregando configurações LLM...")
        self._last_pref_error_message = "" 
        
        #context = self.provider_cards_map.get(list(self.provider_cards_map.keys())[0] if self.provider_cards_map else "", 
        # LLMConfigCard(self.page,{},self.firestore_manager))._get_current_user_context() # Usa um card qualquer para pegar o contexto

        if not check_and_refresh_token_if_needed(self.page): # Usa self.page de LLMSettingsViewContent
            context = None
        else:
            id_token = self.page.session.get("auth_id_token")
            user_id = self.page.session.get("auth_user_id")
            if id_token and user_id:
                context = (id_token, user_id)
            else:
                # Se check_and_refresh_token_if_needed passou mas não temos token/id,
                # isso indicaria um problema de lógica ou estado inesperado.
                _logger.error("load_providers_and_preferences: check_and_refresh_token_if_needed True, mas token/ID ausente.")
                context = None # Tratar como falha de contexto
        
        if not context:
            hide_loading_overlay(self.page)
            show_snackbar(self.page, "Erro de sessão ao carregar configurações.", theme.COLOR_ERROR)
            self.cards_container.controls.clear()
            self.cards_container.controls.append(ft.Text("Erro de sessão. Não foi possível carregar as configurações.", color=theme.COLOR_ERROR))
            if self.page: self.cards_container.update()
            self._last_pref_error_message = "Erro de sessão ao carregar." # Guarda erro
            self._update_status_preferences_display() # Atualiza UI com erro
            return

        id_token, user_id = context

        # 1. Carregar Lista de Provedores do Firestore (Admin/Config Global)
        try:
            # Esta chamada não precisa de token de usuário, pois são configs globais
            # mas _make_firestore_request ainda espera um. Podemos passar o do admin se disponível,
            # ou adaptar _make_firestore_request para chamadas não autenticadas se as regras permitirem.
            # Por simplicidade, vamos assumir que o token do usuário atual tem permissão de leitura
            # para PROVIDERS_COLLECTION, ou que o FbManagerFirestore pode ser adaptado
            # para usar credenciais de admin para esta leitura específica.
            # Se as regras do Firestore para 'llm_providers_config' permitem leitura por usuários autenticados:
            doc_ref_path = f"{PROVIDERS_COLLECTION}/{DEFAULT_PROVIDERS_DOC_ID}"
            response = self.firestore_manager._make_firestore_request("GET", id_token, doc_ref_path) # Usa o token do usuário para ler config
            
            if response.status_code == 200:
                providers_doc = response.json()
                # A lista de provedores estará dentro de um campo, ex: "providers_list"
                # Supondo que o documento tem um campo 'all_providers' que é um array de maps
                providers_array = _from_firestore_value(providers_doc.get("fields", {}).get("all_providers", {"arrayValue": {}}))
                if isinstance(providers_array, list):
                    self.loaded_providers_data = providers_array
                    _logger.info(f"{len(self.loaded_providers_data)} provedores LLM carregados do Firestore.")
                else:
                    _logger.error("Estrutura de dados de provedores LLM no Firestore é inválida (esperado array).")
                    self.loaded_providers_data = []
            elif response.status_code == 404:
                _logger.warning(f"Documento de configuração de provedores LLM '{DEFAULT_PROVIDERS_DOC_ID}' não encontrado.")
                self.loaded_providers_data = [] # Usar uma lista vazia se não encontrar
            else:
                _logger.error(f"Erro ao carregar provedores LLM do Firestore: {response.status_code} - {response.text}")
                self.loaded_providers_data = []

        except Exception as e:
            _logger.error(f"Exceção ao carregar provedores LLM: {e}", exc_info=True)
            self.loaded_providers_data = []
            show_snackbar(self.page, "Erro ao carregar lista de provedores LLM.", theme.COLOR_ERROR)

        # Atualiza os cards de provedor
        self._update_provider_cards()

        # 2. Carregar Preferências do Usuário
        self.user_preferences = {}
        try:
            pref_doc_path = f"{USER_LLM_PREFERENCES_COLLECTION}/{user_id}"
            response_pref = self.firestore_manager._make_firestore_request("GET", id_token, pref_doc_path)
            #_logger.info(f"[DEBUG] Tentando carregar preferências de: {pref_doc_path}")
            
            if response_pref.status_code == 200:
                #self.user_preferences = _from_firestore_value({"mapValue": user_pref_doc.get("fields", {})})
                user_pref_doc_json = response_pref.json()
                #_logger.info(f"[DEBUG] Preferências recebidas do Firestore (JSON cru): {user_pref_doc_json}")
                fields_data = user_pref_doc_json.get("fields")
                if fields_data: # Verifica se 'fields' existe e não é None
                    loaded_prefs = _from_firestore_value({"mapValue": {"fields": fields_data}})
                    if isinstance(loaded_prefs, dict):
                        self.user_preferences = loaded_prefs
                    else:
                        _logger.error(f"Preferências do usuário não foram convertidas para dict após _from_firestore_value: {type(loaded_prefs)}")
                        self.user_preferences = {} # Mantém como dict vazio em caso de falha na conversão
                else:
                    _logger.warning(f"Documento de preferências para {user_id} encontrado, mas não contém o campo 'fields' ou está vazio.")
                    self.user_preferences = {} # Documento existe, mas sem campos de preferência

                _logger.info(f"Preferências LLM do usuário {user_id} carregadas: {self.user_preferences}")
            elif response_pref.status_code == 404:
                _logger.info(f"Nenhuma preferência LLM salva para o usuário {user_id}. Usando padrões.")
                self.user_preferences = {} # Default para vazio
            else:
                self.user_preferences = {}
                _logger.error(f"Erro ao carregar preferências LLM do usuário: {response_pref.status_code} - {response_pref.text}")
                show_snackbar(self.page, "Erro ao carregar suas preferências de LLM.", theme.COLOR_ERROR)
                self._last_pref_error_message = "Erro ao carregar preferências."
        
        except requests.exceptions.RequestException as e_req_pref: # Erros de rede, DNS, etc.
             _logger.error(f"Erro de requisição ao carregar preferências LLM do usuário: {e_req_pref}", exc_info=True)
             self.user_preferences = {}
             show_snackbar(self.page, "Erro de conexão ao carregar suas preferências de LLM.", theme.COLOR_ERROR)
             self._last_pref_error_message = "Erro de conexão ao carregar preferências."
        except Exception as e_pref: # Outras exceções não HTTPError (ex: JSONDecodeError se _make_firestore_request não tratar)
            _logger.error(f"Exceção genérica ao carregar preferências LLM do usuário: {e_pref}", exc_info=True)
            self.user_preferences = {}
            show_snackbar(self.page, "Erro inesperado ao carregar suas preferências de LLM.", theme.COLOR_ERROR)
            self._last_pref_error_message = "Erro de conexão ao carregar preferências."

        hide_loading_overlay(self.page)
        self._update_preference_dropdowns() # Popula e seleciona com base no carregado
        self._update_status_preferences_display()
    
        # Atualizar a UI geral
        if self.page: self.update()

    def _get_dropdown_option_text(self, dropdown: ft.Dropdown, key_value: Optional[str]) -> str:
        """Retorna o texto de uma opção do dropdown com base na sua chave (valor)."""
        if key_value is None:
            return "N/A"
        for option in dropdown.options:
            if option.key == key_value:
                return option.text
        return str(key_value) # Retorna a chave se o texto não for encontrado (fallback)
    
    def _handle_save_preferences(self, e: ft.ControlEvent):
        _logger.info("Salvando preferências de LLM do usuário...")
        self._last_pref_error_message = "" 

        from src.flet_ui.app import check_and_refresh_token_if_needed 
        if not check_and_refresh_token_if_needed(self.page):
            context = None
        else:
            id_token_session = self.page.session.get("auth_id_token")
            user_id_session = self.page.session.get("auth_user_id")
            if id_token_session and user_id_session:
                context = (id_token_session, user_id_session)
            else:
                context = None
        #context = self.provider_cards_map.get(list(self.provider_cards_map.keys())[0] if self.provider_cards_map else "", LLMConfigCard(self.page,{},self.firestore_manager))._get_current_user_context()
        if not context:
            show_snackbar(self.page, "Erro de sessão ao salvar preferências.", theme.COLOR_ERROR)
            self._last_pref_error_message = "Erro de sessão ao salvar."
            self._update_status_preferences_display()
            return
        id_token, user_id = context

        selected_provider = self.default_provider_dropdown.value
        selected_model = self.default_model_dropdown.value

        if not selected_provider:
            show_snackbar(self.page, "Selecione um provedor LLM padrão.", theme.COLOR_WARNING)
            return
        if not selected_model:
            show_snackbar(self.page, "Selecione um modelo LLM padrão para o provedor.", theme.COLOR_WARNING)
            return

        # Verifica se a chave API para o provedor selecionado está configurada
        # Esta verificação depende do estado que o LLMConfigCard mantém ou reporta.
        # Vamos assumir que podemos checar isso.
        # Uma forma é ter os cards atualizando um estado na view pai, ou a view pai consultando os cards.
        # Por simplicidade, se a chave API não estiver na sessão (descriptografada), assumimos que não está configurada
        # ou o usuário precisa configurar/salvar primeiro.
        
        key_for_selected_provider_in_session = f"decrypted_api_key_{selected_provider}"
        if not self.page.session.contains_key(key_for_selected_provider_in_session):
            # Tentativa de carregar do Firestore para a sessão, caso não esteja lá mas esteja salva
            card_instance = self.provider_cards_map.get(selected_provider)
            if card_instance:
                encrypted_bytes = self.firestore_manager.get_user_api_key_client(id_token, user_id, selected_provider)
                if encrypted_bytes:
                    decrypted = credentials_manager.decrypt(encrypted_bytes)
                    if decrypted:
                        self.page.session.set(key_for_selected_provider_in_session, decrypted)
                        _logger.info(f"Chave API para {selected_provider} carregada na sessão para salvar preferências.")
                    else: # Falha ao descriptografar
                        provider_display_name = self._get_dropdown_option_text(self.default_provider_dropdown, selected_provider)
                        show_snackbar(self.page, f"A chave API para {provider_display_name} está salva, mas não pôde ser acessada. Tente salvá-la novamente.", theme.COLOR_ERROR)
                else: # Não tem chave salva no Firestore
                    provider_display_name = self._get_dropdown_option_text(self.default_provider_dropdown, selected_provider)
                    show_snackbar(self.page, f"A chave API para o provedor '{provider_display_name}' não está configurada. Salve-a primeiro.", theme.COLOR_WARNING, duration=5000)
                    return
            else: # Card não encontrado (improvável se o dropdown está populado)
                show_snackbar(self.page, "Erro interno ao verificar configuração da chave API.", theme.COLOR_ERROR)
                return

        new_preferences = {
            "default_provider_system_name": selected_provider,
            "default_model_id": selected_model,
            "updated_at": time.time() # Timestamp da última atualização
        }

        pref_doc_path = f"{USER_LLM_PREFERENCES_COLLECTION}/{user_id}"
        firestore_payload = {"fields": {k: _to_firestore_value(v) for k, v in new_preferences.items()}}

        show_loading_overlay(self.page, "Salvando suas preferências LLM...")
        try:
            # Usar PATCH para criar ou sobrescrever o documento de preferências do usuário
            self.firestore_manager._make_firestore_request(
                method="PATCH", # PATCH para criar/atualizar (set com merge implícito de campos)
                user_token=id_token,
                document_path=pref_doc_path,
                json_data=firestore_payload
                # params={"updateMask.fieldPaths": list(new_preferences.keys())} # Para merge explícito se PATCH não criar
            )
            hide_loading_overlay(self.page)
            self.user_preferences = new_preferences # Atualiza o estado local
            self.save_preferences_button.disabled = True # Desabilita após salvar
            if self.page: 
                self.save_preferences_button.update()
            self._update_status_preferences_display()
            #provider_text = self._get_dropdown_option_text(self.default_provider_dropdown, selected_provider)
            #model_text = self._get_dropdown_option_text(self.default_model_dropdown, selected_model)
            if self.page: 
                self.status_preferences_text.update()
            show_snackbar(self.page, "Preferências de LLM salvas com sucesso!", color=theme.COLOR_SUCCESS)
            _logger.info(f"Preferências LLM salvas para usuário {user_id}: {new_preferences}")

        except Exception as e:
            hide_loading_overlay(self.page)
            _logger.error(f"Erro ao salvar preferências LLM do usuário {user_id}: {e}", exc_info=True)
            self._last_pref_error_message = "Erro ao salvar preferências." # Guarda erro
            self._update_status_preferences_display()
            show_snackbar(self.page, "Não foi possível salvar suas preferências de LLM.", theme.COLOR_ERROR)


def create_llm_settings_view(page: ft.Page) -> ft.Control: # Mudou de ft.View para ft.Control
    _logger.info("Criando o conteúdo da view de Configurações LLM.")

    if not page.session.get("auth_id_token"):
        _logger.warning("Usuário não autenticado tentou acessar Configurações LLM.")
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

