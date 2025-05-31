# src/flet_ui/views/analyze_pdf_view.py
import flet as ft
import threading, json, os
from typing import Optional, Dict, Any, List, Union, Tuple
from time import time, sleep
from datetime import datetime
from enum import Enum 
from pathlib import Path
#from rich import print

from src.flet_ui.components import (
    show_snackbar, show_loading_overlay, hide_loading_overlay,
    ManagedFilePicker, wrapper_panel_1, CompactKeyValueTable,
    CardWithHeader, show_confirmation_dialog 
)
from src.flet_ui import theme
from src.core.pdf_processor import PDFDocumentAnalyzer, PdfPlumberExtractor
from src.core.ai_orchestrator import get_api_key_in_firestore, analyze_text_with_llm

from src.services.firebase_client import FirebaseClientFirestore

from src.settings import (APP_VERSION , UPLOAD_TEMP_DIR, cotacao_dolar_to_real,
                          KEY_SESSION_ANALYSIS_SETTINGS, KEY_SESSION_CLOUD_ANALYSIS_DEFAULTS, 
                          FALLBACK_ANALYSIS_SETTINGS, KEY_SESSION_LOADED_LLM_PROVIDERS,
                          KEY_SESSION_TOKENS_EMBEDDINGS, KEY_SESSION_MODEL_EMBEDDINGS_LIST)

from src.utils import (format_seconds_to_min_sec, obter_string_normalizada, clean_and_convert_to_float, get_sigla_uf, 
                        LISTA_UFS, MUNICIPIOS_POR_UF)

from src.core.prompts import (
    FormatAnaliseInicial,
    tipos_doc, origens_doc, tipos_locais,
    areas_de_atribuição, tipo_a_autuar, assuntos_re,
    lista_delegacias_especializadas,
    lista_delegacias_interior, lista_corregedorias,
    tipos_envolvidos
)

destinacoes_completas = lista_delegacias_especializadas + lista_delegacias_interior + lista_corregedorias

from src.core.doc_generator import DocxExporter

from src.logger.logger import LoggerSetup
_logger = LoggerSetup.get_logger(__name__)

# Chaves de Sessão (mantidas e podem ser expandidas) apv: Refere-se a "Analyze PDF View"
KEY_SESSION_CURRENT_BATCH_NAME = "apv_current_batch_name"
KEY_SESSION_PDF_FILES_ORDERED = "apv_pdf_files_ordered"
KEY_SESSION_PDF_ANALYZER_DATA = "apv_pdf_analyzer_data" # Dados processados das páginas
KEY_SESSION_PDF_CLASSIFIED_INDICES_DATA = "apv_pdf_classified_indices_data" # (relevant_indices, unintelligible_indices, counts...)
KEY_SESSION_PDF_AGGREGATED_TEXT_INFO = "apv_pdf_aggregated_text_info" # (str_pages, aggregated_text, tokens_antes, tokens_depois)
KEY_SESSION_PDF_LLM_RESPONSE = "apv_pdf_llm_response"
KEY_SESSION_PROCESSING_METADATA = "apv_processing_metadata"
KEY_SESSION_LLM_METADATA = "apv_llm_metadata"

# Constantes para nomes de controles (facilita acesso) CTL = Control
CTL_UPLOAD_BTN = "upload_button"
CTL_PROCESS_BTN = "process_button"
CTL_ANALYZE_BTN = "analyze_button"
CTL_PROMPT_STRUCT_BTN = "prompt_structured_button"
CTL_RESTART_BTN = "restart_button"
CTL_EXPORT_BTN = "export_button"
CTL_SETTINGS_BTN = "settings_button"
CTL_RESET_SETTINGS_BTN = "reset_settings_button"
CTL_FILE_LIST_PANEL = "file_list_panel"
CTL_FILE_LIST_PANEL_TITLE = "file_list_panel_title"
CTL_FILE_LIST_VIEW = "file_list_view"
CTL_PROC_METADATA_PANEL = "proc_metadata_panel"
CTL_PROC_METADATA_PANEL_TITLE = "proc_metadata_panel_title"
CTL_PROC_METADATA_CONTENT = "proc_metadata_content"
CTL_LLM_RESULT_TEXT = "llm_result_text"
CTL_LLM_STRUCTURED_RESULT_DISPLAY = "llm_structured_result_display" # Novo
CTL_LLM_RESULT_INFO_TITLE = "llm_result_info_title"
CTL_LLM_STATUS_INFO = "llm_status_info"
CTL_LLM_RESULT_INFO_BALLOON = "llm_result_info_balloon"
CTL_LLM_METADATA_PANEL = "llm_metadata_panel"
CTL_LLM_METADATA_PANEL_TITLE = "llm_metadata_panel_title"
CTL_LLM_METADATA_CONTENT = "llm_metadata_content"
CTL_SETTINGS_DRAWER = "settings_drawer"

# NOVO ENUM para operações do FilePicker
class ExportOperation(Enum):
    NONE = "none"
    SIMPLE_DOCX = "simple_docx"
    TEMPLATE_DOCX = "template_docx"


class AnalyzePDFViewContent(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__(expand=True, spacing=10) # A Column principal expande
        self.page = page
        self.gui_controls: Dict[str, ft.Control] = {}
        self.gui_controls_drawer: Dict[str, ft.Control] = {}
        self.file_list_manager = None # Será instanciado FileListManager (adaptado)
        self.analysis_controller = None # Será instanciado AnalysisController (adaptado)
        self.managed_file_picker: Optional[ManagedFilePicker] = None

        # Instâncias do PDF Analyzer e outros serviços, se necessário manter estado
        self.pdf_analyzer = PDFDocumentAnalyzer()

        self.docx_exporter = DocxExporter()

        # Estado interno da View
        self._is_drawer_open = False
        self._files_processed = False # Indica se o conteúdo dos PDFs foi processado
        self._analysis_requested = False # Indica se a análise LLM foi solicitada/concluída

        # Estado para o FilePicker de exportação
        self.current_export_operation: ExportOperation = ExportOperation.NONE
        self.current_export_template_path: Optional[str] = None # Para armazenar o path do template
        self.global_file_picker_instance: Optional[ft.FilePicker] = None # Referência ao picker global

        self._build_gui_structure()
        self._initialize_pickers()

        self.export_manager = self._ExportManager(self)

        self._setup_event_handlers()
        self._setup_drawer_event_handlers()
        self._restore_state_from_session() # que chama self._update_button_states(), que chama self._update_export_button_menu()

    def _remove_data_session(self, key):
        if self.page.session.contains_key(key):
            self.page.session.remove(key)

    def _build_gui_structure(self):
        _logger.info("Construindo estrutura da UI para Análise de PDF.")
        
        default_icon_size_bar = 25
        width_btn_bar = 180

        # --- 1. Título Fixo ---
        title_bar = ft.Text("Análise inicial de Notícias-Crime e Outros",
                             style=ft.TextThemeStyle.HEADLINE_MEDIUM,
                             text_align=ft.TextAlign.CENTER)

        # --- 2. Barra de Botões Fixa ---
        self.gui_controls[CTL_UPLOAD_BTN] = ft.ElevatedButton("Carregar Arquivo(s)", icon=ft.Icons.UPLOAD_FILE_ROUNDED, width=width_btn_bar)
        self.gui_controls[CTL_PROCESS_BTN] = ft.ElevatedButton("Processar Conteúdo", icon=ft.Icons.MODEL_TRAINING_ROUNDED, width=width_btn_bar)
        self.gui_controls[CTL_ANALYZE_BTN] = ft.ElevatedButton("Solicitar Análise", icon=ft.Icons.ONLINE_PREDICTION_ROUNDED, width=width_btn_bar)
        
        self.gui_controls[CTL_PROMPT_STRUCT_BTN] = ft.ElevatedButton("Prompt Estruturado", icon=ft.Icons.EDIT_NOTE_ROUNDED, width=width_btn_bar)
        self.gui_controls[CTL_RESTART_BTN] = ft.IconButton(icon=ft.Icons.RESTART_ALT_ROUNDED, tooltip="Reiniciar Análise (Limpar Tudo)", icon_size=default_icon_size_bar)
        self.gui_controls[CTL_EXPORT_BTN] = ft.PopupMenuButton(
            icon=ft.Icons.DOWNLOAD_FOR_OFFLINE_ROUNDED,
            tooltip="Exportar Análise", icon_size=default_icon_size_bar,
            items=[]
                #ft.PopupMenuItem(text="Exportar em Simples DOCX", data="docx_simple"),
                #ft.PopupMenuItem(text="Exportar em Template DOCX", data="docx_template", disabled=True), # habilitado após análise LLM
        )
        self.gui_controls[CTL_SETTINGS_BTN] = ft.IconButton(icon=ft.Icons.TUNE_ROUNDED, tooltip="Configurações específicas", icon_size=default_icon_size_bar)

        action_buttons_bar = ft.Row(
            [
                self.gui_controls[CTL_UPLOAD_BTN],
                self.gui_controls[CTL_PROCESS_BTN],
                self.gui_controls[CTL_ANALYZE_BTN],
                ft.Container(expand=True), # Espaçador
                self.gui_controls[CTL_PROMPT_STRUCT_BTN],
                self.gui_controls[CTL_RESTART_BTN],
                self.gui_controls[CTL_EXPORT_BTN],
                self.gui_controls[CTL_SETTINGS_BTN],
            ],
            alignment=ft.MainAxisAlignment.START,
            spacing=10
        )

        # --- 3. Layout de Conteúdo com Panels Expansíveis e Containers ---
        # Panel 1: Lista de Arquivos
        self.gui_controls[CTL_FILE_LIST_PANEL_TITLE] = ft.Text("Nenhum arquivo carregado.", weight=ft.FontWeight.BOLD) # Título dinâmico
        self.gui_controls[CTL_FILE_LIST_VIEW] = ft.ListView(expand=False, spacing=3) # height=0 Altura controlada dinamicamente
        file_list_panel_content = ft.Container(
            content=self.gui_controls[CTL_FILE_LIST_VIEW],
            #border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT), # Para debug padding=5,
            expand=True, # Permite que a ListView use o espaço disponível no ExpansionPanel
            #bgcolor = theme.PANEL_CONTENT_BGCOLOR
        )
        file_list_header_container = ft.Container(content=ft.Row([ft.Container(width=12), self.gui_controls[CTL_FILE_LIST_PANEL_TITLE]]),
                                               expand=True, alignment=ft.alignment.center, # ft.MainAxisAlignment.CENTER, 
                                               bgcolor=None) # theme.PANEL_HEADER_BGCOLOR)
        self.gui_controls[CTL_FILE_LIST_PANEL] = ft.ExpansionPanel(
            header=file_list_header_container,
            content=file_list_panel_content,
            can_tap_header=True, # Permite expandir/recolher clicando no header
            expanded=True, # Começa expandido
            #bgcolor = theme.PANEL_HEADER_BGCOLOR
        )
        self.gui_controls[CTL_FILE_LIST_PANEL] = wrapper_panel_1(self.gui_controls[CTL_FILE_LIST_PANEL]) # wrapper_panel_1 = ExpansionPanelList 
        self.gui_controls[CTL_FILE_LIST_PANEL].visible=False, # visível após carregament de PDF(s)   

        # Panel 2: Metadados do Processamento
        self.gui_controls[CTL_PROC_METADATA_PANEL_TITLE] = ft.Text("Metadados do Processamento", weight=ft.FontWeight.BOLD)
        self.gui_controls[CTL_PROC_METADATA_CONTENT] = ft.Column(spacing=5, expand=True, horizontal_alignment=ft.CrossAxisAlignment.START) # Conteúdo será adicionado dinamicamente
        self.gui_controls[CTL_PROC_METADATA_PANEL] = ft.ExpansionPanel(
            header=ft.Column([ft.Row([ft.Container(width=12), self.gui_controls[CTL_PROC_METADATA_PANEL_TITLE]])], expand=True, alignment=ft.MainAxisAlignment.CENTER),
            content=self.gui_controls[CTL_PROC_METADATA_CONTENT],
            can_tap_header=True,
            expanded=False
        )
        self.gui_controls[CTL_PROC_METADATA_PANEL] = wrapper_panel_1(self.gui_controls[CTL_PROC_METADATA_PANEL])
        self.gui_controls[CTL_PROC_METADATA_PANEL].visible=False, # visível após processamento de PDF(s)

        # Container 3: Resposta/Resultado da Análise
        self.gui_controls[CTL_LLM_RESULT_INFO_TITLE] = ft.Row([ft.Container(width=12), 
                                                                ft.Text("Resultado da Análise LLM:", 
                                                                    style=ft.TextThemeStyle.TITLE_MEDIUM, 
                                                                    weight=ft.FontWeight.BOLD)], visible=False)
        self.gui_controls[CTL_LLM_STATUS_INFO] = ft.Text("Aguardando para exibir os resultados...", italic=True, size=14, expand=True)
        self.gui_controls[CTL_LLM_RESULT_INFO_BALLOON] = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, color=theme.COLOR_INFO, size=30),
                    self.gui_controls[CTL_LLM_STATUS_INFO]
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            ),
            padding=20,
            border_radius=8,
            bgcolor=ft.Colors.with_opacity(0.05, theme.COLOR_INFO),
            visible=True
        )
        
        # Fallback para string não estruturada:
        self.gui_controls[CTL_LLM_RESULT_TEXT] = ft.TextField(
            multiline=True, read_only=True, min_lines=15, max_lines=30,
            expand=True, border_color=theme.PRIMARY, text_size=14,
            visible=False 
        )
        
        # Novo display estruturado:
        self.gui_controls[CTL_LLM_STRUCTURED_RESULT_DISPLAY] = LLMStructuredResultDisplay(self.page)
        self.gui_controls[CTL_LLM_STRUCTURED_RESULT_DISPLAY].visible = False

        self.llm_result_container = ft.Container(
            content=ft.Column( # Usar Stack para sobrepor o balão e o resultado
                [
                    #self.gui_controls[CTL_LLM_RESULT_INFO_BALLOON],
                    #self.gui_controls[CTL_LLM_RESULT_TEXT], # Fallback
                    #self.gui_controls[CTL_LLM_STRUCTURED_RESULT_DISPLAY] # Novo
                ]
            ),
            padding=10,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=5,
            expand=True, # O container de resultado deve expandir
        )

        # Panel 4: Metadados do Resultado da LLM
        self.gui_controls[CTL_LLM_METADATA_PANEL_TITLE] = ft.Text("Metadados da Análise LLM", weight=ft.FontWeight.BOLD)
        self.gui_controls[CTL_LLM_METADATA_CONTENT] = ft.Column(spacing=5, expand=True, horizontal_alignment=ft.CrossAxisAlignment.START) # Conteúdo dinâmico
        self.gui_controls[CTL_LLM_METADATA_PANEL] = ft.ExpansionPanel(
            header=ft.Column([ft.Row([ft.Container(width=12), self.gui_controls[CTL_LLM_METADATA_PANEL_TITLE]])], expand=True, alignment=ft.MainAxisAlignment.CENTER),
            content=self.gui_controls[CTL_LLM_METADATA_CONTENT],
            can_tap_header=True,
            expanded=False
        )
        self.gui_controls[CTL_LLM_METADATA_PANEL] = wrapper_panel_1(self.gui_controls[CTL_LLM_METADATA_PANEL])
        self.gui_controls[CTL_LLM_METADATA_PANEL].visible=False, # visível após resposta da LLM


        # Layout principal dos painéis e resultado
        main_content_column = ft.Column(
            [
                self.gui_controls[CTL_FILE_LIST_PANEL],
                self.gui_controls[CTL_PROC_METADATA_PANEL],
                ft.Column([
                    self.gui_controls[CTL_LLM_RESULT_INFO_TITLE],
                    self.llm_result_container], expand=True, spacing=6,
                    ),
                self.gui_controls[CTL_LLM_METADATA_PANEL]
            ],
            expand=True,
            spacing=15,
            scroll=ft.ScrollMode.ADAPTIVE # Adiciona scroll se o conteúdo for muito grande
        )

        # --- Drawer de Configurações (Placeholder) ---
        self.gui_controls[CTL_SETTINGS_DRAWER] = self._build_settings_drawer_content()
        
        # Container para simular o drawer à direita, controlado por visibilidade/largura
        self.settings_drawer_container = ft.Container(
            content=self.gui_controls[CTL_SETTINGS_DRAWER],
            padding=10, width=0, # Começa fechado
            # shadow=ft.BoxShadow(blur_radius=3, color=ft.Colors.BLACK_26, offset=ft.Offset(0, 2)),
            # animate=ft.animation.Animation(300, ft.AnimationCurve.EASE_OUT_QUINT),
            # border=ft.border.only(left=ft.border.BorderSide(1, ft.Colors.OUTLINE)) # Borda opcional
        )

        # Layout final: Coluna principal dos conteúdos e o "drawer" ao lado
        main_content_with_drawer_row = ft.Row(
            [
                ft.Container(main_content_column, expand=True, padding=ft.padding.only(right=8)), # Conteúdo principal expande
                self.settings_drawer_container # Drawer
            ],
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.START
        )

        # Adiciona os componentes principais à view
        self.controls.extend([
            title_bar,
            action_buttons_bar,
            ft.Divider(height=1),
            main_content_with_drawer_row # Esta linha contém o conteúdo e o drawer
        ])

        # Adaptação do FileListManager (será uma classe interna ou métodos diretos)
        self.file_list_manager = self._InternalFileListManager(self.page, self.gui_controls, self)

        # Adaptação do AnalysisController (será uma classe interna ou métodos diretos)
        self.analysis_controller = self._InternalAnalysisController(self.page, self.gui_controls, self)

    def _build_settings_drawer_content(self) -> ft.Column:
        default_width = 260
        current_analysis_settings = self.page.session.get(KEY_SESSION_ANALYSIS_SETTINGS) or FALLBACK_ANALYSIS_SETTINGS.copy()
        loaded_llm_providers = self.page.session.get(KEY_SESSION_LOADED_LLM_PROVIDERS) or []

        # Seção Processamento
        self.gui_controls_drawer["proc_extractor_dd"] = ft.Dropdown(label="Extrator de Texto PDF", options=[
            ft.dropdown.Option("PyMuPdf-fitz", "PyMuPdf-fitz"),
            ft.dropdown.Option("PdfPlumber", "PdfPlumber"),
            #ft.dropdown.Option("PyPdf2", "PyPdf2"),
        ], value=current_analysis_settings.get("pdf_extractor"), width=default_width) 
        self.gui_controls_drawer["proc_embeddings_dd"]  = ft.Dropdown(label="Modelo de Embeddings", options=[
            ft.dropdown.Option("all-MiniLM-L6-v2", "all-MiniLM-L6-v2"),
            #ft.dropdown.Option("text-embedding-ada-002", "OpenAI text-embedding-ada-002"
            ft.dropdown.Option("text-embedding-3-small", "OpenAI text-embedding-3-small"), 
        ], value=current_analysis_settings.get("embeddings_model"), width=default_width)
        self.gui_controls_drawer["lang_detector_dd"] = ft.Dropdown(
            label="Detector de Idioma", options=[ft.dropdown.Option("langdetect", "langdetect")],
            value=current_analysis_settings.get("language_detector"), width=default_width
        )
        self.gui_controls_drawer["token_counter_dd"] = ft.Dropdown(
            label="Contador de Tokens", options=[ft.dropdown.Option("tiktoken", "tiktoken")],
            value=current_analysis_settings.get("token_counter"), width=default_width
        )
        self.gui_controls_drawer["tfidf_analyzer_dd"] = ft.Dropdown(
            label="Analisador TF-IDF", options=[ft.dropdown.Option("sklearn", "sklearn")],
            value=current_analysis_settings.get("tfidf_analyzer"), width=default_width
        )

        # Seção LLM
         # Dropdown de Provedor LLM (Dinâmico)
        provider_options_drawer = [
            ft.dropdown.Option(key=p['system_name'], text=p.get('name_display', p['system_name']))
            for p in loaded_llm_providers if p.get('system_name')
        ]
        self.gui_controls_drawer["llm_provider_dd"] = ft.Dropdown(label="Provedor LLM", options=provider_options_drawer , 
                                                                  value=current_analysis_settings.get("llm_provider"), width=default_width) 

        # Dropdown de Modelo LLM (Dinâmico, depende do provedor)
        self.gui_controls_drawer["llm_model_dd"] = ft.Dropdown(label="Modelo LLM", options=[], # Será populado por _handle_drawer_provider_change, 
                                                               value=current_analysis_settings.get("llm_model"), width=default_width)

        self._populate_drawer_models_for_selected_provider(current_analysis_settings.get("llm_provider"), current_analysis_settings.get("llm_model"))

        self.gui_controls_drawer["llm_token_limit_tf"] = ft.TextField(
            label="Limite Tokens Input", value=str(current_analysis_settings.get("llm_input_token_limit")),
            input_filter=ft.InputFilter(r"[0-9]"), width=default_width
        )
        self.gui_controls_drawer["llm_output_format_dd"] = ft.Dropdown( 
            label="Formato de Saída", options=[ft.dropdown.Option("Padrão", "Padrão"), 
                                               #ft.dropdown.Option("json_object", "JSON")
                                               ], 
            value=current_analysis_settings.get("llm_output_format"), width=default_width
        )

        self.gui_controls_drawer["llm_max_output_length_tf"] = ft.TextField( 
            label="Comprimento Max. Saída", value=str(current_analysis_settings.get("llm_max_output_length")),
            input_filter=ft.InputFilter(r"[0-9]*"), # Permite vazio ou números
            hint_text="Deixe 'Padrão' ou vazio para usar o default do modelo",
            width=default_width, read_only=True
        )
        
        #def slider_changed(e):
        #    temperature_value.value = f"{(int(e.control.value)/10):.1f}"
        #    temperature_value.update()
        #temperature_slider = ft.Slider(label="{value}", min=0.0, max=20.0, value=2.0, divisions=20, on_change=slider_changed, expand=True) # label="{value}"
        #temperature_value = ft.Text("0.2", weight=ft.FontWeight.BOLD)
        
        # Slider de Temperatura
        initial_temp = current_analysis_settings.get("llm_temperature", 0.2)
        self.gui_controls_drawer["temperature_value_label"] = ft.Text(f"{initial_temp:.1f}", weight=ft.FontWeight.BOLD)
        self.gui_controls_drawer["temperature_slider"] = ft.Slider(
            min=0.0, max=20.0, value=initial_temp * 10, # Slider value de 0 a 20 para representar 0.0 a 2.0
            divisions=20, expand=True,
            label="{value}", # O label do slider em si não é usado para o valor numérico aqui
            on_change=self._handle_drawer_setting_change # Atualiza o Text e a sessão
        )

        # Seção Prompt (apenas para manter consistência, lógica não implementada nesta etapa)
        self.gui_controls_drawer["prompt_structure_rg"] = ft.RadioGroup(
            content=ft.Column([
                ft.Radio(value="prompt_unico", label="Prompt Único"), # TODO: incluir tootip explicativos nesses dois radios
                ft.Radio(value="sequential_chunks", label="Prompt Agrupado", disabled=True),
                #ft.Radio(value="rag_multiple", label="Múltiplos Prompts com RAG", disabled=True),
            ], spacing=1), value=current_analysis_settings.get("prompt_structure")
        )

        # NOVO: Botão de Resetar
        self.gui_controls_drawer[CTL_RESET_SETTINGS_BTN] = ft.ElevatedButton(
            "Resetar para Padrões",
            icon=ft.icons.SETTINGS_BACKUP_RESTORE_ROUNDED,
            on_click=self._handle_reset_drawer_settings,
            visible=False, # Começa invisível
            #width=default_width
        )
        
        return ft.Column(
            [
                ft.Row([ft.Text("Configurações específicas", style=ft.TextThemeStyle.TITLE_LARGE), 
                        ft.IconButton(icon=ft.Icons.CLOSE_ROUNDED, on_click=self._handle_toggle_settings_drawer, tooltip="Fechar Configurações")],
                       alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Divider(),

                ft.Text("Processamento de Documento", style=ft.TextThemeStyle.TITLE_MEDIUM),
                self.gui_controls_drawer["proc_extractor_dd"],
                self.gui_controls_drawer["proc_embeddings_dd"],
                self.gui_controls_drawer["lang_detector_dd"],   
                self.gui_controls_drawer["token_counter_dd"],  
                self.gui_controls_drawer["tfidf_analyzer_dd"], 
                ft.Divider(),

                ft.Text("Modelo de Linguagem (LLM)", style=ft.TextThemeStyle.TITLE_MEDIUM),
                self.gui_controls_drawer["llm_provider_dd"],
                self.gui_controls_drawer["llm_model_dd"],
                self.gui_controls_drawer["llm_token_limit_tf"],

                ft.Column([
                    ft.Text("Temperatura de resposta", style=ft.TextThemeStyle.LABEL_MEDIUM),
                    ft.Row([self.gui_controls_drawer["temperature_slider"],self.gui_controls_drawer["temperature_value_label"]], 
                           alignment=ft.MainAxisAlignment.SPACE_BETWEEN)], 
                    width=default_width, spacing=1), 
                self.gui_controls_drawer["llm_output_format_dd"], 
                self.gui_controls_drawer["llm_max_output_length_tf"],

                ft.Dropdown(label="Configurações Avançadas", options=[ft.dropdown.Option("indisponivel", "Indisponível")], 
                            value="indisponivel", disabled=True, width=default_width),
                ft.Divider(),

                ft.Text("Estrutura do Prompt", style=ft.TextThemeStyle.TITLE_MEDIUM),
                self.gui_controls_drawer["prompt_structure_rg"],

                ft.Container(expand=True), # Para empurrar para baixo
            
                ft.Row([self.gui_controls_drawer[CTL_RESET_SETTINGS_BTN]], 
                       expand=True, alignment=ft.MainAxisAlignment.CENTER),
                ft.Container(height=1)
                #ft.Row([ft.ElevatedButton("Salvar Configurações", icon=ft.Icons.SAVE_ROUNDED, disabled=True)], 
                #       expand=True, alignment=ft.MainAxisAlignment.CENTER) 
            ],
            #spacing=12,
            scroll=ft.ScrollMode.ADAPTIVE, # Permite scroll dentro do drawer
            expand=True # Ocupa a altura do container do drawer
        )

    def _handle_drawer_provider_change(self, e: ft.ControlEvent):
        """Atualiza a lista de modelos no drawer quando o provedor do drawer muda."""
        selected_provider_system_name = e.control.value
        self._populate_drawer_models_for_selected_provider(selected_provider_system_name, new_provider_selected=True)
        self._handle_drawer_setting_change(e) # Chama o handler geral para salvar na sessão e atualizar UI

    def _populate_drawer_models_for_selected_provider(self, provider_system_name: Optional[str], current_model_value: Optional[str] = None, new_provider_selected:bool=False):
        """Popula o dropdown de modelos no drawer com base no provedor selecionado."""
        model_dropdown_drawer = self.gui_controls_drawer.get("llm_model_dd")
        if not model_dropdown_drawer or not isinstance(model_dropdown_drawer, ft.Dropdown):
            return

        model_dropdown_drawer.options = []
        # model_dropdown_drawer.value = None # Não reseta aqui se current_model_value será usado
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
                
                if new_provider_selected and model_options: # Se um novo provedor foi selecionado, sugere o primeiro modelo
                    model_dropdown_drawer.value = model_options[0].key
                elif current_model_value and any(opt.key == current_model_value for opt in model_options):
                    model_dropdown_drawer.value = current_model_value # Mantém valor se válido
                elif model_options: # Se valor atual não é válido mas há opções
                    model_dropdown_drawer.value = model_options[0].key # Fallback para o primeiro
                else: # Sem opções
                    model_dropdown_drawer.value = None


        if model_dropdown_drawer.page: model_dropdown_drawer.update()

    def _setup_drawer_event_handlers(self):
        _logger.info("Configurando handlers de eventos do Drawer de Configurações.")
        # Para cada controle no drawer que pode ser alterado pelo usuário
        controls_to_watch = [
            "proc_extractor_dd" ,"proc_embeddings_dd", "llm_provider_dd", "llm_model_dd", "llm_token_limit_tf", "temperature_slider", 
            # "llm_output_format_dd", "llm_max_output_length_tf", "prompt_structure_rg"
        ]
        for key in controls_to_watch:
            if key in self.gui_controls_drawer:
                control = self.gui_controls_drawer[key]
                control.on_change = self._handle_drawer_setting_change
    
    def _handle_drawer_setting_change(self, e: Optional[ft.ControlEvent] = None):
        """Chamado quando qualquer configuração no drawer é alterada pelo usuário."""
        _logger.debug(f"Configuração do drawer alterada: {e.control.label if hasattr(e.control, 'label') else 'Slider' if isinstance(e.control, ft.Slider) else 'N/A'}")
        
        # Atualiza o valor do label de temperatura se o slider mudou
        if e and isinstance(e.control, ft.Slider) and e.control == self.gui_controls_drawer.get("temperature_slider"):
            slider_val = int(e.control.value) / 10.0 # Converte de 0-20 para 0.0-2.0
            temp_label = self.gui_controls_drawer.get("temperature_value_label")
            if isinstance(temp_label, ft.Text):
                temp_label.value = f"{slider_val:.1f}"
                if temp_label.page: temp_label.update()

        # Coleta todos os valores atuais do drawer
        new_settings = self._get_settings_from_drawer()
        
        # Salva na sessão
        self.page.session.set(KEY_SESSION_ANALYSIS_SETTINGS, new_settings)
        _logger.info(f"Configurações de análise da sessão atualizadas: {new_settings}")
        
        # Atualiza a visibilidade do botão de reset
        self._update_reset_button_visibility()

        # Informa ao usuário que as configurações foram aplicadas à sessão atual
        # Não usar show_snackbar aqui para cada pequena mudança, pode ser irritante.
        # Opcional: habilitar um botão "Aplicar à Sessão" se as mudanças forem muitas.
        # Por ora, a mudança é imediata na sessão.

    def _get_settings_from_drawer(self) -> Dict[str, Any]:
        """Coleta os valores atuais de todos os controles do drawer."""
        settings = {}
        # Mapeia a chave do controle no self.gui_controls_drawer para a chave no dict de settings
        key_map = {
            "proc_extractor_dd": "pdf_extractor",
            "proc_embeddings_dd": "embeddings_model",
            "lang_detector_dd": "language_detector",
            "token_counter_dd": "token_counter",
            "tfidf_analyzer_dd": "tfidf_analyzer",
            "llm_provider_dd": "llm_provider",
            "llm_model_dd": "llm_model",
            "llm_token_limit_tf": "llm_input_token_limit",
            "llm_output_format_dd": "llm_output_format",
            "llm_max_output_length_tf": "llm_max_output_length",
            "temperature_slider": "llm_temperature", # O valor do slider será convertido
            "prompt_structure_rg": "prompt_structure",
        }
        for ctrl_key, setting_key in key_map.items():
            if ctrl_key in self.gui_controls_drawer:
                control = self.gui_controls_drawer[ctrl_key]
                if isinstance(control, (ft.Dropdown, ft.TextField, ft.RadioGroup)):
                    value = control.value
                    if setting_key == "llm_input_token_limit":
                        try: value = int(value) if value else FALLBACK_ANALYSIS_SETTINGS[setting_key]
                        except ValueError: value = FALLBACK_ANALYSIS_SETTINGS[setting_key]
                    elif setting_key == "llm_max_output_length":
                         # Se vazio ou "Padrão", usa o fallback que também é "Padrão"
                        value = value if value and value.lower() != "padrão" else FALLBACK_ANALYSIS_SETTINGS[setting_key]
                        if value != "Padrão": # Tenta converter para int se não for "Padrão"
                            try: value = int(value)
                            except ValueError: value = FALLBACK_ANALYSIS_SETTINGS[setting_key] # Mantém "Padrão"
                    settings[setting_key] = value
                elif isinstance(control, ft.Slider) and setting_key == "llm_temperature":
                    settings[setting_key] = float(control.value) / 10.0
        return settings

    def _load_settings_into_drawer(self, settings_to_load: Dict[str, Any]):
        """Popula os controles do drawer com os valores fornecidos."""
        _logger.info("Carregando configurações da sessão para o drawer.")
        # Mapeamento inverso ou lógica similar a _get_settings_from_drawer

        # Popula dropdown de provedores do drawer
        loaded_llm_providers = self.page.session.get(KEY_SESSION_LOADED_LLM_PROVIDERS) or []
        provider_options_drawer = [
            ft.dropdown.Option(key=p['system_name'], text=p.get('name_display', p['system_name']))
            for p in loaded_llm_providers if p.get('system_name')
        ]
        drawer_provider_dd = self.gui_controls_drawer.get("llm_provider_dd")
        if isinstance(drawer_provider_dd, ft.Dropdown):
            drawer_provider_dd.options = provider_options_drawer
            drawer_provider_dd.value = settings_to_load.get("llm_provider")
            if drawer_provider_dd.page: drawer_provider_dd.update()

        # Popula dropdown de modelos do drawer com base no provedor carregado
        self._populate_drawer_models_for_selected_provider(
            settings_to_load.get("llm_provider"),
            settings_to_load.get("llm_model")
        )

        control_map = {
            "pdf_extractor": self.gui_controls_drawer.get("proc_extractor_dd"),
            "embeddings_model": self.gui_controls_drawer.get("proc_embeddings_dd"),
            "language_detector": self.gui_controls_drawer.get("lang_detector_dd"),
            "token_counter": self.gui_controls_drawer.get("token_counter_dd"),
            "tfidf_analyzer": self.gui_controls_drawer.get("tfidf_analyzer_dd"),
            #"llm_provider": self.gui_controls_drawer.get("llm_provider_dd"),
            #"llm_model": self.gui_controls_drawer.get("llm_model_dd"),
            "llm_input_token_limit": self.gui_controls_drawer.get("llm_token_limit_tf"),
            "llm_output_format": self.gui_controls_drawer.get("llm_output_format_dd"),
            "llm_max_output_length": self.gui_controls_drawer.get("llm_max_output_length_tf"),
            "llm_temperature": self.gui_controls_drawer.get("temperature_slider"),
            "prompt_structure": self.gui_controls_drawer.get("prompt_structure_rg"),
        }

        for setting_key, control in control_map.items():
            if control and setting_key in settings_to_load:
                value = settings_to_load[setting_key]
                if isinstance(control, (ft.Dropdown, ft.RadioGroup)):
                    control.value = value
                elif isinstance(control, ft.TextField):
                    control.value = str(value) # Garante que é string para TextField
                elif isinstance(control, ft.Slider) and setting_key == "llm_temperature":
                    control.value = float(value) * 10.0
                    temp_label = self.gui_controls_drawer.get("temperature_value_label")
                    if isinstance(temp_label, ft.Text):
                        temp_label.value = f"{float(value):.1f}"
                        if temp_label.page : temp_label.update()

                if control.page : control.update() # Atualiza cada controle individualmente
        
        self._update_reset_button_visibility()

    def _handle_reset_drawer_settings(self, e: ft.ControlEvent):
        _logger.info("Botão 'Resetar Configurações' do drawer clicado.")
        cloud_defaults = self.page.session.get(KEY_SESSION_CLOUD_ANALYSIS_DEFAULTS)
        if cloud_defaults:
            self.page.session.set(KEY_SESSION_ANALYSIS_SETTINGS, cloud_defaults.copy())
            self._load_settings_into_drawer(cloud_defaults)
            show_snackbar(self.page, "Configurações resetadas para os padrões da nuvem.", theme.COLOR_INFO)
        else:
            show_snackbar(self.page, "Não foi possível carregar os padrões da nuvem.", theme.COLOR_ERROR)
        self._update_reset_button_visibility() # Botão deve ficar invisível após reset

    def _update_reset_button_visibility(self):
        current_session_settings = self.page.session.get(KEY_SESSION_ANALYSIS_SETTINGS)
        cloud_default_settings = self.page.session.get(KEY_SESSION_CLOUD_ANALYSIS_DEFAULTS)
        reset_button = self.gui_controls_drawer.get(CTL_RESET_SETTINGS_BTN)

        if not current_session_settings or not cloud_default_settings or not reset_button:
            if reset_button : 
                reset_button.visible = False # Segurança
            if reset_button and reset_button.page: 
                reset_button.update()
            return

        # Compara os dicionários. Precisamos ser cuidadosos com tipos (int vs str).
        # _get_settings_from_drawer já normaliza os tipos para o que esperamos na sessão.
        are_different = False
        for key in cloud_default_settings.keys():
            # É importante que a comparação seja feita com os mesmos tipos.
            # A current_session_settings deve ter sido populada por _get_settings_from_drawer
            # ou carregada e normalizada de forma similar.
            val_session = current_session_settings.get(key)
            val_cloud = cloud_default_settings.get(key)

            if isinstance(val_cloud, (int, float)) and isinstance(val_session, str):
                try: # Tenta converter string da sessão para número para comparar
                    if isinstance(val_cloud, int): val_session = int(val_session)
                    elif isinstance(val_cloud, float): val_session = float(val_session)
                except ValueError:
                    pass # Se não puder converter, serão diferentes

            if val_session != val_cloud:
                _logger.debug(f"Diferença encontrada para reset: Chave='{key}', Sessão='{val_session}' (tipo {type(val_session)}), Nuvem='{val_cloud}' (tipo {type(val_cloud)})")
                are_different = True
                break
        
        reset_button.visible = are_different
        if reset_button.page: reset_button.update()

    # --- setup file_picker ---
    def _initialize_pickers(self):
        _logger.info("Inicializando FilePickers (Managed para upload, Global para exportação).")
        
        # Primeiro, obtenha a referência ao picker global
        self.global_file_picker_instance = self.page.data.get("global_file_picker")
        if not self.global_file_picker_instance:
            _logger.critical("FilePicker global NÃO encontrado em page.data! Upload e Exportação podem falhar.")
            show_snackbar(self.page, "Erro crítico: FilePicker não inicializado.", theme.COLOR_ERROR)
            return
        else:
             _logger.info("Referência ao FilePicker GLOBAL para exportação e upload armazenada.")

        # Configura o ManagedFilePicker para UPLOADS, passando a instância global
        if self.global_file_picker_instance: # Só instancia se o picker global existir
            # Callbacks para o ManagedFilePicker (upload)
            def individual_file_upload_complete_cb(success: bool, path_or_msg: str, file_name: Optional[str]):
                if success and file_name and path_or_msg:
                    _logger.info(f"Upload individual de '{file_name}' OK. Path: {path_or_msg}")
                    current_files = self.page.session.get(KEY_SESSION_PDF_FILES_ORDERED) or []
                    if not isinstance(current_files, list): 
                        current_files = []                    
                    if not any(f['name'] == file_name and f['path'] == path_or_msg for f in current_files):
                        new_file_entry = {"name": file_name, 
                                          "path": path_or_msg, 
                                          "original_index": len(current_files)}
                        current_files.append(new_file_entry)
                        self.page.session.set(KEY_SESSION_PDF_FILES_ORDERED, current_files)
                elif path_or_msg == "Seleção cancelada":
                    _logger.info("Seleção de arquivos cancelada.")
                else:
                    _logger.error(f"Falha no upload de '{file_name}': {path_or_msg}")

            def batch_upload_complete_cb(batch_results: List[Dict[str, Any]]):
                _logger.info(f"Upload_Batch Completo (ManagedFilePicker): {len(batch_results)} resultados.") 
                hide_loading_overlay(self.page) 
                
                successful_uploads = [r for r in batch_results if r['success']]
                failed_count = len(batch_results) - len(successful_uploads)
                final_message, final_color = "", theme.COLOR_INFO

                if successful_uploads and not failed_count:
                    final_message = f"{len(successful_uploads)} arquivo(s) carregado(s)!"
                    final_color = theme.COLOR_SUCCESS
                elif successful_uploads and failed_count:
                    final_message = f"{len(successful_uploads)} carregado(s), {failed_count} falha(s)."
                    final_color = theme.COLOR_WARNING
                elif not successful_uploads and failed_count:
                    final_message = f"Todos os {failed_count} uploads falharam."
                    final_color = theme.COLOR_ERROR
                elif not batch_results:
                    _logger.info("Nenhum arquivo selecionado.")
                    final_message = "Nenhum arquivo selecionado."
                    final_color = theme.COLOR_WARNING
                
                if final_message: 
                    show_snackbar(self.page, final_message, color=final_color)
                
                self.file_list_manager.update_selected_files_display()
                if final_message and final_message != "Nenhum arquivo selecionado.": 
                    self._files_processed = False # Novos arquivos, processamento necessário
                    self._analysis_requested = False # Análise LLM também precisará ser refeita
                    self._remove_data_session(KEY_SESSION_PDF_ANALYZER_DATA)
                    self._remove_data_session(KEY_SESSION_PDF_LLM_RESPONSE) # Limpa dados antigos
                    self._clear_processing_metadata_display()
                    self._clear_llm_metadata_display()
                    self._show_info_balloon_or_result(show_balloon=True)
                
                self._update_button_states()
                self.page.update()

            self.managed_file_picker = ManagedFilePicker(
                page=self.page,
                file_picker_instance=self.global_file_picker_instance, # Passa a instância global
                on_individual_file_complete=individual_file_upload_complete_cb,
                upload_dir=UPLOAD_TEMP_DIR,
                on_batch_complete=batch_upload_complete_cb,
                allowed_extensions=["pdf"]
            )
            _logger.info("ManagedFilePicker para UPLOAD instanciado usando o picker global.")
        else:
            _logger.warning("ManagedFilePicker para UPLOAD não pôde ser instanciado pois o picker global não foi encontrado.")

    def _handle_export_selected(self, e: ft.ControlEvent):
        selected_action_data = e.control.data
        _logger.info(f"Opção de exportação selecionada pelo PopupMenuItem.data: {selected_action_data}")

        structured_display_ctrl = self.gui_controls.get(CTL_LLM_STRUCTURED_RESULT_DISPLAY)
        if not isinstance(structured_display_ctrl, LLMStructuredResultDisplay):
            show_snackbar(self.page, "Erro interno: Display de resultados não operacional.", theme.COLOR_ERROR)
            return

        validation_result = structured_display_ctrl.get_current_form_data(validate_for_export=True)
        # ... (lógica de tratamento de validation_result e invalid_field_details como antes) ...
        current_data_for_export: Optional[FormatAnaliseInicial] = None
        invalid_field_details: List[Tuple[str, Optional[ft.Control]]] = []
        if isinstance(validation_result, FormatAnaliseInicial):
            current_data_for_export = validation_result
        elif isinstance(validation_result, list):
            invalid_field_details = validation_result
        
        if invalid_field_details or not current_data_for_export:
            # ... (lógica de exibir diálogo de erro/snackbar como antes) ...
            if invalid_field_details: # Copiando a lógica de tratamento de erro de validação
                _logger.info("Exibindo diálogo de campos inválidos/problemáticos para exportação...")
                first_error_tuple = invalid_field_details[0]
                if first_error_tuple[0].startswith("pydantic_validation_error") or first_error_tuple[0].startswith("internal_form_data_error"):
                    error_msg_detail = "Verifique os campos e tente novamente." if "pydantic" in first_error_tuple[0] else "Tente recarregar os dados."
                    show_snackbar(self.page, f"Erro de validação nos dados do formulário. {error_msg_detail}", theme.COLOR_ERROR, duration=5000)
                    return
                error_messages_list = []
                first_invalid_control_to_focus: Optional[ft.Control] = None
                for field_name, control_instance in invalid_field_details:
                    friendly_field_name = field_name.replace("_", " ").title()
                    error_messages_list.append(f"- {friendly_field_name}")
                    if control_instance and not first_invalid_control_to_focus: first_invalid_control_to_focus = control_instance
                if error_messages_list:
                    dialog_content_controls_list = [ft.Text("Os seguintes campos obrigatórios precisam ser preenchidos antes da exportação:")]
                    for msg_item in error_messages_list: dialog_content_controls_list.append(ft.Text(msg_item))
                    show_confirmation_dialog(
                        page=self.page, title="Campos Obrigatórios Pendentes",
                        content=ft.Column(dialog_content_controls_list, tight=True, spacing=5),
                        confirm_text="OK", cancel_text=None,
                        on_confirm= lambda: first_invalid_control_to_focus.focus() if first_invalid_control_to_focus and hasattr(first_invalid_control_to_focus, 'focus') else None)
                return
            if not current_data_for_export:
                show_snackbar(self.page, "Não há dados de análise válidos para exportar (após checagem final).", theme.COLOR_ERROR)
                _logger.error("current_data_for_export ainda é None após todas as verificações antes de chamar o ExportManager.")
                return
            return # Sai se houve erro de validação ou dados nulos

        # Se chegou aqui, current_data_for_export é válido
        if not self.export_manager:
            _logger.error("ExportManager não inicializado. Não é possível exportar.")
            show_snackbar(self.page, "Erro interno: Serviço de exportação não disponível.", theme.COLOR_ERROR)
            return

        operation_to_perform: Optional[ExportOperation] = None
        template_path_for_operation: Optional[str] = None

        if selected_action_data == "export_simple_docx":
            operation_to_perform = ExportOperation.SIMPLE_DOCX
        elif selected_action_data and selected_action_data.startswith("export_template_"):
            operation_to_perform = ExportOperation.TEMPLATE_DOCX
            template_path_for_operation = selected_action_data[len("export_template_"):]
        elif selected_action_data == "manage_templates":
            show_snackbar(self.page, "Gerenciamento de templates ainda não implementado.", theme.COLOR_WARNING)
            self._update_button_states() # Atualiza UI caso algo tenha mudado
            return
        else:
            _logger.warning(f"Ação de exportação desconhecida recebida: {selected_action_data}")
            self._update_button_states()
            return

        if not operation_to_perform: # Segurança
            self._update_button_states()
            return

        # Agora, chame o export_manager.start_export.
        # A decisão de usar Timer ou não para o fluxo desktop foi movida para dentro do ExportManager
        # na última refatoração. No entanto, o log que você mostrou indicava que o Timer ainda estava lá.
        # Vamos REVERTER a decisão do ExportManager e fazer com que _handle_export_selected
        # decida sobre o Timer para o fluxo desktop, e ExportManager.start_export apenas execute.

        _logger.info(f"_handle_export_selected: Preparando para chamar export_manager.start_export. Operação: {operation_to_perform}, Web: {self.page.web}")

        if self.page.web:
            # Para WEB, chamamos start_export diretamente. Ele lidará com launch_url.
            _logger.debug("_handle_export_selected: MODO WEB. Chamando start_export diretamente.")
            self.export_manager.start_export(operation_to_perform, current_data_for_export, template_path_for_operation)
        else:
            # Para DESKTOP, usamos o Timer para tentar resolver o problema do diálogo não aparecer.
            # A função do timer chamará start_export.
            _logger.debug("_handle_export_selected: MODO DESKTOP. Agendando start_export com Timer.")
            
            # Precisamos passar os argumentos corretos para start_export através do Timer.
            # A função do timer não pode ser um método de instância com `self` facilmente
            # se quisermos passar args diferentes toda vez, a menos que usemos functools.partial
            # ou uma closure.
            
            # Armazena os dados que a thread do timer precisará.
            # É importante que current_data_for_export seja estável (não modificado pela UI principal
            # no pequeno intervalo do timer).
            self.export_manager.current_data_for_export_obj = current_data_for_export # Define no manager para o timer pegar

            def desktop_export_action_via_timer():
                _logger.info(f"THREAD TIMER (Desktop): Iniciando exportação via export_manager.start_export. Operação: {operation_to_perform}")
                # O ExportManager usará seu self.current_data_for_export_obj que foi definido antes do timer.
                self.export_manager.start_export(operation_to_perform, self.export_manager.current_data_for_export_obj, template_path_for_operation)

            # ANTES de agendar o Timer, o `page.update()` pode ser importante
            # para que o Flet processe o estado da UI (ex: fechar o PopupMenu).
            self.page.update()
            _logger.info("_handle_export_selected (Desktop): page.update() chamado ANTES de agendar o Timer.")

            threading.Timer(0.2, desktop_export_action_via_timer).start()
            _logger.info("_handle_export_selected (Desktop): Timer agendado para executar desktop_export_action_via_timer.")
        
        self._update_button_states()
        # O page.update() aqui pode ser redundante se o fluxo web chamou launch_url
        # ou se o fluxo desktop agendou um timer e já fez um update antes.
        # Removê-lo por enquanto para ver se o update antes do timer (desktop) ou o launch_url (web) são suficientes.
        # self.page.update()

    # --- Handlers de Eventos (Implementações Iniciais) ---
    def _setup_event_handlers(self):
        _logger.info("Configurando handlers de eventos da UI.")
        self.gui_controls[CTL_UPLOAD_BTN].on_click = self._handle_upload_click
        self.gui_controls[CTL_PROCESS_BTN].on_click = self._handle_process_content_click
        self.gui_controls[CTL_ANALYZE_BTN].on_click = self._handle_analyze_click
        self.gui_controls[CTL_PROMPT_STRUCT_BTN].on_click = self._handle_prompt_structured_click
        self.gui_controls[CTL_RESTART_BTN].on_click = self._handle_restart_click
        #self.gui_controls[CTL_EXPORT_BTN].on_item_selected = self._handle_export_selected # Para PopupMenuButton
        self.gui_controls[CTL_SETTINGS_BTN].on_click = self._handle_toggle_settings_drawer

    def _handle_upload_click(self, e: ft.ControlEvent):
        _logger.info("Botão 'Carregar Arquivo(s)' clicado.")
        if self.managed_file_picker:
            threading.Timer(0.1, show_loading_overlay, args=[self.page, "A carregar arquivo(s)..."]).start()
            self.managed_file_picker.pick_files(allow_multiple=True, dialog_title_override="Selecione PDF(s) para análise")
            # O hide_loading_overlay será chamado no batch_upload_complete_cb
        else:
            show_snackbar(self.page, "Erro: Gerenciador de upload não está pronto.", theme.COLOR_ERROR)

    def _handle_process_content_click(self, e: ft.ControlEvent):
        _logger.info("Botão 'Processar Conteúdo' clicado.")
        ordered_files = self.page.session.get(KEY_SESSION_PDF_FILES_ORDERED)
        if not ordered_files:
            show_snackbar(self.page, "Nenhum PDF carregado para processar.", theme.COLOR_WARNING)
            return
        
        pdf_paths = [f['path'] for f in ordered_files]
        batch_name = self.page.session.get(KEY_SESSION_CURRENT_BATCH_NAME) or "Lote Atual"

        # Desabilitar botões de processamento
        self._files_processed = False # Sinaliza que está reprocessando
        self._analysis_requested = False
        self._remove_data_session(KEY_SESSION_PDF_LLM_RESPONSE)
        self._update_button_states()
        self._show_info_balloon_or_result(show_balloon=True)

        self.analysis_controller.start_pdf_processing_only(pdf_paths, batch_name)

    def _handle_analyze_click(self, e: ft.ControlEvent):
        _logger.info("Botão 'Solicitar Análise' clicado.")
        if not self._files_processed:
            self._handle_process_and_analyze(e)
            #show_snackbar(self.page, "Conteúdo dos arquivos ainda não processado. Clique em 'Processar Conteúdo' primeiro.", theme.COLOR_WARNING, duration=5000)
            return

        aggregated_text_info = self.page.session.get(KEY_SESSION_PDF_AGGREGATED_TEXT_INFO)
        if not aggregated_text_info or not aggregated_text_info[1]: # [1] é o aggregated_text
            show_snackbar(self.page, "Não há texto agregado para análise. Verifique o processamento.", theme.COLOR_ERROR)
            return
        
        aggregated_text = aggregated_text_info[1]
        batch_name = self.page.session.get(KEY_SESSION_CURRENT_BATCH_NAME) or "Lote Atual"

        self._analysis_requested = False # Sinaliza que está reanalisando
        self._update_button_states()
        self._show_info_balloon_or_result(show_balloon=True) # Limpa resultado anterior

        self.analysis_controller.start_llm_analysis_only(aggregated_text, batch_name)

    def _handle_process_and_analyze(self, e: ft.ControlEvent):
        ordered_files = self.page.session.get(KEY_SESSION_PDF_FILES_ORDERED)
        if not ordered_files:
            show_snackbar(self.page, "Nenhum PDF carregado.", theme.COLOR_WARNING)
            return

        pdf_paths = [f['path'] for f in ordered_files]
        batch_name = self.page.session.get(KEY_SESSION_CURRENT_BATCH_NAME) or "Lote Atual"

        self._files_processed = False
        self._analysis_requested = False
        self._remove_data_session(KEY_SESSION_PDF_LLM_RESPONSE) # Limpa resultado antigo da LLM
        self._update_button_states()
        self._show_info_balloon_or_result(show_balloon=True)

        self.analysis_controller.start_full_analysis_pipeline(pdf_paths, batch_name)

    def _handle_prompt_structured_click(self, e: ft.ControlEvent):
        _logger.info("Botão 'Prompt Estruturado' clicado.")
        show_snackbar(self.page, "Visualização do 'Prompt Estruturado' ainda não implementado.", theme.COLOR_WARNING)
        # TODO: Navegar para a view de prompt estruturado (page.go("/analyze_pdf/prompt_editor")?)

    def _handle_restart_click(self, e: ft.ControlEvent):
        _logger.info("Botão 'Reiniciar' clicado.")
        self._clear_all_data_and_gui()
        show_snackbar(self.page, "Análise reiniciada. Carregue novos arquivos.", theme.COLOR_INFO)

    def _update_export_button_menu(self):
        export_button = self.gui_controls.get(CTL_EXPORT_BTN)
        if not isinstance(export_button, ft.PopupMenuButton):
            return

        export_button.items.clear()

        # Item Simples
        simple_export_item = ft.PopupMenuItem(
            text="Exportar em Simples DOCX",
            data="export_simple_docx"
        )
        simple_export_item.on_click = self._handle_export_selected # Atribui o mesmo handler
        export_button.items.append(simple_export_item)

        available_templates = self.docx_exporter.get_available_templates()
        if available_templates:
            export_button.items.append(ft.PopupMenuItem()) # Funciona como divisor
            export_button.items.append(
                ft.PopupMenuItem(text="Exportar Usando Template:", disabled=True) # Um cabeçalho para a seção de templates
            )
            for friendly_name, template_path in available_templates:
                template_item = ft.PopupMenuItem(
                    text=f"      {friendly_name}", # Indenta para parecer um subitem
                    data=f"export_template_{template_path}"
                )
                template_item.on_click = self._handle_export_selected # Atribui o mesmo handler
                export_button.items.append(template_item)
        else:
            export_button.items.append(ft.PopupMenuItem()) # Divisor
            export_button.items.append(
                 ft.PopupMenuItem(text="Nenhum template DOCX encontrado", disabled=True)
            )    

        # Opção de Gerenciar Templates (ainda desabilitada)
        export_button.items.append(ft.PopupMenuItem()) # Divisor
        manage_templates_item = ft.PopupMenuItem(
            text="Adicionar Novo Template", 
            data="manage_templates",
            #icon=ft.Icons.SETTINGS_APPLICATIONS_OUTLINED,
        )
        manage_templates_item.on_click = self._handle_export_selected # Mesmo handler, que tratará 'manage_templates'
        export_button.items.append(manage_templates_item)
            
        if export_button.page and export_button.uid:
            export_button.update()

    def _handle_toggle_settings_drawer(self, e: Optional[ft.ControlEvent] = None):
        self._is_drawer_open = not self._is_drawer_open
        self.settings_drawer_container.width = 320 if self._is_drawer_open else 0
        # self.settings_drawer_container.visible = self._is_drawer_open # Alternativa à largura
        
        # Animação suave da borda ou sombra
        if self._is_drawer_open:
            self.settings_drawer_container.border = ft.border.only(left=ft.border.BorderSide(2, theme.PRIMARY))
        else:
            self.settings_drawer_container.border = None # Remove a borda ao fechar

        self.settings_drawer_container.update()
        _logger.info(f"Drawer de configurações {'aberto' if self._is_drawer_open else 'fechado'}.")

    # --- Lógica de Atualização da UI (Métodos Internos) ---
    def _update_button_states(self):
        files_exist = bool(self.page.session.get(KEY_SESSION_PDF_FILES_ORDERED))
        llm_response_exists = bool(self.page.session.get(KEY_SESSION_PDF_LLM_RESPONSE))

        # Sempre habilitados
        self.gui_controls[CTL_UPLOAD_BTN].disabled = False
        self.gui_controls[CTL_PROMPT_STRUCT_BTN].disabled = False
        self.gui_controls[CTL_SETTINGS_BTN].disabled = False

        # Habilitados se arquivos existirem
        self.gui_controls[CTL_RESTART_BTN].disabled = not files_exist
        
        # Botões de processamento/análise
        # Desabilitados se já processados/analisados ou se não há arquivos
        self.gui_controls[CTL_PROCESS_BTN].disabled = not (files_exist and not self._files_processed)
        self.gui_controls[CTL_ANALYZE_BTN].disabled = not (files_exist)

        # Botão de Exportar
        self._update_export_button_menu()
        self.gui_controls[CTL_EXPORT_BTN].disabled = not llm_response_exists
        self.gui_controls[CTL_LLM_RESULT_INFO_TITLE].visible = llm_response_exists
        
        if not self.gui_controls[CTL_LLM_STATUS_INFO].value or self.gui_controls[CTL_LLM_STATUS_INFO].color != theme.COLOR_ERROR:
            if not self._files_processed:
                self.gui_controls[CTL_LLM_STATUS_INFO].value = "Aguardando para exibir os resultados..."
            elif not llm_response_exists:
                self.gui_controls[CTL_LLM_STATUS_INFO].value = "Clique em 'Solicitar Análise' para prosseguir "

        # Força atualização dos botões
        for btn_key in [CTL_UPLOAD_BTN, CTL_PROCESS_BTN, CTL_ANALYZE_BTN, CTL_LLM_RESULT_INFO_TITLE, CTL_LLM_STRUCTURED_RESULT_DISPLAY,
                        CTL_PROMPT_STRUCT_BTN, CTL_RESTART_BTN, CTL_EXPORT_BTN, CTL_SETTINGS_BTN, CTL_LLM_STATUS_INFO]:
            if btn_key in self.gui_controls and self.gui_controls[btn_key].page and self.gui_controls[btn_key].uid:
                self.gui_controls[btn_key].update()
        _logger.info("[DEBUG] Estados dos botões atualizados.")

    def _update_processing_metadata_display(self, proc_meta: Optional[Dict[str, Any]] = None):
        content_area = self.gui_controls[CTL_PROC_METADATA_CONTENT]
        content_area.controls.clear()
        metadata_to_display = proc_meta or self.page.session.get(KEY_SESSION_PROCESSING_METADATA)

        if not metadata_to_display:
            #content_area.controls.append(ft.Text("Nenhum metadado de processamento disponível.", italic=True))
            self.gui_controls[CTL_PROC_METADATA_PANEL].visible = False
        else:
            self.gui_controls[CTL_PROC_METADATA_PANEL].visible = True
            # Mapeamento de chaves para labels amigáveis
            labels = [
                ("total_pages_processed",                        "Páginas totais Processadas"),
                ("relevant_pages_global_keys_formatted",         "Páginas Relevantes consideradas"),
                #"count_selected_relevant":                      "Qtd. Páginas Selecionadas como Relevantes",
                ("count_discarded_similarity",                   "Páginas Irrelevantes por Similaridade"),
                ("unintelligible_pages_global_keys_formatted",   "Páginas Descartadas (Ininteligíveis)"),
                #"count_discarded_unintelligible":               "Qtd. Páginas Descartadas (Ininteligíveis)",
                ("total_tokens_before_truncation",               "Tokens totais das Páginas Relevantes"),
                ("final_pages_global_keys_formatted",            "Páginas Selecionadas com limite de tokens"),
                #"count_selected_final":                         "Qtd. Páginas Selecionadas com limite de tokens",
                ("final_aggregated_tokens",                      "Tokens totais das Páginas Selecionadas"),
                ("supressed_tokens_percentage",                  "Percentual de Tokens Suprimidos"),
                ("processing_time",                              "Tempo de processamento")
            ]
            
            ordered_keys = [key for key, _ in labels]
            labels = {k: v for k, v in labels}
            data_rows = []

            for key in ordered_keys:
                if key in ["count_selected_relevant", "count_discarded_unintelligible", "count_selected_final"]:
                    continue

                if key in metadata_to_display and key in labels:
                    label_text = f"{labels[key]}:"
                    value = metadata_to_display.get(key)
                    
                    if key == "final_pages_global_keys_formatted" and value == metadata_to_display.get("relevant_pages_global_keys_formatted"):
                        continue # Quando não houver supressão de páginas por limites de token
                    
                    display_value = str(value if value is not None else "N/A")

                    if key == "supressed_tokens_percentage" and isinstance(value, (int, float)):
                        value = 0 if value < 0 else value
                        display_value = f"{value:.2f}%"
                    elif key == "relevant_pages_global_keys_formatted" and value is not None:
                        total_value = metadata_to_display.get("count_selected_relevant")
                        display_value = f"{total_value} : {display_value}"
                    elif key == "unintelligible_pages_global_keys_formatted" and value is not None:
                        total_value = metadata_to_display.get("count_discarded_unintelligible")
                        display_value = f"{total_value} : {display_value}"
                    elif key == "final_pages_global_keys_formatted" and value is not None:
                        total_value = metadata_to_display.get("count_selected_final")
                        display_value = f"{total_value} : {display_value}"
                                        
                    data_rows.append((label_text, display_value))

            if data_rows:
                metadata_table = CompactKeyValueTable(
                    data=data_rows,
                    key_col_width=290,  # Ajuste a largura da coluna de chaves
                    value_col_width=None, # Deixe None para a coluna de valor expandir ou defina uma largura
                    row_spacing=4,      # Espaçamento entre as "linhas"
                    col_spacing=8,      # Espaçamento entre chave e valor
                    default_text_size=14
                    # Você pode passar key_style e value_style personalizados se desejar
                )
                content_area.controls.append(ft.Container(metadata_table, padding=ft.padding.only(left=30, bottom=10)))

            # Alerta OCR (mantido como estava, abaixo da tabela se houver)
            if metadata_to_display.get("count_discarded_unintelligible", 0) > 0:
                content_area.controls.append(ft.Container(height=1)) # Espaçador
                content_area.controls.append(
                    ft.Container(
                        ft.Row([
                            ft.Icon(ft.icons.WARNING_AMBER_ROUNDED, color=theme.COLOR_WARNING),
                            ft.Text("Páginas ininteligíveis detectadas. Considere usar OCR nelas.", 
                                    color=theme.COLOR_WARNING, weight=ft.FontWeight.BOLD)
                        ], spacing=5, alignment=ft.MainAxisAlignment.START),
                        padding=ft.padding.only(left=20, bottom=10)
                    )
                )
            
        # Comentado devido AssertionError: Text Control must be added to the page first
        # if content_area.page: content_area.update()
        # A view principal faz o update quando _restore_state_from_session ou uma ação que modifique os metadados for concluída.

    def _update_llm_metadata_display(self, llm_meta: Optional[Dict[str, Any]] = None):
        content_area = self.gui_controls[CTL_LLM_METADATA_CONTENT]
        content_area.controls.clear()
        metadata_to_display = llm_meta or self.page.session.get(KEY_SESSION_LLM_METADATA)

        if not metadata_to_display:
            #content_area.controls.append(ft.Text("Nenhum metadado da LLM disponível.", italic=True))
            self.gui_controls[CTL_LLM_METADATA_PANEL].visible = False
        else:
            if not metadata_to_display.get("total_cost_usd"):
                loaded_llm_providers = self.page.session.get(KEY_SESSION_LOADED_LLM_PROVIDERS)
                calculated_cost_usd = self.analysis_controller._calc_costs_llm_analysis(metadata_to_display, loaded_llm_providers)
                metadata_to_display["total_cost_usd"] = calculated_cost_usd

            # --- NOVO: Cálculo e adição de custos de Embeddings ---
            tokens_embeddings_session = self.page.session.get(KEY_SESSION_TOKENS_EMBEDDINGS)
            model_embeddings_list_session = self.page.session.get(KEY_SESSION_MODEL_EMBEDDINGS_LIST)
            
            calculated_embedding_cost_usd = self.analysis_controller._calc_costs_embedding_process(tokens_embeddings_session, model_embeddings_list_session)
            
            self.gui_controls[CTL_FILE_LIST_PANEL].controls[0].expanded = False
            self.gui_controls[CTL_PROC_METADATA_PANEL].controls[0].expanded = False
            self.gui_controls[CTL_LLM_METADATA_PANEL].visible = True
            labels = [
                ("input_tokens",         "Tokens de Entrada"),
                ("cached_tokens",        "Tokens em Cache"), 
                ("output_tokens",        "Tokens de Resposta"),
                #"total_tokens",        "Total de Tokens Processados pela LLM",
                ("total_cost_usd",       "Custo Estimado (USD)"),
                ("total_cost_brl",       "Custo Estimado (BRL)"), 
                ("llm_provider_used",    "Provedor LLM"),
                ("llm_model_used",       "Modelo Utilizado"),
                ("processing_time",      "Tempo de processamento")
            ]
            
            ordered_keys = [key for key, _ in labels]
            labels = {k: v for k, v in labels}
            data_rows = []

            for key in ordered_keys:
                label_text = f"{labels[key]}:"
                if key in ["total_tokens", "successful_requests"]:
                    continue
                elif key =="total_cost_brl":
                    value = metadata_to_display.get("total_cost_usd") * cotacao_dolar_to_real
                else:
                    value = metadata_to_display.get(key)

                if value is not None:
                    display_value = str(value if value is not None else "N/A")
                    if key in ["total_cost_usd", "total_cost_brl"] and isinstance(value, (int, float)):
                        currency_symbol = "U$" if key == "total_cost_usd" else "R$"
                        display_value = f"{currency_symbol} {value:.4f}" # 4 casas decimais para custo
                    
                    data_rows.append((label_text, display_value))

            if calculated_embedding_cost_usd:
                cost_embeddings_usd_str = f"U$ {calculated_embedding_cost_usd:.4f}"
                cost_embeddings_brl_str = f"R$ {(calculated_embedding_cost_usd * cotacao_dolar_to_real):.4f}"
                data_rows.insert(5, ("Custos de Embeddings:", f"{cost_embeddings_usd_str} : {cost_embeddings_brl_str}"))
                
            if data_rows:
                metadata_table = CompactKeyValueTable(
                    data=data_rows,
                    key_col_width=290,  
                    value_col_width=None, 
                    row_spacing=4,      
                    col_spacing=8,      
                    default_text_size=14
                    # Você pode passar key_style e value_style personalizados se desejar
                )
                content_area.controls.append(ft.Container(metadata_table, padding=ft.padding.only(left=30, bottom=10)))
        
        # Comentado devido AssertionError: Text Control must be added to the page first
        # if content_area.page: content_area.update()

    def _show_info_balloon_or_result(self, show_balloon: bool, result_data: Optional[Union[str, FormatAnaliseInicial]] = None):
        # Limpa visibilidade de todos os containers de resultado primeiro
        def only_one_visible(control):
            self.gui_controls[control].visible = True  
            self.llm_result_container.content.controls = [self.gui_controls[control]]
            for ctl in [CTL_LLM_RESULT_INFO_BALLOON, CTL_LLM_RESULT_TEXT, CTL_LLM_STRUCTURED_RESULT_DISPLAY]:
                if ctl != control:
                    self.gui_controls[ctl].visible = False            

        if show_balloon:
            only_one_visible(CTL_LLM_RESULT_INFO_BALLOON)
        elif isinstance(result_data, FormatAnaliseInicial):
            structured_display = self.gui_controls[CTL_LLM_STRUCTURED_RESULT_DISPLAY]
            if isinstance(structured_display, LLMStructuredResultDisplay): # Verifica o tipo
                structured_display.update_data(result_data)
                only_one_visible(CTL_LLM_STRUCTURED_RESULT_DISPLAY)
            else: # Fallback se o controle não for o esperado
                _logger.error("Controle CTL_LLM_STRUCTURED_RESULT_DISPLAY não é uma instância de LLMStructuredResultDisplay.")
                self.gui_controls[CTL_LLM_RESULT_TEXT].value = "Erro interno ao exibir resultado estruturado."
                only_one_visible(CTL_LLM_RESULT_TEXT)
        elif isinstance(result_data, str): # Fallback para string
            self.gui_controls[CTL_LLM_RESULT_TEXT].value = result_data
            only_one_visible(CTL_LLM_RESULT_TEXT)
        else: # Caso padrão, mostra balão
            only_one_visible(CTL_LLM_RESULT_INFO_BALLOON)
            _logger.warning(f"Tipo de result_data inesperado para _show_info_balloon_or_result: {type(result_data)}")
        
        if self.llm_result_container.page and self.llm_result_container.uid:
            self.page.update(self.llm_result_container)

        for ctl in [CTL_LLM_STRUCTURED_RESULT_DISPLAY, CTL_LLM_RESULT_TEXT, CTL_LLM_RESULT_INFO_BALLOON]:
            if ctl in self.gui_controls and self.gui_controls[ctl].page and self.gui_controls[ctl].uid:
                #self.gui_controls[ctl].update()
                self.page.update(self.gui_controls[ctl])        
        
        # Não chamar .update() nos controles individuais aqui.
        # A atualização será feita pelo page.update() no método chamador ou em _restore_state_from_session.

    def _clear_processing_metadata_display(self):
        self._remove_data_session(KEY_SESSION_PROCESSING_METADATA)
        self._update_processing_metadata_display() # Passar None para limpar

    def _clear_llm_metadata_display(self):
        self._remove_data_session(KEY_SESSION_LLM_METADATA)
        self._update_llm_metadata_display()

    # --- Gerenciamento de Estado e Limpeza ---
    def _restore_state_from_session(self):
        _logger.info("Restaurando estado da view Análise PDF da sessão.")
        self.file_list_manager.update_selected_files_display() # Restaura lista de arquivos
        
        self._files_processed = bool(self.page.session.get(KEY_SESSION_PDF_ANALYZER_DATA))
        self._analysis_requested = bool(self.page.session.get(KEY_SESSION_PDF_LLM_RESPONSE))
        
        self._update_processing_metadata_display()
        self._update_llm_metadata_display()

        # Carrega as configurações da sessão para o drawer
        analysis_settings_from_session = self.page.session.get(KEY_SESSION_ANALYSIS_SETTINGS)
        if analysis_settings_from_session:
            self._load_settings_into_drawer(analysis_settings_from_session)
        else: # Caso não haja nada na sessão ainda (ex: primeiro carregamento antes de app.py popular)
            self._load_settings_into_drawer(FALLBACK_ANALYSIS_SETTINGS)

        llm_response_from_session = self.page.session.get(KEY_SESSION_PDF_LLM_RESPONSE)
        
        # Determina o tipo de dado para exibir
        data_to_display = None
        if isinstance(llm_response_from_session, str):
            try:
                json_data = json.loads(llm_response_from_session)
                
                if 'valor_apuracao' in json_data:
                    raw_valor = json_data['valor_apuracao']
                    json_data['valor_apuracao'] = clean_and_convert_to_float(raw_valor)
                    _logger.info(f"Restaurando da sessão: Valor apuracao original: '{raw_valor}', convertido para: {json_data['valor_apuracao']}")

                data_to_display = FormatAnaliseInicial(**json_data)
                _logger.info("Resposta LLM (string da sessão) parseada para FormatAnaliseInicial para restauração.")
            except (json.JSONDecodeError, TypeError, Exception):
                data_to_display = llm_response_from_session # Mantém como string se falhar
                _logger.warning("String da sessão não pôde ser parseada/validada como FormatAnaliseInicial na restauração.")
        elif isinstance(llm_response_from_session, FormatAnaliseInicial):
            data_to_display = llm_response_from_session
        
        if data_to_display:
            self._show_info_balloon_or_result(show_balloon=False, result_data=data_to_display)
        else:
            self._show_info_balloon_or_result(show_balloon=True)
        
        self._update_button_states() # Fundamental após restaurar estado
        
        if self.page: # Garante que a página está disponível
            # self.update() # Atualiza a view principal (AnalyzePDFViewContent)
            # E também os painéis que podem ter mudado de visibilidade
            if self.gui_controls[CTL_PROC_METADATA_PANEL].page:
                self.gui_controls[CTL_PROC_METADATA_PANEL].update()
            if self.gui_controls[CTL_LLM_METADATA_PANEL].page:
                self.gui_controls[CTL_LLM_METADATA_PANEL].update()

    def _clear_all_data_and_gui(self):
        _logger.info("Limpando todos os dados e resetando UI da Análise PDF.")
        # Limpa sessão relacionada a esta view
        keys_to_clear_from_session = [
            KEY_SESSION_CURRENT_BATCH_NAME, KEY_SESSION_PDF_FILES_ORDERED,
            KEY_SESSION_PDF_ANALYZER_DATA, KEY_SESSION_PDF_CLASSIFIED_INDICES_DATA,
            KEY_SESSION_PDF_AGGREGATED_TEXT_INFO, KEY_SESSION_PDF_LLM_RESPONSE,
            KEY_SESSION_PROCESSING_METADATA, KEY_SESSION_LLM_METADATA
        ]
        for key in keys_to_clear_from_session:
            self._remove_data_session(key)
        
        # Reseta estado interno
        self._files_processed = False
        self._analysis_requested = False

        # Limpa UI
        self.file_list_manager.update_selected_files_display() # Isso vai limpar a lista de arquivos
        self._clear_processing_metadata_display()
        self._clear_llm_metadata_display()
        self._show_info_balloon_or_result(show_balloon=True) # Mostra balão informativo
        
        # Limpa diretório de uploads temporários, se o ManagedFilePicker estiver configurado
        if self.managed_file_picker:
             self.managed_file_picker.clear_upload_directory()

        self._update_button_states()
        if self.page: 
            self.page.update()

    # --- Classes Internas para Gerenciamento (Adaptadas) ---
    class _InternalFileListManager:
        def __init__(self, page: ft.Page, gui_controls: Dict[str, ft.Control], parent_view: 'AnalyzePDFViewContent'):
            self.page = page
            self.gui_controls = gui_controls
            self.parent_view = parent_view # Referência à view principal

        def update_selected_files_display(self, files_ordered: Optional[List[Dict[str, Any]]] = None):
            list_view = self.gui_controls[CTL_FILE_LIST_VIEW]
            title_text = self.gui_controls[CTL_FILE_LIST_PANEL_TITLE]
            list_view.controls.clear()
            
            _files = files_ordered if files_ordered is not None else self.page.session.get(KEY_SESSION_PDF_FILES_ORDERED) or []

            if not isinstance(_files, list): _files = []

            if not _files:
                title_text.value = "Nenhum arquivo carregado." # list_view.height = 0
                self.gui_controls[CTL_FILE_LIST_PANEL].visible = False
            else:
                self.gui_controls[CTL_FILE_LIST_PANEL].visible = True
                self.gui_controls[CTL_FILE_LIST_PANEL].controls[0].expanded = True
                for idx, file_info in enumerate(_files):
                    if not isinstance(file_info, dict): 
                        continue # Skip malformado
                    
                    file_name_display = ft.Text(
                        value=file_info.get('name', 'Nome Indisponível'),
                        overflow=ft.TextOverflow.ELLIPSIS, width=700, # expand=True
                        #tooltip=file_info.get('name', 'Nome Indisponível'
                    )
                    action_buttons = ft.Row([
                        ft.IconButton(ft.Icons.ARROW_UPWARD_ROUNDED, on_click=lambda _, i=idx: self._move_file_in_list(i, -1), disabled=(idx == 0), icon_size=18, padding=3, tooltip="Mover para Cima"),
                        ft.IconButton(ft.Icons.ARROW_DOWNWARD_ROUNDED, on_click=lambda _, i=idx: self._move_file_in_list(i, 1), disabled=(idx == len(_files) - 1), icon_size=18, padding=3, tooltip="Mover para Baixo"),
                        ft.IconButton(ft.Icons.DELETE_OUTLINE_ROUNDED, on_click=lambda _, i=idx: self._remove_file_from_list(i), icon_color=theme.COLOR_ERROR, icon_size=18, padding=3, tooltip="Remover Arquivo")
                    ], spacing=0, alignment=ft.MainAxisAlignment.START, width=110)
                    # Necessário definir width aqui devido concorrência de espaço indevido com file_name_text no ListTile 

                    list_tile = ft.ListTile(title=file_name_display, 
                                            leading=ft.Icon(ft.Icons.PICTURE_AS_PDF_ROUNDED), 
                                            trailing=action_buttons,)
                                            # visual_density=ft.VisualDensity.COMPACT,) # Torna o ListTile um pouco mais compacto
                                            # dense=True,) # Outra opção para compactar
                    
                    # Draggable/DragTarget (simplificado, verificar documentação Flet para melhor implementação)
                    # Para este exemplo, a reordenação será via botões. Drag-and-drop pode ser complexo aqui.
                    list_view.controls.append(list_tile)

                if len(_files) == 1:
                    title_text.value = f"Arquivo selecionado: {_files[0]['name']}"
                else:
                    title_text.value = f"Arquivos selecionados: {_files[0]['name']} e Outros {len(_files)-1}"
                #list_view.height = min(len(_files) * 55, 220) # Ajustar altura máxima
            
            # Comentado devido AssertionError: Text Control must be added to the page first
            # if self.page:
            #    title_text.update()
            #    list_view.update()
            
            self.page.session.set(KEY_SESSION_CURRENT_BATCH_NAME, title_text.value) # Salva nome do lote
            # A atualização dos botões será feita pela view principal

        def _move_file_in_list(self, index: int, direction: int):
            current_files = list(self.page.session.get(KEY_SESSION_PDF_FILES_ORDERED) or [])
            new_index = index + direction
            if not (0 <= index < len(current_files) and 0 <= new_index < len(current_files)): return

            current_files.insert(new_index, current_files.pop(index))
            self.page.session.set(KEY_SESSION_PDF_FILES_ORDERED, current_files)
            self.update_selected_files_display(current_files)
            self.parent_view._files_processed = False # Requer reprocessamento
            self.parent_view._analysis_requested = False
            self.parent_view._update_button_states()
            self.parent_view._clear_processing_metadata_display()
            self.parent_view._clear_llm_metadata_display()
            self.parent_view._show_info_balloon_or_result(show_balloon=True)
            title_text = self.gui_controls[CTL_FILE_LIST_PANEL_TITLE]
            list_view = self.gui_controls[CTL_FILE_LIST_VIEW]
            self.page.update(title_text, list_view)

        def _remove_file_from_list(self, index: int):
            current_files = list(self.page.session.get(KEY_SESSION_PDF_FILES_ORDERED) or [])
            if not (0 <= index < len(current_files)): return
            
            removed_file_info = current_files.pop(index)
            self.page.session.set(KEY_SESSION_PDF_FILES_ORDERED, current_files)
            
            if self.parent_view.managed_file_picker:
                self.parent_view.managed_file_picker.clear_upload_state_for_file(removed_file_info['name'])
            
            self.update_selected_files_display(current_files)
            if not current_files: # Se a lista ficou vazia
                self.parent_view._clear_all_data_and_gui() # Limpa tudo
            else: # Apenas marca para reprocessar
                self.parent_view._files_processed = False
                self.parent_view._analysis_requested = False
                self.parent_view._clear_processing_metadata_display()
                self.parent_view._clear_llm_metadata_display()
                self.parent_view._show_info_balloon_or_result(show_balloon=True)

            self.parent_view._update_button_states()
            title_text = self.gui_controls[CTL_FILE_LIST_PANEL_TITLE]
            list_view = self.gui_controls[CTL_FILE_LIST_VIEW]
            self.page.update(title_text, list_view)

    class _InternalAnalysisController:
        def __init__(self, page: ft.Page, gui_controls: Dict[str, ft.Control], parent_view: 'AnalyzePDFViewContent'):
            self.page = page
            self.gui_controls = gui_controls
            self.parent_view = parent_view # Referência à view principal
            self.pdf_analyzer = parent_view.pdf_analyzer # Usa o da view
            self.firestore_client_for_metrics = FirebaseClientFirestore() # Instância para métricas

        def _calc_costs_embedding_process(
            self,
            tokens_and_model_id_session: Optional[Tuple[int, str]],
            model_embeddings_list_session: Optional[List[Dict[str, Any]]]
        ) -> Optional[float]:
            """
            Calcula o custo do processo de embedding com base nos tokens e no modelo utilizado.

            Args:
                tokens_and_model_id_session: Uma tupla contendo a contagem de tokens (int)
                                             e o ID do modelo de embedding (str) usado na sessão.
                                             Ou None se não houver dados de token/modelo.
                model_embeddings_list_session: Lista de dicionários, onde cada dicionário
                                               contém informações de configuração do modelo
                                               de embedding, incluindo 'name' (str) e
                                               'cost_per_million' (float/int).
                                               Ou None se a lista de custos não estiver disponível.

            Returns:
                O custo calculado em USD como float, ou None se o cálculo não puder ser realizado
                devido a dados ausentes, inválidos ou configuração não encontrada.
            """
            # Assume-se que _logger está definido e acessível no escopo da classe ou módulo.
            
            if not tokens_and_model_id_session:
                _logger.info("Dados de tokens e ID do modelo não fornecidos para cálculo de custo de embedding.")
                return None
            
            if not model_embeddings_list_session:
                _logger.info("Lista de custos de modelos de embedding não fornecida.")
                return None

            tokens_count, embedding_model_id = tokens_and_model_id_session

            # Validação dos dados desempacotados
            if not isinstance(tokens_count, int) or tokens_count < 0:
                _logger.warning(
                    f"Contagem de tokens inválida fornecida: {tokens_count}. "
                    "Deve ser um inteiro não negativo."
                )
                return None

            if not embedding_model_id or not isinstance(embedding_model_id, str):
                _logger.warning(
                    f"ID do modelo de embedding inválido ou ausente: '{embedding_model_id}'. "
                    "Deve ser uma string não vazia."
                )
                return None

            # Busca a configuração do modelo de embedding (case-insensitive para o nome do modelo)
            embedding_config = next(
                (
                    emb for emb in model_embeddings_list_session
                    if emb.get("name", "").lower() == embedding_model_id.lower()
                ),
                None
            )

            if not embedding_config:
                _logger.warning(
                    f"Configuração de custo não encontrada para o modelo de embedding: '{embedding_model_id}'."
                )
                return None

            # Obtenção e validação do custo por milhão de tokens
            # Corrigido erro de digitação: "cost_per_million" em vez de "coust_per_million"
            cost_per_million = embedding_config.get("coust_per_million")

            if cost_per_million is None:
                _logger.warning(
                    f"Atributo 'cost_per_million' não definido ou é None para o modelo "
                    f"'{embedding_model_id}' na lista de configurações de custo."
                )
                return None
            
            if not isinstance(cost_per_million, (int, float)) or cost_per_million < 0:
                _logger.warning(
                    f"Valor de 'cost_per_million' inválido ({cost_per_million}) para o modelo "
                    f"'{embedding_model_id}'. Deve ser um valor numérico não negativo."
                )
                return None

            # Se não houver tokens, o custo é zero.
            if tokens_count == 0:
                _logger.info(
                    f"Nenhum token processado para o modelo '{embedding_model_id}'. "
                    "Custo de embedding: U$ 0.00"
                )
                return 0.0

            # Cálculo do custo
            calculated_embedding_cost_usd = (tokens_count / 1_000_000) * cost_per_million

            _logger.info(
                f"Custo de embeddings calculado: {tokens_count} tokens para o modelo "
                f"'{embedding_model_id}' -> U$ {calculated_embedding_cost_usd:.6f}"
            )
            return calculated_embedding_cost_usd

        def _calc_costs_llm_analysis(self, metadata_llm_analysis, loaded_llm_providers):
            calculated_cost_usd = 0.0
            provider_used_raw = metadata_llm_analysis.get("llm_provider_used", "").lower() 
            model_used_raw = metadata_llm_analysis.get("llm_model_used", "").lower()
            
            input_tokens = metadata_llm_analysis.get("input_tokens", 0)
            cached_tokens = metadata_llm_analysis.get("cached_tokens", 0) 
            output_tokens = metadata_llm_analysis.get("output_tokens", 0)

            #loaded_llm_providers = self.page.session.get(KEY_SESSION_LOADED_LLM_PROVIDERS)
            if loaded_llm_providers and provider_used_raw and model_used_raw:
                provider_config = next((
                    p for p in loaded_llm_providers
                    if p.get("system_name", "").lower() == provider_used_raw # Compara com system_name
                ), None)
                
                if provider_config:
                    model_config = next((
                        m for m in provider_config.get("models", [])
                        if m.get('id', "").lower() == model_used_raw
                    ), None)
                    
                    if model_config:
                        cost_input = (input_tokens / 1_000_000) * model_config.get("input_coust_million", 0.0)
                        cost_cache = (cached_tokens / 1_000_000) * model_config.get("cache_coust_million", 0.0)
                        cost_output = (output_tokens / 1_000_000) * model_config.get("output_coust_million", 0.0)
                        calculated_cost_usd = cost_input + cost_cache + cost_output
                        _logger.info(f"Custo calculado: Input=${cost_input:.6f}, Cache=${cost_cache:.6f}, Output=${cost_output:.6f} -> Total=${calculated_cost_usd:.6f}")
                    else:
                        _logger.warning(f"Configuração do modelo '{model_used_raw}' não encontrada para o provedor '{provider_used_raw}' para cálculo de custo.")
                else:
                    _logger.warning(f"Configuração do provedor '{provider_used_raw}' não encontrada para cálculo de custo.")
            else:
                _logger.warning("Dados insuficientes (provedores carregados, provedor/modelo usado) para calcular o custo.")
            
            #metadata_to_display["total_cost_usd"] = calculated_cost_usd 
            return calculated_cost_usd

        def _log_analysis_metrics(self):
            _logger.info("Coletando e enviando métricas da análise.")
            try:
                user_id = self.page.session.get("auth_user_id")
                user_token = self.page.session.get("auth_id_token")

                if not user_id or not user_token:
                    _logger.error("Não foi possível registrar métricas: usuário não autenticado na sessão.")
                    return

                # 1. Filenames
                files_ordered_session = self.page.session.get(KEY_SESSION_PDF_FILES_ORDERED) or []
                filenames_uploaded = [f.get('name', 'unknown_file') for f in files_ordered_session if isinstance(f, dict)]

                # 2. Processing Metadata
                proc_meta_session = self.page.session.get(KEY_SESSION_PROCESSING_METADATA) or {}
                processing_metadata_to_log = {
                    "total_pages_processed": proc_meta_session.get("total_pages_processed"),
                    "relevant_pages_global_keys_formatted": proc_meta_session.get("relevant_pages_global_keys_formatted"),
                    "unintelligible_pages_global_keys_formatted": proc_meta_session.get("unintelligible_pages_global_keys_formatted"),
                    "final_aggregated_tokens": proc_meta_session.get("final_aggregated_tokens"),
                    "processing_time": proc_meta_session.get("processing_time")
                }

                # 3. LLM Analysis Metadata           
                llm_meta_session = self.page.session.get(KEY_SESSION_LLM_METADATA) or {}
                llm_analysis_metadata_to_log = {
                    "input_tokens": llm_meta_session.get("input_tokens"),
                    "cached_tokens": llm_meta_session.get("cached_tokens"),
                    "output_tokens": llm_meta_session.get("output_tokens"),
                    "total_cost_usd": llm_meta_session.get("total_cost_usd"),
                    "llm_provider_used": llm_meta_session.get("llm_provider_used"),
                    "llm_model_used": llm_meta_session.get("llm_model_used"),
                    "processing_time": llm_meta_session.get("processing_time"), # Tempo da LLM
                } 
                
                tokens_embeddings_session = self.page.session.get(KEY_SESSION_TOKENS_EMBEDDINGS)
                model_embeddings_list_session = self.page.session.get(KEY_SESSION_MODEL_EMBEDDINGS_LIST)
                calculated_embedding_cost_usd = self._calc_costs_embedding_process(tokens_embeddings_session, model_embeddings_list_session)

                if calculated_embedding_cost_usd:
                    llm_analysis_metadata_to_log["tokens_embeddings_session"] = tokens_embeddings_session[0] # Não está sendo salvo o modelo_embedding, por ser único.
                    llm_analysis_metadata_to_log["calculated_embedding_cost_usd"] = calculated_embedding_cost_usd

                # Remover chaves com valor None para não poluir o Firestore
                llm_analysis_metadata_to_log = {k: v for k, v in llm_analysis_metadata_to_log.items() if v is not None}

                # 4. LLM Parsed Response Fields
                llm_response_obj = self.page.session.get(KEY_SESSION_PDF_LLM_RESPONSE)
                llm_parsed_response_fields = {}
                if isinstance(llm_response_obj, FormatAnaliseInicial):
                    fields_to_log = [
                        "tipo_documento_origem", "orgao_origem", "uf_origem", "municipio_origem",
                        "tipo_local", "uf_fato", "municipio_fato", "valor_apuracao",
                        "area_atribuicao", "tipificacao_penal", "tipo_a_autuar", "assunto_re", "destinacao"
                    ]
                    for field_name in fields_to_log:
                        if hasattr(llm_response_obj, field_name):
                            llm_parsed_response_fields[field_name] = getattr(llm_response_obj, field_name)

                # 5. Analysis Settings Overrides
                current_settings = self.page.session.get(KEY_SESSION_ANALYSIS_SETTINGS) or {}
                default_settings = self.page.session.get(KEY_SESSION_CLOUD_ANALYSIS_DEFAULTS) or {}
                analysis_settings_overrides = {}
                for key, current_val in current_settings.items():
                    default_val = default_settings.get(key)
                    # Garantir comparação de tipos consistentes, especialmente para números que podem ser strings
                    current_val_typed = current_val
                    default_val_typed = default_val
                    if isinstance(default_val, (int, float)) and isinstance(current_val, str):
                        try:
                            if isinstance(default_val, int): current_val_typed = int(current_val)
                            elif isinstance(default_val, float): current_val_typed = float(current_val)
                        except ValueError:
                            pass # Mantém current_val_typed como string se não puder converter
                    
                    if current_val_typed != default_val_typed:
                        analysis_settings_overrides[key] = current_val # Salva o valor da sessão (pode ser string ou número)

                metric_data = {
                    "event_type": "pdf_analysis_completed",
                    "timestamp_event": datetime.now().isoformat(),
                    "app_version": APP_VERSION,
                    "filenames_uploaded": filenames_uploaded,
                    "processing_metadata": processing_metadata_to_log,
                    "llm_analysis_metadata": llm_analysis_metadata_to_log,
                    "llm_parsed_response_fields": llm_parsed_response_fields,
                    "analysis_settings_overrides": analysis_settings_overrides
                }

                # Envia a métrica
                if not self.firestore_client_for_metrics.save_metrics_client(user_token, user_id, metric_data):
                    _logger.error("Falha ao registrar métricas da análise no Firestore.")
                else:
                    _logger.info("Métricas da análise registradas com sucesso no Firestore.")
                    #Zerar embeddings para não recalcular caso click analyze_only sem reprocessamento
                    if self.page.session.contains_key(KEY_SESSION_TOKENS_EMBEDDINGS):
                        self.page.session.remove(KEY_SESSION_TOKENS_EMBEDDINGS)

            except Exception as e:
                _logger.error(f"Erro ao coletar ou enviar métricas da análise: {e}", exc_info=True)
                
        def _get_current_analysis_settings(self) -> Dict[str, Any]:
            """Busca as configurações de análise atuais da sessão."""
            settings = self.page.session.get(KEY_SESSION_ANALYSIS_SETTINGS)
            if not settings or not isinstance(settings, dict):
                _logger.warning("Configurações de análise não encontradas na sessão ou formato inválido. Usando fallbacks.")
                return FALLBACK_ANALYSIS_SETTINGS.copy() # Retorna uma cópia
            
            # Garante que os tipos numéricos estejam corretos, pois podem vir de TextFields como string
            # Faz uma cópia para não modificar o original na sessão aqui.
            # A normalização de tipos deve ocorrer quando os valores são lidos do drawer.
            # Aqui, apenas garantimos que se o tipo for string e deveria ser número, tentamos converter.
            current_settings = settings.copy()
            try:
                current_settings['llm_input_token_limit'] = int(current_settings.get('llm_input_token_limit', FALLBACK_ANALYSIS_SETTINGS['llm_input_token_limit']))
            except (ValueError, TypeError):
                 current_settings['llm_input_token_limit'] = FALLBACK_ANALYSIS_SETTINGS['llm_input_token_limit']
            
            try:
                current_settings['llm_temperature'] = float(current_settings.get('llm_temperature', FALLBACK_ANALYSIS_SETTINGS['llm_temperature']))
            except (ValueError, TypeError):
                current_settings['llm_temperature'] = FALLBACK_ANALYSIS_SETTINGS['llm_temperature']
            
            return current_settings

        def _update_status_callback(self, text: str, is_error: bool = False, only_txt: bool = False):
            # Este callback será executado pela thread principal via page.run_thread
            #_logger.info(f"[DEBUG] Callback UI: Atualizando {control_key} para '{text}' (Erro: {is_error})")
            
            txt_to_update = self.gui_controls[CTL_LLM_STATUS_INFO] # control_key = ft.Text

            hide_loading_overlay(self.page)
            if not only_txt:
                show_loading_overlay(self.page, text)
            
            if txt_to_update.page and txt_to_update.uid:
                txt_to_update.value = text
                txt_to_update.color = theme.COLOR_ERROR if is_error else None
                txt_to_update.weight = ft.FontWeight.BOLD if is_error else ft.FontWeight.NORMAL
                txt_to_update.update()
            
        def _pdf_processing_thread_func(self, pdf_paths: List[str], batch_name: str, analyze_llm_after: bool):            
            current_analysis_settings = self._get_current_analysis_settings()
            _logger.info(f"Usando configurações de análise para processamento: {current_analysis_settings}")
            pdf_extractor = current_analysis_settings.get("pdf_extractor", FALLBACK_ANALYSIS_SETTINGS["pdf_extractor"])
            provider = current_analysis_settings.get("llm_provider", FALLBACK_ANALYSIS_SETTINGS["llm_provider"])
            model_embedding = current_analysis_settings.get("embeddings_model", FALLBACK_ANALYSIS_SETTINGS["embeddings_model"])
            token_limit_pref = current_analysis_settings.get("llm_input_token_limit", FALLBACK_ANALYSIS_SETTINGS["llm_input_token_limit"])
            
            if pdf_extractor == 'PdfPlumber':
                self.pdf_analyzer.extractor = PdfPlumberExtractor()
                _logger.info("Alterando pdf_extractor para PdfPlumber!")

            decrypted_api_key = self.page.session.get(f"decrypted_api_key_{provider}") 
            if decrypted_api_key:
                _logger.info(f"Chave API descriptografada para '{provider}' obtida da sessão.")
            elif model_embedding == "text-embedding-3-small":
                if not decrypted_api_key and provider == "openai": 
                    user_token = self.page.session.get("auth_id_token")
                    user_id = self.page.session.get("auth_user_id")
                    decrypted_api_key = get_api_key_in_firestore(user_token, user_id, provider)
                    assert decrypted_api_key
                    self.page.session.set(f"decrypted_api_key_{provider}", decrypted_api_key)
            
            try:
                _logger.info(f"Thread: Iniciando processamento de PDFs para '{batch_name}' (LLM depois: {analyze_llm_after})")
                self.page.run_thread(self._update_status_callback, "Etapa 1/5: Extraindo textos do(s) arquivo(s) selecionado(s)...")
                
                #processed_page_data_combined = self.pdf_analyzer.analyze_pdf_documents(pdf_paths)

                processed_files_metadata, all_indices, all_storage, all_analysis_texts, processing_time_1 = \
                                    self.pdf_analyzer.extract_texts_and_preprocess_files(pdf_paths)

                processed_page_data_combined, all_global_page_keys_ordered, processing_time_2 = \
                                    self.pdf_analyzer._build_combined_page_data(processed_files_metadata, all_indices, all_storage)

                self.page.run_thread(self._update_status_callback, f"Etapa 2/5: Processando {len(processed_page_data_combined)} páginas...")
                processed_page_data_combined, processing_time_3, tokens_embeddings = self.pdf_analyzer.analyze_similarity_and_relevance_files(
                                    processed_page_data_combined, all_global_page_keys_ordered, all_analysis_texts, 
                                    model_embedding=model_embedding, api_key=decrypted_api_key)

                # TODO: melhorar sistemática de captura dessa informação
                if tokens_embeddings:
                    self.page.session.set(KEY_SESSION_TOKENS_EMBEDDINGS, (tokens_embeddings, model_embedding))
                    _logger.info(f"Tokens de embedding ({tokens_embeddings}) salvos na sessão.")
                else:
                    if self.page.session.contains_key(KEY_SESSION_TOKENS_EMBEDDINGS):
                        self.page.session.remove(KEY_SESSION_TOKENS_EMBEDDINGS)
                        _logger.info("Tokens de embedding removidos da sessão (não retornados pela análise).")

                if not processed_page_data_combined:
                    raise ValueError("Nenhum dado processável encontrado nos PDFs.")
                
                #print('\n[DEBUG]:\n', processed_page_data_combined, '\n\n')
                self.page.session.set(KEY_SESSION_PDF_ANALYZER_DATA, processed_page_data_combined)
                
                point_time = time()
                self.page.run_thread(self._update_status_callback, "Etapa 3/5: Classificando páginas...")

                classified_data = self.pdf_analyzer.filter_and_classify_pages(processed_page_data_combined)
                self.page.session.set(KEY_SESSION_PDF_CLASSIFIED_INDICES_DATA, classified_data)
                
                relevant_indices, unintelligible_indices, count_similars = classified_data
                count_sel, count_unint = len(relevant_indices), len(unintelligible_indices)

                if not relevant_indices:
                    raise ValueError("Nenhuma página relevante encontrada após classificação.")

                if time() - point_time < 1: sleep(1) # Apenas Garante visibilidade do text_progressing

                point_time = time()
                self.page.run_thread(self._update_status_callback, "Etapa 4/5: Filtrando páginas...")

                aggregated_info = self.pdf_analyzer.group_texts_by_relevance_and_token_limit(
                    processed_page_data_combined, relevant_indices, token_limit_pref
                )
                self.page.session.set(KEY_SESSION_PDF_AGGREGATED_TEXT_INFO, aggregated_info)
                
                pages_agg_indices, _, tokens_antes_agg, tokens_final_agg = aggregated_info
                count_sel_final = len(pages_agg_indices)
                #print('\n[DEBUG]:\n', pages_agg_indices, '\n\n') 

                supressed_tokens = tokens_antes_agg - tokens_final_agg
                perc_supressed = (supressed_tokens / tokens_antes_agg * 100) if tokens_antes_agg > 0 else 0

                total_processing_time = processing_time_1+processing_time_2+processing_time_3

                proc_meta_for_ui = {
                    "total_pages_processed": len(processed_page_data_combined),
                    "relevant_pages_global_keys_formatted": self.pdf_analyzer.format_global_keys_for_display(relevant_indices),
                    "count_selected_relevant": count_sel,
                    "unintelligible_pages_global_keys_formatted": self.pdf_analyzer.format_global_keys_for_display(unintelligible_indices), 
                    "count_discarded_unintelligible": count_unint,
                    "count_discarded_similarity": count_similars,
                    "total_tokens_before_truncation": tokens_antes_agg,
                    "final_pages_global_keys_formatted": self.pdf_analyzer.format_global_keys_for_display(pages_agg_indices),
                    "count_selected_final": count_sel_final,
                    "final_aggregated_tokens": tokens_final_agg,
                    "supressed_tokens_percentage": perc_supressed,
                    "processing_time": format_seconds_to_min_sec(total_processing_time),
                }
                self.page.session.set(KEY_SESSION_PROCESSING_METADATA, proc_meta_for_ui)
                self.page.run_thread(self.parent_view._update_processing_metadata_display, proc_meta_for_ui)

                self.parent_view._files_processed = True
                _logger.info(f"Thread: Processamento de PDF para '{batch_name}' concluído.")

                if time() - point_time < 1: sleep(1) 

                self.page.run_thread(self._update_status_callback, "Aguardando para exibir os resultados...", False, True)

                if analyze_llm_after:
                    self.page.run_thread(self._update_status_callback,  "Etapa 5/5: Requisitando análise da LLM...")
                    self.start_llm_analysis_only(aggregated_info[1], batch_name, from_pipeline=True) # Passa o texto agregado
                    self.page.run_thread(self._update_status_callback, "", False, True)
                else: # Só processou, não vai para LLM agora
                    hide_loading_overlay(self.page)
                    self.page.run_thread(show_snackbar, self.page, f"Conteúdo de '{batch_name}' processado. Pronto para análise LLM.", theme.COLOR_SUCCESS)
            
            except Exception as ex_proc:
                _logger.error(f"Thread: Erro no processamento de PDF para '{batch_name}': {ex_proc}", exc_info=True)
                self.page.run_thread(self._update_status_callback, f"Erro ao processar PDFs: {ex_proc}", True, True)
                self.parent_view._files_processed = False # Falhou
            finally:
                self.gui_controls[CTL_PROC_METADATA_PANEL].visible = True
                self.gui_controls[CTL_PROC_METADATA_PANEL].controls[0].expanded = True
                hide_loading_overlay(self.page)
                self.page.run_thread(self.parent_view._update_button_states)

        def _llm_analysis_thread_func(self, aggregated_text: str, batch_name: str):
            current_analysis_settings = self._get_current_analysis_settings()
            _logger.info(f"Usando configurações de análise para LLM: {current_analysis_settings}")
            provider = current_analysis_settings.get("llm_provider", FALLBACK_ANALYSIS_SETTINGS["llm_provider"])
            model_name = current_analysis_settings.get("llm_model", FALLBACK_ANALYSIS_SETTINGS["llm_model"])
            temperature = current_analysis_settings.get("llm_temperature", FALLBACK_ANALYSIS_SETTINGS["llm_temperature"])
            try:
                _logger.info(f"Thread: Iniciando análise LLM para '{batch_name}'...")
                self.page.run_thread(self._update_status_callback,  "Etapa 5/5: Requisitando análise da LLM...")

                # Simulação de obtenção de chave API da sessão (deve ser carregada/salva via UI de config LLM)
                decrypted_api_key = self.page.session.get(f"decrypted_api_key_{provider}_{provider}") # Exemplo
                if not decrypted_api_key and provider == "openai": # Tenta um fallback se estiver no dev_mode
                     if self.page.data.get("dev_mode", False): # Precisa de uma forma de saber se está em dev_mode
                         decrypted_api_key = self.page.session.get("decrypted_api_key_openai_openai") # Chave mock
                         _logger.warning("Usando chave API OpenAI mockada de dev_mode para análise LLM.")

                if not decrypted_api_key:
                    # Esta lógica agora é feita no ai_orchestrator, que pega da sessão ou do Firestore.
                    # Mas o orchestrator precisa do provider correto.
                    pass # ai_orchestrator tentará carregar

                llm_response_data, token_usage_info, processing_time_llm = analyze_text_with_llm(self.page, 
                                                                                                 "UNIQUE_ANALYSIS_V1", 
                                                                                                 aggregated_text, provider, model_name, temperature)

                if llm_response_data:
                    # llm_response_data PODE ser um objeto FormatAnaliseInicial ou uma string
                    # Se for string e parece JSON, tenta parsear para FormatAnaliseInicial
                    if isinstance(llm_response_data, str):
                        try:
                            json_data_from_llm  = json.loads(llm_response_data)
                            
                            if 'valor_apuracao' in json_data_from_llm:
                                raw_valor = json_data_from_llm['valor_apuracao']
                                json_data_from_llm['valor_apuracao'] = clean_and_convert_to_float(raw_valor)
                                _logger.info(f"Valor apuracao original da LLM: '{raw_valor}', convertido para: {json_data_from_llm['valor_apuracao']}")

                            llm_response_data = FormatAnaliseInicial(**json_data_from_llm )
                            _logger.info("Resposta LLM (string) parseada com sucesso para FormatAnaliseInicial.")
                        except (json.JSONDecodeError, TypeError, Exception) as parse_error: # Exception para Pydantic ValidationError
                            _logger.warning(f"Resposta LLM é string, mas falhou ao parsear/validar como FormatAnaliseInicial: {parse_error}. Usando como texto puro.")
                            # Mantém llm_response_data como string para o fallback
                    elif isinstance(llm_response_data, FormatAnaliseInicial):
                        _logger.info("Resposta LLM já é um objeto FormatAnaliseInicial.")

                    self.page.session.set(KEY_SESSION_PDF_LLM_RESPONSE, llm_response_data)
                    self.page.run_thread(self.parent_view._show_info_balloon_or_result, False, llm_response_data)
                    
                    llm_meta_for_gui = token_usage_info if token_usage_info else {} 
                    llm_meta_for_gui.update({
                        "llm_provider_used": provider.upper(),
                        "llm_model_used": model_name.upper(),
                        "processing_time": format_seconds_to_min_sec(processing_time_llm)
                    }) 
                        
                    self.page.session.set(KEY_SESSION_LLM_METADATA, llm_meta_for_gui)
                    self.page.run_thread(self.parent_view._update_llm_metadata_display, llm_meta_for_gui)
                    self.page.run_thread(show_snackbar, self.page, "Análise LLM concluída!", theme.COLOR_SUCCESS)
                    self.parent_view._analysis_requested = True
                    self.page.run_thread(self._update_status_callback,  "", False, True)
                    self._log_analysis_metrics()
                else:
                    self.page.run_thread(self.parent_view._show_info_balloon_or_result, True) # Mostra balão de novo
                    self.page.run_thread(self._update_status_callback,  "Análise LLM: Falha ao obter resposta da IA.", True, True)

                    self.page.run_thread(show_snackbar, self.page, "Erro na consulta à LLM.", theme.COLOR_ERROR)
                    self.parent_view._analysis_requested = False
            except Exception as ex_llm:
                _logger.error(f"Thread: Erro na análise LLM para '{batch_name}': {ex_llm}", exc_info=True)
                self.page.run_thread(self.parent_view._show_info_balloon_or_result, True)
                self.page.run_thread(self._update_status_callback,  f"Erro na consulta à LLM: {ex_llm}", True, True)
                self.parent_view._analysis_requested = False
            finally:
                self.gui_controls[CTL_LLM_METADATA_PANEL].visible = True
                self.gui_controls[CTL_LLM_METADATA_PANEL].controls[0].expanded = True
                hide_loading_overlay(self.page)
                self.page.run_thread(self.parent_view._update_button_states)

        def start_pdf_processing_only(self, pdf_paths: List[str], batch_name: str):
            #show_loading_overlay(self.page, f"Processando conteúdo de '{batch_name}'...")
            # Limpa metadados anteriores de LLM e o resultado
            self.parent_view._clear_llm_metadata_display()
            self.parent_view._remove_data_session(KEY_SESSION_PDF_LLM_RESPONSE)
            self.parent_view._show_info_balloon_or_result(show_balloon=True)
            
            thread = threading.Thread(target=self._pdf_processing_thread_func, args=(pdf_paths, batch_name, False), daemon=True)
            thread.start()

        def start_llm_analysis_only(self, aggregated_text: str, batch_name: str, from_pipeline:bool = False):
            if not from_pipeline: # Se chamado diretamente (não pelo pipeline do fast_forward)
                ...
            # A thread _llm_analysis_thread_func já lida com hide_loading_overlay no finally
            thread = threading.Thread(target=self._llm_analysis_thread_func, args=(aggregated_text, batch_name), daemon=True)
            thread.start()
        
        def start_full_analysis_pipeline(self, pdf_paths: List[str], batch_name: str):
            # Limpa metadados anteriores de LLM e o resultado
            self.parent_view._clear_llm_metadata_display()
            self.parent_view._remove_data_session(KEY_SESSION_PDF_LLM_RESPONSE)
            self.parent_view._show_info_balloon_or_result(show_balloon=True)

            thread = threading.Thread(target=self._pdf_processing_thread_func, args=(pdf_paths, batch_name, True), daemon=True)
            thread.start()

    class _ExportManager:
        def __init__(self, parent_view: 'AnalyzePDFViewContent'):
            self.parent_view = parent_view
            self.page = parent_view.page
            self.docx_exporter = parent_view.docx_exporter
            self.global_file_picker = parent_view.global_file_picker_instance 

            self.desktop_picker_operation: ExportOperation = ExportOperation.NONE 
            self.desktop_picker_template_path: Optional[str] = None 
            self.current_data_for_export_obj: Optional[FormatAnaliseInicial] = None

        def _get_default_filename_base(self) -> str:
            base = self.page.session.get(KEY_SESSION_CURRENT_BATCH_NAME) or "analise_documento"
            return base.replace("Arquivos selecionados: ", "").replace("Arquivo selecionado: ", "").split(" e Outros")[0].replace(".pdf", "")

        def _handle_desktop_save_result(self, event: ft.FilePickerResultEvent):
            _logger.info(f"EXPORT_MANAGER (Desktop): _handle_desktop_save_result. Operação: {self.current_operation}, Path: {event.path}")
            
            if not self.current_data_for_export_obj:
                _logger.error("EXPORT_MANAGER (Desktop): current_data_for_export_obj é None. Abortando.")
                show_snackbar(self.page, "Erro interno: Dados para exportação não disponíveis no callback.", theme.COLOR_ERROR)
                return

            output_path = event.path # Vem do diálogo "Salvar Como"
            
            # Resetar estado antes de processar, independentemente do resultado
            operation_that_finished = self.desktop_picker_operation
            template_path_that_finished = self.desktop_picker_template_path
            data_that_was_exported = self.current_data_for_export_obj 
            
            # Resetar estado do picker desktop
            self.desktop_picker_operation = ExportOperation.NONE
            self.desktop_picker_template_path = None
            self.current_data_for_export_obj = None # Limpa após uso

            if not output_path: # Usuário cancelou o diálogo "Salvar Como"
                _logger.info("EXPORT_MANAGER (Desktop): Operação de salvamento cancelada pelo usuário.")
                show_snackbar(self.page, "Operação de salvamento cancelada.", theme.COLOR_INFO)
                return

            output_path_final = output_path if output_path.lower().endswith(".docx") else output_path + ".docx"
            show_loading_overlay(self.page, f"Exportando para {os.path.basename(output_path_final)}...")

            success = False
            missing_keys_report: List[str] = []

            if operation_that_finished == ExportOperation.SIMPLE_DOCX:
                success = self.docx_exporter.export_simple_docx(data_that_was_exported, output_path_final)
            elif operation_that_finished == ExportOperation.TEMPLATE_DOCX and template_path_that_finished:
                success, missing_keys_report = self.docx_exporter.export_from_template_docx(
                    data_that_was_exported, template_path_that_finished, output_path_final
                )
            
            hide_loading_overlay(self.page)
            if success:
                show_snackbar(self.page, f"Arquivo salvo em: {output_path_final}", theme.COLOR_SUCCESS)
                if missing_keys_report: # Lógica de aviso de chaves ausentes
                    template_name_friendly = os.path.basename(template_path_that_finished or "").replace(".docx","").replace("_", " ").title()
                    missing_keys_str = ", ".join(missing_keys_report)
                    show_confirmation_dialog(
                        self.page, title="Aviso de Exportação",
                        content=ft.Column([
                            ft.Text(f"Os seguintes campos possuem valores, mas não foram encontrados como placeholders no template '{template_name_friendly}':"),
                            ft.Text(missing_keys_str, weight=ft.FontWeight.BOLD, selectable=True)
                        ], tight=True),
                        confirm_text="OK", cancel_text=None)
            else:
                show_snackbar(self.page, f"Falha ao exportar arquivo DOCX.", theme.COLOR_ERROR)

        def start_export(self, operation_type: ExportOperation, data_to_export: FormatAnaliseInicial, template_path: Optional[str] = None):
            _logger.info(f"EXPORT_MANAGER: start_export chamado. Operação: {operation_type}, Web: {self.page.web}")

            # data_to_export já deve ser o objeto validado.
            # Se self.current_data_for_export_obj foi definido pelo chamador (para o timer desktop), use-o.
            # Caso contrário (chamada direta para web), use o argumento data_to_export.
            actual_data_to_export = self.current_data_for_export_obj if self.current_data_for_export_obj and not self.page.web else data_to_export
            
            if not actual_data_to_export: # Checagem de segurança
                _logger.error("EXPORT_MANAGER: Nenhum dado válido para exportar fornecido.")
                show_snackbar(self.page, "Erro interno: Dados para exportação ausentes.", theme.COLOR_ERROR)
                return
            
            default_filename_base = self._get_default_filename_base()

            if self.page.web:
                # --- LÓGICA PARA MODO WEB ---
                _logger.info("EXPORT_MANAGER (Web): Executando lógica de download via servidor.")
                # ... (lógica web como implementada anteriormente, sem o timer) ...
                show_loading_overlay(self.page, "Preparando arquivo para download...")
                temp_server_filename = ""
                export_success_on_server = False
                missing_keys_on_server: List[str] = []
                server_save_path = ""

                if operation_type == ExportOperation.SIMPLE_DOCX:
                    temp_server_filename = f"{default_filename_base}_simples_{int(time())}.docx"
                    server_save_path = os.path.join(UPLOAD_TEMP_DIR, temp_server_filename) # UPLOAD_TEMP_DIR é o assets_dir
                    export_success_on_server = self.docx_exporter.export_simple_docx(actual_data_to_export, server_save_path)
                elif operation_type == ExportOperation.TEMPLATE_DOCX and template_path:
                    template_name_friendly_for_filename = os.path.basename(template_path).replace(".docx","").replace(" ", "_").lower()
                    temp_server_filename = f"{default_filename_base}_{template_name_friendly_for_filename}_{int(time())}.docx"
                    server_save_path = os.path.join(UPLOAD_TEMP_DIR, temp_server_filename) # UPLOAD_TEMP_DIR é o assets_dir
                    export_success_on_server, missing_keys_on_server = self.docx_exporter.export_from_template_docx(
                        actual_data_to_export, template_path, server_save_path)
                else:
                    _logger.error(f"EXPORT_MANAGER (Web): Tipo de operação desconhecido ou template_path ausente: {operation_type}")
                    hide_loading_overlay(self.page)
                    show_snackbar(self.page, "Erro: Tipo de exportação inválido.", theme.COLOR_ERROR)
                    self.current_data_for_export_obj = None # Limpa
                    return
                
                hide_loading_overlay(self.page)
                if export_success_on_server and temp_server_filename:
                    #upload_dir_folder_name = Path(UPLOAD_TEMP_DIR).name
                    #download_url = f"/{upload_dir_folder_name}/{temp_server_filename}"
                    # Se UPLOAD_TEMP_DIR está em assets_dir:
                    download_url = f"/{temp_server_filename}" # URL direta ao arquivo
                    _logger.info(f"EXPORT_MANAGER (Web): Arquivo gerado em '{server_save_path}'. URL para download: {download_url}")
                    self.page.launch_url(download_url, web_window_name="_self") # ou _blank
                    show_snackbar(self.page, f"Download de '{temp_server_filename}' iniciado.", theme.COLOR_SUCCESS)
                    if missing_keys_on_server and operation_type == ExportOperation.TEMPLATE_DOCX:
                        template_name_friendly = os.path.basename(template_path or "").replace(".docx","").replace("_", " ").title()
                        missing_keys_str = "\n".join(missing_keys_on_server)
                        threading.Timer(1.0, lambda: show_confirmation_dialog(
                            self.page, title="Aviso de Exportação",
                            content=ft.Column([
                                ft.Text(f"Os seguintes campos possuem valores, mas não foram encontrados como placeholders no template '{template_name_friendly}':"),
                                ft.Text(missing_keys_str, weight=ft.FontWeight.BOLD, selectable=True)], tight=True),
                            confirm_text="OK", cancel_text=None )).start()
                else:
                    _logger.error(f"EXPORT_MANAGER (Web): Falha ao gerar arquivo DOCX no servidor. Arquivo: {server_save_path}")
                    show_snackbar(self.page, "Falha ao gerar arquivo para download.", theme.COLOR_ERROR)
                self.current_data_for_export_obj = None # Limpa após uso

            else:
                # --- LÓGICA PARA MODO DESKTOP ---
                if not self.global_file_picker:
                    show_snackbar(self.page, "FilePicker não está disponível (Desktop).", theme.COLOR_ERROR)
                    _logger.error("EXPORT_MANAGER (Desktop): global_file_picker é None.")
                    self.current_data_for_export_obj = None # Limpa
                    return

                _logger.info("EXPORT_MANAGER (Desktop): Iniciando save_file().")
                self.desktop_picker_operation = operation_type
                self.desktop_picker_template_path = template_path
                
                self.global_file_picker.on_result = self._handle_desktop_save_result
                _logger.debug("EXPORT_MANAGER (Desktop): on_result do global_file_picker DEFINIDO para _handle_desktop_save_result.")

                dialog_title_str = "Salvar Relatório Como..."
                file_name_str = f"{default_filename_base}.docx"

                if operation_type == ExportOperation.SIMPLE_DOCX:
                    dialog_title_str = "Salvar DOCX Simples Como..."
                    file_name_str = f"{default_filename_base}_simples.docx"
                elif operation_type == ExportOperation.TEMPLATE_DOCX and template_path:
                    template_name_friendly_for_filename = os.path.basename(template_path).replace(".docx","").replace(" ", "_").lower()
                    dialog_title_str = "Salvar Cópia de Template Como..."
                    file_name_str = f"{default_filename_base}_{template_name_friendly_for_filename}.docx"
                
                try:
                    # A chamada page.update() ANTES de save_file é crucial aqui para DESKTOP.
                    self.page.update()
                    _logger.info("EXPORT_MANAGER (Desktop): page.update() chamado ANTES de save_file().")
                    
                    self.global_file_picker.save_file(
                        dialog_title=dialog_title_str,
                        file_name=file_name_str,
                        allowed_extensions=["docx"],
                        file_type=ft.FilePickerFileType.ANY 
                    )
                    _logger.info(f"EXPORT_MANAGER (Desktop): Chamada a save_file() com nome: {file_name_str} concluída.")
                except Exception as e_save_file_desktop:
                    _logger.error(f"EXPORT_MANAGER (Desktop): Exceção ao chamar save_file(): {e_save_file_desktop}", exc_info=True)
                    show_snackbar(self.page, f"Erro ao tentar abrir diálogo de salvar: {e_save_file_desktop}", theme.COLOR_ERROR)
                    self.desktop_picker_operation = ExportOperation.NONE # Reseta estado em erro
                    self.desktop_picker_template_path = None
                    self.current_data_for_export_obj = None

class LLMStructuredResultDisplay(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__(
            scroll=ft.ScrollMode.ADAPTIVE, 
            expand=True, 
            spacing=12,
            #horizontal_alignment=ft.CrossAxisAlignment.CENTER # Centraliza os cards
        )
        self.page = page
        self.data: Optional[FormatAnaliseInicial] = None
        self.gui_fields: Dict[str, ft.Control] = {}

        # Referências para controles que precisam ser atualizados dinamicamente (ex: municípios)
        self.dropdown_uf_origem: Optional[ft.Dropdown] = None
        self.dropdown_municipio_origem: Optional[ft.Dropdown] = None
        self.dropdown_uf_fato: Optional[ft.Dropdown] = None
        self.dropdown_municipio_fato: Optional[ft.Dropdown] = None

        # Listas de referência (carregadas uma vez)
        self.ufs_list = LISTA_UFS  # TODO: incluir atualização a partir do firestore

    def _create_justificativa_icon(self, justificativa: Optional[str]) -> ft.IconButton:
        return ft.IconButton(
            icon=ft.icons.INFO_OUTLINE_ROUNDED,
            tooltip=justificativa if justificativa else "Justificativa não fornecida.",
            icon_size=18,
            opacity=0.7 if justificativa else 0.3,
            disabled=not bool(justificativa),
            padding=ft.padding.only(left=1, right=1),
        )

    def _atualizar_municipios_origem(self, e=None):
        if self.dropdown_uf_origem and self.dropdown_municipio_origem:
            selected_uf = self.dropdown_uf_origem.value
            if selected_uf:
                municipios = MUNICIPIOS_POR_UF[selected_uf]
                self.dropdown_municipio_origem.options = [ft.dropdown.Option(m) for m in municipios]
                # Tenta manter o valor se ainda for válido, ou reseta
                current_municipio_val = self.dropdown_municipio_origem.value
                if current_municipio_val not in [opt.key for opt in self.dropdown_municipio_origem.options]:
                    self.dropdown_municipio_origem.value = None
            else:
                self.dropdown_municipio_origem.options = []
                self.dropdown_municipio_origem.value = None

            if e is not None and self.page and self.dropdown_municipio_origem.uid: # 'e' indica chamada por evento de usuário
                self.dropdown_municipio_origem.update()

    def _atualizar_municipios_fato(self, e=None):
        if self.dropdown_uf_fato and self.dropdown_municipio_fato:
            selected_uf = self.dropdown_uf_fato.value
            if selected_uf:
                municipios = MUNICIPIOS_POR_UF[selected_uf]
                self.dropdown_municipio_fato.options = [ft.dropdown.Option(m) for m in municipios]
                current_municipio_val = self.dropdown_municipio_fato.value
                if current_municipio_val not in [opt.key for opt in self.dropdown_municipio_fato.options]:
                    self.dropdown_municipio_fato.value = None
            else:
                self.dropdown_municipio_fato.options = []
                self.dropdown_municipio_fato.value = None
            
            if e is not None and self.page and self.dropdown_municipio_fato.uid: # 'e' indica chamada por evento de usuário
                self.dropdown_municipio_fato.update()

    def update_data(self, data: FormatAnaliseInicial):
        self.data = data # Armazena os dados originais/base
        self.controls.clear()
        self.gui_fields.clear() # Limpa referências de campos antigos

        if not self.data:
            self.controls.append(ft.Text("Nenhum dado de análise estruturada para exibir."))
            if self.page and self.uid:
                self.update()
            return

        # Normaliza UFs nos dados recebidos antes de popular a UI
        # Isso garante que os valores iniciais dos dropdowns de UF sejam válidos.
        self.data.uf_origem = get_sigla_uf(self.data.uf_origem)
        self.data.uf_fato = get_sigla_uf(self.data.uf_fato)

        # --- Seção 1: Identificação do Documento ---
        self.gui_fields["descricao_geral"] = ft.TextField(label="Descrição Geral", value=self.data.descricao_geral, multiline=True, min_lines=2, dense=True, width=1600)
        self.gui_fields["tipo_documento_origem"] = ft.Dropdown(label="Tipo Documento Origem", 
                                                               options=[ft.dropdown.Option(td) for td in tipos_doc], 
                                                               value=self.data.tipo_documento_origem if self.data.tipo_documento_origem in tipos_doc else None, 
                                                               width=400, dense=True)
        self.gui_fields["orgao_origem"] = ft.Dropdown(label="Órgão de Origem", 
                                                      options=[ft.dropdown.Option(oo) for oo in origens_doc], 
                                                      value=self.data.orgao_origem if self.data.orgao_origem in origens_doc else None, 
                                                      width=530, dense=True) # Removido expand=True

        self.dropdown_uf_origem = ft.Dropdown(
            label="UF de Origem", options=[ft.dropdown.Option(uf) for uf in self.ufs_list],
            value=self.data.uf_origem if self.data.uf_origem in self.ufs_list else None,
            on_change=self._atualizar_municipios_origem, width=170, dense=True
        )
        self.gui_fields["uf_origem"] = self.dropdown_uf_origem # Adiciona ao ui_fields

        municipios_origem_init = MUNICIPIOS_POR_UF.get(self.data.uf_origem, []) if self.data.uf_origem else []
        self.dropdown_municipio_origem = ft.Dropdown(
            label="Município de Origem",
            options=[ft.dropdown.Option(m) for m in municipios_origem_init],
            value=obter_string_normalizada(self.data.municipio_origem, municipios_origem_init),
            dense=True, width=320, # Removido expand=True
        )
        self.gui_fields["municipio_origem"] = self.dropdown_municipio_origem
        
        self._atualizar_municipios_origem() # Popula municípios com base na UF inicial

        id_doc_card_content = ft.Column([
            self.gui_fields["descricao_geral"],
            ft.Row([
                self.gui_fields["tipo_documento_origem"],
                self._create_justificativa_icon(self.data.justificativa_tipo_documento_origem),
                self.gui_fields["orgao_origem"],
                self._create_justificativa_icon(self.data.justificativa_orgao_origem),
                self.dropdown_uf_origem, # Já está em ui_fields
                self.dropdown_municipio_origem, # Já está em ui_fields
                self._create_justificativa_icon(self.data.justificativa_municipio_uf_origem)
            ], spacing=10), # Ajuste o spacing conforme necessário
        ], spacing=12)
        
        id_doc_card = CardWithHeader(title="Identificação do Documento", content=id_doc_card_content, header_bgcolor=ft.Colors.GREY_300)
        self.controls.append(id_doc_card)


        # --- Seção 2: Detalhes do Fato ---
        self.gui_fields["resumo_fato"] = ft.TextField(label="Resumo do Fato", value=self.data.resumo_fato, multiline=True, min_lines=3, dense=True, width=1600)
        
        self.dropdown_uf_fato = ft.Dropdown(
            label="UF do Fato", options=[ft.dropdown.Option(uf) for uf in self.ufs_list],
            value=self.data.uf_fato if self.data.uf_fato in self.ufs_list else None,
            on_change=self._atualizar_municipios_fato, width=170, dense=True
        )
        self.gui_fields["uf_fato"] = self.dropdown_uf_fato

        municipios_fato_init = MUNICIPIOS_POR_UF.get(self.data.uf_fato, []) if self.data.uf_fato else []
        self.dropdown_municipio_fato = ft.Dropdown(
            label="Município do Fato",
            options=[ft.dropdown.Option(m) for m in municipios_fato_init],
            value=obter_string_normalizada(self.data.municipio_fato, municipios_fato_init),
            dense=True, width=320, # Removido expand=True
        )
        self.gui_fields["municipio_fato"] = self.dropdown_municipio_fato
        self._atualizar_municipios_fato()

        self.gui_fields["tipo_local"] = ft.Dropdown(label="Tipo de Local", 
                                                    options=[ft.dropdown.Option(tl) for tl in tipos_locais], 
                                                    value=self.data.tipo_local if self.data.tipo_local in tipos_locais else None, 
                                                    width=480, dense=True) # expand=True
        
        valor_apuracao_str = f"{self.data.valor_apuracao:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if isinstance(self.data.valor_apuracao, float) else str(self.data.valor_apuracao)
        self.gui_fields["valor_apuracao"] = ft.TextField(label="Valor da Apuração (R$)", value=valor_apuracao_str, keyboard_type=ft.KeyboardType.NUMBER, width=480, prefix_text="R$ ", dense=True)
        
        self.gui_fields["pessoas_envolvidas"] = ft.TextField(label="Pessoas Envolvidas (Nome - CPF/CNPJ - Tipo)", value="\n".join(self.data.pessoas_envolvidas) if self.data.pessoas_envolvidas else "", multiline=True, min_lines=2, hint_text="Uma pessoa por linha: Nome - CPF/CNPJ - Tipo (conforme lista de referência)", dense=True, width=1600)
        self.gui_fields["linha_do_tempo"] = ft.TextField(label="Linha do Tempo (Evento - Data)", value="\n".join(self.data.linha_do_tempo) if self.data.linha_do_tempo else "", multiline=True, min_lines=2, hint_text="Um evento por linha: Descrição do Evento - DD/MM/AAAA", dense=True, width=1600)

        det_fato_card_content = ft.Column([
            self.gui_fields["resumo_fato"],
            ft.Row([
                self.dropdown_uf_fato,
                self.dropdown_municipio_fato,
                self._create_justificativa_icon(self.data.justificativa_municipio_uf_fato),
                self.gui_fields["tipo_local"],
                self._create_justificativa_icon(self.data.justificativa_tipo_local),
                self.gui_fields["valor_apuracao"],
                self._create_justificativa_icon(self.data.justificativa_valor_apuracao)
            ], spacing=10), # Ajuste o spacing
            self.gui_fields["pessoas_envolvidas"],
            self.gui_fields["linha_do_tempo"],
        ], spacing=12)
        det_fato_card = CardWithHeader(title="Detalhes do Fato", content=det_fato_card_content, header_bgcolor=ft.Colors.GREY_300)
        self.controls.append(det_fato_card)

        # --- Seção 3: Classificação e Encaminhamento ---
        self.gui_fields["area_atribuicao"] = ft.Dropdown(label="Área de Atribuição", options=[ft.dropdown.Option(aa) for aa in areas_de_atribuição], 
                                                         value=self.data.area_atribuicao if self.data.area_atribuicao in areas_de_atribuição else None, 
                                                         width=660, dense=True)
        self.gui_fields["tipificacao_penal"] = ft.TextField(label="Tipificação Penal", value=self.data.tipificacao_penal, width=840, dense=True)
        self.gui_fields["destinacao"] = ft.Dropdown(label="Destinação", options=[ft.dropdown.Option(d) for d in destinacoes_completas], 
                                                    value=self.data.destinacao if self.data.destinacao in destinacoes_completas else None, 
                                                    width=250, dense=True)
        self.gui_fields["tipo_a_autuar"] = ft.Dropdown(label="Tipo a Autuar", options=[ft.dropdown.Option(ta) for ta in tipo_a_autuar], 
                                                       value=self.data.tipo_a_autuar if self.data.tipo_a_autuar in tipo_a_autuar else None, 
                                                       width=350, dense=True)
        self.gui_fields["assunto_re"] = ft.Dropdown(label="Assunto (RE)", options=[ft.dropdown.Option(ar) for ar in assuntos_re], 
                                                    value=self.data.assunto_re if self.data.assunto_re in assuntos_re else None, 
                                                    width=840, dense=True)

        class_enc_card_content = ft.Column([
            ft.Row([
                self.gui_fields["area_atribuicao"],
                self._create_justificativa_icon(self.data.justificativa_area_atribuicao),
                self.gui_fields["tipificacao_penal"],
                self._create_justificativa_icon(self.data.justificativa_tipificacao_penal)
            ], spacing=10), # Ajuste
            ft.Row([
                self.gui_fields["destinacao"],
                self._create_justificativa_icon(self.data.justificativa_destinacao),
                self.gui_fields["tipo_a_autuar"],
                self._create_justificativa_icon(self.data.justificativa_tipo_a_autuar),
                self.gui_fields["assunto_re"],
                self._create_justificativa_icon(self.data.justificativa_assunto_re)
            ], spacing=10), # Ajuste
        ], spacing=12)
        class_enc_card = CardWithHeader(title="Classificação e Encaminhamento", content=class_enc_card_content, header_bgcolor=ft.Colors.GREY_300)
        self.controls.append(class_enc_card)

        # --- Seção 4: Observações ---
        self.gui_fields["observacoes"] = ft.TextField(label="Observações", value=self.data.observacoes, multiline=True, min_lines=2, dense=True, width=1600)
        obs_card_content = ft.Column([self.gui_fields["observacoes"]], spacing=10)
        obs_card = CardWithHeader(title="Observações Adicionais", content=obs_card_content, header_bgcolor=ft.Colors.GREY_300)
        self.controls.append(obs_card)

        if self.page and self.uid:
            self.update()

    def get_current_form_data(self, validate_for_export: bool = False) -> Union[Optional[FormatAnaliseInicial], List[str]]:
        """
        Coleta os dados atuais dos campos da UI, atualiza self.data.
        Se validate_for_export for True, valida campos obrigatórios para exportação.

        Returns:
            - FormatAnaliseInicial: se os dados são válidos (ou validação não solicitada).
            - List[str]: Lista de nomes de campos inválidos/vazios se validate_for_export é True e há erros.
            - None: Se self.data base não estiver definido.
        """
        if not self.data: # Se não há dados base (ex: LLM não retornou nada)
            _logger.warning("get_current_form_data: self.data não está definido. Não é possível coletar dados da UI.")
            return None

        # Passo 1: Coletar valores dos campos da UI (self.ui_fields)
        collected_values_from_ui = {}
        invalid_fields_for_export: List[Tuple[str, ft.Control]] = [] # (field_name, control_instance)

        # Define aqui os campos que são OBRIGATÓRIOS para a exportação; Estes devem corresponder às chaves em self.ui_fields
        required_fields_for_export = [
            "tipo_documento_origem", "orgao_origem", "uf_origem", "municipio_origem",
            "resumo_fato", # Mesmo sendo multiline, pode ser obrigatório
            "tipo_local", "uf_fato", "municipio_fato",
            # "valor_apuracao", # Pode ser opcional ou zero
            "area_atribuicao",
            "tipo_a_autuar", "destinacao",
            # "descricao_geral" 
            # "tipificacao_penal" e "assunto_re" são Optional[str] no FormatAnaliseInicial
            # "pessoas_envolvidas", "linha_do_tempo", "observacoes" são Optional[List[str]]
        ]
        _logger.debug(f"Campos definidos como obrigatórios para exportação: {required_fields_for_export}")

        for field_name, control in self.gui_fields.items():
            value = None
            is_dropdown = isinstance(control, ft.Dropdown)
            if isinstance(control, (ft.TextField, ft.Dropdown)):
                value = control.value
                _logger.debug(f"Coletando para '{field_name}': '{value}' (Tipo: {type(value)}, É Dropdown: {is_dropdown})")
            
            # Validação para exportação
            if validate_for_export and field_name in required_fields_for_export:
                is_empty = False
                if value is None: # Principal condição para Dropdowns não selecionados ou TextFields vazios que retornam None
                    is_empty = True
                elif isinstance(value, str) and not value.strip(): # Para TextFields que podem ter string vazia
                    is_empty = True
                # Para TextFields multiline que representam listas (como pessoas_envolvidas)
                elif field_name in ["pessoas_envolvidas", "linha_do_tempo"] and isinstance(value, str):
                    processed_list_val = [line.strip() for line in value.split('\n') if line.strip()]
                    if not processed_list_val:
                        is_empty = True
                
                if is_empty:
                    _logger.warning(f"Campo obrigatório '{field_name}' está vazio. Valor atual: '{value}'")
                    invalid_fields_for_export.append((field_name, control))


            # Tratamentos específicos de tipo (continua como antes)
            if field_name == "valor_apuracao":
                value = clean_and_convert_to_float(value)
            elif field_name in ["pessoas_envolvidas", "linha_do_tempo"] and isinstance(value, str):
                value = [line.strip() for line in value.split('\n') if line.strip()] if value else []
            
            collected_values_from_ui[field_name] = value

        if validate_for_export and invalid_fields_for_export:
            _logger.warning(f"Validação para exportação falhou. Campos vazios: {[f[0] for f in invalid_fields_for_export]}")
            # Retorna a lista de tuplas (nome_do_campo, instancia_do_controle)
            return invalid_fields_for_export 

        # Se passou na validação (ou não foi solicitada), prossiga para criar o objeto
        final_data_for_pydantic = {}
        if self.data:
            final_data_for_pydantic = self.data.model_dump()
        final_data_for_pydantic.update(collected_values_from_ui)

        for pydantic_field_name in FormatAnaliseInicial.model_fields.keys():
            if pydantic_field_name not in final_data_for_pydantic:
                if hasattr(self.data, pydantic_field_name):
                    final_data_for_pydantic[pydantic_field_name] = getattr(self.data, pydantic_field_name)
        
        try:
            _logger.debug(f"Dados para instanciar FormatAnaliseInicial: {final_data_for_pydantic}")
            current_ui_data = FormatAnaliseInicial(**final_data_for_pydantic)
            self.data = current_ui_data 
            _logger.info("Dados do formulário estruturado coletados, validados por Pydantic, e self.data atualizado.")
            self.page.session.set(KEY_SESSION_PDF_LLM_RESPONSE, self.data)
            return self.data
        except Exception as pydantic_error: # Use ValidationError de Pydantic se importado
            _logger.error(f"Erro de validação Pydantic FINAL ao criar FormatAnaliseInicial: {pydantic_error}", exc_info=False)
            # ... (logar erros pydantic detalhados)
            if hasattr(pydantic_error, 'errors'): # Se for ValidationError do Pydantic
                 for error in pydantic_error.errors():
                    _logger.error(f"  - Pydantic Detail: Campo: {'.'.join(map(str, error['loc'])) if error.get('loc') else 'N/A'}, Erro: {error['msg']}")

            if validate_for_export:
                return [("pydantic_validation_error_final", None)] 
            return None
    

# Função principal da view (chamada pelo router)
def create_analyze_pdf_content(page: ft.Page) -> ft.Control:
    _logger.info("View Análise de PDF: Iniciando criação (nova estrutura).")
    # Esta view agora é um ft.Column que contém todos os elementos.
    # O router irá inseri-la no layout principal da página.
    return AnalyzePDFViewContent(page)

