# src/flet_ui/views/nc_analyze_view.py
import logging, copy
logger = logging.getLogger(__name__)

from time import perf_counter
start_time = perf_counter()
logger.debug(f"{start_time:.4f}s - Iniciando nc_analyze_view.py")

import flet as ft
import threading, os, shutil, json
from typing import Optional, Dict, Any, List, Union, Tuple, Callable
from time import time, sleep
from datetime import datetime
from enum import Enum
#from pathlib import Path
#from rich import print

from SOURCE import app_cache
from SOURCE.logger.cloud_logger_handler import context_wrap
from SOURCE.flet_ui.components.components import (
    show_snackbar, show_loading_overlay, hide_loading_overlay,
    ManagedFilePicker, wrapper_panel_1, CompactKeyValueTable,
    CardWithHeader, show_confirmation_dialog, ReadOnlySelectableTextField,
    safe_control_update, safe_page_update,
)

from SOURCE.flet_ui.components.file_list_manager import FileListManager
from SOURCE.flet_ui.components.settings_drawer import AnalyzeSettingsDrawer
from SOURCE.flet_ui import theme

from SOURCE.settings import (KEY_SESSION_CURRENT_BATCH_NAME, 
                          KEY_SESSION_PROMPTS_FINAL, KEY_SESSION_PROMPTS_DICT, KEY_SESSION_LIST_TO_PROMPTS,
                          KEY_SESSION_SHARED_FILES_ORDERED, KEY_SESSION_SHARED_DOCUMENT_CONTEXT,
                          KEY_SESSION_SHARED_PROCESSING_METADATA)

from SOURCE.settings import (UPLOAD_TEMP_DIR, ASSETS_DIR, WEB_TEMP_EXPORTS_SUBDIR, TEMPLATES_DOCX_SUBDIR,
                          cotacao_dolar_to_real, KEY_SESSION_NC_ANALYZE_SETTINGS,
                          KEY_SESSION_CLOUD_ANALYSIS_DEFAULTS, FALLBACK_ANALYSIS_SETTINGS,
                          KEY_SESSION_LOADED_LLM_PROVIDERS,
                          KEY_SESSION_TOKENS_EMBEDDINGS, KEY_SESSION_MODEL_EMBEDDINGS_LIST,
                          PROMPTS_COLLECTION, PROMPTS_DOCUMENT_ID)

from SOURCE.utils import (format_seconds_to_min_sec, clean_and_convert_to_float, convert_to_list_of_strings,
                        get_lista_ufs_cached, get_municipios_por_uf_cached, calcular_similaridade_rouge_l)

# Outros imports pesados aqui:
from SOURCE.core.prompts import (formatted_initial_analysis, get_prompts_for_initial_analysis)

from SOURCE.utils import _initialize_heavy_utils
_initialize_heavy_utils()

from SOURCE.core.pdf_processor import PDFDocumentAnalyzer, PdfPlumberExtractor
import SOURCE.core.ai_orchestrator as ai_orchestrator
from SOURCE.core.ai_orchestrator import ContextLengthExceededError
from SOURCE.core.doc_generator import DocxExporter

ufs_list = get_lista_ufs_cached()  # TODO: incluir atualização a partir do firestore
municipios_list = get_municipios_por_uf_cached()

from SOURCE.services.firebase_client import FirebaseClientFirestore, _from_firestore_value
firestore_client = FirebaseClientFirestore()

logger.debug(f"Carregamento pesado dentro de NC_ANALYZE_VIEW em {perf_counter()-start_time:.4f}s")

from SOURCE.utils import get_user_cache

# --- Constantes de Chave de Sessão/Cache Local para NC_ANALYZE_VIEW ---
KEY_SESSION_PDF_FILES_ORDERED = "apv_pdf_files_ordered"
KEY_SESSION_PROCESSING_METADATA = "apv_processing_metadata"
KEY_SESSION_LLM_METADATA = "apv_llm_metadata"
KEY_SESSION_FEEDBACK_COLLECTED_FOR_CURRENT_ANALYSIS = "apv_feedback_collected"  # Flag para indicar se o feedback já foi coletado.
KEY_SESSION_LLM_REANALYSIS = "apv_llm_reanalysis_flag"

# Dados a ficar em _SERVER_SIDE_CACHE:
KEY_SESSION_PDF_AGGREGATED_TEXT_INFO = "apv_pdf_aggregated_text_info" # (str_pages, aggregated_text, tokens_antes, tokens_depois)
KEY_SESSION_PDF_LLM_RESPONSE = "apv_pdf_llm_response"                                           # Resposta original da IA
KEY_SESSION_PDF_LLM_RESPONSE_ACTUAL = "apv_pdf_llm_response_actual"                             # Resposta na GUI (que pode ter sido editada pelo usuário) # LLMStructuredResultDisplay.get_current_form_data()
KEY_SESSION_PDF_LLM_RESPONSE_SNAPSHOT_FOR_FEEDBACK = "apv_llm_response_snapshot_for_feedback"   # Cópia da resposta original p/ fins de comparação com a respota editada pelo usuário.
KEY_SESSION_CHAT_HAS_FILES_OPTIMIZED = "has_analyzer_data"
KEY_SESSION_HAS_LLM_REPONSE = "has_llm_response"

# Constantes para nomes de controles (facilita acesso) CTL = Control
# TODO: Alterar para variáveis diretas na classe, em vez de usar dict.
CTL_UPLOAD_BTN = "upload_button"
CTL_PROCESS_BTN = "process_button"
CTL_ANALYZE_BTN = "analyze_button"
CTL_PROMPT_STRUCT_BTN = "prompt_structured_button"
CTL_RESTART_BTN = "restart_button"
CTL_EXPORT_BTN = "export_button"
CTL_TEXT_MODEL_BTN = "active_model_button"
CTL_SETTINGS_BTN = "settings_button"
CTL_RESET_SETTINGS_BTN = "reset_settings_button"
CTL_LLM_RESULT_TEXT = "llm_result_text"
CTL_LLM_STRUCTURED_RESULT_DISPLAY = "llm_structured_result_display" # Novo
CTL_LLM_STATUS_INFO = "llm_status_info"
CTL_LLM_RESULT_INFO_BALLOON = "llm_result_info_balloon"
CTL_LLM_METADATA_PANEL = "llm_metadata_panel"
CTL_LLM_METADATA_PANEL_TITLE = "llm_metadata_panel_title"
CTL_LLM_METADATA_CONTENT = "llm_metadata_content"
CTL_LLM_AI_WARNING_BALLOON = "llm_ai_warning_balloon"

CTL_PROMPT_SAVE_BTN = "prompt_save_button"
KEY_USER_CACHE_PROMPTS_EDITED_DATA = "apv_user_cache_prompts_edited_data"
KEY_SESSION_PROMPT_IS_EDITED_FLAG = "apv_session_prompt_is_edited_flag"

# Enum para operações do FilePicker
class ExportOperation(Enum):
    NONE = "none"
    SIMPLE_DOCX = "simple_docx"
    TEMPLATE_DOCX = "template_docx"

class FeedbackDialogAction(Enum):
    CONFIRM_AND_CONTINUE = "confirm_and_continue"
    RETURN_TO_EDIT = "return_to_edit"
    SKIP_AND_CONTINUE = "skip_and_continue"
    CANCELLED_OR_ERROR = "cancelled_or_error" 

# ---

class AnalyzePDFViewContent(ft.Column):
    """
    Conteúdo principal da view de Análise de Notícias-Crime e Outros Documentos.

    Gerencia a UI, o fluxo de carregamento, processamento e análise de PDFs
    usando modelos de linguagem (LLMs), além da exportação dos resultados.
    """
    def __init__(self, page: ft.Page):
        """
        Inicializa a view de Análise de Notícias-Crime e Outros Documentos.

        Configura os componentes da interface do usuário, gerencia o estado interno da view,
        e inicializa os gerenciadores de arquivos, análise, configurações e exportação.

        Args:
            page (ft.Page): A página Flet à qual esta view será adicionada.
        """
        super().__init__(expand=True, spacing=10)
        self.page = page
        self._is_mounted = False
        self.gui_controls: Dict[str, ft.Control] = {}
        # self.settings_drawer_manager: Optional[SettingsDrawerManager] = None
        # self.gui_controls_drawer: Dict[str, ft.Control] = {}

        self.user_cache = get_user_cache(self.page)

        # Estado interno da View
        self._is_drawer_open = False
        self._files_processed = False
        self._analysis_requested = False
        self._prompt_text_fields: Dict[str, ft.TextField] = {}

        # --- Adicionado para visualização do prompt ---
        self._is_prompt_view_active = False
        self._original_main_layout_container: Optional[ft.Row] = None
        self._prompt_display_layout: Optional[ft.Container] = None
    
        self._build_gui_structure()
        
        self.export_manager = InternalExportManager(self)
        self.analysis_controller = InternalAnalysisController(self.page, self.gui_controls, self)
        self.feedback_workflow_manager = FeedbackWorkflowManager(self.page, self)

        self._initialize_file_picker()  # Inicia o self.managed_file_picker
        self.file_list_manager = self._initialize_file_list_manager()

        self._setup_event_handlers()

        self.settings_drawer_component.load_settings_into_controls() # Carrega configurações em page.session
        # self._update_gui_from_state() # -> Chamado no did_mount

    def did_mount(self):
        """
        Chamado sempre que a view é montada, garantindo que a UI reflita o estado
        mais recente da sessão, mesmo ao retornar de cache.
        """
        self._is_mounted = True
        self._update_gui_from_state()

    def will_unmount(self):
        """Invalida referências à page ao desmontar, evitando uso pós-desmontagem."""
        self._is_mounted = False
        self.page = None

    def _is_view_usable(self) -> bool:
        """
        Indica se a view ainda pode tocar a UI/sessão com segurança.

        Necessário porque as threads de processamento e de análise LLM (e os
        callbacks que elas agendam via `page.run_thread`) podem concluir depois de
        o usuário navegar para outra view. Nesse momento `will_unmount` — e o
        próprio Flet, em `Page.__handle_mount_unmount` — já anularam `self.page`.

        Returns:
            True se a view está montada e com referência válida à página.
        """
        return bool(self._is_mounted and self.page)

    def _remove_data_session(self, key: str):
        """
        Remove um dado específico da sessão da página, se existir.

        Não faz nada se a view já tiver sido desmontada (sem `page`, não há sessão
        acessível) — o método é chamado também a partir da thread de análise LLM,
        que pode terminar após o usuário sair da view.

        Args:
            key (str): A chave do dado a ser removido da sessão.
        """
        if not self.page:
            logger.debug(f"_remove_data_session ignorado para '{key}': view desmontada.")
            return

        if self.page.session.contains_key(key):
            self.page.session.remove(key)

    def _build_gui_structure(self):
        """
        Constrói a estrutura visual (GUI) da view, incluindo a barra de botões,
        painéis expansíveis para arquivos, metadados de processamento e resultados LLM,
        e o drawer de configurações.
        """
        logger.debug("Construindo estrutura da GUI para Análise de PDF.")
        
        default_icon_size_bar = 25
        width_btn_bar = 180

        # --- 1. Título Fixo ---
        title_bar = ft.Text("Análise inicial de Notícias-Crime e Outros",
                             style=ft.TextThemeStyle.HEADLINE_SMALL,
                             text_align=ft.TextAlign.CENTER)

        # --- 2. Barra de Botões Fixa ---
        self.gui_controls[CTL_UPLOAD_BTN] = ft.ElevatedButton("Carregar Arquivo(s)", icon=ft.Icons.UPLOAD_FILE_ROUNDED, width=width_btn_bar)
        self.gui_controls[CTL_PROCESS_BTN] = ft.ElevatedButton("Processar Conteúdo", icon=ft.Icons.PLAY_CIRCLE_OUTLINE, width=width_btn_bar) # MODEL_TRAINING_ROUNDED
        self.gui_controls[CTL_ANALYZE_BTN] = ft.ElevatedButton("Solicitar Análise", icon=ft.Icons.ONLINE_PREDICTION_ROUNDED, width=width_btn_bar)
        
        self.gui_controls[CTL_PROMPT_STRUCT_BTN] = ft.ElevatedButton("Prompt Estruturado", icon=ft.Icons.EDIT_NOTE_ROUNDED, width=width_btn_bar)
        self.gui_controls[CTL_PROMPT_SAVE_BTN] = ft.ElevatedButton("Salvar Prompt Temporariamente", icon=ft.Icons.SAVE_AS_ROUNDED, width=250, visible=False, bgcolor=ft.Colors.with_opacity(0.2, theme.COLOR_SUCCESS))
        self.gui_controls[CTL_RESTART_BTN] = ft.IconButton(icon=ft.Icons.RESTART_ALT_ROUNDED, tooltip="Reiniciar Análise (Limpar Tudo)", icon_size=default_icon_size_bar)
        self.gui_controls[CTL_EXPORT_BTN] = ft.PopupMenuButton(
            icon=ft.Icons.DOWNLOAD_FOR_OFFLINE_ROUNDED,
            tooltip="Exportar Análise", icon_size=default_icon_size_bar,
            items=[]
                #ft.PopupMenuItem(text="Exportar em Simples DOCX", data="docx_simple"),
                #ft.PopupMenuItem(text="Exportar em Template DOCX", data="docx_template", disabled=True), # habilitado após análise LLM
        )
        self.gui_controls[CTL_TEXT_MODEL_BTN] = ft.TextButton(
            text="Modelo: Carregando...",
            icon=ft.Icons.MODEL_TRAINING_OUTLINED,
            tooltip="Clique ver e alterar as configurações de análise",
            width=300,
            style=ft.ButtonStyle(padding=ft.padding.symmetric(horizontal=12))
        )
        self.gui_controls[CTL_SETTINGS_BTN] = ft.IconButton(icon=ft.Icons.TUNE_ROUNDED, tooltip="Configurações específicas", icon_size=default_icon_size_bar)

        action_buttons_bar = ft.Row(
            [
                ft.Row([
                    self.gui_controls[CTL_UPLOAD_BTN],
                    self.gui_controls[CTL_PROCESS_BTN],
                    self.gui_controls[CTL_ANALYZE_BTN]], wrap=True),
                #ft.Container(expand=True), # Espaçador
                ft.Row([
                    self.gui_controls[CTL_PROMPT_STRUCT_BTN],
                    self.gui_controls[CTL_TEXT_MODEL_BTN],
                    self.gui_controls[CTL_RESTART_BTN],
                    self.gui_controls[CTL_EXPORT_BTN],
                    self.gui_controls[CTL_SETTINGS_BTN]], wrap=True)
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            wrap=True, width=self.page.width*0.9 # spacing=10
        )

        # --- 3. Layout de Conteúdo com Panels Expansíveis e Containers ---
        # Panel 1: Lista de Arquivos

        # O FileListManager agora é um controle completo que será inserido no layout.
        # A referência será criada em _initialize_file_list_manager.

        # Panel 2: Metadados do Processamento
        # O painel de metadados do processamento foi migrado para dentro do FileListManager

        # Container 3: Resposta/Resultado da Análise
        self.llm_result_title = ft.Row([ft.Container(width=12),
                                        ft.Text("Resultado da Análise LLM:",
                                            style=ft.TextThemeStyle.TITLE_MEDIUM,
                                            weight=ft.FontWeight.BOLD)], visible=False)
        
        self.gui_controls[CTL_LLM_AI_WARNING_BALLOON] = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=theme.COLOR_WARNING, size=24),
                    ft.Text(
                        "Atenção: Todos os campos, classificações e resumos a seguir foram gerados por inteligência artificial e devem ser tratados como uma sugestão inicial.\n"
                        "Revise e valide cuidadosamente cada informação antes de prosseguir com qualquer ato administrativo ou encaminhamento oficial.",
                        expand=True, italic=True, size=13,
                        #color=ft.Colors.with_opacity(0.9, theme.COLOR_WARNING)
                    ),
                    ft.IconButton(
                        ft.Icons.CLOSE_ROUNDED,
                        on_click=lambda e: (setattr(e.control.parent.parent, 'visible', False), e.control.parent.parent.update()),
                        icon_size=18,
                        tooltip="Fechar Aviso"
                    )
                ],
                vertical_alignment=ft.CrossAxisAlignment.START,
                spacing=10,
            ),
            padding=12,
            border_radius=8,
            border=ft.border.all(1, theme.COLOR_WARNING),
            bgcolor=ft.Colors.with_opacity(0.05, theme.COLOR_WARNING),
            visible=False,  # Começa invisível
            #margin=ft.margin.only(right=0)
        )

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
                   self.gui_controls[CTL_LLM_RESULT_INFO_BALLOON],
                   self.gui_controls[CTL_LLM_RESULT_TEXT],
                   self.gui_controls[CTL_LLM_STRUCTURED_RESULT_DISPLAY]
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
            header=ft.Column([ft.Row([ft.Container(width=12), self.gui_controls[CTL_LLM_METADATA_PANEL_TITLE]])], 
                             expand=True, alignment=ft.MainAxisAlignment.CENTER),
            content=self.gui_controls[CTL_LLM_METADATA_CONTENT],
            can_tap_header=True, expanded=False,
            on_animation_end = lambda e: self.llm_result_container.scroll_to(offset=-1, duration=500),
            bgcolor = ft.Colors.ON_INVERSE_SURFACE
        )
        self.gui_controls[CTL_LLM_METADATA_PANEL] = wrapper_panel_1(self.gui_controls[CTL_LLM_METADATA_PANEL])
        self.gui_controls[CTL_LLM_METADATA_PANEL].visible=False # visível após resposta da LLM

        # Layout principal dos painéis e resultado
        main_content_column = ft.Column(
            [
                # O FileListManager será inserido aqui dinamicamente
                ft.Column(spacing=5, expand=True, horizontal_alignment=ft.CrossAxisAlignment.START),
                ft.Column([
                    self.llm_result_title,
                    self.gui_controls[CTL_LLM_AI_WARNING_BALLOON],
                    self.llm_result_container], expand=True, spacing=6,
                    ),

                self.gui_controls[CTL_LLM_METADATA_PANEL]
            ],
            expand=True,
            spacing=15,
            scroll=ft.ScrollMode.ADAPTIVE # Adiciona scroll se o conteúdo for muito grande
        )

        # --- Drawer de Configurações (Placeholder) ---
        self.settings_drawer_component = AnalyzeSettingsDrawer(self.page, session_key=KEY_SESSION_NC_ANALYZE_SETTINGS, 
                                                               on_settings_changed=self._update_active_model_button)
        self.settings_drawer_container = ft.Container(content=self.settings_drawer_component, padding=10, width=0)
        # self.settings_drawer_manager não é mais necessário

        self._original_main_layout_container = ft.Row(
            [ft.Container(main_content_column, expand=True, padding=ft.padding.only(right=8, bottom=5)),
             self.settings_drawer_container],
            expand=True, vertical_alignment=ft.CrossAxisAlignment.START
        )
      
        # Adiciona os componentes principais à view
        self.controls.extend([
            title_bar,
            action_buttons_bar,
            ft.Divider(height=1),
            self._original_main_layout_container # Esta linha contém o conteúdo e o drawer
        ])
    
    def _create_prompt_display_layout(self) -> ft.Container:
        """
        Cria e retorna o layout para exibir os prompts estruturados utilizados na análise LLM.
        Este layout permite a visualização dos prompts de sistema, instrução e outros prompts
        segmentados, com o conteúdo do PDF substituído por um placeholder para clareza.

        Returns:
            ft.Container: Um container Flet contendo os TextFields com os prompts.
        """
        self.user_cache = get_user_cache(self.page)
        prompts = self.user_cache.get(KEY_SESSION_PROMPTS_DICT)

        logger.debug("Criando layout de visualização do prompt.")

        prompt_variables_to_display = ["system_prompt_A0", "general_instruction_B1_2", "start_action_B2", 
                                        "prompt_C0", "prompt_D0", "prompt_F0", "prompt_G1", "prompt_G2",
                                        "prompt_H1", "prompt_I1", "prompt_I2", "prompt_J0", "prompt_K0"]
        
        prompt_variables_to_display = [(key_prompt, prompts[key_prompt]) for key_prompt in prompt_variables_to_display]
        
        prompt_text_fields = [ft.Container(height=1)]
        for name_str, prompt_dict_obj in prompt_variables_to_display:
            content_value = prompt_dict_obj.get("content", "Conteúdo não encontrado")
            # Limpar {input_text} se presente, para clareza na visualização
            content_value_cleaned = content_value.replace("\n{input_text}\n", "[CONTEÚDO_DO_PDF_é_INSERIDO_AQUI]")

            prompt_field = ft.TextField(
                label=name_str,
                value=content_value_cleaned,
                multiline=True,
                read_only=False,
                expand=True,
                border=ft.InputBorder.OUTLINE,
                text_size=12,
            )

            self._prompt_text_fields[name_str] = prompt_field
            prompt_text_fields.append(prompt_field)

        save_button_row = ft.Row(
            [
                ft.Container(expand=True),
                self.gui_controls[CTL_PROMPT_SAVE_BTN]
            ],
            alignment=ft.MainAxisAlignment.END
        )

        return ft.Container(
            content=ft.Column(
                [
                    ft.Column(
                        prompt_text_fields,
                        scroll=ft.ScrollMode.ALWAYS, expand=True,
                        spacing=9,
                    ),
                    save_button_row
                ]
            ),
            expand=True, padding=15,
            # border=ft.border.all(1, ft.Colors.TEAL_ACCENT_700) # Para debug
        )
    
    # --- setup file_picker ---
    def _initialize_file_picker(self):
        """
        Inicializa os FilePickers necessários para upload e exportação.

        Configura o ManagedFilePicker para uploads de PDF e o InternalExportManager
        para gerenciar as operações de exportação, utilizando a instância global
        do FilePicker da página.
        """
        logger.debug("Inicializando FilePickers (Managed para upload, Global para exportação).")
        
        # Primeiro, obtém a referência ao picker global
        if not self.page.data.get("global_file_picker"):
            logger.critical("FilePicker global NÃO encontrado em page.data! Upload e Exportação podem falhar.")
            show_snackbar(self.page, "Erro crítico: FilePicker não inicializado.", theme.COLOR_ERROR)
            return
        else:
            logger.debug("Referência ao FilePicker GLOBAL para exportação e upload armazenada.")
    
        if not hasattr(self, 'managed_file_picker'):
            self.managed_file_picker = ManagedFilePicker(
                page=self.page,
                upload_dir=UPLOAD_TEMP_DIR,
                allowed_extensions=["pdf"]
            )
            logger.debug("ManagedFilePicker para UPLOAD instanciado.")

    def _initialize_file_list_manager(self) -> FileListManager:
        """Cria e configura a instância do FileListManager."""
        manager = FileListManager(
            page=self.page,
            session_key_files_ordered=KEY_SESSION_PDF_FILES_ORDERED,
            managed_file_picker=self.managed_file_picker,
            on_list_changed=self._on_file_list_changed
        )
        self._original_main_layout_container.controls[0].content.controls[0] = manager # Insere no layout: self._original_main_layout_container -> main_content_column
        # self.controls[3].controls[0].controls[0] = manager 
        return manager

    def _on_file_list_changed(self):
        """Callback chamado pelo FileListManager quando a lista de arquivos muda."""
        # A ação primária é resetar os resultados, já que a fonte de dados mudou.
        def primary_action():
            self._reset_processing_and_llm_results()
            safe_page_update(self.page)

        # Se houver uma análise LLM (que será invalidada), o fluxo de feedback é acionado.
        # O contexto da ação é genérico, pois pode ser uma remoção ou reordenação.
        if self.feedback_workflow_manager:
            self.feedback_workflow_manager.request_feedback_and_proceed(
                action_context_name="Modificar Lista de Arquivos",
                primary_action_callable=primary_action,
            )
        else:
            primary_action()

    def _setup_event_handlers(self):
        """
        Configura os handlers de eventos para os controles da UI.
        Associa as funções de tratamento de eventos aos respectivos botões e elementos interativos.
        """
        logger.debug("Configurando handlers de eventos da UI.")
        self.gui_controls[CTL_UPLOAD_BTN].on_click = self._handle_upload_click
        self.gui_controls[CTL_PROCESS_BTN].on_click = self._handle_process_content_click
        self.gui_controls[CTL_ANALYZE_BTN].on_click = self._handle_analyze_click
        self.gui_controls[CTL_RESTART_BTN].on_click = self._handle_restart_click
        #self.gui_controls[CTL_EXPORT_BTN].on_item_selected = self.export_manager.handle_export_selected # Para PopupMenuButton
        self.gui_controls[CTL_TEXT_MODEL_BTN].on_click = self._handle_toggle_settings_drawer
        self.gui_controls[CTL_SETTINGS_BTN].on_click = self._handle_toggle_settings_drawer
        self.gui_controls[CTL_PROMPT_STRUCT_BTN].on_click = self._toggle_prompt_view
        self.gui_controls[CTL_PROMPT_SAVE_BTN].on_click = self._save_edited_prompts_to_cache

    def _handle_upload_click(self, e: ft.ControlEvent):
        """
        Handler para o clique no botão 'Carregar Arquivo(s)'.

        Inicia o processo de seleção e upload de arquivos PDF, exibindo um overlay de carregamento.
        Integra-se com o `FeedbackWorkflowManager` para solicitar feedback antes de prosseguir,
        se aplicável.

        Args:
            e (ft.ControlEvent): O evento de clique do botão.
        """
        logger.info("Botão 'Carregar Arquivo(s)' clicado.")

        # Callbacks para o ManagedFilePicker (upload)
        def individual_file_upload_complete_cb(success: bool, path_or_msg: str, file_name: Optional[str]):
            """
            Callback executado quando o upload de um arquivo individual é concluído.

            Args:
                success (bool): True se o upload foi bem-sucedido, False caso contrário.
                path_or_msg (str): O caminho temporário do arquivo no servidor (se sucesso) ou uma mensagem de erro.
                file_name (Optional[str]): O nome original do arquivo.
            """
            if success and file_name and path_or_msg:
                logger.debug(f"Upload individual de '{file_name}' OK. Path: {path_or_msg}")
                current_files = self.page.session.get(KEY_SESSION_PDF_FILES_ORDERED) or []
                if not isinstance(current_files, list):
                    current_files = []
                if not any(f['name'] == file_name and f['path_or_message'] == path_or_msg for f in current_files):
                    new_file_entry = {  "name": file_name,
                                        "path_or_message": path_or_msg,
                                        "original_index": len(current_files)}
                    current_files.append(new_file_entry)
                    self.page.session.set(KEY_SESSION_PDF_FILES_ORDERED, current_files)
                    self.page.session.set(KEY_SESSION_SHARED_FILES_ORDERED, current_files)
            elif path_or_msg == "Seleção cancelada":
                logger.info("Seleção de arquivos cancelada.")
            else:
                logger.error(f"Falha no upload de '{file_name}': {path_or_msg}")
            
        def batch_upload_complete_cb(batch_results: List[Dict[str, Any]]):
            """
            Callback executado quando o upload de um lote de arquivos é concluído.

            Atualiza a UI com o status do upload e o estado da view.

            Args:
                batch_results (List[Dict[str, Any]]): Lista de dicionários com os resultados de cada arquivo no lote.
            """
            logger.info(f"Upload_Batch Completo (ManagedFilePicker): {len(batch_results)} resultados.")
            _page = self.page
            if not _page:
                return
            hide_loading_overlay(_page)
            
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
                logger.debug("Nenhum arquivo selecionado.")
                final_message = "Nenhum arquivo selecionado."
                final_color = theme.COLOR_WARNING
            
            if final_message:
                show_snackbar(_page, final_message, color=final_color)
            
            # Se novos arquivos foram adicionados, invalida os resultados anteriores.
            if successful_uploads:
                self._reset_processing_and_llm_results()
            else:
                # Se todos os uploads falharam, apenas atualiza a UI sem resetar os dados
                self._update_gui_from_state()
            
            self.file_list_manager.expand_container()

            safe_page_update(_page)
        
        def primary_upload_action():
            if self.managed_file_picker:
                threading.Timer(0.1, show_loading_overlay, args=[self.page, "A carregar arquivo(s)..."]).start()
                self.managed_file_picker.pick_files(allow_multiple=True, 
                                                    dialog_title_override="Selecione PDF(s) para análise",
                                                    on_individual_file_complete=individual_file_upload_complete_cb,
                                                    on_batch_complete=batch_upload_complete_cb)
            else:
                show_snackbar(self.page, "Erro: Gerenciador de upload não está pronto.", theme.COLOR_ERROR)

        if self.feedback_workflow_manager:
            self.feedback_workflow_manager.request_feedback_and_proceed(
                action_context_name="Carregar Novos Arquivos",
                primary_action_callable=primary_upload_action,
            )
        else: # Fallback se o manager não estiver pronto
            primary_upload_action()

    def _initiate_analysis_step(self,
                                step_type: str,
                                event: Optional[ft.ControlEvent] = None):
        """
        Inicia uma etapa específica do fluxo de análise (processamento, análise LLM, ou ambos).

        Verifica a existência de arquivos carregados e, se necessário, solicita feedback
        ao usuário antes de executar a ação primária.

        Args:
            step_type (str): O tipo de etapa a ser iniciada ("process_only", "analyze_only", "process_and_analyze").
            event (Optional[ft.ControlEvent]): O evento de controle original que disparou a ação (opcional, para logging).
        """
        logger.info(f"Iniciando etapa de análise: '{step_type}'")

        # 1. Verificar se há arquivos carregados (necessário para todas as etapas)
        ordered_files = self.page.session.get(KEY_SESSION_PDF_FILES_ORDERED)
        if not ordered_files and step_type != "analyze_only": # "analyze_only" pode teoricamente rodar se já processado
            show_snackbar(self.page, "Nenhum PDF carregado para esta ação.", theme.COLOR_WARNING)
            logger.warning(f"Ação '{step_type}' abortada: Nenhum PDF carregado.")
            return
        
        pdf_paths = [f['path_or_message'] for f in ordered_files] if ordered_files else []
        batch_name = self.page.session.get(KEY_SESSION_CURRENT_BATCH_NAME) or "Lote Atual"

        # Verifica se é uma reanálise ANTES de limpar os resultados existentes
        is_reanalysis = False
        if step_type in ["analyze_only", "process_and_analyze"]:
            # É uma reanálise se já existe uma resposta LLM no cache
            if self.user_cache.get(KEY_SESSION_PDF_LLM_RESPONSE):
                is_reanalysis = True
                logger.info("Detectada solicitação de REANÁLISE LLM.")

        # 2. Definir a ação primária específica para a etapa
        primary_action_callable: Optional[Callable[[], None]] = None
        action_context_name_for_feedback = ""

        if step_type == "process_only":
            action_context_name_for_feedback = "Processar Arquivos"
            
            def primary_process_action():
                # Apenas reseta o estado. A UI será atualizada pelo método de reset.
                self._reset_processing_and_llm_results() 
                self.analysis_controller.start_pdf_processing_only(pdf_paths, batch_name)
            
            primary_action_callable = primary_process_action

        elif step_type == "analyze_only":
            action_context_name_for_feedback = "Solicitar Nova Análise"
            # Esta etapa requer que os arquivos já tenham sido processados
            if not self._files_processed:
                show_snackbar(self.page, "Conteúdo dos arquivos ainda não processado. Clique em 'Processar Conteúdo' primeiro.", theme.COLOR_WARNING, duration=5000)
                logger.warning("Ação 'analyze_only' abortada: Arquivos não processados.")
                # Talvez chamar o _initiate_analysis_step("process_and_analyze") aqui?
                # Por ora, apenas informa o usuário.
                return # Retorna para o usuário clicar no botão correto.

            def primary_llm_analysis_action():
                # A lógica de decidir entre pipeline completo ou só LLM está dentro de proceed_with_llm_analysis
                # do exemplo anterior, que agora será parte de primary_analyze_action.        
                aggregated_text = self.user_cache.get(KEY_SESSION_PDF_AGGREGATED_TEXT_INFO)
                if not aggregated_text: 
                    show_snackbar(self.page, "Não há texto agregado para análise. Verifique o processamento.", theme.COLOR_ERROR)
                    return
                
                # Apenas reseta os resultados da LLM.
                self._reset_llm_results()
                self.analysis_controller.start_llm_analysis_only(aggregated_text, batch_name, is_reanalysis=is_reanalysis)
            
            primary_action_callable = primary_llm_analysis_action

        elif step_type == "process_and_analyze":
            action_context_name_for_feedback = "Processar e Solicitar Nova Análise"
            
            def primary_full_pipeline_action():
                self._reset_processing_and_llm_results()
                self.analysis_controller.start_full_analysis_pipeline(pdf_paths, batch_name, is_reanalysis=is_reanalysis)
            
            primary_action_callable = primary_full_pipeline_action
        
        else:
            logger.error(f"Tipo de etapa de análise desconhecido: {step_type}")
            return

        # 4. Chamar o FeedbackWorkflowManager (se existir e for aplicável)
        if self.feedback_workflow_manager:
            self.feedback_workflow_manager.request_feedback_and_proceed(
                action_context_name=action_context_name_for_feedback,
                primary_action_callable=primary_action_callable,

            )
        else:
            # Se não houver gerenciador de feedback, executa a ação diretament
            if primary_action_callable:
                primary_action_callable()

    def _handle_process_content_click(self, e: ft.ControlEvent):
        """
        Handler para o clique no botão 'Processar Conteúdo'.

        Inicia a etapa de processamento de conteúdo dos PDFs.

        Args:
            e (ft.ControlEvent): O evento de clique do botão.
        """
        logger.info("Botão 'Processar Conteúdo' clicado.")
        self._initiate_analysis_step(step_type="process_only", event=e)

    def _handle_analyze_click(self, e: ft.ControlEvent):
        """
        Handler para o clique no botão 'Solicitar Análise'.

        Inicia a etapa de análise LLM. Se os arquivos ainda não foram processados,
        redireciona para o pipeline completo (processar e analisar).

        Args:
            e (ft.ControlEvent): O evento de clique do botão.
        """
        logger.info("Botão 'Solicitar Análise' clicado.")

        if not self._files_processed:
            logger.debug("'Solicitar Análise' clicado, mas arquivos não processados. Redirecionando para 'process_and_analyze'.")
            # Se os arquivos não foram processados, o clique em "Analisar" deve, na verdade,
            # executar o pipeline completo.
            self._initiate_analysis_step(step_type="process_and_analyze", event=e)
        else:
            # Se os arquivos já foram processados, apenas executa a análise LLM.
            self._initiate_analysis_step(step_type="analyze_only", event=e)

    def _handle_restart_click(self, e: ft.ControlEvent):
        """
        Handler para o clique no botão 'Reiniciar Análise'.

        Limpa todos os dados da sessão e reseta a interface do usuário para o estado inicial.
        Integra-se com o `FeedbackWorkflowManager` para solicitar feedback antes de prosseguir,
        se aplicável.

        Args:
            e (ft.ControlEvent): O evento de clique do botão.
        """
        logger.info("Botão 'Reiniciar' clicado.")

        def primary_restart_action():
            self._clear_all_data_and_gui()
            show_snackbar(self.page, "Análise reiniciada. Carregue novos arquivos.", theme.COLOR_INFO)

        if self.feedback_workflow_manager:
            self.feedback_workflow_manager.request_feedback_and_proceed(
                action_context_name="Reiniciar Análise",
                primary_action_callable=primary_restart_action,
            )
        else:
            primary_restart_action()

    def _update_export_button_menu(self):
        """
        Atualiza os itens do menu do botão de Exportar.

        Popula o menu com opções de exportação simples e baseadas em templates,
        habilitando ou desabilitando itens conforme a disponibilidade de templates
        e o estado da análise.
        """
        export_button = self.gui_controls.get(CTL_EXPORT_BTN)
        if not isinstance(export_button, ft.PopupMenuButton):
            return

        export_button.items.clear()

        # Item Simples
        simple_export_item = ft.PopupMenuItem(
            text="Exportar em Simples DOCX",
            data="export_simple_docx"
        )
        simple_export_item.on_click = self.export_manager.handle_export_selected # Atribui o mesmo handler
        export_button.items.append(simple_export_item)

        available_templates = self.export_manager.docx_exporter.get_available_templates()
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
                template_item.on_click = self.export_manager.handle_export_selected # Atribui o mesmo handler
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
        manage_templates_item.on_click = self.export_manager.handle_export_selected # Mesmo handler, que tratará 'manage_templates'
        export_button.items.append(manage_templates_item)
            
        safe_control_update(export_button)

    def _handle_toggle_settings_drawer(self, e: Optional[ft.ControlEvent] = None):
        """
        Handler para abrir/fechar o drawer de configurações.

        Controla a largura e a visibilidade do drawer, além de aplicar efeitos visuais
        no botão de configurações.

        Args:
            e (Optional[ft.ControlEvent]): O evento de clique do botão (opcional).
        """
        self._is_drawer_open = not self._is_drawer_open
        self.settings_drawer_container.width = 320 if self._is_drawer_open else 0
        # self.settings_drawer_container.visible = self._is_drawer_open # Alternativa à largura
        
        # Animação suave da borda ou sombra
        if self._is_drawer_open:
            self.settings_drawer_container.border = ft.border.only(left=ft.border.BorderSide(2, theme.PRIMARY))
            self.gui_controls[CTL_SETTINGS_BTN].bgcolor = ft.Colors.with_opacity(0.40, theme.COLOR_ERROR)
        else:
            self.settings_drawer_container.border = None # Remove a borda ao fechar
            self.gui_controls[CTL_SETTINGS_BTN].bgcolor = None

        self.settings_drawer_container.update()
        self.gui_controls[CTL_SETTINGS_BTN].update()
        logger.debug(f"Drawer de configurações {'aberto' if self._is_drawer_open else 'fechado'}.")

    def _toggle_prompt_view(self, e: ft.ControlEvent):
        """
        Handler para o clique no botão 'Prompt Estruturado'.

        Alterna a exibição entre o layout principal da análise e o layout de visualização
        dos prompts estruturados.

        Args:
            e (ft.ControlEvent): O evento de clique do botão.
        """
        #_logger.info("Botão 'Prompt Estruturado' clicado.")
        #show_snackbar(self.page, "Visualização do 'Prompt Estruturado' ainda não implementado.", theme.COLOR_WARNING)
        prompt_save_button = self.gui_controls.get(CTL_PROMPT_SAVE_BTN)
        self._is_prompt_view_active = not self._is_prompt_view_active
        prompt_button = self.gui_controls.get(CTL_PROMPT_STRUCT_BTN)

        if self._is_prompt_view_active:
            logger.info("Ativando visualização do prompt estruturado.")
            # Salva o layout original se ainda não foi salvo (já feito ao inicializar _original_main_layout_container)
            
            # Cria ou obtém o layout de exibição do prompt
            if not self._prompt_display_layout:
                self._prompt_display_layout = self._create_prompt_display_layout()

            # Substitui o conteúdo principal
            if self.controls and self.controls[3] == self._original_main_layout_container: # Verifica se o controle esperado está lá
                self.controls[3] = self._prompt_display_layout
            else:
                logger.error("Estrutura de controle inesperada ao tentar mostrar a visualização do prompt.")
                # Reverter e não fazer nada
                self._is_prompt_view_active = False
                if prompt_button and prompt_button.page:
                    prompt_button.update()
                self.update()
                return

            # Altera o botão "Prompt Estruturado"
            if isinstance(prompt_button, ft.ElevatedButton):
                prompt_button.icon = ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED
                prompt_button.bgcolor = ft.Colors.with_opacity(0.25, theme.COLOR_INFO)
            if isinstance(prompt_save_button, ft.ElevatedButton):
                prompt_save_button.visible = True                
        
        else: # Voltando para a visualização normal
            logger.debug("Desativando visualização do prompt, voltando para análise.")
            # Restaura layout original
            if self._original_main_layout_container and self._prompt_display_layout:
                if self.controls and self.controls[3] == self._prompt_display_layout:
                     self.controls[3] = self._original_main_layout_container
                else:
                    logger.error("Estrutura de controle inesperada ao tentar restaurar a visualização principal.")
                    if prompt_button and prompt_button.page: 
                        prompt_button.update()
                    self.update()
                    return
            
            # Reverte botão "Prompt Estruturado"
            if isinstance(prompt_button, ft.ElevatedButton):
                prompt_button.icon = ft.Icons.EDIT_NOTE_ROUNDED
                prompt_button.bgcolor = None # prompt_button.color = None
            if isinstance(prompt_save_button, ft.ElevatedButton):
                prompt_save_button.visible = False                

        # Atualiza o estado dos botões e a UI
        self._update_button_states() 
        self.update()       

    def _save_edited_prompts_to_cache(self, e: ft.ControlEvent):
        """Salva os prompts editados pelo usuário no cache para uso na próxima análise."""
        logger.info("Salvando prompts editados temporariamente no cache do usuário.")
        self.user_cache = get_user_cache(self.page)
        original_prompts_dict = self.user_cache.get(KEY_SESSION_PROMPTS_DICT)
        if not original_prompts_dict:
            show_snackbar(self.page, "Erro: Prompts originais não encontrados para edição.", theme.COLOR_ERROR)
            return

        # Cria uma cópia profunda para não modificar o original no cache
        edited_prompts_dict = copy.deepcopy(original_prompts_dict)

        for name_str, text_field in self._prompt_text_fields.items():
            if name_str in edited_prompts_dict:
                edited_content = text_field.value.replace("[CONTEÚDO_DO_PDF_é_INSERIDO_AQUI]", "\n{input_text}\n")
                edited_prompts_dict[name_str]["content"] = edited_content

        self.user_cache[KEY_USER_CACHE_PROMPTS_EDITED_DATA] = edited_prompts_dict
        self.page.session.set(KEY_SESSION_PROMPT_IS_EDITED_FLAG, True)

        show_snackbar(self.page, "Prompt modificado salvo! Ele será usado na próxima análise.", theme.COLOR_SUCCESS, duration=5000)
        
    def _restore_original_prompts_and_notify(self):
        """Restaura o prompt original removendo a versão editada do cache."""
        if not self._is_view_usable():
            logger.debug("_restore_original_prompts_and_notify ignorado: view não montada ou page inválida.")
            return

        logger.info("Restaurando prompt original após análise com versão editada.")
        self.user_cache = get_user_cache(self.page)
        if self.user_cache.pop(KEY_USER_CACHE_PROMPTS_EDITED_DATA, None):
            logger.debug("Dados de prompt editado removidos do cache.")
        if self.page.session.contains_key(KEY_SESSION_PROMPT_IS_EDITED_FLAG):
            self.page.session.remove(KEY_SESSION_PROMPT_IS_EDITED_FLAG)
            logger.debug("Flag de prompt editado removida da sessão.")

        # Força a recriação da view de prompt na próxima vez que for acessada
        self._prompt_display_layout = None
        self._prompt_text_fields.clear()
        logger.debug("Layout de exibição de prompt invalidado para forçar recarregamento visual.")

        show_snackbar(self.page, "Análise concluída. O prompt original foi restaurado para futuras análises.", theme.COLOR_INFO, duration=6000)

    # --- Lógica de Atualização da UI (Métodos Internos) ---
    def _update_active_model_button(self):
        """
        Atualiza o texto do TextButton que mostra o modelo LLM ativo.
        """
        settings = self.page.session.get(KEY_SESSION_NC_ANALYZE_SETTINGS) or {}
        model_name = settings.get("llm_model", "N/D")
        
        button = self.gui_controls.get(CTL_TEXT_MODEL_BTN)
        if isinstance(button, ft.TextButton):
            button.text = f"Modelo: {model_name}"
            safe_control_update(button)
        logger.debug(f"Botão de modelo ativo atualizado para: {model_name}")

    def _update_button_states(self):
        """
        Atualiza o estado (habilitado/desabilitado) dos botões da UI com base no estado atual da view.

        Os botões são habilitados ou desabilitados dinamicamente para guiar o usuário
        através do fluxo de trabalho (carregar, processar, analisar, exportar).
        """
        if not self._is_view_usable():
            logger.debug("_update_button_states ignorado: view não montada ou page inválida.")
            return

        barra_main_btns = [CTL_UPLOAD_BTN, CTL_PROCESS_BTN, CTL_ANALYZE_BTN, CTL_PROMPT_STRUCT_BTN, CTL_RESTART_BTN, CTL_EXPORT_BTN, CTL_SETTINGS_BTN]

        if self._is_prompt_view_active:
            for key in barra_main_btns:
                if key in self.gui_controls and key != CTL_PROMPT_STRUCT_BTN:
                    self.gui_controls[key].disabled = True
                elif key in self.gui_controls and key == CTL_PROMPT_STRUCT_BTN:
                    self.gui_controls[key].disabled = False
                    
                safe_control_update(self.gui_controls[key])

            logger.debug("Estados dos botões atualizados (Prompt View Ativa).")
            return # Termina aqui se a visualização do prompt estiver ativa

        files_exist = bool(self.page.session.get(KEY_SESSION_PDF_FILES_ORDERED))
        llm_response_exists = bool(self.user_cache.get(KEY_SESSION_PDF_LLM_RESPONSE))

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

        self.llm_result_title.visible = llm_response_exists
        
        if not self.gui_controls[CTL_LLM_STATUS_INFO].value or self.gui_controls[CTL_LLM_STATUS_INFO].color != theme.COLOR_ERROR:
            if not self._files_processed:
                self.gui_controls[CTL_LLM_STATUS_INFO].value = "Aguardando para exibir os resultados..."
            elif not llm_response_exists:
                self.gui_controls[CTL_LLM_STATUS_INFO].value = "Clique em 'Solicitar Análise' para prosseguir "

        # Força atualização dos botões
        llm_btns = [CTL_LLM_STATUS_INFO, CTL_LLM_STRUCTURED_RESULT_DISPLAY]
        for btn_key in barra_main_btns + llm_btns:
            if btn_key in self.gui_controls:
                safe_control_update(self.gui_controls[btn_key])

        safe_control_update(self.llm_result_title)

        logger.debug("Estados dos botões atualizados.")

    def _update_processing_metadata_display(self, proc_meta: Optional[Dict[str, Any]] = None):
        """
        Atualiza a exibição dos metadados do processamento de PDF no painel correspondente.

        Args:
            proc_meta (Optional[Dict[str, Any]]): Dicionário opcional contendo os metadados a serem exibidos.
                                                  Se None, tenta obter da sessão.
        """
        if not self._is_view_usable():
            logger.debug("_update_processing_metadata_display ignorado: view não montada ou page inválida.")
            return

        metadata_to_display = proc_meta or self.page.session.get(KEY_SESSION_PROCESSING_METADATA)
        
        if not metadata_to_display:
            self.file_list_manager.update_metadata_display(None)
        else:
            # Mapeamento de chaves para labels amigáveis
            labels = [
                ("total_pages_processed",                        "Páginas totais Processadas"),
                ("relevant_pages_global_keys_formatted",         "Páginas Relevantes consideradas"),
                #"count_selected_relevant":                      "Qtd. Páginas Selecionadas como Relevantes",
                ("count_discarded_similarity",                   "Páginas Irrelevantes por Similaridade"),
                ("unintelligible_pages_global_keys_formatted",   "Páginas Descartadas (Ininteligíveis)"),
                #"count_discarded_unintelligible":               "Qtd. Páginas Descartadas (Ininteligíveis)",
                ("total_tokens_before_truncation",               "Tokens totais das Páginas Relevantes"),
                ("final_pages_global_keys_formatted",            "Páginas Selecionadas até limite de tokens"),
                #"count_selected_final":                         "Qtd. Páginas Selecionadas até limite de tokens",
                ("final_aggregated_tokens",                      "Tokens totais das Páginas Selecionadas"),
                ("supressed_tokens_percentage",                  "Percentual de Tokens Suprimidos"),
                ("processing_time",                              "Tempo de processamento"),
                ("calculated_embedding_cost_usd",                "Custos de Embeddings")
            ]

            ordered_keys = [key for key, _ in labels]
            labels = {k: v for k, v in labels}
            data_rows = []
 
            calculated_embedding_cost_usd = metadata_to_display.get("calculated_embedding_cost_usd")
            for key in ordered_keys: # A lista `ordered_keys` garante a ordem de exibição
                if key in ["count_selected_relevant", "count_discarded_unintelligible", "count_selected_final"]:
                    continue
 
                if key in metadata_to_display and key in labels:
                    label_text = f"{labels[key]}:"
                    value = metadata_to_display.get(key)
                    
                    if key == "final_pages_global_keys_formatted" and value == metadata_to_display.get("relevant_pages_global_keys_formatted"):
                        continue # Quando não houver supressão de páginas por limites de token
                    
                    if key == "calculated_embedding_cost_usd" and not calculated_embedding_cost_usd:
                        calculated_embedding_cost_usd = 0
 
                    display_value = str(value if value is not None else "N/A")

                    if key == "total_pages_processed":
                        initial_total_tokens = metadata_to_display.get("total_tokens_before_filter", 0)
                        final_total_tokens = metadata_to_display.get("final_aggregated_tokens", 0)
                        if initial_total_tokens != final_total_tokens:
                            display_value = f"{value} ({initial_total_tokens:,} tokens)".replace(",", ".")                        
                    elif key == "supressed_tokens_percentage" and isinstance(value, (int, float)):
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
                    elif key == "calculated_embedding_cost_usd":
                        if not calculated_embedding_cost_usd:
                            continue
                        cost_embeddings_usd_str = f"U$ {calculated_embedding_cost_usd:.4f}"
                        cost_embeddings_brl_str = f"R$ {(calculated_embedding_cost_usd * cotacao_dolar_to_real):.4f}"
                        display_value = f"{cost_embeddings_usd_str} : {cost_embeddings_brl_str}"
                                        
                    data_rows.append((label_text, display_value))
 
            if data_rows:
                metadata_table = CompactKeyValueTable(
                    data=data_rows,
                    key_col_width=290,  # Ajuste a largura da coluna de chaves
                    value_col_width=None, # Deixe None para a coluna de valor expandir ou defina uma largura
                    row_spacing=4,      # Espaçamento entre as "linhas"
                    col_spacing=8,      # Espaçamento entre chave e valor
                    default_text_size=14
                )
                final_metadata_content = ft.Column([
                    ft.Container(height=5),
                    ft.Container(ft.Text("Dados do Processamento:", weight=ft.FontWeight.BOLD, size=14), padding=ft.padding.only(left=20)),
                    ft.Container(metadata_table, padding=ft.padding.only(left=30, top=10, bottom=10))
                ])                

                if metadata_to_display.get("count_discarded_unintelligible", 0) > 0:
                    final_metadata_content.controls.append(
                    ft.Container(
                        ft.Row([
                            ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=theme.COLOR_WARNING),
                            ft.Text("Páginas ininteligíveis detectadas. Considere usar OCR nelas.",
                                    color=theme.COLOR_WARNING, weight=ft.FontWeight.BOLD)
                        ], spacing=5, alignment=ft.MainAxisAlignment.START),
                            padding=ft.padding.only(top=10, left=20, bottom=10)
                        )
                    )
                self.file_list_manager.update_metadata_display(final_metadata_content)

        logger.debug("Procedido: _update_processing_metadata_display")

    def _update_llm_metadata_display(self, llm_meta: Optional[Dict[str, Any]] = None):
        """
        Atualiza a exibição dos metadados da análise LLM no painel correspondente.

        Args:
            llm_meta (Optional[Dict[str, Any]]): Dicionário opcional contendo os metadados a serem exibidos.
                                                  Se None, tenta obter da sessão.
        """
        content_area = self.gui_controls[CTL_LLM_METADATA_CONTENT]
        content_area.controls.clear()
        metadata_to_display = llm_meta or self.page.session.get(KEY_SESSION_LLM_METADATA)
 
        if not metadata_to_display:
            #content_area.controls.append(ft.Text("Nenhum metadado da LLM disponível.", italic=True))
            self.gui_controls[CTL_LLM_METADATA_PANEL].visible = False
        else:
            self.gui_controls[CTL_LLM_METADATA_PANEL].visible = True
            labels = [
                ("input_tokens",         "Tokens de Entrada"),
                ("cached_tokens",        "Tokens em Cache"),
                ("output_tokens",        "Tokens de Resposta"),
                ("reasoning_tokens",     "Tokens de Reflexão"),
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
            
            safe_control_update(self.gui_controls[CTL_LLM_METADATA_PANEL])

        safe_control_update(content_area)
        logger.debug("Procedido: _update_llm_metadata_display")

    def _show_info_balloon_or_result(self, show_balloon: bool, result_data: Optional[Union[str, formatted_initial_analysis]] = None,
                                     is_initial_llm_response: bool = False):
        """
        Controla a visibilidade entre o balão informativo, o resultado LLM em texto puro
        e o display estruturado, exibindo o conteúdo apropriado.

        Args:
            show_balloon (bool): Se True, exibe o balão informativo.
            result_data (Optional[Union[str, formatted_initial_analysis]]): Os dados do resultado da LLM (string ou FormatAnaliseInicial).
                                                                             Ignorado se show_balloon for True.
            is_initial_llm_response (bool): Indica se `result_data` é uma resposta inicial da LLM.
        """
        balloon = self.gui_controls[CTL_LLM_RESULT_INFO_BALLOON]
        text_result = self.gui_controls[CTL_LLM_RESULT_TEXT]
        structured_result = self.gui_controls[CTL_LLM_STRUCTURED_RESULT_DISPLAY]
        warning_balloon = self.gui_controls[CTL_LLM_AI_WARNING_BALLOON]

        # Esconde todos por padrão
        balloon.visible = False
        text_result.visible = False
        structured_result.visible = False
        warning_balloon.visible = False

        if show_balloon:
            balloon.visible = True
        elif isinstance(result_data, formatted_initial_analysis):
            if isinstance(structured_result, LLMStructuredResultDisplay):
                structured_result.update_data(result_data, is_new_llm_response=is_initial_llm_response)
                structured_result.visible = True
                warning_balloon.visible = True
            else:
                logger.error("Controle CTL_LLM_STRUCTURED_RESULT_DISPLAY não é uma instância de LLMStructuredResultDisplay.")
                text_result.value = "Erro interno ao exibir resultado estruturado."
                text_result.visible = True
        elif isinstance(result_data, str):
            text_result.value = result_data
            text_result.visible = True
            warning_balloon.visible = True
        else: # Caso padrão, mostra balão
            balloon.visible = True
            logger.warning(f"Tipo de result_data inesperado: {type(result_data)}")
        
        # Atualiza o container que contém o Stack e outros elementos
        for ctl in [self.llm_result_container, warning_balloon, structured_result]:
            safe_control_update(ctl)
        logger.debug("Procedido: _show_info_balloon_or_result")

    def _reset_processing_and_llm_results(self):
        """
        Limpa os resultados do processamento de PDF e da análise LLM da sessão e do cache do usuário.
        Este método é usado quando a lista de arquivos carregados é alterada, invalidando análises anteriores.
        """
        logger.debug("Resetando resultados de processamento e LLM.")
        
        self.user_cache = get_user_cache(self.page)
        self.user_cache.pop(KEY_SESSION_PDF_AGGREGATED_TEXT_INFO, None)
        self.user_cache.pop(KEY_SESSION_SHARED_DOCUMENT_CONTEXT, None)
        self.user_cache.pop(KEY_SESSION_PDF_LLM_RESPONSE, None)
        self.user_cache.pop(KEY_SESSION_PDF_LLM_RESPONSE_ACTUAL, None)
        self.user_cache.pop(KEY_SESSION_PDF_LLM_RESPONSE_SNAPSHOT_FOR_FEEDBACK, None)
        
        keys_to_clear = [
            KEY_SESSION_PROCESSING_METADATA, KEY_SESSION_LLM_METADATA,
            KEY_SESSION_FEEDBACK_COLLECTED_FOR_CURRENT_ANALYSIS,
            KEY_SESSION_SHARED_PROCESSING_METADATA,
            KEY_SESSION_CHAT_HAS_FILES_OPTIMIZED, KEY_SESSION_HAS_LLM_REPONSE
        ]
        for key in keys_to_clear:
            self._remove_data_session(key)
        
        # Atualiza a GUI para refletir o estado limpo
        self._update_gui_from_state()

    def _reset_llm_results(self):
        """
        Limpa apenas os resultados da análise LLM da sessão e do cache do usuário.
        Este método é usado quando uma nova análise LLM é solicitada, mas o processamento de PDF permanece válido.
        """
        logger.debug("Resetando resultados da LLM.")
        
        self.user_cache = get_user_cache(self.page)
        self.user_cache.pop(KEY_SESSION_PDF_LLM_RESPONSE, None)
        self.user_cache.pop(KEY_SESSION_PDF_LLM_RESPONSE_ACTUAL, None)
        self.user_cache.pop(KEY_SESSION_PDF_LLM_RESPONSE_SNAPSHOT_FOR_FEEDBACK, None)
 
        keys_to_clear = [
            KEY_SESSION_LLM_METADATA,
            KEY_SESSION_FEEDBACK_COLLECTED_FOR_CURRENT_ANALYSIS,
            KEY_SESSION_HAS_LLM_REPONSE
        ]
        for key in keys_to_clear:
            self._remove_data_session(key)
            
        # Atualiza a UI para refletir o estado limpo
        self._update_gui_from_state()

    def _update_gui_from_state(self):
        """
        Atualiza toda a GUI da view com base no estado atual salvo na sessão.
        Este método centraliza todas as chamadas de atualização da GUI, garantindo
        que a interface reflita o estado mais recente dos dados e configurações.
        """
        logger.debug("Atualizando GUI a partir do estado da sessão...")
        if not self._is_view_usable():
            logger.debug("_update_gui_from_state ignorado: view não montada ou page inválida.")
            return
        hide_loading_overlay(self.page)

        # Lógica de carregamento: Prioriza a chave da view, depois a compartilhada.
        if not self.page.session.get(KEY_SESSION_PDF_FILES_ORDERED):
            shared_files = self.page.session.get(KEY_SESSION_SHARED_FILES_ORDERED)
            if shared_files:
                self.page.session.set(KEY_SESSION_PDF_FILES_ORDERED, shared_files)
                logger.info("Contexto de arquivos carregado da sessão compartilhada.")
        
        self.user_cache = get_user_cache(self.page)
        if not self.user_cache.get(KEY_SESSION_PDF_AGGREGATED_TEXT_INFO):
            shared_text = self.user_cache.get(KEY_SESSION_SHARED_DOCUMENT_CONTEXT)
            if shared_text:
                # A chave desta view espera uma tupla, mas só temos o texto. Criamos uma tupla parcial.
                self.user_cache[KEY_SESSION_PDF_AGGREGATED_TEXT_INFO] = shared_text
                logger.info("Contexto de texto carregado da sessão compartilhada.")

        if not self.page.session.get(KEY_SESSION_PROCESSING_METADATA):
            shared_metadata = self.page.session.get(KEY_SESSION_SHARED_PROCESSING_METADATA)
            if shared_metadata:
                self.page.session.set(KEY_SESSION_PROCESSING_METADATA, shared_metadata)
                logger.info("Metadados de processamento carregados da sessão compartilhada.")
                
        # Atualiza flags internas com base na sessão Flet
        self._files_processed = self.page.session.get(KEY_SESSION_CHAT_HAS_FILES_OPTIMIZED) or False
        if not self._files_processed:
            # confere se houve otimização na sessão compartilhada
            processing_metada = self.page.session.get(KEY_SESSION_PROCESSING_METADATA)
            self._files_processed = processing_metada and "relevant_pages_global_keys_formatted" in processing_metada
        self._analysis_requested = self.page.session.get(KEY_SESSION_HAS_LLM_REPONSE) or False
        
        # 2. Chama os métodos de atualização individuais
        # Resincroniza os controles do drawer (ex.: esforço de reflexão) com a sessão:
        # em did_mount a thread de carregamento de configurações (threaded_load_settings)
        # pode já ter concluído após a construção inicial do drawer, então este refresh
        # garante que a UI não fique presa nos valores capturados naquele primeiro instante.
        self.settings_drawer_component.load_settings_into_controls()
        self.file_list_manager.update_display()
        self._update_processing_metadata_display()
        self._update_llm_metadata_display()
        self._update_active_model_button()

        self.user_cache = get_user_cache(self.page)
        # 3. Decide qual conteúdo de resultado LLM exibir
        llm_response_to_show = self.user_cache.get(KEY_SESSION_PDF_LLM_RESPONSE_ACTUAL) or \
                               self.user_cache.get(KEY_SESSION_PDF_LLM_RESPONSE)
        
        is_initial_response = self.page.session.get("is_new_llm_response_flag") or False
        if is_initial_response:
            if self.page.session.contains_key("is_new_llm_response_flag"):
                self.page.session.remove("is_new_llm_response_flag")

        if llm_response_to_show:
            #is_initial_response = not bool(self.user_cache.get(KEY_SESSION_PDF_LLM_RESPONSE_ACTUAL))
            self._show_info_balloon_or_result(False, llm_response_to_show, is_initial_response)
        else:
            self.file_list_manager.expand_container()
            self._show_info_balloon_or_result(True)

        # 4. Atualiza o estado dos botões (que depende das flags atualizadas)
        self._update_button_states()

        # 5. Renderiza todas as alterações na página de uma só vez
        # threading.Timer(0.1, lambda: self.page.update()).start()
        
        # Adquire o Lock global antes de chamar page.go()
        # update_lock = self.page.data.get("global_update_lock")
        # with update_lock:
        #     self.page.update()

        logger.info("Atualização da GUI a partir do estado concluída.")
        
    # --- Gerenciamento de Estado e Limpeza ---
    def _clear_all_data_and_gui(self):
        """
        Limpa todos os dados da sessão relacionados a esta view e reseta a UI para o estado inicial.

        Isso inclui o cache do servidor, dados de arquivos, metadados de processamento e LLM,
        e o estado interno da view. Também limpa o diretório de uploads temporários.
        """
        logger.info("Limpando todos os dados e resetando UI da Análise PDF.")
        
        # Limpa o cache do servidor para este usuário
        keys_to_preserve = [
            KEY_SESSION_PROMPTS_FINAL,
            KEY_SESSION_PROMPTS_DICT,
            KEY_SESSION_LIST_TO_PROMPTS
        ]
        cache_to_clear = [KEY_SESSION_PDF_LLM_RESPONSE_SNAPSHOT_FOR_FEEDBACK, KEY_SESSION_PDF_LLM_RESPONSE_ACTUAL,
            KEY_SESSION_PDF_LLM_RESPONSE, KEY_SESSION_PDF_AGGREGATED_TEXT_INFO, KEY_SESSION_SHARED_DOCUMENT_CONTEXT]
        for _key in cache_to_clear:
            self.user_cache.pop(_key, None)

        # Limpa sessão relacionada a esta view
        keys_to_clear_from_session = [
            KEY_SESSION_CURRENT_BATCH_NAME, KEY_SESSION_PDF_FILES_ORDERED,
            KEY_SESSION_PROCESSING_METADATA, KEY_SESSION_LLM_METADATA,
            KEY_SESSION_FEEDBACK_COLLECTED_FOR_CURRENT_ANALYSIS,
            KEY_SESSION_SHARED_FILES_ORDERED, KEY_SESSION_SHARED_PROCESSING_METADATA,
            KEY_SESSION_CHAT_HAS_FILES_OPTIMIZED, KEY_SESSION_HAS_LLM_REPONSE
        ]
        for key in keys_to_clear_from_session:
            self._remove_data_session(key)
        
        # Reseta estado interno
        self._files_processed = False
        self._analysis_requested = False
        
        # Limpa diretório de uploads temporários, se o ManagedFilePicker estiver configurado
        # if self.managed_file_picker: self.managed_file_picker.clear_upload_directory()

        # Chama o método central para atualizar toda a GUI para o estado limpo
        self._update_gui_from_state()
        #self._show_info_balloon_or_result(show_balloon=True)

# --- Classe Interna com GUI_build complementar ---
class LLMStructuredResultDisplay(ft.Column):
    """
    Componente Flet para exibir e editar os resultados estruturados da análise LLM.

    Apresenta os dados em um formulário editável, permitindo ao usuário revisar
    e ajustar os campos antes da exportação.
    """
    def __init__(self, page: ft.Page):
        """
        Inicializa o display de resultados estruturados.

        Args:
            page (ft.Page): A página Flet.
        """
        super().__init__(
            scroll=ft.ScrollMode.ADAPTIVE,
            expand=True,
            spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            #horizontal_alignment=ft.CrossAxisAlignment.CENTER # Centraliza os cards
        )
        self.page = page
        self.data: Optional[formatted_initial_analysis] = None
        self.original_llm_data_snapshot: Optional[formatted_initial_analysis] = None
        self.gui_fields: Dict[str, ft.Control] = {}

        # Referências para controles que precisam ser atualizados dinamicamente (ex: municípios)
        self.dropdown_uf_origem: Optional[ft.Dropdown] = None
        self.dropdown_municipio_origem: Optional[ft.Dropdown] = None
        self.dropdown_uf_fato: Optional[ft.Dropdown] = None
        self.dropdown_municipio_fato: Optional[ft.Dropdown] = None

        self.user_cache = get_user_cache(self.page)

    def _create_justificativa_icon(self, justificativa: Optional[str]) -> ft.IconButton:
        """
        Cria um ícone informativo com tooltip para exibir justificativas.

        Args:
            justificativa (Optional[str]): A string de justificativa a ser exibida no tooltip.
 
        Returns:
            ft.IconButton: Um ft.IconButton configurado.
        """
        return ft.IconButton(
            icon=ft.Icons.INFO_OUTLINE_ROUNDED,
            tooltip=justificativa if justificativa else "Justificativa não fornecida.",
            icon_size=18,
            opacity=0.7 if justificativa else 0.3,
            disabled=not bool(justificativa),
            padding=ft.padding.only(left=0, right=1),
        )
 
    def _atualizar_municipios_origem(self, e: Optional[ft.ControlEvent] = None):
        """
        Atualiza as opções do dropdown de municípios de origem com base na UF selecionada.
 
        Args:
            e (Optional[ft.ControlEvent]): Evento opcional (se chamado por um evento de UI).
        """
        if self.dropdown_uf_origem and self.dropdown_municipio_origem:
            selected_uf = self.dropdown_uf_origem.value
            if selected_uf:
                municipios = municipios_list[selected_uf]
                self.dropdown_municipio_origem.options = [ft.dropdown.Option(m) for m in municipios]
                # Tenta manter o valor se ainda for válido, ou reseta
                current_municipio_val = self.dropdown_municipio_origem.value
                if current_municipio_val not in [opt.key for opt in self.dropdown_municipio_origem.options]:
                    self.dropdown_municipio_origem.value = None
            else:
                self.dropdown_municipio_origem.options = []
                self.dropdown_municipio_origem.value = None
 
            if e is not None: # 'e' indica chamada por evento de usuário
                safe_control_update(self.dropdown_municipio_origem)
 
    def _atualizar_municipios_fato(self, e: Optional[ft.ControlEvent] = None):
        """
        Atualiza as opções do dropdown de municípios do fato com base na UF selecionada.
 
        Args:
            e (Optional[ft.ControlEvent]): Evento opcional (se chamado por um evento de UI).
        """
        if self.dropdown_uf_fato and self.dropdown_municipio_fato:
            selected_uf = self.dropdown_uf_fato.value
            if selected_uf:
                municipios = municipios_list[selected_uf]
                self.dropdown_municipio_fato.options = [ft.dropdown.Option(m) for m in municipios]
                current_municipio_val = self.dropdown_municipio_fato.value
                if current_municipio_val not in [opt.key for opt in self.dropdown_municipio_fato.options]:
                    self.dropdown_municipio_fato.value = None
            else:
                self.dropdown_municipio_fato.options = []
                self.dropdown_municipio_fato.value = None
            
            if e is not None: # 'e' indica chamada por evento de usuário
                safe_control_update(self.dropdown_municipio_fato)
 
    def update_data(self, data_to_display_in_gui: formatted_initial_analysis, is_new_llm_response: bool = False):
        """
        Atualiza o display com novos dados de análise estruturada.
        Popula os campos da UI e gerencia o snapshot original para feedback.

        Args:
            data_to_display_in_gui (formatted_initial_analysis): O objeto FormatAnaliseInicial para exibir na UI.
                                                                Pode ser None para limpar a UI.
            is_new_llm_response (bool): True se data_to_display_in_gui é uma resposta fresca da LLM,
                                        False caso contrário (ex: restauração de sessão).
        """
        logger.debug(f"LLMStructuredResultDisplay.update_data chamado. is_new_llm_response={is_new_llm_response}, data_is_none={data_to_display_in_gui is None}")
        
        if data_to_display_in_gui is None:
            logger.warning("LLMStructuredResultDisplay.update_data: data_to_display_in_gui é None. Limpando display e snapshots.")
            self.original_llm_data_snapshot = None
            self.data = None
            self.user_cache[KEY_SESSION_PDF_LLM_RESPONSE_SNAPSHOT_FOR_FEEDBACK] = None
            self.controls.clear()
            self.gui_fields.clear()

            safe_control_update(self)
            return

        # 1. Define self.data (o que será usado para construir/atualizar a UI)
        self.data = data_to_display_in_gui

        # 2. Gerencia o original_llm_data_snapshot
        self.user_cache = get_user_cache(self.page)
        if is_new_llm_response:
            # É uma resposta fresca da LLM, este é o nosso "original" definitivo.
            self.original_llm_data_snapshot = data_to_display_in_gui.model_copy(deep=True)
            self.user_cache[KEY_SESSION_PDF_LLM_RESPONSE_SNAPSHOT_FOR_FEEDBACK] = self.original_llm_data_snapshot
            logger.debug("Snapshot dos dados ORIGINAIS da LLM capturado e salvo na sessão (is_new_llm_response=True).")
        else:
            # Não é uma nova resposta LLM (ex: restauração de sessão, ou após edição do usuário).
            # Tentamos carregar o snapshot da sessão dedicada.
            snapshot_from_session = self.user_cache.get(KEY_SESSION_PDF_LLM_RESPONSE_SNAPSHOT_FOR_FEEDBACK)
            if snapshot_from_session and isinstance(snapshot_from_session, formatted_initial_analysis):
                self.original_llm_data_snapshot = snapshot_from_session
                logger.debug("Snapshot original da LLM restaurado da sessão dedicada.")
            else:
                # Se não há snapshot na sessão dedicada, e não é uma nova resposta LLM,
                # este é o caso "tardio". Usamos os dados atuais (data_to_display_in_gui) como base, com warning.
                self.original_llm_data_snapshot = data_to_display_in_gui.model_copy(deep=True)
                logger.warning("LLMStructuredResultDisplay.update_data: Snapshot original não encontrado na sessão dedicada e dados não são 'is_new_llm_response'. "
                                "Capturando snapshot com dados atuais da UI como base. O feedback pode ser impreciso se os dados já foram editados anteriormente e o snapshot original não foi salvo corretamente.")
                # Opcional: Salvar este snapshot "tardio" na sessão dedicada também, para consistência na sessão atual,
                # mas sabendo que pode não ser o "verdadeiro" original da LLM.
                self.user_cache[KEY_SESSION_PDF_LLM_RESPONSE_SNAPSHOT_FOR_FEEDBACK] = self.original_llm_data_snapshot

        # Limpa controles antigos e reconstrói a UI
        self.controls.clear()
        self.gui_fields.clear()

        # --- CRIAÇÃO DOS CAMPOS GUI ---
        self._create_gui_fields()

        # --- CRIAÇÃO DOS CARDS ---
        self._create_identification_card()
        self._create_fact_details_card()
        self._create_classification_card()
        self._create_observations_card()

        safe_control_update(self)

    def _create_field_with_icon(self, field_control, justificativa_text):
        """Cria um campo com ícone de justificativa de forma consistente."""
        return ft.Row(
            [
                field_control,
                self._create_justificativa_icon(justificativa_text)
            ],
            expand=True,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )
        return ft.Container(
            content=ft.Row([
                field_control,
                self._create_justificativa_icon(justificativa_text)
            ], 
            expand=True,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER),
            expand=True
        )

    def _create_gui_fields(self):
        """Cria todos os campos da interface de forma padronizada."""
        
        self.user_cache = get_user_cache(self.page)
        lists_to_prompts = self.user_cache.get(KEY_SESSION_LIST_TO_PROMPTS)

        key_lists = ['tipos_doc', 'origens_doc', 'tipos_locais',
        'areas_de_atribuição', 'tipos_a_autuar', 'assuntos_re',
        'materias_prometheus', 'destinacoes_completas']

        for k in key_lists:
            if k not in lists_to_prompts:
                msg_erro = "Chave(s) ausente(s) nas referências de Lista para composição de prompts."
                logger.error(msg_erro)
                raise Exception(msg_erro)

        tipos_doc = lists_to_prompts['tipos_doc']
        origens_doc = lists_to_prompts['origens_doc']
        tipos_locais = lists_to_prompts['tipos_locais']
        areas_de_atribuição = lists_to_prompts['areas_de_atribuição']
        tipos_a_autuar = lists_to_prompts['tipos_a_autuar']
        assuntos_re = lists_to_prompts['assuntos_re']
        materias_prometheus = lists_to_prompts['materias_prometheus']
        destinacoes_completas = lists_to_prompts['destinacoes_completas']

        # === Campos de Identificação ===
        self.gui_fields["descricao_geral"] = ft.TextField(
            label="Descrição Geral", 
            value=self.data.descricao_geral, 
            multiline=True, min_lines=2, 
            dense=True, expand=True
        )
        
        self.gui_fields["tipo_documento_origem"] = ft.Dropdown(
            label="Tipo Documento Origem",
            options=[ft.dropdown.Option(td) for td in tipos_doc],
            value=self.data.tipo_documento_origem if self.data.tipo_documento_origem in tipos_doc else "",
            dense=True, expand=True, width=500
        )
        
        self.gui_fields["orgao_origem"] = ft.Dropdown(
            label="Órgão de Origem",
            options=[ft.dropdown.Option(oo) for oo in origens_doc],
            value=self.data.orgao_origem if self.data.orgao_origem in origens_doc else "",
            dense=True, expand=True, width=500
        )

        # Dropdowns de UF e Município (Origem)
        self.dropdown_uf_origem = ft.Dropdown(
            label="UF de Origem", 
            options=[ft.dropdown.Option(uf) for uf in ufs_list],
            value=self.data.uf_origem if self.data.uf_origem in ufs_list else "",
            on_change=self._atualizar_municipios_origem, 
            width=145, dense=True
        )
        self.gui_fields["uf_origem"] = self.dropdown_uf_origem

        municipios_origem_init = municipios_list[self.data.uf_origem] if self.data.uf_origem else []
        self.dropdown_municipio_origem = ft.Dropdown(
            label="Município de Origem",
            options=[ft.dropdown.Option(m) for m in municipios_origem_init],
            value=self.data.municipio_origem if self.data.municipio_origem else "",
            dense=True, width=320, expand=True
        )
        self.gui_fields["municipio_origem"] = self.dropdown_municipio_origem
        self._atualizar_municipios_origem()

        # === Campos de Detalhes do Fato ===
        self.gui_fields["resumo_fato"] = ft.TextField(
            label="Resumo do Fato", 
            value=self.data.resumo_fato, 
            multiline=True, min_lines=3, 
            dense=True, expand=True
        )

        # Dropdowns de UF e Município (Fato)
        self.dropdown_uf_fato = ft.Dropdown(
            label="UF do Fato", 
            options=[ft.dropdown.Option(uf) for uf in ufs_list],
            value=self.data.uf_fato if self.data.uf_fato in ufs_list else "",
            on_change=self._atualizar_municipios_fato, 
            width=145, dense=True
        )
        self.gui_fields["uf_fato"] = self.dropdown_uf_fato

        municipios_fato_init = municipios_list[self.data.uf_fato] if self.data.uf_fato else []
        self.dropdown_municipio_fato = ft.Dropdown(
            label="Município do Fato",
            options=[ft.dropdown.Option(m) for m in municipios_fato_init],
            value=self.data.municipio_fato if self.data.municipio_fato else "",
            dense=True, width=320, expand=True
        )
        self.gui_fields["municipio_fato"] = self.dropdown_municipio_fato
        self._atualizar_municipios_fato()

        self.gui_fields["tipo_local"] = ft.Dropdown(
            label="Tipo de Local",
            options=[ft.dropdown.Option(tl) for tl in tipos_locais],
            value=self.data.tipo_local if self.data.tipo_local in tipos_locais else "",
            dense=True, expand=True, width=500
        )

        valor_apuracao_str = f"{self.data.valor_apuracao:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if isinstance(self.data.valor_apuracao, float) else str(self.data.valor_apuracao)
        self.gui_fields["valor_apuracao"] = ft.TextField(
            label="Valor da Apuração (R$)", 
            value=valor_apuracao_str, 
            keyboard_type=ft.KeyboardType.NUMBER,
            prefix_text="R$ ", height=60,
            dense=True, expand=True, width=500
        )

        self.gui_fields["pessoas_envolvidas"] = ft.TextField(
            label="Pessoas Envolvidas (Nome - CPF/CNPJ - Tipo)", 
            value="\n".join([
                f"{p.nome} - {p.cpf or p.cnpj or 'S/CPF/CNPJ'} - {p.papel}" 
                for p in self.data.pessoas_envolvidas
            ]) if self.data.pessoas_envolvidas else "", 
            multiline=True, min_lines=2, 
            hint_text="Uma pessoa por linha: Nome - CPF/CNPJ - Tipo (conforme lista de referência)", 
            dense=True, expand=True
        )

        self.gui_fields["linha_do_tempo"] = ft.TextField(
            label="Linha do Tempo (Evento - Data)", 
            value="\n".join(self.data.linha_do_tempo) if self.data.linha_do_tempo else "", 
            multiline=True, min_lines=2, 
            hint_text="Um evento por linha: Descrição do Evento - DD/MM/AAAA", 
            dense=True, expand=True
        )

        # === Campos de Classificação ===
        self.gui_fields["area_atribuicao"] = ft.Dropdown(
            label="Área de Atribuição", 
            options=[ft.dropdown.Option(aa) for aa in areas_de_atribuição],
            value=self.data.area_atribuicao if self.data.area_atribuicao in areas_de_atribuição else "",
            dense=True, expand=True, width=500
        )

        self.gui_fields["destinacao"] = ft.Dropdown(
            label="Destinação", 
            options=[ft.dropdown.Option(d) for d in destinacoes_completas],
            value=self.data.destinacao if self.data.destinacao in destinacoes_completas else "",
            dense=True, expand=True, width=500
        )

        self.gui_fields["tipo_a_autuar"] = ft.Dropdown(
            label="Tipo a Autuar", 
            options=[ft.dropdown.Option(ta) for ta in tipos_a_autuar],
            value=self.data.tipo_a_autuar if self.data.tipo_a_autuar in tipos_a_autuar else "",
            dense=True, expand=True, width=500
        )

        self.gui_fields["tipificacao_penal"] = ft.TextField(
            label="Tipificação Penal", height=60,
            value=self.data.tipificacao_penal, 
            dense=True, expand=True, width=500
        )

        self.gui_fields["materia_especial"] = ft.Dropdown(
            label="Tratamento especial", 
            options=[ft.dropdown.Option(mp) for mp in materias_prometheus],
            value=self.data.materia_especial if self.data.materia_especial in materias_prometheus else "",
            dense=True, expand=True, width=500
        )

        self.gui_fields["assunto_re"] = ft.Dropdown(
            label="Assunto (RE)", 
            options=[ft.dropdown.Option(ar) for ar in assuntos_re],
            value=self.data.assunto_re if self.data.assunto_re in assuntos_re else "",
            dense=True, expand=True, width=500
        )

        # === Campo de Observações ===
        self.gui_fields["observacoes"] = ft.TextField(
            label="Observações", 
            value=self.data.observacoes, 
            multiline=True, min_lines=2, 
            dense=True, expand=True
        )

    def _create_identification_card(self):
        """Cria o card de Identificação do Documento."""
        id_doc_card_content = ft.Column([
            ft.ResponsiveRow([
                ft.Column(col=12, controls=[self.gui_fields["descricao_geral"]])
            ]),
            ft.ResponsiveRow([
                ft.Column(
                    col={"lg": 4, "md": 6, "sm": 12}, 
                    controls=[
                        ft.Row([
                            self.gui_fields["tipo_documento_origem"], 
                            self._create_justificativa_icon(self.data.justificativa_tipo_documento_origem)
                        ], alignment=ft.MainAxisAlignment.START, expand=True)
                    ]
                ),
                ft.Column(
                    col={"lg": 4, "md": 6, "sm": 12}, 
                    controls=[
                        ft.Row([
                            self.gui_fields["orgao_origem"], 
                            self._create_justificativa_icon(self.data.justificativa_orgao_origem)
                        ], alignment=ft.MainAxisAlignment.START, expand=True)
                    ]
                ),
                ft.Column(
                    col={"lg": 4, "md": 6, "sm": 12}, 
                    controls=[
                        ft.Row([
                            self.dropdown_uf_origem, 
                            self.dropdown_municipio_origem, 
                            self._create_justificativa_icon(self.data.justificativa_municipio_uf_origem)
                        ], spacing=5, alignment=ft.MainAxisAlignment.START, expand=True)
                    ]
                )
            ], vertical_alignment=ft.CrossAxisAlignment.START)
        ], spacing=12)
        
        id_doc_card = CardWithHeader(
            title="Identificação do Documento", 
            content=id_doc_card_content, 
            header_bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.OUTLINE), 
            expand=True
        )
        self.controls.append(id_doc_card)
        
    def _create_fact_details_card(self):
        """Cria o card de Detalhes do Fato."""
        det_fato_card_content = ft.Column([
            ft.ResponsiveRow([
                ft.Column(col=12, controls=[self.gui_fields["resumo_fato"]])
            ]),
            ft.ResponsiveRow([
                ft.Column(
                    col={"lg": 4, "md": 6, "sm": 12}, 
                    controls=[
                        ft.Row([
                            self.dropdown_uf_fato, 
                            self.dropdown_municipio_fato, 
                            self._create_justificativa_icon(self.data.justificativa_municipio_uf_fato)
                        ], spacing=5, alignment=ft.MainAxisAlignment.START, expand=True)
                    ]
                ),
                ft.Column(
                    col={"lg": 4, "md": 6, "sm": 12}, 
                    controls=[
                        ft.Row([
                            self.gui_fields["tipo_local"], 
                            self._create_justificativa_icon(self.data.justificativa_tipo_local)
                        ], alignment=ft.MainAxisAlignment.START, expand=True)
                    ]
                ),
                ft.Column(
                    col={"lg": 4, "md": 6, "sm": 12}, 
                    controls=[
                        ft.Row([
                            self.gui_fields["valor_apuracao"], 
                            self._create_justificativa_icon(self.data.justificativa_valor_apuracao)
                        ], alignment=ft.MainAxisAlignment.START, expand=True)
                    ]
                ),
            ], vertical_alignment=ft.CrossAxisAlignment.START),
            ft.ResponsiveRow([
                ft.Column(col=12, controls=[self.gui_fields["pessoas_envolvidas"]])
            ]),
            ft.ResponsiveRow([
                ft.Column(col=12, controls=[self.gui_fields["linha_do_tempo"]])
            ]),
        ], spacing=12)

        det_fato_card = CardWithHeader(
            title="Detalhes do Fato", 
            content=det_fato_card_content, 
            header_bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.OUTLINE), 
            expand=True
        )
        self.controls.append(det_fato_card)

    def _create_classification_card(self):
        """Cria o card de Classificação e Encaminhamento."""
        class_enc_card_content = ft.Column([
            ft.ResponsiveRow([
                ft.Column(
                    col={"lg": 4, "md": 6, "sm": 12},
                    controls=[
                        ft.Row([
                            self.gui_fields["area_atribuicao"],
                            self._create_justificativa_icon(self.data.justificativa_area_atribuicao)
                        ], expand=True)
                    ]
                ),
                ft.Column(
                    col={"lg": 4, "md": 6, "sm": 12},
                    controls=[
                        ft.Row([
                            self.gui_fields["destinacao"],
                            self._create_justificativa_icon(self.data.justificativa_destinacao)
                        ], expand=True)
                    ]
                ),
                ft.Column(
                    col={"lg": 4, "md": 6, "sm": 12},
                    controls=[
                        ft.Row([
                            self.gui_fields["tipo_a_autuar"],
                            self._create_justificativa_icon(self.data.justificativa_tipo_a_autuar)
                        ], expand=True)
                    ]
                ),
            ]),
            ft.ResponsiveRow([
                ft.Column(
                    col={"lg": 4, "md": 6, "sm": 12},
                    controls=[
                        ft.Row([
                            self.gui_fields["tipificacao_penal"],
                            self._create_justificativa_icon(self.data.justificativa_tipificacao_penal)
                        ], expand=True)
                    ]
                ),
                ft.Column(
                    col={"lg": 4, "md": 6, "sm": 12},
                    controls=[
                        ft.Row([
                            self.gui_fields["materia_especial"],
                            self._create_justificativa_icon(self.data.justificativa_materia_especial)
                        ], expand=True)
                    ]
                ),
                ft.Column(
                    col={"lg": 4, "md": 6, "sm": 12},
                    controls=[
                        ft.Row([
                            self.gui_fields["assunto_re"],
                            self._create_justificativa_icon(self.data.justificativa_assunto_re)
                        ], expand=True)
                    ]
                ),
            ]),
        ], spacing=12)

        class_enc_card = CardWithHeader(
            title="Classificação e Encaminhamento", 
            content=class_enc_card_content, 
            header_bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.OUTLINE), 
            expand=True
        )
        self.controls.append(class_enc_card)

    def _create_observations_card(self):
        """Cria o card de Observações Adicionais."""
        obs_card_content = ft.Column([
            ft.ResponsiveRow([
                ft.Column(col=12, controls=[self.gui_fields["observacoes"]])
            ])
        ], spacing=10)

        obs_card = CardWithHeader(
            title="Observações Adicionais", 
            content=obs_card_content, 
            header_bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.OUTLINE), 
            expand=True
        )
        self.controls.append(obs_card)

    def get_current_form_data(self, validate_for_export: bool = False) -> Union[Optional[formatted_initial_analysis], List[str]]:
        """
        Coleta os dados atuais dos campos da UI, atualiza self.data.
        Se validate_for_export for True, valida campos obrigatórios para exportação.
 
        Returns:
            - FormatAnaliseInicial: se os dados são válidos (ou validação não solicitada).
            - List[str]: Lista de nomes de campos inválidos/vazios se validate_for_export é True e há erros.
            - None: Se self.data base não estiver definido.
        """
        if not self.data: # Se não há dados base (ex: LLM não retornou nada)
            logger.warning("get_current_form_data: self.data não está definido. Não é possível coletar dados da GUI.")
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
        logger.debug(f"Campos definidos como obrigatórios para exportação: {required_fields_for_export}")
 
        for field_name, control in self.gui_fields.items():
            value = None
            is_dropdown = isinstance(control, ft.Dropdown)
            if isinstance(control, (ft.TextField, ft.Dropdown)):
                value = control.value
                if field_name not in ['descricao_geral', 'resumo_fato', 'pessoas_envolvidas', 'linha_do_tempo', 'observacoes']:
                    logger.debug(f"Coletando para '{field_name}': '{value}' (Tipo: {type(value)}, É Dropdown: {is_dropdown})")
            
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
                    logger.warning(f"Campo obrigatório '{field_name}' está vazio. Valor atual: '{value}'")
                    invalid_fields_for_export.append((field_name, control))
 
            # Tratamentos específicos de tipo (continua como antes)
            if field_name == "valor_apuracao":
                value = clean_and_convert_to_float(value)
            elif field_name == "linha_do_tempo" and isinstance(value, str):
                value = convert_to_list_of_strings(value)
            elif field_name == "pessoas_envolvidas" and isinstance(value, str):
                parsed_pessoas = []
                for line in value.split('\n'):
                    line = line.strip()
                    if not line: continue
                    parts = [p.strip() for p in line.split(' - ')]
                    nome = parts[0] if len(parts) > 0 else line
                    doc = ""
                    papel = ""
                    if len(parts) == 2:
                        papel = parts[1]
                    elif len(parts) >= 3:
                        papel = parts[-1]
                        doc = " - ".join(parts[1:-1])
                    
                    pessoa_dict = {"nome": nome, "papel": papel, "cpf": None, "cnpj": None}
                    if doc and doc.upper() not in ["S/CPF/CNPJ", "NONE", "NULL", ""]:
                        clean_doc = ''.join(filter(str.isdigit, doc))
                        if len(clean_doc) > 11:
                            pessoa_dict["cnpj"] = doc
                        else:
                            pessoa_dict["cpf"] = doc
                    parsed_pessoas.append(pessoa_dict)
                value = parsed_pessoas    

            collected_values_from_ui[field_name] = value
 
        if validate_for_export and invalid_fields_for_export:
            logger.warning(f"Validação para exportação falhou. Campos vazios: {[f[0] for f in invalid_fields_for_export]}")
            # Retorna a lista de tuplas (nome_do_campo, instancia_do_controle)
            return invalid_fields_for_export
 
        # Se passou na validação (ou não foi solicitada), prossiga para criar o objeto
        # final_data_for_pydantic = {}
        # if self.data:
        #    final_data_for_pydantic = self.data.model_dump()
        
        # Começa com uma cópia do snapshot original para pegar as justificativas e outros campos não na UI
        if self.original_llm_data_snapshot:
            final_data_for_pydantic = self.original_llm_data_snapshot.model_dump()
        else: # Fallback se original_llm_data_snapshot for None (não deveria acontecer se update_data foi chamado com dados)
            final_data_for_pydantic = {}
 
        final_data_for_pydantic.update(collected_values_from_ui)
 
        for pydantic_field_name in formatted_initial_analysis.model_fields.keys():
            # Se não foi coletado da UI e não estava no snapshot original (improvável para campos principais),
            # pegue o valor default do modelo Pydantic se existir, ou defina como None.
            # O model_dump() do snapshot já cuida disso.
            # Essa parte é mais para garantir que não haja chaves ausentes se a lógica mudar.
            if pydantic_field_name not in final_data_for_pydantic:
                #if hasattr(self.data, pydantic_field_name):
                #    final_data_for_pydantic[pydantic_field_name] = getattr(self.data, pydantic_field_name)
                if hasattr(self.original_llm_data_snapshot, pydantic_field_name) and self.original_llm_data_snapshot:
                     final_data_for_pydantic[pydantic_field_name] = getattr(self.original_llm_data_snapshot, pydantic_field_name)
                elif formatted_initial_analysis.model_fields[pydantic_field_name].default is not Ellipsis: # type: ignore
                     final_data_for_pydantic[pydantic_field_name] = formatted_initial_analysis.model_fields[pydantic_field_name].default
                else:
                     final_data_for_pydantic[pydantic_field_name] = None
        try:
            logger.debug(f"Dados para instanciar FormatAnaliseInicial: {final_data_for_pydantic}")
 
            self.data = formatted_initial_analysis(**final_data_for_pydantic)  # Atualiza o self.data da instância com os dados atuais da UI, já validados por Pydantic
            logger.debug("Dados do formulário estruturado coletados, validados por Pydantic, e self.data atualizado.")
 
            # Atualiza também a sessão com a representação mais recente (objeto Pydantic)
            self.user_cache = get_user_cache(self.page)
            self.user_cache[KEY_SESSION_PDF_LLM_RESPONSE_ACTUAL] = self.data
            logger.debug("KEY_SESSION_PDF_LLM_RESPONSE atualizado na sessão com os dados da GUI.")
            return self.data
        except Exception as pydantic_error: # Use ValidationError de Pydantic se importado
            logger.error(f"Erro de validação Pydantic FINAL ao criar FormatAnaliseInicial: {pydantic_error}", exc_info=False)
            # ... (logar erros pydantic detalhados)
            if hasattr(pydantic_error, 'errors'): # Se for ValidationError do Pydantic
                 for error in pydantic_error.errors():
                    logger.error(f"  - Pydantic Detail: Campo: {'.'.join(map(str, error['loc'])) if error.get('loc') else 'N/A'}, Erro: {error['msg']}")

            if validate_for_export:
                return [("pydantic_validation_error_final", None)] 
            return None

# --- Classes Internas para Gerenciamento ---
class InternalAnalysisController:
    """
    Controla o fluxo de processamento de PDF e análise LLM.

    Gerencia as etapas de extração de texto, pré-processamento, análise de similaridade,
    classificação, agregação de texto e a chamada ao orquestrador de IA para análise LLM.
    Também lida com a atualização do estado da UI e o registro de métricas.
    """
    def __init__(self, page: ft.Page, gui_controls: Dict[str, ft.Control], parent_view: 'AnalyzePDFViewContent'):
        """
        Inicializa o controlador de análise.

        Args:
            page (ft.Page): A página Flet.
            gui_controls (Dict[str, ft.Control]): Dicionário de controles da UI da view principal.
            parent_view (AnalyzePDFViewContent): Referência à instância da view principal.
        """
        self.page = page
        self.gui_controls = gui_controls
        self.parent_view = parent_view
        self.pdf_analyzer = PDFDocumentAnalyzer()
        self.firestore_client = firestore_client
        self.user_cache = get_user_cache(self.page)

    def _get_current_analysis_settings(self) -> Dict[str, Any]:
        """Busca as configurações de análise específicas para esta view da sessão."""
        settings = self.page.session.get(KEY_SESSION_NC_ANALYZE_SETTINGS)
        if not settings or not isinstance(settings, dict):
            logger.warning("Configurações de 'nc_analyze' não encontradas na sessão. Usando fallbacks.")
            return FALLBACK_ANALYSIS_SETTINGS.copy()

        # Garante que os tipos numéricos estejam corretos
        # None preserva o modo de truncagem automática (calculada em runtime para llm_pf).
        current_settings = settings.copy()
        raw_token_limit = current_settings.get('llm_input_token_limit', FALLBACK_ANALYSIS_SETTINGS['llm_input_token_limit'])
        if raw_token_limit is None:
            current_settings['llm_input_token_limit'] = None
        else:
            try:
                current_settings['llm_input_token_limit'] = int(raw_token_limit)
            except (ValueError, TypeError):
                current_settings['llm_input_token_limit'] = FALLBACK_ANALYSIS_SETTINGS['llm_input_token_limit']

        try:
            current_settings['llm_temperature'] = float(current_settings.get('llm_temperature', FALLBACK_ANALYSIS_SETTINGS['llm_temperature']))
        except (ValueError, TypeError):
            current_settings['llm_temperature'] = FALLBACK_ANALYSIS_SETTINGS['llm_temperature']
        try:
            current_settings['vectorization_model'] = current_settings.get('vectorization_model', FALLBACK_ANALYSIS_SETTINGS['vectorization_model'])
            current_settings['similarity_threshold'] = float(current_settings.get('similarity_threshold', FALLBACK_ANALYSIS_SETTINGS['similarity_threshold']))
        except (ValueError, TypeError):
            current_settings['vectorization_model'] =  FALLBACK_ANALYSIS_SETTINGS['vectorization_model']
            current_settings['similarity_threshold'] = FALLBACK_ANALYSIS_SETTINGS['similarity_threshold']
        
        return current_settings

    def _update_status_callback(self, text: str, is_error: bool = False, only_txt: bool = False):
        """
        Callback para atualizar o texto de status na UI (executado na thread principal).

        Args:
            text (str): O texto de status a ser exibido.
            is_error (bool): Se True, formata o texto como erro.
            only_txt (bool): Se True, atualiza apenas o texto, sem mostrar/esconder o overlay de loading.
        """
        # Este callback será executado pela thread principal via page.run_thread
        #_logger.info(f"[DEBUG] Callback UI: Atualizando {control_key} para '{text}' (Erro: {is_error})")
        
        txt_to_update = self.gui_controls[CTL_LLM_STATUS_INFO] # control_key = ft.Text
 
        hide_loading_overlay(self.page)
        if not only_txt:
            show_loading_overlay(self.page, text)
        
        txt_to_update.value = text
        txt_to_update.color = theme.COLOR_ERROR if is_error else None
        txt_to_update.weight = ft.FontWeight.BOLD if is_error else ft.FontWeight.NORMAL
        safe_control_update(txt_to_update)
        
    def _pdf_processing_thread_func(self, pdf_paths: List[str], batch_name: str, analyze_llm_after: bool, is_reanalysis: bool = False):
        """
        Função executada em uma thread separada para realizar o processamento de PDF.

        Esta função orquestra as etapas de extração de texto, pré-processamento,
        cálculo de embeddings, classificação de páginas por relevância e agregação de texto,
        atualizando a UI com o progresso. Opcionalmente, pode iniciar a análise LLM em seguida.

        Args:
            pdf_paths (List[str]): Lista de caminhos para os arquivos PDF a serem processados.
            batch_name (str): Nome do lote de arquivos, usado para identificação nos logs e UI.
            analyze_llm_after (bool): Se True, inicia a análise LLM automaticamente após o processamento de PDF.
            is_reanalysis (bool): Indica se esta é uma reanálise, afetando o comportamento de logging e feedback.
        """
        current_analysis_settings = self._get_current_analysis_settings()
        logger.info(f"Usando configurações de análise para processamento: {current_analysis_settings}")
        pdf_extractor = current_analysis_settings.get("pdf_extractor", FALLBACK_ANALYSIS_SETTINGS["pdf_extractor"])
        provider = current_analysis_settings.get("llm_provider", FALLBACK_ANALYSIS_SETTINGS["llm_provider"])
        vectorization_model = current_analysis_settings.get("vectorization_model", FALLBACK_ANALYSIS_SETTINGS["vectorization_model"])
        similarity_threshold = current_analysis_settings.get("similarity_threshold", FALLBACK_ANALYSIS_SETTINGS["similarity_threshold"])
        token_limit_pref = current_analysis_settings.get("llm_input_token_limit", FALLBACK_ANALYSIS_SETTINGS["llm_input_token_limit"])

        # O orçamento da truncagem automática (token_limit_pref is None) é calculado adiante, após a
        # extração: ele depende do desvio entre o tiktoken e o tokenizer real do Qwen, que só pode
        # ser medido sobre o texto deste documento.

        # TODO: avaliar se tornar esses parâmetros mutáveis na Gui:
        mode_main_filter = 'get_pages_among_similars_graphs'
        mode_filter_similar = 'bigger_content'
        
        if pdf_extractor == 'PdfPlumber':
            self.pdf_analyzer.extractor = PdfPlumberExtractor()
            logger.debug("Alterando pdf_extractor para PdfPlumber!")
  
        try:
            start_time = perf_counter()
            import requests

            if not self.parent_view._is_mounted or not self.page:
                logger.debug("_pdf_processing_thread_func abortada: view desmontada.")
                return

            logger.debug(f"Thread: Iniciando processamento de PDFs para '{batch_name}' (LLM depois: {analyze_llm_after})")
            self.page.run_thread(self._update_status_callback, "Etapa 1/5: Extraindo textos do(s) arquivo(s) selecionado(s)...")
 
            processed_files_metadata, all_indices, all_texts_to_storage, all_texts_to_loop = \
                                self.pdf_analyzer.extract_texts_and_preprocess_files(pdf_paths)
 
            processed_page_data_combined, all_global_page_keys_ordered = \
                                self.pdf_analyzer.build_combined_page_data(processed_files_metadata, all_indices, all_texts_to_storage)
 
            self.page.run_thread(self._update_status_callback, f"Etapa 2/5: Processando {len(processed_page_data_combined)} páginas...")
 
            ready_embeddings, tokens_embeddings = None, None
            calculated_embedding_cost_usd = 0
            if vectorization_model == "text-embedding-3-small":
                decrypted_api_key = self.page.session.get(f"decrypted_api_key_{provider}")
                if decrypted_api_key:
                    logger.debug(f"Chave API descriptografada para '{provider}' obtida da sessão.")
                else:
                    decrypted_api_key = get_api_key_in_firestore(self.page, provider, self.firestore_client)
                    assert decrypted_api_key, "Chave de API não encontrada ou não cadastrada! Verifique."
 
                loaded_embeddings_providers = self.page.session.get(KEY_SESSION_MODEL_EMBEDDINGS_LIST)
                ready_embeddings, tokens_embeddings, calculated_embedding_cost_usd = ai_orchestrator.get_embeddings_from_api(
                                                                                     all_texts_to_loop, vectorization_model, decrypted_api_key, loaded_embeddings_providers)

            elif vectorization_model == "all-MiniLM-L6-v2":
                from SOURCE.services.ml_client import get_embeddings_from_engine
                logger.info("Requisitando get_embeddings_from_engine ...")
                ready_embeddings = get_embeddings_from_engine(all_texts_to_loop)
                logger.info("Requisição concluída.")

            embedding_vectors_combined, tfidf_vectors_combined, tf_idf_scores_array_combined = self.pdf_analyzer.get_similarity_and_tfidf_score_docs(
                                                                            all_texts_to_loop, model_embedding=vectorization_model, ready_embeddings=ready_embeddings)
            
            point_time = perf_counter()
            self.page.run_thread(self._update_status_callback, "Etapa 3/5: Classificando páginas...")
 
            if tokens_embeddings:
                self.page.session.set(KEY_SESSION_TOKENS_EMBEDDINGS, (tokens_embeddings, vectorization_model))
                logger.debug(f"Tokens de embedding ({tokens_embeddings}) salvos na sessão.")
            else:
                if self.page.session.contains_key(KEY_SESSION_TOKENS_EMBEDDINGS):
                    self.page.session.remove(KEY_SESSION_TOKENS_EMBEDDINGS)
                    logger.debug("Tokens de embedding removidos da sessão (não retornados pela análise).")
                
            if not processed_page_data_combined:
                raise ValueError("Nenhum dado processável encontrado nos PDFs.")
            
            #pr-int('\n[DEBUG]:\n', processed_page_data_combined, '\n\n')
            classified_data = self.pdf_analyzer.filter_and_classify_pages(processed_page_data_combined, all_global_page_keys_ordered,
                                                                          embedding_vectors_combined, tfidf_vectors_combined, tf_idf_scores_array_combined,
                                                                          mode_main_filter, mode_filter_similar, similarity_threshold)
            
            relevant_ordered_indices, unintelligible_indices, count_similars = classified_data
            count_sel, count_unint = len(relevant_ordered_indices), len(unintelligible_indices)
 
            if not relevant_ordered_indices:
                raise ValueError("Nenhuma página relevante encontrada após classificação.")
 
            if perf_counter() - point_time < 1: sleep(1) # Apenas Garante visibilidade do text_progressing
 
            point_time = perf_counter()
            self.page.run_thread(self._update_status_callback, "Etapa 4/5: Filtrando páginas...")
 
            # O pdf_processor conta as páginas em unidades de tiktoken, mas a janela do modelo é
            # medida no tokenizer do Qwen. O desvio é medido uma vez neste lote e serve a dois fins:
            # converter o orçamento da truncagem e converter os totais exibidos no painel.
            drift_ratio = ai_orchestrator.measure_llm_pf_token_drift(all_texts_to_loop) if provider == "llm_pf" else None

            if token_limit_pref is None:
                # Truncagem automática: calcula o orçamento de tokens em runtime, descontando
                # o overhead real do prompt fixo (já carregado no cache) da janela do modelo.
                if provider == "llm_pf":
                    prompt_cache = self.user_cache.get(KEY_SESSION_PROMPTS_FINAL) or {}
                    prompt_messages = prompt_cache.get("PROMPT_UNICO_for_INITIAL_ANALYSIS", [])
                    # A reserva de saída acompanha o modo de raciocínio selecionado agora; alterá-lo
                    # antes de 'Solicitar Análise' exige reprocessar (aviso em [MAX_OUTPUT_TOKENS]).
                    enable_thinking = ai_orchestrator.is_thinking_enabled(
                        current_analysis_settings.get("reasoning_effort",
                                                      FALLBACK_ANALYSIS_SETTINGS["reasoning_effort"])
                    )
                    token_limit_pref = ai_orchestrator.compute_llm_pf_auto_token_limit(
                        prompt_messages, drift_ratio=drift_ratio, enable_thinking=enable_thinking
                    )
                    logger.info(f"Truncagem automática (llm_pf): orçamento calculado = {token_limit_pref} tokens.")
                else:
                    # Sem tabela de janela de contexto por modelo para outros providers ainda;
                    # mantém o comportamento anterior (fallback numérico fixo) nesse caso.
                    token_limit_pref = 180_000
                    logger.warning(
                        f"Truncagem automática solicitada, mas não suportada para provider '{provider}'. "
                        f"Usando fallback fixo de {token_limit_pref} tokens."
                    )

            aggregated_info = self.pdf_analyzer.group_texts_by_relevance_and_token_limit(processed_page_data_combined, relevant_ordered_indices, token_limit_pref)
            
            self.user_cache = get_user_cache(self.page)
            self.user_cache[KEY_SESSION_PDF_AGGREGATED_TEXT_INFO] = aggregated_info[1] # Texto agregado
            self.user_cache[KEY_SESSION_SHARED_DOCUMENT_CONTEXT] = aggregated_info[1] 
            self.page.session.set(KEY_SESSION_CHAT_HAS_FILES_OPTIMIZED, True)
            
            pages_agg_indices, _, tokens_antes_filtro, tokens_antes_trunc, tokens_final_agg = aggregated_info
            count_sel_final = len(pages_agg_indices)
            #pr-int('\n[DEBUG]:\n', pages_agg_indices, '\n\n')
            
            supressed_tokens = tokens_antes_trunc - tokens_final_agg
            perc_supressed = (supressed_tokens / tokens_antes_trunc * 100) if tokens_antes_trunc > 0 else 0
 
            total_processing_time = perf_counter() - start_time
            
            # Totais convertidos para o tokenizer real do modelo (ver scale_tokens_to_real): é o
            # número que o modelo enxerga e o mesmo critério das métricas pós-análise (usage da API).
            # O percentual suprimido é razão entre duas contagens, logo independe da unidade.
            proc_meta_for_ui = {
                "total_pages_processed": len(processed_page_data_combined),
                "total_tokens_before_filter": ai_orchestrator.scale_tokens_to_real(tokens_antes_filtro, drift_ratio),
                "relevant_pages_global_keys_formatted": self.pdf_analyzer.format_global_keys_for_display(relevant_ordered_indices),
                "count_selected_relevant": count_sel,
                "unintelligible_pages_global_keys_formatted": self.pdf_analyzer.format_global_keys_for_display(unintelligible_indices),
                "count_discarded_unintelligible": count_unint,
                "count_discarded_similarity": count_similars,
                "total_tokens_before_truncation": ai_orchestrator.scale_tokens_to_real(tokens_antes_trunc, drift_ratio),
                "final_pages_global_keys_formatted": self.pdf_analyzer.format_global_keys_for_display(pages_agg_indices),
                "count_selected_final": count_sel_final,
                "final_aggregated_tokens": ai_orchestrator.scale_tokens_to_real(tokens_final_agg, drift_ratio),
                "supressed_tokens_percentage": perc_supressed,
                "processing_time": format_seconds_to_min_sec(total_processing_time),
                "calculated_embedding_cost_usd": calculated_embedding_cost_usd
            }
            self.page.session.set(KEY_SESSION_PROCESSING_METADATA, proc_meta_for_ui)
            self.page.session.set(KEY_SESSION_SHARED_PROCESSING_METADATA, proc_meta_for_ui)
            self.page.run_thread(self.parent_view._update_processing_metadata_display, proc_meta_for_ui)
 
            self.parent_view._files_processed = True
            logger.info(f"Thread: Processamento de PDF para '{batch_name}' concluído.")
 
            if perf_counter() - point_time < 1: sleep(1)
            self.page.run_thread(self._update_status_callback, "Aguardando para exibir os resultados...", False, True)
 
            if analyze_llm_after:
                self.page.run_thread(self._update_status_callback,  "Etapa 5/5: Requisitando análise da LLM...")
                self.start_llm_analysis_only(aggregated_info[1], batch_name, from_pipeline=True, is_reanalysis=is_reanalysis) # Passa o texto agregado
                self.page.run_thread(self._update_status_callback, "", False, True)
            else: # Só processou, não vai para LLM agora
                hide_loading_overlay(self.page)
                # Se não vai para a LLM, a UI precisa ser atualizada agora com os resultados do processamento.
                self.page.run_thread(self.parent_view._update_gui_from_state)
                self.page.run_thread(show_snackbar, self.page, f"Conteúdo de '{batch_name}' processado. Pronto para análise LLM.", theme.COLOR_SUCCESS)

        except requests.exceptions.ConnectionError as conn_err:
            logger.warning(f"Erro de conexão ao tentar se comunicar com o motor de ML: {conn_err}")
            def update_ui_on_conn_error():
                hide_loading_overlay(self.page)
                msg_amigavel = ("Não foi possível conectar ao motor de Vetorização. "
                                "Ele pode ainda estar inicializando em segundo plano. "
                                "Por favor, aguarde alguns instantes e tente novamente.")
                show_snackbar(self.page, msg_amigavel, color=theme.COLOR_WARNING, duration=8000)
            self.page.run_thread(update_ui_on_conn_error)

        except Exception as ex_proc:
            logger.error(f"Thread: Erro no processamento de PDF para '{batch_name}': {ex_proc}", exc_info=True)
            self.page.run_thread(self._update_status_callback, f"Erro ao processar PDFs: {ex_proc}", True, True)
            self.parent_view._files_processed = False # Falhou
        finally:
            # Overlay é global da página: escondido antes da checagem de montagem para
            # não ficar preso na tela caso o usuário tenha navegado durante o processamento.
            hide_loading_overlay(self.page)
            if not self.parent_view._is_mounted or not self.parent_view.page:
                logger.debug("Finalização de _pdf_processing_thread_func ignorada: view desmontada.")
                return
            # Garante que, mesmo em erro, os botões sejam reavaliados.
            # Se a análise não prosseguir para a LLM, a atualização da UI já foi feita no try.
            if not analyze_llm_after:
                self.page.run_thread(self.parent_view._update_button_states)

    def _get_valid_user_context(self) -> Optional[Tuple[str, str]]:
        """
        Verifica e renova o token se necessário, retornando um contexto de usuário válido.
        Centraliza a lógica de verificação de token para a view.

        Returns:
            Optional[Tuple[str, str]]: Uma tupla (user_token, user_id) se a sessão for válida,
                                       ou None se a sessão for inválida (e o logout for acionado).
        """
        from SOURCE.flet_ui.app import check_and_refresh_token_if_needed
        
        if not check_and_refresh_token_if_needed(self.page):
            logger.error("Contexto do usuário inválido ou sessão expirada. Ação abortada.")
            return None
        
        user_token = self.page.session.get("auth_id_token")
        user_id = self.page.session.get("auth_user_id")

        if not user_token or not user_id:
            logger.error("Token ou ID do usuário ausente da sessão mesmo após verificação. Ação abortada.")
            return None
            
        return user_token, user_id
    
    def _get_data_to_log(self):
        """
        Coleta e retorna os dados relevantes da sessão e do cache para fins de logging e métricas.

        Retorna:
            Tuple: Uma tupla contendo:
                - user_id (str): ID do usuário autenticado.
                - user_token (str): Token de autenticação do usuário.
                - filenames_uploaded (List[str]): Lista de nomes dos arquivos PDF carregados.
                - proc_meta_session (Dict[str, Any]): Metadados do processamento de PDF.
                - tokens_embeddings_session (Tuple): Informações sobre tokens de embeddings.
                - llm_meta_session (Dict[str, Any]): Metadados da análise LLM.
                - current_settings (Dict[str, Any]): Configurações de análise atuais.
                - default_settings (Dict[str, Any]): Configurações padrão da nuvem.
                - llm_response_obj (formatted_initial_analysis): Objeto de resposta estruturada da LLM.
                - fields_to_log (List[str]): Lista de campos da resposta LLM a serem logados.
        """
        context = self._get_valid_user_context()
        if not context:
            logger.error("Não foi possível obter contexto de usuário válido para coletar dados de log.")
            # Retorna uma tupla com Nones para evitar que o chamador quebre
            return (None, None, [], {}, None, {}, {}, {}, None, [])
            
        user_token, user_id = context
    
        llm_meta_session = self.page.session.get(KEY_SESSION_LLM_METADATA) or {}

        if llm_meta_session: # Salva no objeto que será logado
            event_timestamp_for_llm_analysis = datetime.now().isoformat() # Timestamp desta análise
            llm_meta_session["event_timestamp_iso"] = event_timestamp_for_llm_analysis
            # Também salva na sessão para que o save_feedback_data_now possa pegar
            self.page.session.set(KEY_SESSION_LLM_METADATA, llm_meta_session)

        files_ordered_session = self.page.session.get(KEY_SESSION_PDF_FILES_ORDERED) or []
        filenames_uploaded = [f.get('name', 'unknown_file') for f in files_ordered_session if isinstance(f, dict)]
        
        proc_meta_session = self.page.session.get(KEY_SESSION_PROCESSING_METADATA) or {}
        tokens_embeddings_session = self.page.session.get(KEY_SESSION_TOKENS_EMBEDDINGS)
        current_settings = self.page.session.get(KEY_SESSION_NC_ANALYZE_SETTINGS) or {}
        default_settings = self.page.session.get(KEY_SESSION_CLOUD_ANALYSIS_DEFAULTS) or {}
        
        llm_response_obj = self.user_cache.get(KEY_SESSION_PDF_LLM_RESPONSE)

        # if llm_response_obj and isinstance(llm_response_obj, formatted_initial_analysis):
        #     fields_to_log = [
        #         "tipo_documento_origem", "orgao_origem", "uf_origem", "municipio_origem",
        #         "tipo_local", "uf_fato", "municipio_fato", "valor_apuracao",
        #         "area_atribuicao", "tipificacao_penal", "tipo_a_autuar", "assunto_re",
        #         "materia_especial", "destinacao"
        #     ]
        # else:
        #     fields_to_log = []
        
        return (user_id, user_token, filenames_uploaded, proc_meta_session, tokens_embeddings_session, llm_meta_session,
            current_settings, default_settings, llm_response_obj)
    
    def _llm_analysis_thread_func(self, aggregated_text: str, batch_name: str, is_reanalysis: bool = False):
        """
        Função executada em uma thread separada para realizar a análise LLM.

        Orquestra a chamada ao modelo de linguagem, gerencia o uso de chaves de API,
        atualiza o estado da UI com os resultados da análise e registra métricas.

        Args:
            aggregated_text (str): O texto agregado das páginas relevantes do PDF para análise.
            batch_name (str): Nome do lote de arquivos, usado para identificação nos logs e UI.
            is_reanalysis (bool): Indica se esta é uma reanálise, afetando o comportamento de logging e feedback.
        """
        import SOURCE.core.ai_orchestrator as ai_orchestrator
 
        if not self.parent_view._is_mounted or not self.page:
            logger.debug("_llm_analysis_thread_func abortada: view desmontada.")
            return

        current_analysis_settings = self._get_current_analysis_settings()
        logger.debug(f"Usando configurações de análise para LLM: {current_analysis_settings}")
        provider = current_analysis_settings.get("llm_provider", FALLBACK_ANALYSIS_SETTINGS["llm_provider"])
        model_name = current_analysis_settings.get("llm_model", FALLBACK_ANALYSIS_SETTINGS["llm_model"])
        temperature = current_analysis_settings.get("llm_temperature", FALLBACK_ANALYSIS_SETTINGS["llm_temperature"])
        mode_prompt = current_analysis_settings.get("prompt_structure", FALLBACK_ANALYSIS_SETTINGS["prompt_structure"])
        reasoning_effort = current_analysis_settings.get("reasoning_effort", FALLBACK_ANALYSIS_SETTINGS["reasoning_effort"])
  
        if mode_prompt == "sequential_prompts":
            key_prompt_group = "PROMPTS_SEGMENTADOS_for_INITIAL_ANALYSIS"
        else: # if mode_prompt == "prompt_unico":
            key_prompt_group = "PROMPT_UNICO_for_INITIAL_ANALYSIS"

        self.user_cache = get_user_cache(self.page)
        final_prompts_to_use = None
        prompt_was_edited = self.page.session.get(KEY_SESSION_PROMPT_IS_EDITED_FLAG) or False

        if prompt_was_edited:
            edited_prompts_dict = self.user_cache.get(KEY_USER_CACHE_PROMPTS_EDITED_DATA)
            all_lists_dict = self.user_cache.get(KEY_SESSION_LIST_TO_PROMPTS)
            if edited_prompts_dict and all_lists_dict:
                logger.info("Usando PROMPT EDITADO PELO USUÁRIO para esta análise.")
                # Remontar a lista de prompts para a API a partir do dicionário editado
                final_prompts_to_use, _ = get_prompts_for_initial_analysis(all_lists_dict, edited_prompts_dict)
            else:
                logger.error("Flag de prompt editado ativa, mas dados do prompt e/ou listas não encontrados no cache! Revertendo para o prompt original.")
        
        if not final_prompts_to_use:
            logger.info("Usando PROMPT ORIGINAL para esta análise.")
            final_prompts_to_use = self.user_cache.get(KEY_SESSION_PROMPTS_FINAL)

        if not final_prompts_to_use:        
            logger.error("Prompts ausentes para a thread de análise!")
            self.page.run_thread(self.parent_view._update_gui_from_state)
            self.page.run_thread(self._update_status_callback, f"Erro crítico: Não foi possível carregar os prompts de análise.", True, True)
            hide_loading_overlay(self.page)
            return # Aborta a execução da thread

        try:
            logger.debug(f"Thread: Iniciando análise LLM para '{batch_name}'...")
            self.page.run_thread(self._update_status_callback,  "Etapa 5/5: Requisitando análise da LLM...")
 
            if provider == "llm_pf":
                decrypted_api_key = "EMPTY"
            else:
                decrypted_api_key = self.page.session.get(f"decrypted_api_key_{provider}")
                if decrypted_api_key:
                    logger.debug(f"Chave API descriptografada para '{provider}' obtida da sessão.")
                else:
                    decrypted_api_key = get_api_key_in_firestore(self.page, provider, self.firestore_client)
                    assert decrypted_api_key, "Chave de API não encontrada ou não cadastrada! Verifique."
 
            loaded_llm_providers = self.page.session.get(KEY_SESSION_LOADED_LLM_PROVIDERS)
 
            llm_response_data, token_usage_info, processing_time_llm = ai_orchestrator.analyze_text_with_llm(key_prompt_group, final_prompts_to_use, aggregated_text,
                                                                                                 provider, model_name, temperature,
                                                                                                 decrypted_api_key, loaded_llm_providers,
                                                                                                 reasoning_effort=reasoning_effort)
 
            if llm_response_data:
                # Se já existe uma llm_response na sessão é porque é caso de reanálise (usuário clicou em 'Solicitar Análise' novamente).
                # Registrar essa informação para o feedback_metric
                self.page.session.set(KEY_SESSION_LLM_REANALYSIS, is_reanalysis)
                
                self.user_cache[KEY_SESSION_PDF_LLM_RESPONSE] = llm_response_data
                self.page.session.set(KEY_SESSION_HAS_LLM_REPONSE, True)
                # A flag 'is_new_llm_response' será passada para a sessão para ser usada por _update_ui_from_state

                # Se a resposta veio como string bruta (fallback), removemos a flag de nova resposta estruturada
                if isinstance(llm_response_data, str):
                    if self.page.session.contains_key("is_new_llm_response_flag"):
                        self.page.session.remove("is_new_llm_response_flag")
                else:
                    self.page.session.set("is_new_llm_response_flag", True)
                
                llm_meta_for_gui = token_usage_info if token_usage_info else {}
                llm_meta_for_gui.update({
                    "llm_provider_used": provider.upper(),
                    "llm_model_used": model_name.upper(),
                    "processing_time": format_seconds_to_min_sec(processing_time_llm)
                })
                
                self.parent_view._analysis_requested = True
                self.page.session.set(KEY_SESSION_LLM_METADATA, llm_meta_for_gui)
                self.page.run_thread(self.parent_view._update_gui_from_state)
                self.page.run_thread(show_snackbar, self.page, "Análise LLM concluída!", theme.COLOR_SUCCESS)
                self.page.run_thread(self._update_status_callback,  "", False, True)
 
                data_to_log = self._get_data_to_log()
                if self.firestore_client.save_analysis_metrics(*data_to_log):
                    # Zerar embeddings para não recalcular caso click analyze_only sem reprocessamento
                    self.parent_view._remove_data_session(KEY_SESSION_TOKENS_EMBEDDINGS)

                if prompt_was_edited:
                    self.page.run_thread(self.parent_view._restore_original_prompts_and_notify)                    
 
            else:
                self.page.run_thread(self.parent_view._update_gui_from_state) # Atualiza a UI para mostrar o balão de falha
                self.page.run_thread(self._update_status_callback,  "Análise LLM: Falha ao obter resposta da IA.", True, True)
                self.page.run_thread(show_snackbar, self.page, "Erro na consulta à LLM.", theme.COLOR_ERROR)
                self.parent_view._analysis_requested = False
        except Exception as ex_llm:
            logger.error(f"Thread: Erro na análise LLM para '{batch_name}': {ex_llm}", exc_info=True)
            self.parent_view._analysis_requested = False
            self.page.run_thread(self.parent_view._update_gui_from_state) # Atualiza a UI para mostrar o balão de falha
            if isinstance(ex_llm, ContextLengthExceededError):
                _msg_status = (
                    f"Documento muito longo para o modelo atual.\n{ex_llm}"
                )
                _msg_snack = (
                    f"⚠ Limite de contexto atingido — {ex_llm} "
                    "Reduza os filtros de conteúdo, divida o documento ou selecione "
                    "um modelo com maior context window nas Configurações LLM."
                )
                self.page.run_thread(self._update_status_callback, _msg_status, True, True)
                self.page.run_thread(show_snackbar, self.page, _msg_snack,
                                     theme.COLOR_WARNING)
            else:
                self.page.run_thread(self._update_status_callback,
                                     f"Erro na consulta à LLM: {ex_llm}", True, True)
                self.page.run_thread(show_snackbar, self.page,
                                     "Erro inesperado na consulta à LLM.", theme.COLOR_ERROR)            
        finally:
            # O overlay é global da página (não da view), então é escondido antes de
            # qualquer checagem de montagem — senão ficaria preso na tela se o usuário
            # tivesse navegado para outra view durante a análise.
            hide_loading_overlay(self.page)

            # Só a partir daqui tocamos em controles da view: se ela já foi desmontada,
            # os controles não têm mais 'uid'/'page' válidos e o Flet lança AssertionError,
            # matando esta thread.
            if not self.parent_view._is_mounted or not self.parent_view.page:
                logger.debug("Finalização de _llm_analysis_thread_func ignorada: view desmontada.")
                return

            self.parent_view.file_list_manager.collapse_container()
            self.gui_controls[CTL_LLM_METADATA_PANEL].visible = True
            # self.gui_controls[CTL_LLM_METADATA_PANEL].controls[0].expanded = True
            # self.gui_controls[CTL_LLM_METADATA_PANEL].update()
            # A atualização da GUI já foi tratada dentro do try/except, não precisa aqui.
 
    def start_pdf_processing_only(self, pdf_paths: List[str], batch_name: str):
        """
        Inicia o processo de extração e pré-processamento de PDF em uma nova thread.

        Args:
            pdf_paths (List[str]): Lista de caminhos para os arquivos PDF.
            batch_name (str): Nome do lote de arquivos.
        """
        show_loading_overlay(self.page, "Iniciando processamento...")
        thread = threading.Thread(target=context_wrap(self._pdf_processing_thread_func, pdf_paths, batch_name, False), daemon=True)
        thread.start()

    def start_llm_analysis_only(self, aggregated_text: str, batch_name: str, from_pipeline:bool = False, is_reanalysis: bool = False):
        """
        Inicia a análise LLM em uma nova thread.

        Args:
            aggregated_text (str): O texto agregado para análise.
            batch_name (str): Nome do lote de arquivos.
            from_pipeline (bool): Indica se a chamada veio do pipeline completo (True) ou diretamente (False).
        """
        if not from_pipeline: # Se chamado diretamente (não pelo pipeline do fast_forward)
            ...
        # A thread _llm_analysis_thread_func já lida com hide_loading_overlay no finally
        thread = threading.Thread(target=context_wrap(self._llm_analysis_thread_func, aggregated_text, batch_name, is_reanalysis), daemon=True)
        thread.start()
    
    def start_full_analysis_pipeline(self, pdf_paths: List[str], batch_name: str, is_reanalysis: bool = False):
        """
        Inicia o pipeline completo: processamento de PDF seguido por análise LLM.

        Args:
            pdf_paths (List[str]): Lista de caminhos para os arquivos PDF.
            batch_name (str): Nome do lote de arquivos.
            is_reanalysis (bool): Indica se esta é uma reanálise.
        """
        show_loading_overlay(self.page, "Iniciando processamento e análise...")
        thread = threading.Thread(target=context_wrap(self._pdf_processing_thread_func, pdf_paths, batch_name, True, is_reanalysis), daemon=True)
        thread.start()

class InternalExportManager:
    """
    Gerencia as operações de exportação dos resultados da análise para DOCX.

    Lida com a interação com o FilePicker para salvar arquivos e utiliza o DocxExporter
    para gerar os documentos nos formatos simples ou usando templates.
    """
    def __init__(self, parent_view: AnalyzePDFViewContent):
        """
        Inicializa o gerenciador de exportação.

        Args:
            parent_view (AnalyzePDFViewContent): Referência à instância da view principal.
            docx_exporter (DocxExporter): Instância do DocxExporter para gerar os arquivos.
            global_file_picker (Optional[ft.FilePicker]): Instância global do FilePicker para operações de salvar.
        """
        self.parent_view = parent_view
        self.page = parent_view.page
        user_id = self.page.session.get("auth_user_id") or "global"
        self.docx_exporter = DocxExporter(user_id=user_id)

    def _get_default_filename_base(self) -> str:
        """
        Gera um nome de arquivo base padrão para exportação, derivado do nome do lote atual.

        Returns:
            str: O nome de arquivo base limpo e formatado.
        """
        base = self.page.session.get(KEY_SESSION_CURRENT_BATCH_NAME) or "analise_documento"
        return base.replace("Arquivos selecionados: ", "").replace("Arquivo selecionado: ", "").split(" e Outros")[0].replace(".pdf", "")

    def start_export(self, operation_type: ExportOperation, data_to_export: formatted_initial_analysis, template_path: Optional[str] = None):
        """
        Inicia o processo de exportação dos resultados da análise para um arquivo DOCX.

        Gerencia a lógica de exportação para o modo web (download) e desktop (salvar como),
        utilizando o DocxExporter para a geração do documento.

        Args:
            operation_type (ExportOperation): O tipo de exportação (simples ou com template).
            data_to_export (formatted_initial_analysis): Os dados estruturados da análise a serem exportados.
            template_path (Optional[str]): O caminho para o arquivo de template DOCX (obrigatório para exportação com template).
        """
        logger.debug(f"ExportManager: start_export. Op: {operation_type}, Web: {self.page.web}")

        if not data_to_export: # Verificação de segurança
            logger.error("ExportManager (start_export): Dados para exportação ausentes ou inválidos.")
            show_snackbar(self.page, "Erro: Dados para exportação inválidos.", theme.COLOR_ERROR)
            return
        
        default_filename_base = self._get_default_filename_base()
        if self.page.web:
            # --- LÓGICA PARA MODO WEB ---
            show_loading_overlay(self.page, "Preparando arquivo para download...")
            temp_server_filename = ""
            export_success_on_server = False
            missing_keys_on_server: List[str] = []
            server_save_path = ""
            
            try:
                temp_exports_path = os.path.join(ASSETS_DIR, WEB_TEMP_EXPORTS_SUBDIR)
                os.makedirs(temp_exports_path, exist_ok=True)
            except OSError as e:
                logger.error(f"EXPORT_MANAGER (Web): Falha ao criar diretório de exportações temporárias '{temp_exports_path}': {e}")
                hide_loading_overlay(self.page)
                show_snackbar(self.page, "Erro ao preparar diretório para download.", theme.COLOR_ERROR)
                return
            
            if operation_type == ExportOperation.SIMPLE_DOCX:
                temp_server_filename = f"{default_filename_base}_simples_{int(time())}.docx"
                server_save_path = os.path.join(temp_exports_path, temp_server_filename)
                export_success_on_server = self.docx_exporter.export_simple_docx(data_to_export, server_save_path)
            elif operation_type == ExportOperation.TEMPLATE_DOCX and template_path:
                template_name = os.path.basename(template_path).replace(".docx","").replace(" ", "_").lower()
                temp_server_filename = f"{default_filename_base}_{template_name}_{int(time())}.docx"
                server_save_path = os.path.join(temp_exports_path, temp_server_filename)
                export_success_on_server, _ = self.docx_exporter.export_from_template_docx(data_to_export, template_path, server_save_path)
            else: 
                logger.error(f"EXPORT_MANAGER (Web): Tipo de operação desconhecido ou template_path ausente: {operation_type}")
                hide_loading_overlay(self.page)
                show_snackbar(self.page, "Erro: Tipo de exportação inválido.", theme.COLOR_ERROR)
                return
            
            hide_loading_overlay(self.page)
            if export_success_on_server and temp_server_filename:
                download_url = f"/{WEB_TEMP_EXPORTS_SUBDIR}/{temp_server_filename}"
                self.page.launch_url(download_url, web_window_name="_blank") # or web_window_name="_self"
                show_snackbar(self.page, f"Download de '{temp_server_filename}' iniciado.", theme.COLOR_SUCCESS)
            else: 
                logger.error(f"ExportManager (Web): Falha ao gerar DOCX: {server_save_path}")
                show_snackbar(self.page, "Falha ao gerar arquivo para download.", theme.COLOR_ERROR)
                    
        else: # Desktop
            raise ValueError("Método não customizado para desktop!")

    def handle_add_new_template_click(self):
        """
        Handler para o clique no item 'Adicionar Novo Template'.

        Inicia o processo de seleção de um novo arquivo de template DOCX,
        diferenciando o comportamento para o modo web (upload) e desktop (cópia local).
        """
        logger.info("Botão 'Adicionar Novo Template' clicado.")
        
        # Lista de placeholders que o usuário pode usar no template
        placeholders_disponiveis = [
            "<descricao_geral>", "<tipo_documento_origem>", "<orgao_origem>",
            "<uf_origem>", "<municipio_origem>", "<resumo_fato>", "<uf_fato>",
            "<municipio_fato>", "<tipo_local>", "<valor_apuracao>", "<tipificacao_penal>",
            "<materia_especial>", "<area_atribuicao>", "<destinacao>", "<tipo_a_autuar>",
            "<assunto_re>", "<pessoas_envolvidas>", "<linha_do_tempo>", "<observacoes>"
        ]
        placeholders_text = "\n".join([f"- {ph}" for ph in placeholders_disponiveis])
        
        dialog_content = ft.Column(
            [
                ft.Text("Para criar um template .docx, insira os seguintes placeholders no seu documento onde você deseja que os dados da análise sejam inseridos. \n"
                        "A aplicação irá substituí-los pelos valores correspondentes.", selectable=True),
                ft.Divider(),
                ft.Text("Placeholders Disponíveis:", weight=ft.FontWeight.BOLD),
                ft.TextField(
                    value=placeholders_text,
                    multiline=True,
                    read_only=True,
                    border=ft.InputBorder.NONE,
                    height=250 # Ajuste a altura conforme necessário
                )
            ],
            tight=True,
            scroll=ft.ScrollMode.ALWAYS
        )

        def proceed_to_upload(e=None):
            # Esta função é chamada quando o usuário clica em "Continuar"

            if not hasattr(self, 'template_uploader'):
                self.template_uploader = ManagedFilePicker(
                    page=self.page,
                    upload_dir=UPLOAD_TEMP_DIR,
                    allowed_extensions=["docx"],
                )
            self.template_uploader.pick_files(
                dialog_title_override="Selecionar Template .docx",
                allow_multiple=False,
                on_batch_complete=self.on_template_file_uploaded
            )
            
        show_confirmation_dialog(
            page=self.page,
            title="Como Adicionar um Novo Template",
            content=dialog_content,
            confirm_text="Continuar para Upload",
            cancel_text="Cancelar",
            on_confirm=proceed_to_upload
        )

    def on_template_file_uploaded(self, batch_results: List[Dict[str, Any]]):
        """Callback chamado quando o upload do template (web ou desktop) é concluído."""
        hide_loading_overlay(self.page)
        if not batch_results or not batch_results[0].get("success"):
            error_msg = batch_results[0].get("path_or_message", "Erro desconhecido no upload.") if batch_results else "Upload cancelado."
            show_snackbar(self.page, f"Falha ao carregar template: {error_msg}", theme.COLOR_ERROR)
            return
        
        uploaded_file = batch_results[0]
        source_path = uploaded_file["path_or_message"]
        file_name = uploaded_file["name"]
        
        # O source_path já é o caminho final (seja no desktop ou na pasta de uploads web)
        self.copy_template_to_assets(source_path, file_name, is_web_upload_temp=self.page.web)


    def copy_template_to_assets(self, source_path: str, original_filename: str, is_web_upload_temp: bool = False):
        """
        Copia um arquivo de template para o diretório de assets.

        Args:
            source_path (str): O caminho de origem do arquivo.
            original_filename (str): O nome original do arquivo.
            is_web_upload_temp (bool): Indica se o arquivo de origem é um temporário de upload web.
        """
        user_id = self.page.session.get("auth_user_id") or "global"
        templates_dir = os.path.join(ASSETS_DIR, TEMPLATES_DOCX_SUBDIR, user_id)
        os.makedirs(templates_dir, exist_ok=True)
        destination_path = os.path.join(templates_dir, original_filename)
        try:
            shutil.copy2(source_path, destination_path)
            show_snackbar(self.page, f"Template '{original_filename}' adicionado!", theme.COLOR_SUCCESS)
            self.parent_view._update_export_button_menu() # Acessa via parent_view
            safe_page_update(self.page)
        except Exception as ex:
            logger.error(f"Erro ao copiar template '{original_filename}': {ex}", exc_info=True)
            show_snackbar(self.page, f"Falha: {ex}", theme.COLOR_ERROR)
        finally:
            if is_web_upload_temp and source_path.startswith(os.path.abspath(UPLOAD_TEMP_DIR)):
                try:
                    os.remove(source_path)
                except OSError as er:
                    logger.warning(f"Não remover temp template '{source_path}': {er}")
 
    def _trigger_feedback_and_export(self, export_operation: ExportOperation, template_path: Optional[str]):
        """
        Dispara o fluxo de feedback do usuário antes de iniciar a exportação.

        Valida os dados do formulário para exportação e, se válidos, solicita feedback
        ao usuário antes de chamar a função de exportação primária.

        Args:
            export_operation (ExportOperation): O tipo de exportação a ser realizada.
            template_path (Optional[str]): O caminho para o arquivo de template DOCX (se aplicável).
        """
        logger.debug(f"ExportManager: Disparando diálogo de feedback antes da exportação (Op: {export_operation}).")
 
        llm_display_component = self.parent_view.gui_controls.get(CTL_LLM_STRUCTURED_RESULT_DISPLAY)
        if not isinstance(llm_display_component, LLMStructuredResultDisplay):
            logger.error("ExportManager: LLMStructuredResultDisplay não encontrado.")
            show_snackbar(self.page, "Erro interno: Display de resultados não operacional.", theme.COLOR_ERROR)
            return
 
        # Garante que os dados da UI sejam validados E obtidos.
        # A validação para exportação acontece aqui, antes do diálogo de feedback.
        data_to_export_or_errors = llm_display_component.get_current_form_data(validate_for_export=True)
 
        if isinstance(data_to_export_or_errors, list):
            first_error_tuple = data_to_export_or_errors[0]
            if first_error_tuple[0].startswith("pydantic_validation_error") or first_error_tuple[0].startswith("internal_form_data_error"):
                error_msg_detail = "Verifique os campos e tente novamente." if "pydantic" in first_error_tuple[0] else "Tente recarregar os dados."
                show_snackbar(self.page, f"Erro de validação nos dados do formulário. {error_msg_detail}", theme.COLOR_ERROR, duration=5000)
                return
            
            error_messages = []
            first_invalid_ctrl: Optional[ft.Control] = None
            for field_name, control_instance in data_to_export_or_errors:
                friendly_field_name = field_name.replace("_", " ").title()
                error_messages.append(f"- {friendly_field_name}")
                if control_instance and not first_invalid_ctrl:
                    first_invalid_ctrl = control_instance
 
            if error_messages:
                dialog_content_controls_list = [ft.Text("Os seguintes campos obrigatórios precisam ser preenchidos antes da exportação:")]
                for msg_item in error_messages:
                    dialog_content_controls_list.append(ft.Text(msg_item))
                show_confirmation_dialog(
                    page=self.page, title="Campos Obrigatórios Pendentes",
                    content=ft.Column(dialog_content_controls_list, tight=True, spacing=5),
                    confirm_text="OK", cancel_text=None,
                    on_confirm= lambda: first_invalid_ctrl.focus() if first_invalid_ctrl and hasattr(first_invalid_ctrl, 'focus') else None)
                return
            
        elif not data_to_export_or_errors:
            show_snackbar(self.page, "Dados de análise inválidos.", theme.COLOR_ERROR)
            return
 
        # Se chegou aqui, data_to_export_or_errors é um objeto FormatAnaliseInicial válido
        current_data_for_export = data_to_export_or_errors
 
        def primary_export_action():
            self.start_export(export_operation, current_data_for_export, template_path)
        
        # `feedback_workflow_manager` é acessado via `self.parent_view`
        if self.parent_view.feedback_workflow_manager:
            self.parent_view.feedback_workflow_manager.request_feedback_and_proceed(
                action_context_name="Exportar Análise",
                primary_action_callable=primary_export_action,
            )
        else: # Fallback se o manager não estiver pronto
            primary_export_action()
 
    def handle_export_selected(self, e: ft.ControlEvent):
        """
        Handler para a seleção de um item no menu do botão de Exportar.

        Args:
            e (ft.ControlEvent): O evento do controle.
        """
        logger.debug(f"ExportManager: Item de exportação selecionado - Data: {e.control.data}")
        selected_action_data = e.control.data
                   
        operation: Optional[ExportOperation] = None
        template_p: Optional[str] = None
 
        if selected_action_data == "export_simple_docx":
            operation = ExportOperation.SIMPLE_DOCX
        elif selected_action_data and selected_action_data.startswith("export_template_"):
            operation = ExportOperation.TEMPLATE_DOCX
            template_p = selected_action_data[len("export_template_"):]
        elif selected_action_data == "manage_templates":
            self.handle_add_new_template_click()
            return
        else:
            logger.warning(f"Ação de exportação desconhecida: {selected_action_data}")
            return
 
        if not operation: # Se a operação não foi definida (ex: manage_templates já retornou)
            return
            
        # A validação e obtenção dos dados, bem como o disparo do diálogo de feedback,
        # são agora responsabilidade de _trigger_feedback_and_export.
        # Se a validação em _trigger_feedback_and_export falhar (get_current_form_data retornar lista de erros),
        # a exportação não prosseguirá.
        self._trigger_feedback_and_export(operation, template_p) # Passa template_p

class FeedbackDialog(ft.AlertDialog):
    """
    Diálogo para coletar feedback do usuário sobre a precisão da análise da LLM.
    """
    def __init__(
        self,
        page_ref: ft.Page,
        fields_feedback_data: List[Dict[str, Any]],
        # Callback que será chamado com uma instância de FeedbackDialogAction
        on_close_callback: Callable[[FeedbackDialogAction], None],
    ):
        """
        Inicializa o diálogo para coletar feedback do usuário sobre a precisão da análise da LLM.

        Args:
            page_ref (ft.Page): Referência à página Flet.
            fields_feedback_data (List[Dict[str, Any]]): Lista de dicionários, cada um contendo:
                - "nome_campo" (str): Nome interno do campo.
                - "label_campo" (str): Nome amigável do campo para exibição.
                - "valor_original_llm" (Any): Valor original da LLM.
                - "valor_atual_ui" (Any): Valor atual na UI (editado ou não).
                - "foi_editado" (bool): True se o campo foi editado.
                - "tipo_campo" (str): Tipo do campo (ex: "textfield_multiline", "dropdown").
            on_close_callback (Callable[[FeedbackDialogAction], None]): Função a ser chamada quando o diálogo for fechado por uma ação.
        """
        super().__init__(
            modal=True,
            title=ft.Text("Avaliação de Precisão da IA Assistente", weight=ft.FontWeight.BOLD, size=20),
            # O conteúdo será construído dinamicamente
            content=ft.Text("Carregando conteúdo do feedback..."),
            actions_alignment=ft.MainAxisAlignment.CENTER,
            # As actions também serão definidas dinamicamente
        )
        self.page_ref = page_ref
        self.fields_feedback_data = fields_feedback_data
        self.on_close_callback = on_close_callback

        self.open = False # Controla a visibilidade

        # FB-3.3: Construir dinamicamente o conteúdo do diálogo
        self._build_dialog_content()
        # FB-3.4: Implementar os botões de ação
        self._build_dialog_actions()

    def _build_dialog_content(self):
        """
        Constrói o conteúdo visual do diálogo de feedback, exibindo os campos
        que foram editados pelo usuário e os que não foram, com informações de similaridade.
        """
        logger.debug(f"FeedbackDialog: Construindo conteúdo com {len(self.fields_feedback_data)} campos.")
        
        intro_text = ft.Text(
            "Sua avaliação é importante para aprimorar a ferramenta.\n"
            "Revise os resultados abaixo.",
            size=14,
            italic=True,
            color=ft.Colors.ON_SURFACE # ft.Colors.with_opacity(0.8, ft.Colors.ON_SURFACE)
        )

        nao_editados_controls: List[ft.Control] = []
        editados_controls: List[ft.Control] = []

        for field_data in self.fields_feedback_data:
            nome_campo = field_data.get("nome_campo", "Desconhecido")
            label_campo = field_data.get("label_campo", nome_campo.replace("_", " ").title())
            foi_editado = field_data.get("foi_editado", False)
            tipo_campo = field_data.get("tipo_campo", "textfield")

            if not foi_editado:
                nao_editados_controls.append(
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, color=theme.COLOR_SUCCESS, size=18),
                            ft.Text(label_campo, weight=ft.FontWeight.NORMAL, size=13, expand=True),
                            #ft.Text("(Não Editado)", italic=True, color=ft.Colors.with_opacity(0.7, ft.Colors.ON_SURFACE), size=11)
                        ],
                        spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER
                    )
                )
            else: # Foi editado
                status_text = ""
                status_color = ft.Colors.ORANGE_900 # Padrão para editado
                icon_name = ft.Icons.EDIT_NOTE_ROUNDED

                if tipo_campo in ["textfield_multiline", "textfield_lista", "textfield"]:
                    similaridade = field_data.get("similaridade_pos_edicao")
                    if similaridade is not None:
                        status_text = f"(Editado - Aproveitamento: {similaridade:.0%})"
                    else: # Fallback se similaridade não foi calculada/aplicável
                        status_text = "(Editado)"
                    #if similaridade > 0.85: # Exemplo de limite para "quase igual"
                    #    icon_name = ft.Icons.EDIT_ROUNDED # Um pouco menos "alerta"
                    #    status_color = ft.Colors.with_opacity(0.8, theme.COLOR_WARNING)

                elif tipo_campo in ["dropdown", "radio_button", "textfield_valor"]: # Campos de valor único
                    status_text = "(Alterada resposta)" # Corrigido pelo Usuário
                    icon_name = ft.Icons.SWAP_HORIZ_ROUNDED
                    status_color = ft.Colors.RED_600
                elif tipo_campo == "checkbox": # Campos de múltipla escolha
                    # Lógica de comparação para checkboxes (ex: Jaccard ou contagem)
                    # Por agora, uma mensagem genérica: # TODO
                    status_text = "(Editado - Seleção Modificada)"
                    icon_name = ft.Icons.RULE_ROUNDED
                
                editados_controls.append(
                    ft.Row(
                        [
                            ft.Icon(icon_name, color=status_color, size=18),
                            ft.Text(label_campo, weight=ft.FontWeight.NORMAL, size=13, expand=True),
                            ft.Text(status_text, italic=True, color=status_color, size=13)
                        ],
                        spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER
                    )
                )
        
        # Montar seções
        sections: List[ft.Control] = [intro_text, ft.Divider(height=10)]

        if nao_editados_controls:
            sections.append(ft.Text("Respostas da IA consideradas Corretas (Sem edição):", weight=ft.FontWeight.BOLD, size=14))
            sections.append(ft.Column(nao_editados_controls, spacing=5))
            sections.append(ft.Divider(height=8))
        
        if editados_controls:
            sections.append(ft.Text("Itens Corrigidos ou Complementados por Você:", weight=ft.FontWeight.BOLD, size=14))
            sections.append(ft.Column(editados_controls, spacing=5))
            sections.append(ft.Divider(height=8))
        
        if not nao_editados_controls and not editados_controls:
            sections.append(ft.Text("Nenhum campo para avaliação /ou/ Dados de feedback ausentes.", italic=True))

        self.content = ft.Container(
            content=ft.Column(sections, spacing=10, scroll=ft.ScrollMode.ADAPTIVE),
            width=480, # Largura do diálogo
            height=620, # Altura máxima, com scroll
            padding=ft.padding.symmetric(vertical=10)
        )

    def _build_dialog_actions(self):
        """
        Constrói os botões de ação para o diálogo de feedback.

        Inclui opções para confirmar a avaliação, retornar para edição ou ignorar a avaliação.
        """
        actions = []
        
        actions.append(
            ft.ElevatedButton(
                f"Confirmar Avaliação", width=160, bgcolor=ft.Colors.GREEN_100, color=ft.Colors.BLACK,
                on_click=lambda _: self._handle_action_click(FeedbackDialogAction.CONFIRM_AND_CONTINUE),
            )
        )
        actions.append(
            ft.ElevatedButton(
                "Retornar para Edição", width=160, bgcolor=ft.Colors.AMBER_100, color=ft.Colors.BLACK,
                on_click=lambda _: self._handle_action_click(FeedbackDialogAction.RETURN_TO_EDIT)
            )
        )
        actions.append(
            ft.ElevatedButton(
                f"Ignorar avaliação", width=160, bgcolor=ft.Colors.DEEP_ORANGE_100, color=ft.Colors.BLACK,
                on_click=lambda _: self._handle_action_click(FeedbackDialogAction.SKIP_AND_CONTINUE)
            )
        )       
        self.actions = actions

    def _handle_action_click(self, action: FeedbackDialogAction):
        """
        Handler para o clique em um dos botões de ação do diálogo de feedback.

        Fecha o diálogo e invoca o callback `on_close_callback` com a ação selecionada.

        Args:
            action (FeedbackDialogAction): A ação selecionada pelo usuário.
        """
        logger.debug(f"FeedbackDialog: Ação '{action.value}' selecionada.")
        self.open = False
        if self.page_ref and self.uid: # Garante que está na árvore da UI para atualizar
            self.page_ref.update(self) # Atualiza para fechar visualmente

        # Remove do overlay e chama o callback após um pequeno delay para a UI atualizar

        data_for_callback: Optional[List[Dict[str, Any]]] = None
        if action == FeedbackDialogAction.CONFIRM_AND_CONTINUE:
            pass

        def delayed_callback():
            if self in self.page_ref.overlay:
                self.page_ref.overlay.remove(self)
                # Não é necessário self.page_ref.update() aqui se o callback for fazer algo
                # que já atualize a página (ex: show_snackbar, navegação, etc.)
                # Mas se o callback não fizer, pode ser preciso.
            self.on_close_callback(action)

        threading.Timer(0.15, delayed_callback).start() # Pequeno delay

    def show(self):
        """
        Exibe o diálogo de feedback na página.
        """
        logger.debug("FeedbackDialog: Solicitado para mostrar.")
        if self not in self.page_ref.overlay:
            self.page_ref.overlay.append(self)
        self.open = True
        if self.page_ref and self.page_ref.uid:
            self.page_ref.update()

class FeedbackWorkflowManager:
    """
    Gerencia o fluxo de solicitação de feedback do usuário antes de executar ações
    que podem invalidar ou concluir uma análise LLM.
    """
    def __init__(self, page: ft.Page, parent_view: 'AnalyzePDFViewContent'):
        self.page = page
        self.parent_view = parent_view # Referência à AnalyzePDFViewContent
        self.firestore_client = firestore_client

    def _prepare_and_show_feedback_dialog(
        self,
        feedback_fields_list_prepared: List[Dict[str, Any]],
        # Este é o callback final que lida com a lógica de negócios após o feedback:
        on_feedback_flow_completed: Callable[[FeedbackDialogAction, Optional[List[Dict[str, Any]]]], None]
    ):
        llm_display_component = self.parent_view.gui_controls.get(CTL_LLM_STRUCTURED_RESULT_DISPLAY)
        if not isinstance(llm_display_component, LLMStructuredResultDisplay):
            logger.error("_prepare_and_show_feedback_dialog: LLMStructuredResultDisplay não encontrado.")
            on_feedback_flow_completed(FeedbackDialogAction.CANCELLED_OR_ERROR, None)
            return

        if not feedback_fields_list_prepared:
            logger.warning("_prepare_and_show_feedback_dialog: Nenhum dado de campo preparado para o diálogo de feedback.")
            on_feedback_flow_completed(FeedbackDialogAction.CANCELLED_OR_ERROR, None)
            return
        
        def internal_on_close_wrapper_for_dialog(action_from_dialog: FeedbackDialogAction):
            data_to_pass_to_final_callback = None
            if action_from_dialog == FeedbackDialogAction.CONFIRM_AND_CONTINUE:
                data_to_pass_to_final_callback = feedback_fields_list_prepared
            
            on_feedback_flow_completed(action_from_dialog, data_to_pass_to_final_callback)

        feedback_dialog = FeedbackDialog(
            page_ref=self.page,
            fields_feedback_data=feedback_fields_list_prepared, # Passa os dados para o diálogo construir sua UI
            on_close_callback=internal_on_close_wrapper_for_dialog, # Este é o callback que o diálogo chamará
            #action_context_name=action_context_name,
        )
        feedback_dialog.show()

    def request_feedback_and_proceed(
        self,
        action_context_name: str,
        primary_action_callable: Callable[[], None], # Ação a ser executada (upload, restart, etc.)
        # Callback opcional para executar após o feedback ser salvo (se confirmado
    ):
        """
        Verifica se o feedback deve ser solicitado. Se sim, mostra o diálogo.
        Executa a `primary_action_callable` com base na resposta do diálogo.
        """ 
        # 0. CONDIÇÃO: Só prosseguir com o fluxo de feedback se houver uma resposta da LLM para avaliar.
        self.user_cache = get_user_cache(self.page)
        llm_response = self.user_cache.get(KEY_SESSION_PDF_LLM_RESPONSE_ACTUAL) or self.user_cache.get(KEY_SESSION_PDF_LLM_RESPONSE)
        if not llm_response:
            logger.debug(f"FeedbackWorkflowManager: Nenhuma análise LLM anterior encontrada para '{action_context_name}'. Prosseguindo sem solicitar feedback.")
            primary_action_callable()
            return

        if self.page.session.get(KEY_SESSION_FEEDBACK_COLLECTED_FOR_CURRENT_ANALYSIS):
            logger.debug(f"FeedbackWorkflowManager: Feedback já coletado para '{action_context_name}'. Prosseguindo com ação primária.")
            primary_action_callable()
            return
        
        llm_display_component = self.parent_view.gui_controls.get(CTL_LLM_STRUCTURED_RESULT_DISPLAY)
        if not isinstance(llm_display_component, LLMStructuredResultDisplay):
            logger.error(f"FeedbackWorkflowManager: LLMStructuredResultDisplay não encontrado para '{action_context_name}'. Prosseguindo sem feedback.")
            primary_action_callable()
            return

        # 1. Garante que os dados da UI estejam carregados no componente de display
        current_form_data_or_errors = llm_display_component.get_current_form_data(validate_for_export=False)
        if not isinstance(current_form_data_or_errors, formatted_initial_analysis):
            logger.warning(f"FeedbackWorkflowManager: Dados do formulário inválidos ou não disponíveis para '{action_context_name}'. Prosseguindo sem feedback.")
            primary_action_callable()
            return

        # 2. Prepara os dados para o diálogo de feedback
        # Acessa o snapshot original e os dados atuais da UI através do llm_display_component
        original_snapshot = llm_display_component.original_llm_data_snapshot
        # self.data em llm_display_component já reflete a UI após get_current_form_data()
        # que deve ter sido chamado antes de _get_prepared_feedback_data ser invocado.
        current_data_ui = llm_display_component.data 

        feedback_fields_data = get_prepared_feedback_data(original_snapshot, current_data_ui, llm_display_component.gui_fields)

        if not feedback_fields_data:
            logger.warning(f"FeedbackWorkflowManager: Não foi possível preparar dados para feedback para '{action_context_name}'. Prosseguindo sem feedback.")
            primary_action_callable()
            return

        # Só pede feedback se houver uma análise LLM anterior
        user_cache = get_user_cache(self.page)
        if not user_cache.get(KEY_SESSION_PDF_LLM_RESPONSE):
            logger.debug(f"FeedbackWorkflowManager: Nenhuma análise LLM anterior para '{action_context_name}'. Prosseguindo com ação primária.")
            primary_action_callable()
            return

        # 3. Chama o diálogo de feedback
        def on_feedback_dialog_closed_final_logic(action_taken: FeedbackDialogAction, collected_feedback_data: Optional[List[Dict[str, Any]]]):
            logger.debug(f"FeedbackWorkflowManager (final_logic): Diálogo para '{action_context_name}' fechado com ação: {action_taken.value}")
            
            if action_taken == FeedbackDialogAction.CONFIRM_AND_CONTINUE:
                if collected_feedback_data:
                    user_id = self.page.session.get("auth_user_id")
                    user_token = self.page.session.get("auth_id_token")
                    llm_metadata_session = self.page.session.get(KEY_SESSION_LLM_METADATA)
                    if self.page.session.get(KEY_SESSION_LLM_REANALYSIS):
                        reanalysis_occurrence = True
                    else:
                        reanalysis_occurrence = False
                    related_batch_name = self.page.session.get(KEY_SESSION_CURRENT_BATCH_NAME) or "N/A"

                    if self.firestore_client.save_feedback_data(user_id, user_token, collected_feedback_data, llm_metadata_session, reanalysis_occurrence, related_batch_name):
                        self.page.session.set(KEY_SESSION_FEEDBACK_COLLECTED_FOR_CURRENT_ANALYSIS, True)
                    else: 
                        logger.error("Falha ao salvar feedback no Firestore. A flag de 'feedback coletado' não será setada para esta sessão de análise.")
                        show_snackbar(self.page, "Erro: Não foi possível registrar sua avaliação.", theme.COLOR_ERROR)

                primary_action_callable()
            
            elif action_taken == FeedbackDialogAction.SKIP_AND_CONTINUE:
                primary_action_callable()
            
            elif action_taken == FeedbackDialogAction.RETURN_TO_EDIT:
                logger.debug(f"FeedbackWorkflowManager (final_logic): Usuário escolheu retornar para edição para '{action_context_name}'. Ação primária cancelada.")
            
            elif action_taken == FeedbackDialogAction.CANCELLED_OR_ERROR:
                logger.warning(f"FeedbackWorkflowManager (final_logic): Diálogo para '{action_context_name}' fechado inesperadamente. Ação primária não será executada.")

        # Chama _prepare_and_show_feedback_dialog, passando o callback final
        self._prepare_and_show_feedback_dialog(
            feedback_fields_data,
            on_feedback_flow_completed=on_feedback_dialog_closed_final_logic
        )

# Função principal da view (chamada pelo router)
def create_analyze_pdf_content(page: ft.Page) -> ft.Control:
    """
    Função de fábrica para criar a view de Análise de PDF.

    Args:
        page (ft.Page): A página Flet.

    Returns:
        ft.Control: Uma instância de AnalyzePDFViewContent.
    """
    # Aguarda o pré-carregamento dos módulos pesados ser concluído
    if not app_cache.heavy_imports_loading_event.is_set():
        logger.info("Aguardando conclusão do pré-carregamento de módulos...")
        # Define um timeout para não travar a aplicação indefinidamente
        app_cache.heavy_imports_loading_event.wait(timeout=180)
    else:
        logger.debug("Pré-carregamento de módulos já concluído.")

    logger.info("View Análise de PDF: Iniciando criação (nova estrutura).")

    # 1. Ponto de verificação e carregamento dos prompts
    user_cache = get_user_cache(page)
    if not user_cache.get(KEY_SESSION_PROMPTS_FINAL):
        try:
            # A função `load_prompts_from_firestore` já salva no cache
            start_time_p = perf_counter()
            load_prompts_from_firestore(page)
            execution_time_p = perf_counter() - start_time_p
            logger.debug(f"Carregado Prompts_from_firestore em {execution_time_p:.4f}s")
            # Verificação pós-carregamento para garantir que tudo correu bem:
            if not user_cache.get(KEY_SESSION_PROMPTS_FINAL):
                raise RuntimeError("load_prompts_from_firestore foi chamada mas não populou o cache.")
        except Exception as e:
            logger.critical(f"Falha crítica ao carregar prompts para a view de análise: {e}", exc_info=True)
            # Retorna uma view de erro se os prompts são essenciais e falharam ao carregar
            return ft.Column([
                ft.Icon(ft.Icons.ERROR, color=theme.COLOR_ERROR, size=50),
                ft.Text("Erro Crítico", style=ft.TextThemeStyle.HEADLINE_SMALL),
                ft.Text("Não foi possível carregar as configurações de análise necessárias. "
                        "Tente recarregar a página ou contate o suporte.",
                        text_align=ft.TextAlign.CENTER)
            ],
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=15)
    else:
        logger.debug("Prompts já estavam carregados no cache da sessão. Pulando recarregamento.")

    start_time_p = perf_counter()
    retorno = AnalyzePDFViewContent(page)
    execution_time_p = perf_counter() - start_time_p
    logger.debug(f"Create_analyze_pdf_content em {execution_time_p:.4f}s")
    
    return retorno

# Funções acessórias:

def load_prompts_from_firestore(page: ft.Page):
    """
    Carrega os componentes base de prompts (ALL_lists, ALL_prompts) do Firestore,
    constrói os pipelines de prompts finais e os armazena no cache do servidor.
    """
    logger.debug("Carregando componentes base de prompt...")
    user_token = page.session.get("auth_id_token")
    user_id = page.session.get("auth_user_id")
    refresh_token = page.session.get("auth_refresh_token")
    user_cache = get_user_cache(page)

    prompts_path = os.path.join(ASSETS_DIR, 'dict_prompts.json')

    loaded_components = None

    if user_token:
        prompts_doc_path = f"{PROMPTS_COLLECTION}/{PROMPTS_DOCUMENT_ID}"
        try:
            # refresh_token habilita a camada reativa de _make_firestore_request: se o
            # token da sessão já estiver obsoleto no momento desta chamada (carregada no
            # início da criação da view, antes de qualquer refresh proativo posterior),
            # o método tenta renovar e repetir a requisição uma única vez em vez de falhar
            # direto com 401 (ver Tarefa 6 / incidente confirmado em prompt_templates).
            response = firestore_client._make_firestore_request(
                "GET", user_token, prompts_doc_path, refresh_token=refresh_token
            )
            if response.status_code == 200:
                prompts_data = response.json()
                fields = prompts_data.get("fields", {})
                if fields:
                    loaded_components = {k: _from_firestore_value(v) for k, v in fields.items()}
                    logger.debug("Componentes base de prompt carregados com sucesso do Firestore.")
                    # Salva uma cópia local ao baixar com sucesso
                    with open(prompts_path, 'w', encoding='utf-8') as f:
                        json.dump(loaded_components, f, ensure_ascii=False, indent=4)
                        logger.debug(f"Cópia local dos prompts salva em: {prompts_path}")
        except Exception as e:
            logger.error(f"Exceção ao carregar componentes de prompts do Firestore: {e}", exc_info=True)

    # É esperado trabalhar somente com prompts baixados ou versão local em assets; 
    # prompts hardocoded em prompts.py serão descontinuados
    if not loaded_components: 
        if os.path.exists(prompts_path):
            with open(prompts_path, 'r', encoding='utf-8') as f:
                loaded_components = json.load(f)
                logger.debug("Fallback: Componentes de prompts carregados localmente.")
    
    if not loaded_components:
        msg_erro = "Nenhum componente de prompt carregado localmente."
        logger.critical(msg_erro)
        raise Exception(msg_erro)

    user_cache = get_user_cache(page)
    # Agora, construa os prompts finais usando os componentes carregados (do Firestore ou fallback)
    try:
        # Passa os componentes carregados para a função de construção
        final_prompts, prompts_dict = get_prompts_for_initial_analysis(
            loaded_components["ALL_lists"],
            loaded_components["ALL_prompts"]
        )
        # Armazena o resultado final no cache do servidor
        user_cache[KEY_SESSION_LIST_TO_PROMPTS] = loaded_components["ALL_lists"]
        user_cache[KEY_SESSION_PROMPTS_DICT]    = prompts_dict
        user_cache[KEY_SESSION_PROMPTS_FINAL]   = final_prompts
        logger.info("Pipelines de prompts finais construídos e armazenados no cache do servidor.")
    except Exception as e:
        logger.error(f"Falha ao construir pipelines de prompts finais: {e}", exc_info=True)
        # Em caso de erro, armazena um dicionário vazio para evitar falhas posteriores
        user_cache[KEY_SESSION_LIST_TO_PROMPTS] = {}
        user_cache[KEY_SESSION_PROMPTS_DICT]    = {}
        user_cache[KEY_SESSION_PROMPTS_FINAL]   = {}

def get_api_key_in_firestore(page: ft.Page, provider: str, firestore_client: FirebaseClientFirestore) -> Optional[str]:
    """
    Busca a chave de API criptografada para um provedor específico no Firestore
    e a descriptografa.

    Args:
        page (ft.Page): A página Flet, usada para acessar a sessão do usuário.
        provider (str): O nome do provedor (ex: "openai").
        firestore_client (FirebaseClientFirestore): Instância do cliente Firestore.

    Returns:
        Optional[str]: A chave de API descriptografada como string, ou None se não for encontrada
                       ou houver erro na descriptografia.
    """
    from SOURCE.services import credentials_manager

    user_token = page.session.get("auth_id_token")
    user_id = page.session.get("auth_user_id")
    
    service_name_firestore = f"{provider}" # Ou uma lógica de mapeamento mais robusta
    logger.debug(f"Buscando chave API criptografada para serviço: {service_name_firestore}")
    encrypted_key_bytes = firestore_client.get_user_api_key_client(
        user_token, user_id, service_name_firestore
    )

    if not encrypted_key_bytes:
        logger.error(f"Chave API criptografada para '{service_name_firestore}' não encontrada no Firestore para o usuário {user_id}.")
        # A UI deve informar o usuário para configurar a chave.
        return None

    logger.debug("Descriptografando chave API...")
    decrypted_api_key = credentials_manager.decrypt(encrypted_key_bytes)

    if not decrypted_api_key:
        logger.error(f"Falha ao descriptografar a chave API para '{service_name_firestore}' do usuário {user_id}.")
        # Pode indicar chave de criptografia local ausente ou corrompida.
        return None

    logger.debug(f"Chave API para o provedor '{provider}' obtida e descriptografada com sucesso.")
    
    page.session.set(f"decrypted_api_key_{provider}", decrypted_api_key)
    return decrypted_api_key

def get_prepared_feedback_data(original_snapshot: formatted_initial_analysis, current_data_ui: formatted_initial_analysis, gui_fields: Dict[str, ft.Control]) -> Optional[List[Dict[str, Any]]]:
    """
    Prepara os dados para serem enviados ao FeedbackDialog, incluindo o status 'foi_editado'
    e a similaridade de texto para campos editados.

    Args:
        original_snapshot (formatted_initial_analysis): O snapshot original dos dados da LLM.
        current_data_ui (formatted_initial_analysis): Os dados atuais da UI, que podem ter sido editados pelo usuário.
        gui_fields (Dict[str, ft.Control]): Dicionário de controles da GUI para obter labels amigáveis e tipos de campo.

    Returns:
        Optional[List[Dict[str, Any]]]: Uma lista de dicionários, cada um representando um campo e seu status,
                                        ou None se os dados originais ou atuais não estiverem disponíveis.
    """
    
    if not original_snapshot or not current_data_ui:
        logger.warning("FeedbackWorkflowManager: Dados originais ou atuais da UI ausentes em LLMStructuredResultDisplay.")
        return None

    feedback_field_data_prepared  = []
    fields_for_feedback = [
        "descricao_geral", "tipo_documento_origem", "orgao_origem", "uf_origem", "municipio_origem",
        "resumo_fato", "tipo_local", "uf_fato", "municipio_fato", "valor_apuracao",
        "area_atribuicao", "tipificacao_penal", "tipo_a_autuar", "assunto_re",
        "destinacao", "materia_especial",
        "pessoas_envolvidas", "linha_do_tempo", "observacoes"
    ]

    for field_name in fields_for_feedback:
        # Pega os valores diretamente dos objetos Pydantic
        original_value = getattr(original_snapshot, field_name, None)
        current_value_ui = getattr(current_data_ui, field_name, None)

        # Lógica de comparação para 'foi_editado' (permanece a mesma)
        foi_editado = False
        
        # Demais normalizações tratadas na origem.
        if field_name == "valor_apuracao":
            original_float = original_value if isinstance(original_value, float) else 0.0
            current_float_ui = current_value_ui if isinstance(current_value_ui, float) else 0.0
            # Use math.isclose para comparar floats com tolerância, se necessário
            # import math
            # foi_editado = not math.isclose(original_float, current_float_ui, rel_tol=1e-9)
            foi_editado = (original_float != current_float_ui)
        elif field_name in ["pessoas_envolvidas", "linha_do_tempo"]:
            original_list = original_value if isinstance(original_value, list) else []
            current_list_ui = current_value_ui if isinstance(current_value_ui, list) else []
            foi_editado = (original_list != current_list_ui)
        else: # Campos string ou dropdowns diretos
            foi_editado = (original_value != current_value_ui)
        
        if field_name not in ['descricao_geral', 'resumo_fato', 'pessoas_envolvidas', 'linha_do_tempo', 'observacoes']:
            logger.debug(f"Feedback Prep (Manager): Campo '{field_name}', Original: '{original_value}', Atual UI: '{current_value_ui}', Editado: {foi_editado}")

        # Obter o label amigável e o tipo do campo
        label_campo = field_name.replace("_", " ").title() # Default label
        control_gui = gui_fields.get(field_name)
        if control_gui and hasattr(control_gui, 'label') and control_gui.label:
            label_campo = str(control_gui.label)
        
        tipo_campo_str = get_field_type_for_feedback(field_name, gui_fields)

        field_data_entry  = {
            "nome_campo": field_name,
            "label_campo": label_campo, # Adicionado para o diálogo
            "tipo_campo": tipo_campo_str,
            "llm_acertou": not foi_editado, # Novo campo para o Firestore
            "foi_editado": foi_editado,
            "valor_original_llm": original_value,
            "valor_atual_ui": current_value_ui,
        }

        # Adiciona similaridade apenas se editado e for um tipo de texto aplicável
        if foi_editado and tipo_campo_str in ["textfield_multiline", "textfield", "textfield_lista"]:
            field_data_entry["similaridade_pos_edicao"] = calcular_similaridade_rouge_l(
                str(original_value or ""), str(current_value_ui or "")
            )
        
        feedback_field_data_prepared.append(field_data_entry)
        
    return feedback_field_data_prepared

def get_field_type_for_feedback(field_name: str, gui_fields: Dict[str, ft.Control]) -> str:
    """
    Retorna o tipo de controle Flet associado a um campo específico para categorização no feedback.

    Args:
        field_name (str): O nome do campo (atributo do objeto formatted_initial_analysis).
        gui_fields (Dict[str, ft.Control]): Dicionário de controles da GUI.

    Returns:
        str: Uma string representando o tipo do campo (ex: "textfield_multiline", "dropdown", "textfield_valor").
    """
    # Mapeamento simplificado, pode ser expandido
    if field_name in ["descricao_geral", "resumo_fato", "tipificacao_penal", "observacoes"]:
        return "textfield_multiline"
    elif field_name == "valor_apuracao":
        return "textfield_valor"
    elif field_name in ["pessoas_envolvidas", "linha_do_tempo"]:
        return "textfield_lista" # Representa uma lista, mas editado como multiline
    elif gui_fields.get(field_name) and isinstance(gui_fields[field_name], ft.Dropdown):
        return "dropdown"
    # Adicionar outros tipos se necessário (radio, checkbox etc.)
    return "textfield" # Defa


execution_time = perf_counter() - start_time
logger.debug(f"Carregado NC_ANALYZE_VIEW em {execution_time:.4f}s")
