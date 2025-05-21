# src/flet_ui/views/analyze_pdf_view.py
import flet as ft
import threading
from typing import Optional, Dict, Any, List, Tuple
from time import sleep
#from rich import print

from src.utils import format_seconds_to_min_sec

from src.flet_ui.components import (
    show_snackbar, show_loading_overlay, hide_loading_overlay,
    ManagedFilePicker, wrapper_panel_1, CompactKeyValueTable 
)
from src.flet_ui import theme
from src.core.pdf_processor import PDFDocumentAnalyzer
from src.core.ai_orchestrator import analyze_text_with_llm
from src.settings import UPLOAD_TEMP_DIR, cotacao_dolar_to_real

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
CTL_FILE_LIST_PANEL = "file_list_panel"
CTL_FILE_LIST_PANEL_TITLE = "file_list_panel_title"
CTL_FILE_LIST_VIEW = "file_list_view"
CTL_PROC_METADATA_PANEL = "proc_metadata_panel"
CTL_PROC_METADATA_PANEL_TITLE = "proc_metadata_panel_title"
CTL_PROC_METADATA_CONTENT = "proc_metadata_content"
CTL_LLM_RESULT_TEXT = "llm_result_text"
CTL_LLM_RESULT_INFO_TITLE = "llm_result_info_title"
CTL_LLM_STAUS_INFO = "llm_status_info"
CTL_LLM_RESULT_INFO_BALLOON = "llm_result_info_balloon"
CTL_LLM_METADATA_PANEL = "llm_metadata_panel"
CTL_LLM_METADATA_PANEL_TITLE = "llm_metadata_panel_title"
CTL_LLM_METADATA_CONTENT = "llm_metadata_content"
CTL_SETTINGS_DRAWER = "settings_drawer"


class AnalyzePDFViewContent(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__(expand=True, spacing=10) # A Column principal expande
        self.page = page
        self.gui_controls: Dict[str, ft.Control] = {}
        self.file_list_manager = None # Será instanciado FileListManager (adaptado)
        self.analysis_controller = None # Será instanciado AnalysisController (adaptado)
        self.managed_file_picker: Optional[ManagedFilePicker] = None

        # Instâncias do PDF Analyzer e outros serviços, se necessário manter estado
        self.pdf_analyzer = PDFDocumentAnalyzer()

        # Estado interno da View
        self._is_drawer_open = False
        self._files_processed = False # Indica se o conteúdo dos PDFs foi processado
        self._analysis_requested = False # Indica se a análise LLM foi solicitada/concluída

        self._build_gui_structure()
        self._initialize_file_picker() # Deve ser chamado após _build_ui_structure
        self._setup_event_handlers()
        self._restore_state_from_session()
        self._update_button_states() # Estado inicial dos botões

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
            items=[
                ft.PopupMenuItem(text="Exportar para DOCX (Simples)", data="docx_simple"),
                ft.PopupMenuItem(text="Exportar com Template (Breve)", data="docx_template", disabled=True), # habilitado após análise LLM
            ]
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
            #border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT), # Para debug
            #padding=5,
            expand=True # Permite que a ListView use o espaço disponível no ExpansionPanel
        )
        self.gui_controls[CTL_FILE_LIST_PANEL] = ft.ExpansionPanel(
            header=ft.Column([ft.Row([ft.Container(width=12), self.gui_controls[CTL_FILE_LIST_PANEL_TITLE]])], expand=True, alignment=ft.MainAxisAlignment.CENTER),
            content=file_list_panel_content,
            can_tap_header=True, # Permite expandir/recolher clicando no header
            expanded=True # Começa expandido
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
        self.gui_controls[CTL_LLM_RESULT_INFO_TITLE] = ft.Text("Resultado da Análise LLM:", 
                                                               style=ft.TextThemeStyle.TITLE_MEDIUM, 
                                                               weight=ft.FontWeight.BOLD, visible=False)
        self.gui_controls[CTL_LLM_STAUS_INFO] = ft.Text("Aguardando para exibir os resultados...", italic=True, size=14, expand=True)
        self.gui_controls[CTL_LLM_RESULT_INFO_BALLOON] = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, color=theme.COLOR_INFO, size=30),
                    self.gui_controls[CTL_LLM_STAUS_INFO]
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            ),
            padding=20,
            border_radius=8,
            bgcolor=ft.Colors.with_opacity(0.05, theme.COLOR_INFO),
            visible=True
        )
        self.gui_controls[CTL_LLM_RESULT_TEXT] = ft.TextField(
            multiline=True, read_only=True, min_lines=15, max_lines=30,
            expand=True, border_color=theme.PRIMARY, text_size=14,
            visible=False # Começa invisível até ter resultado
        )
        llm_result_container = ft.Container(
            content=ft.Stack( # Usar Stack para sobrepor o balão e o resultado
                [
                    self.gui_controls[CTL_LLM_RESULT_INFO_BALLOON],
                    self.gui_controls[CTL_LLM_RESULT_TEXT],
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
                    llm_result_container], expand=True, spacing=6,
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
                ft.Container(main_content_column, expand=True, padding=ft.padding.only(right=5)), # Conteúdo principal expande
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
        # TODO: itens a popular de estado, config ou firestore
        # Seção Processamento
        proc_extractor_dd = ft.Dropdown(label="Extrator de Texto PDF", options=[
            ft.dropdown.Option("PyMuPdf_fitz", "PyMuPdf-fitz"),
            ft.dropdown.Option("PdfPlumber", "PdfPlumber"),
            ft.dropdown.Option("PyPdf2", "PyPdf2"),
        ], value="PyMuPdf_fitz", width=default_width) 
        proc_embeddings_dd = ft.Dropdown(label="Modelo de Embeddings", options=[
            ft.dropdown.Option("all-MiniLM-L6-v2", "all-MiniLM-L6-v2"),
            ft.dropdown.Option("text-embedding-ada-002", "OpenAI text-embedding-ada-002"), # Exemplo
        ], value="all-MiniLM-L6-v2", width=default_width)
        lang_detector_dd = ft.Dropdown(label="Detector de Idioma", options=[
            ft.dropdown.Option("langdetect", "langdetect"),
        ], value="langdetect", width=default_width)
        token_counter_dd = ft.Dropdown(label="Contador de Tokens", options=[
            ft.dropdown.Option("tiktoken", "tiktoken"),
        ], value="tiktoken", width=default_width)
        tfidf_analyzer_dd = ft.Dropdown(label="Analisador TF-IDF", options=[
            ft.dropdown.Option("sklearn", "sklearn"),
        ], value="sklearn", width=default_width)

        # Seção LLM
        llm_provider_dd = ft.Dropdown(label="Provedor LLM", options=[
            ft.dropdown.Option("openai", "OpenAI"),
            #ft.dropdown.Option("azure_openai", "Azure OpenAI"), # Exemplo
        ], value="openai", width=default_width) 
        llm_model_dd = ft.Dropdown(label="Modelo LLM", options=[
            ft.dropdown.Option("gpt-4.1-nano", "GPT-4.1 Nano"), # Exemplo
            ft.dropdown.Option("gpt-4.1-mini", "GPT-4.1 Mini"),
            ft.dropdown.Option("o4-mini", "OpenAI o4-mini"),
            ft.dropdown.Option("gpt-4.1", "GPT-4.1"),
        ], value="gpt-4.1-nano", width=default_width)
        llm_token_limit_field = ft.TextField(label="Limite Tokens Inputo)", value="180000", 
                                             input_filter=ft.InputFilter(r"[0-9]"), width=default_width)
        llm_format_output_dd = ft.Dropdown(label="Formato de Saída", options=[
            ft.dropdown.Option("texto", "Texto"), ft.dropdown.Option("json", "Json") ], value="texto", width=default_width)
        
        def slider_changed(e):
            temperature_value.value = f"{(int(e.control.value)/10):.1f}"
            temperature_value.update()
        temperature_slider = ft.Slider(label="{value}", min=0.0, max=20.0, value=2.0, divisions=20, on_change=slider_changed, expand=True) # label="{value}"
        temperature_value = ft.Text("0.2", weight=ft.FontWeight.BOLD)

        output_length_field = ft.TextField(label="Comprimento max. Saída", value="100000", 
                                           input_filter=ft.InputFilter(r"[0-9]"), width=default_width)

        # Seção Prompt
        prompt_structure_rg = ft.RadioGroup(content=ft.Column([
            ft.Radio(value="single_context", label="Prompt Único (Todo Contexto)"),
            ft.Radio(value="sequential_chunks", label="Prompts Agrupados (Sequencial)", disabled=True),
            ft.Radio(value="rag_multiple", label="Múltiplos Prompts com RAG", disabled=True),
        ]), value="single_context")

        return ft.Column(
            [
                ft.Row([ft.Text("Configurações específicas", style=ft.TextThemeStyle.TITLE_LARGE), 
                        ft.IconButton(icon=ft.Icons.CLOSE_ROUNDED, on_click=self._handle_toggle_settings_drawer, tooltip="Fechar Configurações")],
                       alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Divider(),

                ft.Text("Processamento de Documento", style=ft.TextThemeStyle.TITLE_MEDIUM),
                proc_extractor_dd, proc_embeddings_dd, lang_detector_dd, token_counter_dd, tfidf_analyzer_dd,
                ft.Divider(),

                ft.Text("Modelo de Linguagem (LLM)", style=ft.TextThemeStyle.TITLE_MEDIUM),
                llm_provider_dd, llm_model_dd, llm_token_limit_field,

                ft.Column([
                    ft.Text("Temperatura de resposta", style=ft.TextThemeStyle.LABEL_MEDIUM),
                    ft.Row([temperature_slider, temperature_value], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)], 
                    width=default_width, spacing=1), 
                llm_format_output_dd,
                output_length_field,

                ft.Dropdown(label="Configurações Avançadas", options=[ft.dropdown.Option("indisponivel", "Indisponível")], 
                            value="indisponivel", disabled=True, width=default_width),
                ft.Divider(),

                ft.Text("Estrutura do Prompt", style=ft.TextThemeStyle.TITLE_MEDIUM),
                prompt_structure_rg,

                ft.Container(expand=True), # Para empurrar para baixo
                ft.Row([ft.ElevatedButton("Salvar Configurações", icon=ft.Icons.SAVE_ROUNDED, disabled=True)], 
                       expand=True, alignment=ft.MainAxisAlignment.CENTER) # TODO: Lógica de salvar
            ],
            #spacing=12,
            scroll=ft.ScrollMode.ADAPTIVE, # Permite scroll dentro do drawer
            expand=True # Ocupa a altura do container do drawer
        )

    def _initialize_file_picker(self):
        _logger.info("Inicializando ManagedFilePicker para Análise de PDF.")
        
        def individual_file_upload_complete_cb(success: bool, path_or_msg: str, file_name: Optional[str]):
            if success and file_name and path_or_msg:
                _logger.info(f"Upload individual de '{file_name}' OK. Path: {path_or_msg}")
                current_files = self.page.session.get(KEY_SESSION_PDF_FILES_ORDERED) or []
                if not isinstance(current_files, list): current_files = []
                
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
            _logger.info(f"Upload_Batch Completo: {len(batch_results)} resultados.")
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
                final_message = "Nenhum arquivo selecionado."
                final_color = theme.COLOR_WARNING
            
            if final_message: 
                show_snackbar(self.page, final_message, color=final_color)
            
            self.file_list_manager.update_selected_files_display() # Atualiza a lista na UI
            
            # file_list_manager.clear_cached_analysis_results()
            # page.update(file_list_manager.current_batch_name_text, 
            #             file_list_manager.selected_files_list_view, 
            #             file_list_manager.analyze_button) 

            if final_message and final_message != "Nenhum arquivo selecionado.":
                self._files_processed = False # Novos arquivos, processamento necessário
                self._analysis_requested = False # Análise LLM também precisará ser refeita
                self._remove_data_session(KEY_SESSION_PDF_ANALYZER_DATA)
                self._remove_data_session(KEY_SESSION_PDF_LLM_RESPONSE) # Limpa dados antigos
                self._clear_processing_metadata_display()
                self._clear_llm_metadata_display()
            
            self._update_button_states()
            self._show_info_balloon_or_result(show_balloon=True)
            
            self.page.update()


        file_picker_instance = self.page.data.get("global_file_picker")
        if not file_picker_instance:
            _logger.critical("FilePicker global não encontrado na página! Upload não funcionará.")
            show_snackbar(self.page, "Erro crítico: FilePicker não inicializado.", theme.COLOR_ERROR)
            return

        self.managed_file_picker = ManagedFilePicker(
            page=self.page,
            file_picker_instance=file_picker_instance,
            on_individual_file_complete=individual_file_upload_complete_cb,
            upload_dir=UPLOAD_TEMP_DIR,
            on_batch_complete=batch_upload_complete_cb,
            allowed_extensions=["pdf"]
        )
        _logger.info("ManagedFilePicker instanciado e pronto.")

    def _setup_event_handlers(self):
        _logger.info("Configurando handlers de eventos da UI.")
        self.gui_controls[CTL_UPLOAD_BTN].on_click = self._handle_upload_click
        self.gui_controls[CTL_PROCESS_BTN].on_click = self._handle_process_content_click
        self.gui_controls[CTL_ANALYZE_BTN].on_click = self._handle_analyze_click
        self.gui_controls[CTL_PROMPT_STRUCT_BTN].on_click = self._handle_prompt_structured_click
        self.gui_controls[CTL_RESTART_BTN].on_click = self._handle_restart_click
        self.gui_controls[CTL_EXPORT_BTN].on_item_selected = self._handle_export_selected # Para PopupMenuButton
        self.gui_controls[CTL_SETTINGS_BTN].on_click = self._handle_toggle_settings_drawer

    # --- Handlers de Eventos (Implementações Iniciais) ---
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

    def _handle_export_selected(self, e: ft.ControlEvent):
        selected_action = e.control.data
        _logger.info(f"Opção de exportação selecionada: {selected_action}")
        if selected_action == "docx_simple":
            # TODO: Implementar lógica de exportação simples
            llm_response = self.page.session.get(KEY_SESSION_PDF_LLM_RESPONSE)
            if not llm_response:
                show_snackbar(self.page, "Nenhum resultado de análise LLM para exportar.", theme.COLOR_WARNING)
                return
            show_snackbar(self.page, "Exportação DOCX Simples (Breve)...", theme.COLOR_INFO)
            # Chamar doc_generator.export_simple_docx(llm_response, page)
        elif selected_action == "docx_template":
            show_snackbar(self.page, "Exportação com Template (Breve)...", theme.COLOR_INFO)

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
        self.gui_controls[CTL_EXPORT_BTN].disabled = not llm_response_exists
        self.gui_controls[CTL_LLM_RESULT_INFO_TITLE].visible = llm_response_exists
        
        if not self._files_processed:
            self.gui_controls[CTL_LLM_STAUS_INFO].value = "Aguardando para exibir os resultados..."
        elif not llm_response_exists:
            self.gui_controls[CTL_LLM_STAUS_INFO].value = "Clique em 'Solicitar Análise' para prosseguir "

        # Força atualização dos botões
        for btn_key in [CTL_UPLOAD_BTN, CTL_PROCESS_BTN, CTL_ANALYZE_BTN, CTL_LLM_RESULT_INFO_TITLE,
                        CTL_PROMPT_STRUCT_BTN, CTL_RESTART_BTN, CTL_EXPORT_BTN, CTL_SETTINGS_BTN, CTL_LLM_STAUS_INFO]:
            if btn_key in self.gui_controls and self.gui_controls[btn_key].page:
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
                ("processing_time",                              "Tempo de processamento (s)")
            ]
            
            ordered_keys = [key for key, _ in labels]
            labels = {k: v for k, v in labels}
            data_rows = []

            for key in ordered_keys:
                if key in ["count_selected_relevant", "count_discarded_unintelligible", "count_selected_final"]:
                    continue

                if key in metadata_to_display and key in labels:
                    label_text = labels[key]
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
                content_area.controls.append(ft.Container(metadata_table, padding=ft.padding.only(left=30)))

            # Alerta OCR (mantido como estava, abaixo da tabela se houver)
            if metadata_to_display.get("count_discarded_unintelligible", 0) > 0:
                content_area.controls.append(ft.Container(height=6)) # Espaçador
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
                ("llm_model_used",       "Modelo Utilizado")
            ]
            
            ordered_keys = [key for key, _ in labels]
            labels = {k: v for k, v in labels}
            data_rows = []

            for key in ordered_keys:
                label_text = labels[key]
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
                content_area.controls.append(ft.Container(metadata_table, padding=ft.padding.only(left=30)))
        
        # Comentado devido AssertionError: Text Control must be added to the page first
        # if content_area.page: content_area.update()

    def _show_info_balloon_or_result(self, show_balloon: bool, result_text: Optional[str] = None):
        self.gui_controls[CTL_LLM_RESULT_INFO_BALLOON].visible = show_balloon
        self.gui_controls[CTL_LLM_RESULT_TEXT].visible = not show_balloon
        if not show_balloon and result_text is not None:
            self.gui_controls[CTL_LLM_RESULT_TEXT].value = result_text
        
        # Comentado devido AssertionError: Text Control must be added to the page first
        # if self.page:
        #    self.gui_controls[CTL_LLM_RESULT_INFO_BALLOON].update()
        #    self.gui_controls[CTL_LLM_RESULT_TEXT].update()

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

        llm_response = self.page.session.get(KEY_SESSION_PDF_LLM_RESPONSE)
        if llm_response:
            self._show_info_balloon_or_result(show_balloon=False, result_text=llm_response)
        else:
            self._show_info_balloon_or_result(show_balloon=True)
        
        # Configurações do Drawer (TODO: Ler da sessão/configurações do usuário)

        self._update_button_states() # Fundamental após restaurar estado
        #self.update() # comentado devido AssertionError

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

        def _update_status_callback(self, text: str, is_error: bool = False, only_txt: bool = False):
            # Este callback será executado pela thread principal via page.run_thread
            #_logger.info(f"[DEBUG] Callback UI: Atualizando {control_key} para '{text}' (Erro: {is_error})")
            
            txt_to_update = self.gui_controls[CTL_LLM_STAUS_INFO] # control_key = ft.Text

            hide_loading_overlay(self.page)
            if not only_txt:
                show_loading_overlay(self.page, text)
            
            txt_to_update.value = text
            txt_to_update.color = theme.COLOR_ERROR if is_error else None
            txt_to_update.weight = ft.FontWeight.BOLD if is_error else ft.FontWeight.NORMAL
            txt_to_update.update()
            

        def _pdf_processing_thread_func(self, pdf_paths: List[str], batch_name: str, analyze_llm_after: bool):
            try:
                _logger.info(f"Thread: Iniciando processamento de PDFs para '{batch_name}' (LLM depois: {analyze_llm_after})")
                self.page.run_thread(self._update_status_callback, "Etapa 1/5: Extraindo textos do(s) arquivo(s) selecionado(s)...")
                
                #processed_page_data_combined = self.pdf_analyzer.analyze_pdf_documents(pdf_paths)

                processed_files_metadata, all_indices, all_storage, all_analysis_texts, processing_time_1 = \
                                    self.pdf_analyzer.extract_texts_and_preprocess_files(pdf_paths)

                processed_page_data_combined, all_global_page_keys_ordered, processing_time_2 = \
                                    self.pdf_analyzer._build_combined_page_data(processed_files_metadata, all_indices, all_storage)

                self.page.run_thread(self._update_status_callback, f"Etapa 2/5: Processando {len(processed_page_data_combined)} páginas...")
                processed_page_data_combined, processing_time_3 = self.pdf_analyzer.analyze_similarity_and_relevance_files(
                                    processed_page_data_combined, all_global_page_keys_ordered, all_analysis_texts)

                if not processed_page_data_combined:
                    raise ValueError("Nenhum dado processável encontrado nos PDFs.")
                
                #print('\n[DEBUG]:\n', processed_page_data_combined, '\n\n')
                self.page.session.set(KEY_SESSION_PDF_ANALYZER_DATA, processed_page_data_combined)
                self.page.run_thread(self._update_status_callback, "Etapa 3/5: Classificando páginas...")

                classified_data = self.pdf_analyzer.filter_and_classify_pages(processed_page_data_combined)
                self.page.session.set(KEY_SESSION_PDF_CLASSIFIED_INDICES_DATA, classified_data)
                
                relevant_indices, unintelligible_indices, count_similars = classified_data
                count_sel, count_unint = len(relevant_indices), len(unintelligible_indices)
                #print('\n[DEBUG]:\n', relevant_indices, '\n\n', unintelligible_indices, '\n\n') 

                if not relevant_indices:
                    raise ValueError("Nenhuma página relevante encontrada após classificação.")

                self.page.run_thread(self._update_status_callback, "Etapa 4/5: Filtrando páginas...")
                token_limit_pref = 180000 # TODO: Ler do drawer/configurações
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
                    "processing_time": format_seconds_to_min_sec(total_processing_time)
                }
                self.page.session.set(KEY_SESSION_PROCESSING_METADATA, proc_meta_for_ui)
                self.page.run_thread(self.parent_view._update_processing_metadata_display, proc_meta_for_ui)

                self.parent_view._files_processed = True
                _logger.info(f"Thread: Processamento de PDF para '{batch_name}' concluído.")

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
            try:
                _logger.info(f"Thread: Iniciando análise LLM para '{batch_name}'...")
                self.page.run_thread(self._update_status_callback,  "Etapa 5/5: Requisitando análise da LLM...")

                # TODO: Obter provedor e modelo das configurações do Drawer
                provider = "openai"
                model_name = "gpt-4.1-nano" 
                
                # Simulação de obtenção de chave API da sessão (deve ser carregada/salva via UI de config LLM)
                decrypted_api_key = self.page.session.get(f"decrypted_api_key_{provider}_{provider}_api_key") # Exemplo
                if not decrypted_api_key and provider == "openai": # Tenta um fallback se estiver no dev_mode
                     if self.page.data.get("dev_mode", False): # Precisa de uma forma de saber se está em dev_mode
                         decrypted_api_key = self.page.session.get("decrypted_api_key_OpenAI_openai_api_key") # Chave mock
                         _logger.warning("Usando chave API OpenAI mockada de dev_mode para análise LLM.")

                if not decrypted_api_key:
                    # Esta lógica agora é feita no ai_orchestrator, que pega da sessão ou do Firestore.
                    # Mas o orchestrator precisa do provider correto.
                    pass # ai_orchestrator tentará carregar

                llm_response, token_usage_info = analyze_text_with_llm(self.page, aggregated_text, provider, model_name)

                if llm_response:
                    self.page.session.set(KEY_SESSION_PDF_LLM_RESPONSE, llm_response)
                    self.page.run_thread(self.parent_view._show_info_balloon_or_result, False, llm_response)
                    
                    # TODO: Calcular metadados da LLM (tokens, custo) - Isso exigiria que `analyze_text_with_llm` retornasse mais infos.
                    # Por ora, mockamos alguns. # Obter dados do result da consulta da API
                    llm_meta_for_gui = token_usage_info
                    llm_meta_for_gui.update({
                        "llm_provider_used": provider.capitalize(),
                        "llm_model_used": model_name
                    }) 
                        
                    self.page.session.set(KEY_SESSION_LLM_METADATA, llm_meta_for_gui)
                    self.page.run_thread(self.parent_view._update_llm_metadata_display, llm_meta_for_gui)
                    self.page.run_thread(show_snackbar, self.page, "Análise LLM concluída!", theme.COLOR_SUCCESS)
                    self.parent_view._analysis_requested = True
                    self.page.run_thread(self._update_status_callback,  "", False, True)
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


# Função principal da view (chamada pelo router)
def create_analyze_pdf_content(page: ft.Page) -> ft.Control:
    _logger.info("View Análise de PDF: Iniciando criação (nova estrutura).")
    # Esta view agora é um ft.Column que contém todos os elementos.
    # O router irá inseri-la no layout principal da página.
    return AnalyzePDFViewContent(page)

