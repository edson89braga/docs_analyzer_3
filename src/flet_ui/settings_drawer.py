# src/flet_ui/settings_drawer.py
import flet as ft
from typing import Dict, Any, Optional, List
from src.services.local_db_manager import LocalDBManager
from src.flet_ui.components import show_snackbar, ManagedAlertDialog
from src.flet_ui import theme
from src.settings import (

    KEY_SESSION_ANALYSIS_SETTINGS,
    KEY_SESSION_CLOUD_ANALYSIS_DEFAULTS,
    FALLBACK_ANALYSIS_SETTINGS,
    KEY_SESSION_LOADED_LLM_PROVIDERS,

    APP_DEFAULT_SETTINGS_COLLECTION,
    CHAT_PROMPTS_DEFAULTS_DOC_ID,
    
    KEY_SESSION_CHAT_PROMPT_STRICT,
    KEY_SESSION_CHAT_PROMPT_FLEXIBLE,
    KEY_SESSION_CHAT_PROMPT_CUSTOM,
    KEY_SESSION_CHAT_PROMPT_ACTIVE_KEY,
)

from src.services.firebase_client import FirebaseClientFirestore, _from_firestore_value
from src.utils import get_user_cache

import logging
logger = logging.getLogger(__name__)

default_width = 260

class BaseSettingsDrawer(ft.Column):
    """
    Classe base para drawers de configurações de análise e LLM.
    Contém a lógica comum para carregar provedores, modelos, e resetar configurações.
    """

    # Mapeamento base -> ctrl_key: setting_key
    KEY_MAP = {
        "llm_provider_dd": "llm_provider",
        "llm_model_dd":    "llm_model",
        "proc_vectorization_dd":        "vectorization_model",
        "similarity_threshold_slider":  "similarity_threshold",
        "llm_token_limit_tf":           "llm_input_token_limit",
        "temperature_slider":           "llm_temperature",
        "llm_max_output_length_tf":     "llm_max_output_length",
        "reasoning_effort_dd":          "reasoning_effort",
        "verbosity_level_dd":           "verbosity_level"
    }
    
    def __init__(self, page: ft.Page):
        super().__init__(scroll=ft.ScrollMode.ADAPTIVE, expand=True)
        self.page = page
        self.gui_controls: Dict[str, ft.Control] = {}
        
        # Controls fora das Sections:
        self.gui_controls["reset_settings_button"] = ft.ElevatedButton(
            "Resetar para Padrões", icon=ft.Icons.SETTINGS_BACKUP_RESTORE_ROUNDED,
            on_click=self._handle_reset_settings_click, visible=False
        )

        # Constrói o conteúdo que é definido pelas classes filhas
        self.build_content()
        self.setup_event_handlers()
        self.load_settings_into_controls()

    def build_content(self):
        """
        Constrói a estrutura visual do drawer. Deve ser implementado pelas classes filhas.
        """
        raise NotImplementedError("As classes filhas devem implementar build_content()")

    def _build_common_processing_section(self) -> List[ft.Control]:
        """
        Constrói a seção comum de configurações de Processamento de Documento.
        """        
        self.gui_controls["proc_vectorization_dd"] = ft.Dropdown(
            label="Modelo de Vetorização",
            options=[
                ft.dropdown.Option("tfidf_vectorizer", "Tf-Idf Vectorizer"),
                ft.dropdown.Option("all-MiniLM-L6-v2", "all-MiniLM-L6-v2"),
                ft.dropdown.Option("text-embedding-3-small", "OpenAI text-embedding-3-small"),
            ],
            width=default_width
        )

        self.gui_controls["similarity_threshold_value_label"] = ft.Text("", weight=ft.FontWeight.BOLD)
        self.gui_controls["similarity_threshold_slider"] = ft.Slider(
            min=0, max=100, divisions=100, expand=True, label="{value}",
            on_change=lambda e: self._handle_slider_change(e, "similarity_threshold_value_label")
        )

        return [
            ft.Text("Processamento de Documento", style=ft.TextThemeStyle.TITLE_MEDIUM),
            self.gui_controls["proc_vectorization_dd"],
            ft.Column([
                ft.Text("Limiar de similaridade"),
                ft.Row([self.gui_controls["similarity_threshold_slider"], self.gui_controls["similarity_threshold_value_label"]]),
            ], spacing=1, width=default_width),
        ]

    def _build_common_llm_section(self) -> List[ft.Control]:
        """
        Constrói a seção comum de seleção de Provedor e Modelo LLM.
        """
        loaded_providers = self.page.session.get(KEY_SESSION_LOADED_LLM_PROVIDERS) or []
        provider_options = [
            ft.dropdown.Option(key=p['system_name'], text=p.get('name_display', p['system_name']))
                                for p in loaded_providers if p.get('system_name')
        ]
        self.gui_controls["llm_provider_dd"] = ft.Dropdown(
            label="Provedor LLM", 
            options=provider_options,
            width=default_width
        )
        self.gui_controls["llm_model_dd"] = ft.Dropdown(
            label="Modelo LLM", 
            options=[],
            width=default_width
        )
        
        return [
            ft.Text("Modelo de Linguagem (LLM)", style=ft.TextThemeStyle.TITLE_MEDIUM),
            self.gui_controls["llm_provider_dd"],
            self.gui_controls["llm_model_dd"],
        ]

    def _build_models_section(self) -> List[ft.Control]:
        """
        Constrói os controles que dependem do modelo LLM selecionado.
        """
        # All models
        self.gui_controls["llm_token_limit_tf"] = ft.TextField(
            label="Limite Tokens Input", 
            input_filter=ft.InputFilter(r"[0-9]"), 
            width=default_width
        )        

        # gpt-4
        self.gui_controls["temperature_value_label"] = ft.Text("", weight=ft.FontWeight.BOLD)
        self.gui_controls["temperature_slider"] = ft.Slider(
            min=0.0, max=200.0, divisions=20, expand=True, label="{value}",
            on_change=lambda e: self._handle_slider_change(e, "temperature_value_label")
        )
        self.gui_controls["llm_max_output_length_tf"] = ft.TextField(
            label="Comprimento Máx. Saída", 
            hint_text="Padrão do modelo", 
            value="Padrão",
            width=default_width, 
            read_only=True # A princípio não editável
        )
        
        # gpt-5
        self.gui_controls["reasoning_effort_dd"] = ft.Dropdown(
            label="Esforço de Reflexão", 
            options=[ft.dropdown.Option(k) for k in ["minimal", "low", "medium", "high"]],
            value="medium", 
            width=default_width
        )
        self.gui_controls["verbosity_level_dd"] = ft.Dropdown(
            label="Nível de Verbosidade", 
            options=[ft.dropdown.Option(k) for k in ["low", "medium", "high"]],
            value="medium", 
            width=default_width
        )
        
        return [
            ft.Text("Parâmetros do Modelo", style=ft.TextThemeStyle.TITLE_MEDIUM),
            self.gui_controls["llm_token_limit_tf"],
            ft.Column([
                ft.Text("Temperatura de Resposta"),
                ft.Row([self.gui_controls["temperature_slider"], self.gui_controls["temperature_value_label"]]),
            ], spacing=1, width=default_width),
            self.gui_controls["llm_max_output_length_tf"],
            self.gui_controls["reasoning_effort_dd"],
            self.gui_controls["verbosity_level_dd"],
        ]
    
    def setup_event_handlers(self):
        """
        Configura os handlers de eventos para os controles comuns.
        """
        if "llm_provider_dd" in self.gui_controls:
            self.gui_controls["llm_provider_dd"].on_change = self._handle_provider_change
        if "llm_model_dd" in self.gui_controls:
            self.gui_controls["llm_model_dd"].on_change = self._handle_model_change
        
        for ctrl in ["proc_vectorization_dd", "llm_token_limit_tf", "llm_max_output_length_tf", 
                     "reasoning_effort_dd", "verbosity_level_dd"]:
            if ctrl in self.gui_controls:
                self.gui_controls[ctrl].on_change = self._handle_setting_change

        for ctrl in ("similarity_threshold_slider", "temperature_slider"):
            if ctrl in self.gui_controls:
                self.gui_controls[ctrl].on_change_end = self._handle_setting_change 

    def _handle_reset_settings_click(self, e: ft.ControlEvent):
        """
        Reseta as configurações para os padrões da nuvem.
        """
        cloud_defaults = self.page.session.get(KEY_SESSION_CLOUD_ANALYSIS_DEFAULTS)
        if cloud_defaults:
            self.page.session.set(KEY_SESSION_ANALYSIS_SETTINGS, cloud_defaults.copy())
            self.load_settings_into_controls()
            show_snackbar(self.page, "Configurações resetadas para os padrões.", theme.COLOR_INFO)
        else:
            show_snackbar(self.page, "Padrões da nuvem não encontrados.", theme.COLOR_ERROR)
            
    def _populate_models_for_selected_provider(self, provider_system_name: Optional[str], current_model_value: Optional[str] = None, new_provider_selected: bool = False):
        """
        Popula o dropdown de modelos com base no provedor selecionado.
        """
        model_dd = self.gui_controls.get("llm_model_dd")
        if not isinstance(model_dd, ft.Dropdown): return

        model_dd.options = []
        model_dd.disabled = True
        loaded_providers = self.page.session.get(KEY_SESSION_LOADED_LLM_PROVIDERS) or []

        if provider_system_name and loaded_providers:
            provider_config = next((p for p in loaded_providers if p.get("system_name") == provider_system_name), None)
            if provider_config and provider_config.get("models"):
                model_options = [
                    ft.dropdown.Option(key=m['id'], text=m.get('name', m['id']))
                    for m in provider_config["models"] if m.get("id")
                ]
                model_dd.options = model_options
                model_dd.disabled = False
                
                if new_provider_selected and model_options:
                    model_dd.value = model_options[0].key
                elif current_model_value and any(opt.key == current_model_value for opt in model_options):
                    model_dd.value = current_model_value
                elif model_options:
                    model_dd.value = model_options[0].key
                else:
                    model_dd.value = None
        
        if model_dd.page: model_dd.update()

    def _handle_provider_change(self, e: ft.ControlEvent):
        """
        Handler para a mudança de provedor LLM. Atualiza as opções de modelo.
        """
        self._populate_models_for_selected_provider(e.control.value, new_provider_selected=True)
        self._handle_model_change(e) # Para reavaliar os campos gpt-4/gpt-5

    def _toggle_model_specific_fields(self, update_ui: bool = True):
        """
        Habilita/desabilita os campos de configuração com base no modelo selecionado.
        """
        model_value = self.gui_controls["llm_model_dd"].value or ""
        is_gpt4 = model_value.startswith("gpt-4")
        is_gpt5 = model_value.startswith("gpt-5")
        
        # GPT-4
        self.gui_controls["temperature_slider"].disabled = not is_gpt4
        self.gui_controls["llm_max_output_length_tf"].disabled = not is_gpt4
        # GPT-5
        self.gui_controls["reasoning_effort_dd"].disabled = not is_gpt5
        self.gui_controls["verbosity_level_dd"].disabled = not is_gpt5
        
        if update_ui and self.page:
            for key in ["temperature_slider", "llm_max_output_length_tf", "reasoning_effort_dd", "verbosity_level_dd"]:
                if self.gui_controls[key].page: # Verificação extra de segurança
                    self.gui_controls[key].update()

    def _handle_model_change(self, e: ft.ControlEvent):
        """
        Handler para a mudança de modelo LLM. Salva a configuração e atualiza a UI.
        Este método será estendido nas classes filhas para lógica específica.
        """
        self._toggle_model_specific_fields(update_ui=True)
        self.save_settings_to_session()

    def _handle_slider_change(self, e: ft.ControlEvent, label_key: str, divisor: int = 100, format_str: str = "{:.2f}"):
        """Atualiza o label de um slider."""
        label = self.gui_controls.get(label_key)
        if isinstance(label, ft.Text):
            label.value = format_str.format(float(e.control.value) / divisor)
            if label.page: label.update()

    def _handle_setting_change(self, e: ft.ControlEvent):
        """Handler genérico para salvar qualquer mudança."""
        self.save_settings_to_session()

    def save_settings_to_session(self):
        """
        Coleta os valores dos controles e os salva na sessão da página.
        """
        # Apenas administradores podem alterar
        if not self.page.session.get("is_admin"):
            ...
            # show_snackbar(self.page, "Alteração de configurações restrita a administradores.", color=theme.COLOR_WARNING)
            # self.load_settings_into_controls() # Reverte
            # return

        new_settings = self._get_settings_from_controls()
        self.page.session.set(KEY_SESSION_ANALYSIS_SETTINGS, new_settings)
        logger.info(f"[DEBUG] Configurações da sessão atualizadas: {new_settings}")
        self._update_reset_button_visibility()

    def _get_settings_from_controls(self) -> Dict[str, Any]:
        """
        Coleta os valores dos controles da UI. 
        Deve ser estendido pelas classes filhas, se necessário.
        """
        settings = {}
        
        for ctrl_key, setting_key in self.KEY_MAP.items():
            if ctrl_key in self.gui_controls and hasattr(self.gui_controls[ctrl_key], 'value'):
                control = self.gui_controls[ctrl_key]
                value = self.gui_controls[ctrl_key].value
                if isinstance(control, ft.Slider) and setting_key in ("llm_temperature", "similarity_threshold"):
                    value = float(control.value) / 100.0
                settings[setting_key] = value
        
        return settings
    
    def load_settings_into_controls(self):
        """
        Carrega as configurações da sessão para os controles da UI.
        Deve ser estendido pelas classes filhas, se necessário.
        """
        current_settings = self.page.session.get(KEY_SESSION_ANALYSIS_SETTINGS) or FALLBACK_ANALYSIS_SETTINGS.copy()
        initial_simi_threshold = current_settings.get("similarity_threshold", 0.87)
        initial_temp = current_settings.get("llm_temperature", 0.20)

        self._populate_models_for_selected_provider(current_settings.get("llm_provider"), current_settings.get("llm_model"))

        for ctrl_key, setting_key in self.KEY_MAP.items():
            if ctrl_key in self.gui_controls:
                if ctrl_key.endswith("_tf"):
                    self.gui_controls[ctrl_key].value = str(current_settings.get(setting_key))
                elif ctrl_key == "similarity_threshold_slider":
                    self.gui_controls[ctrl_key].value = initial_simi_threshold * 100
                    self.gui_controls["similarity_threshold_value_label"].value = f"{initial_simi_threshold:.2f}"
                elif ctrl_key == "temperature_slider":
                    self.gui_controls[ctrl_key].value = initial_temp * 100
                    self.gui_controls["temperature_value_label"].value = f"{initial_temp:.2f}"
                else:
                    self.gui_controls[ctrl_key].value = current_settings.get(setting_key)

        self._update_reset_button_visibility()
        self._toggle_model_specific_fields(update_ui=False) # Garante o estado de disabled correto
        # if self.page: self.update()               

    def _update_reset_button_visibility(self):
        """
        Mostra ou esconde o botão de resetar com base nas diferenças entre as
        configurações atuais e as padrões.
        """
        current_settings = self.page.session.get(KEY_SESSION_ANALYSIS_SETTINGS) or {}
        cloud_defaults = self.page.session.get(KEY_SESSION_CLOUD_ANALYSIS_DEFAULTS) or {}
        reset_button = self.gui_controls.get("reset_settings_button")
        
        if not reset_button: return

        are_different = False
        # Compara apenas as chaves que existem em ambos, para evitar problemas
        common_keys = set(current_settings.keys()) & set(cloud_defaults.keys())
        for key in common_keys:
            if current_settings[key] != cloud_defaults[key]:
                are_different = True
                break
        
        reset_button.visible = are_different
        if reset_button.page: reset_button.update()


class AnalyzeSettingsDrawer(BaseSettingsDrawer):
    """
    Drawer de configurações específico para a view de Análise de Documentos (nc_analyze).
    """
    def build_content(self):
        """
        Constrói a UI do drawer de análise, incluindo seções específicas de modelo.
        """
        self.controls = [
            ft.Text("Configurações", style=ft.TextThemeStyle.TITLE_LARGE),
            ft.Divider(),
            *self._build_common_processing_section(),
            ft.Divider(),            
            *self._build_common_llm_section(),
            ft.Divider(),
            *self._build_models_section(),
            ft.Container(expand=True), # Empurra para baixo
            ft.Row([self.gui_controls["reset_settings_button"]], alignment=ft.MainAxisAlignment.CENTER),
            ft.Container(height=1)
        ]
        
DEFAULT_PROMPTS = {
    "estrito": '''
Você é um assistente especializado em análise de documentos para a Polícia Federal.  
Sua principal função é responder perguntas baseando-se estrita e exclusivamente no texto do(s) documento(s) fornecido(s).  

Regras:  
- Seja preciso, objetivo e neutro.  
- Se a resposta não estiver claramente contida no(s) documento(s), informe:  
  "A informação não foi encontrada no(s) documento(s) fornecido(s)."  
- Não invente, não deduza, não utilize conhecimento externo ao(s) documento(s).  
- Não use exemplos ou analogias que não estejam presentes nos documentos.  
''',
    
    "flexivel": '''
Você é um assistente especializado em análise de documentos para a Polícia Federal.  
Sua principal função é responder perguntas dando prioridade ao(s) documento(s) fornecido(s), mas você também pode utilizar seu conhecimento geral para complementar informações.  

Regras:  
- Sempre indique claramente quando a resposta vem do documento (ex.: "No documento consta que...")  
- Se utilizar conhecimento externo, diferencie com clareza (ex.: "Além do documento, em termos gerais...").  
- Seja preciso, objetivo e mantenha tom neutro.  
- Caso não haja referência direta no documento, explique com transparência que a resposta foi baseada em conhecimento geral.  
'''
}

class ChatSettingsDrawer(AnalyzeSettingsDrawer):
    """
    Drawer de configurações específico para a view de Chat com Documentos.
    Herda de AnalyzeSettingsDrawer e adiciona a seção de Prompt de Instruções.
    """
    PROMPT_KEY_MAP = { # session_key: cache_key
        "estrito": KEY_SESSION_CHAT_PROMPT_STRICT,
        "flexivel": KEY_SESSION_CHAT_PROMPT_FLEXIBLE,
        "custom": KEY_SESSION_CHAT_PROMPT_CUSTOM,
    }
    DEFAULT_KEY = "flexivel"
    
    def __init__(self, page: ft.Page):
        self.page = page
        self.user_cache = get_user_cache(self.page) # chamar aqui antes de super()
        self.db_manager = LocalDBManager()
        super().__init__(page)

    def build_content(self):
        """
        Constrói a UI do drawer de chat, adicionando a seção de prompt.
        """
        # Chama a implementação da classe pai para construir as seções comuns
        super().build_content()
        
        # Adiciona a nova seção de prompt
        self.controls.insert(1, ft.Divider()) 
        self.controls.insert(2, self._build_instructions_prompt_section())

    def _build_instructions_prompt_section(self) -> ft.Control:
        """
        Constrói a seção para gerenciar o prompt de instruções do sistema.
        """
        # Carrega o prompt ativo para exibir no campo
        active_prompt_text = self._get_active_prompt_text()

        self.gui_controls["instructions_prompt_tf"] = ft.TextField(
            label="Prompt de Instruções do Sistema",
            value=active_prompt_text,
            multiline=True, min_lines=4, max_lines=4,
            read_only=True, width=default_width,
            on_click=self.open_prompt_dialog,
            tooltip="Clique para editar as instruções do assistente"
        )
        return ft.Column([
            ft.Text("Instruções do Assistente", style=ft.TextThemeStyle.TITLE_MEDIUM),
            self.gui_controls["instructions_prompt_tf"]
        ])

    def _get_active_prompt_text(self) -> str:
        """
        Retorna o texto do prompt de sistema ativo com base na sessão.
        """
        # Garante que os prompts padrão (de Firestore ou fallback) estejam na sessão
        if KEY_SESSION_CHAT_PROMPT_FLEXIBLE not in self.user_cache:
            self.load_default_prompts_from_firestore_or_fallback()
        
        session_key = self.page.session.get(KEY_SESSION_CHAT_PROMPT_ACTIVE_KEY) or self.DEFAULT_KEY
        cache_key = self.PROMPT_KEY_MAP.get(session_key)
        if not cache_key: return "" # Segurança

        if session_key == "custom":
            # Para custom, tenta o cache primeiro, depois o DB
            custom_prompt = self.user_cache.get(cache_key) or self.db_manager.get_custom_prompt("chat_custom")
            if custom_prompt:
                self.user_cache[cache_key] = custom_prompt # Garante que está em cache
                logger.info(f"[DEBUG] GetActivePrompt: Chave ativa='{session_key}' - '{cache_key}' -> Texto: '{custom_prompt[:60]}...'")
                return custom_prompt

        # O fallback aqui é uma segurança extra, mas _load_default... já deve ter populado
        prompt_text = self.user_cache.get(cache_key) or DEFAULT_PROMPTS[self.DEFAULT_KEY] or ""
        logger.info(f"[DEBUG] GetActivePrompt: Chave ativa='{session_key}' - '{cache_key}' -> Texto: '{prompt_text[:60]}...'")
        return prompt_text
    
    def load_default_prompts_from_firestore_or_fallback(self):
        """
        Tenta carregar os prompts padrão do Firestore. Se falhar, usa os
        prompts hardcoded como fallback e os salva na sessão.
        """
        # Verifica se já foram carregados para evitar chamadas de rede desnecessárias
        if (KEY_SESSION_CHAT_PROMPT_STRICT in self.user_cache and
            KEY_SESSION_CHAT_PROMPT_FLEXIBLE in self.user_cache):
            logger.info("[DEBUG] Prompts padrão já estão no cache. Pulando carregamento.")
            return

        logger.info("[DEBUG] Tentando carregar prompts padrão do Firestore...")
        user_token = self.page.session.get("auth_id_token")
        if not user_token:
            logger.warning("Drawer: Token de usuário ausente, usando prompts de fallback.")
            self.user_cache[KEY_SESSION_CHAT_PROMPT_STRICT] = DEFAULT_PROMPTS["estrito"]
            self.user_cache[KEY_SESSION_CHAT_PROMPT_FLEXIBLE] = DEFAULT_PROMPTS["flexivel"]
            return

        try:
            firestore_client = FirebaseClientFirestore()
            doc_path = f"{APP_DEFAULT_SETTINGS_COLLECTION}/{CHAT_PROMPTS_DEFAULTS_DOC_ID}"
            response = firestore_client._make_firestore_request("GET", user_token, doc_path)

            if response.status_code == 200:
                fields = response.json().get("fields", {})

                prompt_estrito = _from_firestore_value(fields.get("estrito", {}))   or DEFAULT_PROMPTS["estrito"]
                prompt_flexivel = _from_firestore_value(fields.get("flexivel", {})) or DEFAULT_PROMPTS["flexivel"]

                self.user_cache[KEY_SESSION_CHAT_PROMPT_STRICT] = prompt_estrito
                self.user_cache[KEY_SESSION_CHAT_PROMPT_FLEXIBLE] = prompt_flexivel

                logger.info("Drawer: Prompts padrão carregados com sucesso do Firestore.")
                return
            else:
                logger.error(f"Drawer: Erro ao buscar prompts do Firestore: {response.status_code}. Usando fallback.")

        except Exception as e:
            logger.error(f"Drawer: Erro ao buscar prompts do Firestore: {e}. Usando fallback.", exc_info=True)

        # Lógica de Fallback
        logger.warning("Drawer: Usando prompts padrão de fallback (hardcoded).")
        self.user_cache[KEY_SESSION_CHAT_PROMPT_STRICT] = DEFAULT_PROMPTS["estrito"]
        self.user_cache[KEY_SESSION_CHAT_PROMPT_FLEXIBLE] = DEFAULT_PROMPTS["flexivel"]

    def open_prompt_dialog(self, e: ft.ControlEvent):
        """
        Abre o diálogo de edição do prompt de instruções.
        """
        logger.info("[DEBUG] Abrindo diálogo de edição de prompt.")

        prompt_editor_tf = ft.TextField(
            value=self._get_active_prompt_text(), width=self.page.width * 0.6,
            multiline=True, min_lines=10, max_lines=20, expand=True, border_radius=8
        )

        def update_editor_text(e: ft.ControlEvent):
            selected_key = e.control.value
            cache_key = self.PROMPT_KEY_MAP.get(str(selected_key))
            if not cache_key:
                logger.warning(f"Chave de prompt inválida '{selected_key}' no RadioGroup.")
                show_snackbar(self.page, f"Chave de prompt inválida ({selected_key}).", theme.COLOR_ERROR)
                return
            prompt_text = self.user_cache.get(cache_key) or DEFAULT_PROMPTS.get(str(selected_key), "")
            logger.info(f"[DEBUG] RadioGroup alterado para '{selected_key}'. Carregando texto do prompt: '{prompt_text[:60]}...'")
            prompt_editor_tf.value = prompt_text

            # Força a atualização de ambos os controles para evitar bugs de estado
            prompt_selection_rg.update()
            prompt_editor_tf.read_only = selected_key in ["estrito", "flexivel"]
            prompt_editor_tf.update()

        active_key = self.page.session.get(KEY_SESSION_CHAT_PROMPT_ACTIVE_KEY) or self.DEFAULT_KEY

        prompt_selection_rg = ft.RadioGroup(
            value=active_key,
            content=ft.Row([
                ft.Radio(value="estrito", label="Estrito (Apenas no Documento)"),
                ft.Radio(value="flexivel", label="Flexível (Permite Conhecimento Geral)"),
                ft.Radio(value="custom", label="Personalizado"),
            ]),
            on_change=update_editor_text,
        )

        def save_and_close(e: ft.ControlEvent):
            selected_key = prompt_selection_rg.value
            logger.info(f"[DEBUG] Salvando prompt. Chave ativa selecionada: '{selected_key}'")
            self.page.session.set(KEY_SESSION_CHAT_PROMPT_ACTIVE_KEY, selected_key)
            
            # Se a opção customizada estiver selecionada, salva o texto editado
            if selected_key == "custom":
                custom_text_to_save = prompt_editor_tf.value
                self.user_cache[KEY_SESSION_CHAT_PROMPT_CUSTOM] = custom_text_to_save
                logger.info(f"[DEBUG] Salvando texto customizado na sessão: '{custom_text_to_save[:60]}...'")
                self.db_manager.save_custom_prompt("chat_custom", custom_text_to_save)
            
            # Atualiza o campo principal na drawer
            self.gui_controls["instructions_prompt_tf"].value = self._get_active_prompt_text()
            self.gui_controls["instructions_prompt_tf"].update()
            
            # Fecha o diálogo (usando o ManagedAlertDialog)
            dialog.close_programmatically(result_data_for_callback="saved")

        dialog_content = ft.Column(
            [prompt_selection_rg, 
             prompt_editor_tf],
            spacing=15, scroll=ft.ScrollMode.ADAPTIVE, expand=True
        )

        dialog = ManagedAlertDialog(
            page_ref=self.page,
            title="Editar Prompt de Instruções",
            content=dialog_content,
            actions=[
                ft.ElevatedButton("Cancelar", width=100, on_click=lambda e: dialog.close_programmatically("cancelled"), data="cancel"),
                ft.ElevatedButton("Salvar", width=100, on_click=save_and_close, data="save"),
            ],
        )
        dialog.show()
    

        