# src/flet_ui/components/settings_drawer.py
import flet as ft
from typing import Dict, Any, Optional

from src.flet_ui.components import show_snackbar
from src.flet_ui import theme
from src.settings import (
    KEY_SESSION_ANALYSIS_SETTINGS,
    KEY_SESSION_CLOUD_ANALYSIS_DEFAULTS,
    FALLBACK_ANALYSIS_SETTINGS,
    KEY_SESSION_LOADED_LLM_PROVIDERS
)

import logging
logger = logging.getLogger(__name__)

class SettingsDrawerManager(ft.Column):
    """
    Componente de Drawer reutilizável para gerenciar as configurações de análise de documentos e LLM.
    """
    def __init__(self, page: ft.Page):
        super().__init__(scroll=ft.ScrollMode.ADAPTIVE, expand=True)
        self.page = page
        self.gui_controls: Dict[str, ft.Control] = {}
        
        self._build_content()
        self.setup_event_handlers()
        self._load_settings_into_controls()

    def _build_content(self):
        """
        Constrói e retorna o conteúdo visual do drawer de configurações.

        Este método cria os controles de UI para as diversas configurações de processamento
        de documentos e modelos de linguagem (LLM), incluindo sliders, dropdowns e campos de texto.

        Returns:
            ft.Column: Um ft.Column contendo todos os controles de configuração.
        """
        logger.debug("SettingsDrawerManager: Construindo conteúdo do drawer.")
        default_width = 260
        current_analysis_settings = self.page.session.get(KEY_SESSION_ANALYSIS_SETTINGS) or FALLBACK_ANALYSIS_SETTINGS.copy()
        loaded_llm_providers = self.page.session.get(KEY_SESSION_LOADED_LLM_PROVIDERS) or []

        self.gui_controls["proc_vectorization_dd"]  = ft.Dropdown(label="Modelo de Vetorização", options=[
            ft.dropdown.Option("tfidf_vectorizer", "Tf-Idf Vectorizer"),
            ft.dropdown.Option("all-MiniLM-L6-v2", "all-MiniLM-L6-v2"),
            ft.dropdown.Option("text-embedding-3-small", "OpenAI text-embedding-3-small"),
        ], value=current_analysis_settings.get("vectorization_model"), width=default_width)

        initial_temp_sim = current_analysis_settings.get("similarity_threshold", 0.87)
        self.gui_controls["similarity_threshold_value_label"] = ft.Text(f"{initial_temp_sim:.2f}", weight=ft.FontWeight.BOLD)
        self.gui_controls["similarity_threshold_slider"] = ft.Slider(
            min=0, max=100, value=initial_temp_sim * 100,
            divisions=100, expand=True, label="{value}",
        )
 
        provider_options_drawer = [
            ft.dropdown.Option(key=p['system_name'], text=p.get('name_display', p['system_name']))
            for p in loaded_llm_providers if p.get('system_name')
        ]
        self.gui_controls["llm_provider_dd"] = ft.Dropdown(label="Provedor LLM", options=provider_options_drawer,
                                                                  value=current_analysis_settings.get("llm_provider"), width=default_width)
        self.gui_controls["llm_model_dd"] = ft.Dropdown(label="Modelo LLM", options=[],
                                                               value=current_analysis_settings.get("llm_model"), width=default_width)
        self._populate_models_for_selected_provider(current_analysis_settings.get("llm_provider"), current_analysis_settings.get("llm_model"))
 
        self.gui_controls["llm_token_limit_tf"] = ft.TextField(
            label="Limite Tokens Input", value=str(current_analysis_settings.get("llm_input_token_limit")),
            input_filter=ft.InputFilter(r"[0-9]"), width=default_width
        )
        self.gui_controls["llm_max_output_length_tf"] = ft.TextField(
            label="Comprimento Max. Saída", value=str(current_analysis_settings.get("llm_max_output_length")),
            input_filter=ft.InputFilter(r"[0-9]*"),
            hint_text="Deixe 'Padrão' ou vazio para usar o default do modelo",
            width=default_width, read_only=True
        )
 
        initial_temp_llm = current_analysis_settings.get("llm_temperature", 0.2)
        self.gui_controls["temperature_value_label"] = ft.Text(f"{initial_temp_llm:.1f}", weight=ft.FontWeight.BOLD)
        self.gui_controls["temperature_slider"] = ft.Slider(
            min=0.0, max=20.0, value=initial_temp_llm * 10,
            divisions=20, expand=True, label="{value}",
        )
 
        self.gui_controls["prompt_structure_rg"] = ft.RadioGroup(
            content=ft.Column([
                ft.Radio(value="prompt_unico", label="Prompt Único"),
                ft.Radio(value="sequential_prompts", label="Prompt Agrupado", disabled=False),
            ], spacing=1), value=current_analysis_settings.get("prompt_structure")
        )
 
        self.gui_controls["reset_settings_button"] = ft.ElevatedButton(
            "Resetar para Padrões",
            icon=ft.Icons.SETTINGS_BACKUP_RESTORE_ROUNDED,
            on_click=self._handle_reset_settings_click,
            visible=False,
        )
 
        self.controls = [
            ft.Text("Configurações da Análise", style=ft.TextThemeStyle.TITLE_LARGE),
            ft.Divider(),
            ft.Text("Processamento de Documento", style=ft.TextThemeStyle.TITLE_MEDIUM),
            self.gui_controls["proc_vectorization_dd"],
            ft.Column([
                ft.Text("Limiar de similaridade", style=ft.TextThemeStyle.LABEL_MEDIUM),
                ft.Row([self.gui_controls["similarity_threshold_slider"],self.gui_controls["similarity_threshold_value_label"]],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN)],
                width=default_width, spacing=1),
            ft.Divider(),
            ft.Text("Modelo de Linguagem (LLM)", style=ft.TextThemeStyle.TITLE_MEDIUM),
            self.gui_controls["llm_provider_dd"],
            self.gui_controls["llm_model_dd"],
            self.gui_controls["llm_token_limit_tf"],
            self.gui_controls["llm_max_output_length_tf"],
            ft.Column([
                ft.Text("Temperatura de resposta", style=ft.TextThemeStyle.LABEL_MEDIUM),
                ft.Row([self.gui_controls["temperature_slider"],self.gui_controls["temperature_value_label"]],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN)],
                width=default_width, spacing=1),
            ft.Divider(),
            ft.Text("Estrutura do Prompt", style=ft.TextThemeStyle.TITLE_MEDIUM),
            self.gui_controls["prompt_structure_rg"],
            ft.Container(expand=True),
            ft.Row([self.gui_controls["reset_settings_button"]],
                    expand=True, alignment=ft.MainAxisAlignment.CENTER),
            ft.Container(height=1)
        ]

    def setup_event_handlers(self):
        """
        Configura os handlers de eventos para os controles dentro do drawer.

        Associa as funções de tratamento de eventos aos controles de configuração
        para que as alterações do usuário sejam capturadas e as configurações sejam atualizadas.
        """
        logger.debug("SettingsDrawerManager: Configurando handlers de eventos.")
        controls_to_watch = [
            "proc_vectorization_dd", "llm_provider_dd", "llm_model_dd", "llm_token_limit_tf", "temperature_slider",
            "prompt_structure_rg", "similarity_threshold_slider"
        ]
        for key in controls_to_watch:
            if key in self.gui_controls:
                control = self.gui_controls[key]
                if key == "llm_provider_dd":
                    control.on_change = self._handle_provider_change_drawer
                elif key in ["temperature_slider", "similarity_threshold_slider"]:
                    control.on_change = self._handle_setting_change_drawer
                elif hasattr(control, 'on_change'):
                     control.on_change = self._handle_setting_change_drawer
                # Para RadioGroup, o evento é on_change, já coberto acima

    def _handle_setting_change_drawer(self, e: Optional[ft.ControlEvent] = None):
        """
        Chamado quando qualquer configuração no drawer é alterada pelo usuário.

        Atualiza as configurações na sessão e a visibilidade do botão de reset.
        Se o usuário não for administrador, reverte a alteração e exibe um aviso.

        Args:
            e (Optional[ft.ControlEvent]): O evento de controle que disparou a alteração (opcional).
        """
        if not self.page.session.get("is_admin"):
            show_snackbar(self.page, "Alteração de configurações restrita à usuários administradores.", color=theme.COLOR_WARNING)
            current_settings = self.page.session.get(KEY_SESSION_ANALYSIS_SETTINGS) or FALLBACK_ANALYSIS_SETTINGS.copy()
            self._load_settings_into_controls(current_settings)
            return
        
        if e and isinstance(e.control, ft.Slider) and e.control == self.gui_controls.get("temperature_slider"):
            slider_val = float(e.control.value) / 10.0
            temp_label = self.gui_controls.get("temperature_value_label")
            if isinstance(temp_label, ft.Text):
                temp_label.value = f"{slider_val:.1f}"
                if temp_label.page: temp_label.update()
        elif e and isinstance(e.control, ft.Slider) and e.control == self.gui_controls.get("similarity_threshold_slider"):
            slider_val = float(e.control.value) / 100.0
            temp_label = self.gui_controls.get("similarity_threshold_value_label")
            if isinstance(temp_label, ft.Text):
                temp_label.value = f"{slider_val:.2f}"
                if temp_label.page: temp_label.update()
 
        new_settings = self._get_settings_from_controls()
        self.page.session.set(KEY_SESSION_ANALYSIS_SETTINGS, new_settings)
        logger.debug(f"SettingsDrawerManager: Configurações da sessão atualizadas: {new_settings}")
        self._update_reset_button_visibility()

    def _handle_provider_change_drawer(self, e: ft.ControlEvent):
        """
        Handler para a mudança de provedor LLM no dropdown do drawer.

        Atualiza as opções de modelo LLM disponíveis com base no provedor selecionado
        e chama o handler de alteração de configuração geral.

        Args:
            e (ft.ControlEvent): O evento de alteração do dropdown.
        """
        if not self.page.session.get("is_admin"):
            show_snackbar(self.page, "Alteração de configurações restrita à usuários administradores.", color=theme.COLOR_WARNING)
            current_settings = self.page.session.get(KEY_SESSION_ANALYSIS_SETTINGS) or FALLBACK_ANALYSIS_SETTINGS.copy()
            self._load_settings_into_controls(current_settings)
            return
        selected_provider_system_name = e.control.value
        self._populate_models_for_selected_provider(selected_provider_system_name, new_provider_selected=True)
        self._handle_setting_change_drawer(e)

    def _populate_models_for_selected_provider(self, provider_system_name: Optional[str], current_model_value: Optional[str] = None, new_provider_selected:bool=False):
        """
        Popula o dropdown de modelos LLM com base no provedor selecionado.
 
        Args:
            provider_system_name (Optional[str]): O nome do sistema do provedor selecionado.
            current_model_value (Optional[str]): O valor do modelo atualmente selecionado (para restaurar estado).
            new_provider_selected (bool): Indica se um novo provedor foi selecionado (para resetar o modelo para o primeiro disponível).
        """
        model_dropdown_drawer = self.gui_controls.get("llm_model_dd")
        if not model_dropdown_drawer or not isinstance(model_dropdown_drawer, ft.Dropdown):
            return
 
        model_dropdown_drawer.options = []
        model_dropdown_drawer.disabled = True
        loaded_llm_providers = self.page.session.get(KEY_SESSION_LOADED_LLM_PROVIDERS) or []
 
        if provider_system_name and loaded_llm_providers:
            provider_config = next((p for p in loaded_llm_providers if p.get("system_name") == provider_system_name), None)
            if provider_config and provider_config.get("models"):
                model_options = [
                    ft.dropdown.Option(key=m['id'], text=m.get('name', m['id']))
                    for m in provider_config["models"] if m.get("id")
                ]
                model_dropdown_drawer.options = model_options
                model_dropdown_drawer.disabled = False
 
                if new_provider_selected and model_options:
                    model_dropdown_drawer.value = model_options[0].key
                elif current_model_value and any(opt.key == current_model_value for opt in model_options):
                    model_dropdown_drawer.value = current_model_value
                elif model_options:
                    model_dropdown_drawer.value = model_options[0].key
                else:
                    model_dropdown_drawer.value = None
 
        if model_dropdown_drawer.page: model_dropdown_drawer.update()

    def _get_settings_from_controls(self) -> Dict[str, Any]:
        """
        Coleta os valores atuais dos controles do drawer e os retorna como um dicionário de configurações.
 
        Realiza a conversão de tipos quando necessário (ex: string para int/float).
 
        Returns:
            Dict[str, Any]: Um dicionário contendo as configurações atuais do drawer.
        """
        settings = {}
        key_map = {
            "proc_vectorization_dd": "vectorization_model",
            "llm_provider_dd": "llm_provider",
            "llm_model_dd": "llm_model",
            "llm_token_limit_tf": "llm_input_token_limit",
            "llm_max_output_length_tf": "llm_max_output_length",
            "temperature_slider": "llm_temperature",
            "similarity_threshold_slider": "similarity_threshold",
            "prompt_structure_rg": "prompt_structure",
        }
        for ctrl_key, setting_key in key_map.items():
            if ctrl_key in self.gui_controls:
                control = self.gui_controls[ctrl_key]
                value = control.value
                if setting_key == "llm_input_token_limit":
                    try: value = int(value) if value else FALLBACK_ANALYSIS_SETTINGS[setting_key]
                    except ValueError: value = FALLBACK_ANALYSIS_SETTINGS[setting_key]
                elif setting_key == "llm_max_output_length":
                    value = value if value and value.lower() != "padrão" else FALLBACK_ANALYSIS_SETTINGS[setting_key]
                    if value != "Padrão":
                        try: value = int(value)
                        except ValueError: value = FALLBACK_ANALYSIS_SETTINGS[setting_key]
                elif setting_key == "llm_temperature" and isinstance(control, ft.Slider):
                    value = float(control.value) / 10.0
                elif setting_key == "similarity_threshold" and isinstance(control, ft.Slider):
                    value = float(control.value) / 100.0
                settings[setting_key] = value
        return settings

    def _load_settings_into_controls(self, settings_to_load: Optional[Dict[str, Any]] = None):
        """
        Carrega um dicionário de configurações para os controles do drawer.
 
        Args:
            settings_to_load (Dict[str, Any]): O dicionário de configurações a ser carregado.
        """
        logger.debug("SettingsDrawerManager: Carregando configurações para o drawer.")
        if settings_to_load is None:
            settings_to_load = self.page.session.get(KEY_SESSION_ANALYSIS_SETTINGS) or FALLBACK_ANALYSIS_SETTINGS.copy()

        loaded_llm_providers = self.page.session.get(KEY_SESSION_LOADED_LLM_PROVIDERS) or []
        provider_options_drawer = [
            ft.dropdown.Option(key=p['system_name'], text=p.get('name_display', p['system_name']))
            for p in loaded_llm_providers if p.get('system_name')
        ]
        drawer_provider_dd = self.gui_controls.get("llm_provider_dd")
        if isinstance(drawer_provider_dd, ft.Dropdown):
            drawer_provider_dd.options = provider_options_drawer
            drawer_provider_dd.value = settings_to_load.get("llm_provider")
            if drawer_provider_dd.page: drawer_provider_dd.update()
 
        self._populate_models_for_selected_provider(
            settings_to_load.get("llm_provider"),
            settings_to_load.get("llm_model")
        )
        control_map = {
            "vectorization_model": self.gui_controls.get("proc_vectorization_dd"),
            "llm_input_token_limit": self.gui_controls.get("llm_token_limit_tf"),
            "llm_max_output_length": self.gui_controls.get("llm_max_output_length_tf"),
            "llm_temperature": self.gui_controls.get("temperature_slider"),
            "similarity_threshold": self.gui_controls.get("similarity_threshold_slider"),
            "prompt_structure": self.gui_controls.get("prompt_structure_rg"),
        }
        for setting_key, control in control_map.items():
            if control and setting_key in settings_to_load:
                value = settings_to_load[setting_key]
                if isinstance(control, (ft.Dropdown, ft.RadioGroup)): control.value = value
                elif isinstance(control, ft.TextField): control.value = str(value)
                elif isinstance(control, ft.Slider) and setting_key == "llm_temperature":
                    control.value = float(value) * 10.0
                    temp_label = self.gui_controls.get("temperature_value_label")
                    if isinstance(temp_label, ft.Text):
                        temp_label.value = f"{float(value):.1f}"
                        if temp_label.page : temp_label.update()
                elif isinstance(control, ft.Slider) and setting_key == "similarity_threshold":
                    control.value = float(value) * 100.0
                    temp_label = self.gui_controls.get("similarity_threshold_value_label")
                    if isinstance(temp_label, ft.Text):
                        temp_label.value = f"{float(value):.2f}"
                        if temp_label.page : temp_label.update()
                if control.page : control.update()
        self._update_reset_button_visibility()

    def _handle_reset_settings_click(self, e: ft.ControlEvent):
        """
        Handler para o clique no botão 'Resetar para Padrões'.

        Reseta as configurações de análise para os valores padrão da nuvem,
        atualiza a sessão e a UI.

        Args:
            e (ft.ControlEvent): O evento de clique do botão.
        """
        logger.info("SettingsDrawerManager: Botão 'Resetar Configurações' clicado.")
        cloud_defaults = self.page.session.get(KEY_SESSION_CLOUD_ANALYSIS_DEFAULTS)
        if cloud_defaults:
            self.page.session.set(KEY_SESSION_ANALYSIS_SETTINGS, cloud_defaults.copy())
            self._load_settings_into_controls(cloud_defaults)
            show_snackbar(self.page, "Configurações resetadas para os padrões da nuvem.", theme.COLOR_INFO)
        else:
            show_snackbar(self.page, "Não foi possível carregar os padrões em nuvem.", theme.COLOR_ERROR)
        self._update_reset_button_visibility()

    def _update_reset_button_visibility(self):
        """
        Atualiza a visibilidade do botão 'Resetar para Padrões'.
 
        O botão fica visível se as configurações atuais na sessão forem diferentes
        das configurações padrão da nuvem.
        """
        current_session_settings = self.page.session.get(KEY_SESSION_ANALYSIS_SETTINGS)
        cloud_default_settings = self.page.session.get(KEY_SESSION_CLOUD_ANALYSIS_DEFAULTS)
        reset_button = self.gui_controls.get("reset_settings_button")
 
        if not current_session_settings or not cloud_default_settings or not reset_button:
            if reset_button : reset_button.visible = False
            if reset_button and reset_button.page: reset_button.update()
            return
 
        are_different = False
        for key in cloud_default_settings.keys():
            val_session = current_session_settings.get(key)
            val_cloud = cloud_default_settings.get(key)
            if isinstance(val_cloud, (int, float)) and isinstance(val_session, str):
                try:
                    if isinstance(val_cloud, int): val_session = int(val_session)
                    elif isinstance(val_cloud, float): val_session = float(val_session)
                except ValueError: pass
            if val_session != val_cloud:
                logger.debug(f"Diferença para reset (Drawer): Chave='{key}', Sessão='{val_session}', Nuvem='{val_cloud}'")
                are_different = True
                break
        reset_button.visible = are_different
        if reset_button.page: reset_button.update()

