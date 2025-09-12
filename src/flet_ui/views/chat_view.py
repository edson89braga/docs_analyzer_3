# src/flet_ui/views/chat_view.py
import flet as ft
import time, threading, os
from typing import List, Dict, Any, Optional

from src.flet_ui import theme
from src.flet_ui.components import (
    show_confirmation_dialog,
    ManagedFilePicker,
    show_loading_overlay,
    hide_loading_overlay,
    show_snackbar
)
# Importa o novo componente de drawer refatorado
from src.flet_ui.settings_drawer import SettingsDrawerManager

# Adiciona import do novo orquestrador e settings
from src.core.chat_llm_orchestrator import ChatLLMOrchestrator
from src.settings import (UPLOAD_TEMP_DIR, KEY_SESSION_ANALYSIS_SETTINGS, 
                          KEY_SESSION_LOADED_LLM_PROVIDERS, DEFAULT_LLM_PROVIDER,
                          DEFAULT_LLM_MODEL, DEFAULT_TEMPERATURE)

import logging
logger = logging.getLogger(__name__)

# Chave de sessão para os arquivos carregados no chat
KEY_SESSION_CHAT_FILES = "chat_view_loaded_files"
KEY_SESSION_CHAT_DOCUMENT_CONTEXT = "chat_view_document_context"

system_prompt_estrito = '''
Você é um assistente especializado em análise de documentos para a Polícia Federal.  
Sua principal função é responder perguntas baseando-se estrita e exclusivamente no texto do(s) documento(s) fornecido(s).  

Regras:  
- Seja preciso, objetivo e neutro.  
- Se a resposta não estiver claramente contida no(s) documento(s), informe:  
  "A informação não foi encontrada no(s) documento(s) fornecido(s)."  
- Não invente, não deduza, não utilize conhecimento externo ao(s) documento(s).  
- Não use exemplos ou analogias que não estejam presentes nos documentos.  
'''

system_prompt_flexivel = '''
Você é um assistente especializado em análise de documentos para a Polícia Federal.  
Sua principal função é responder perguntas dando prioridade ao(s) documento(s) fornecido(s), mas você também pode utilizar seu conhecimento geral para complementar informações.  

Regras:  
- Sempre indique claramente quando a resposta vem do documento (ex.: "No documento consta que...")  
- Se utilizar conhecimento externo, diferencie com clareza (ex.: "Além do documento, em termos gerais...").  
- Seja preciso, objetivo e mantenha tom neutro.  
- Caso não haja referência direta no documento, explique com transparência que a resposta foi baseada em conhecimento geral.  
'''
    
class ChatViewContent(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__(expand=True, spacing=10)
        self.page = page

        self.orchestrator = ChatLLMOrchestrator()
        
        # Estado da UI
        self.messages: List[Dict[str, Any]] = []
        self.is_processing_response = False
        self.editing_message_id: Optional[float] = None
        self._is_drawer_open = False

        # Controles da UI
        self.upload_button = ft.ElevatedButton("Carregar Arquivos", icon=ft.Icons.UPLOAD_FILE, on_click=self._handle_upload_click)
        self.optimize_button = ft.ElevatedButton("Otimizar Páginas", icon=ft.Icons.FILTER_LIST, on_click=self._handle_optimize_click, disabled=True, 
                                                 tooltip="Filtra páginas irrelevantes para economizar tokens e melhorar o foco da IA.")
        self.anonymize_button = ft.ElevatedButton("Anonimizar Dados", icon=ft.Icons.PRIVACY_TIP_OUTLINED, on_click=self._handle_anonymize_click, 
                                                    disabled=True, tooltip="Identifica e oculta dados e entidades antes de enviar à IA.")
        self.clear_chat_button = ft.IconButton(icon=ft.Icons.DELETE_SWEEP_OUTLINED, tooltip="Limpar Conversa", on_click=self._handle_clear_chat)
        self.settings_button = ft.IconButton(icon=ft.Icons.TUNE_ROUNDED, tooltip="Configurações", on_click=self._handle_toggle_settings_drawer)
        
        self.file_list_view = ft.ListView(expand=False, spacing=3)
        self.file_list_panel = self._create_panel("Arquivos Carregados", self.file_list_view, visible=False)
        
        self.metrics_content = ft.Column(spacing=2)
        self.metrics_panel = self._create_panel("Métricas da Sessão", self.metrics_content, visible=False)
        
        self.chat_history_view = ft.ListView(expand=True, spacing=15, auto_scroll=False)
        
        self.user_input_field = ft.TextField(
            hint_text="Digite sua pergunta...",
            expand=True, multiline=True, min_lines=2, max_lines=15,
            filled=True, border_radius=8, on_submit=self._handle_send_message,
            disabled=True # Inicia desabilitado
        )
        self.send_button = ft.IconButton(icon=ft.Icons.SEND_ROUNDED, tooltip="Enviar Mensagem", on_click=self._handle_send_message, disabled=True)
        
        self.managed_file_picker = self._initialize_file_picker()
        
        # Drawer de Configurações (agora um container lateral)
        self.settings_drawer_component = SettingsDrawerManager(self.page) # Mantém a lógica do drawer
        self.settings_drawer_container = ft.Container(content=self.settings_drawer_component, padding=10, width=0, animate=ft.Animation(300, ft.AnimationCurve.EASE_OUT_QUART))
        
        self._build_layout()
        self._show_initial_greeting()

    def _initialize_file_picker(self) -> ManagedFilePicker:
        """Inicializa e retorna uma instância do ManagedFilePicker."""
        global_picker = self.page.data.get("global_file_picker")
        if not global_picker:
            raise RuntimeError("FilePicker global não foi inicializado no app principal.")

        return ManagedFilePicker(
            page=self.page,
            file_picker_instance=global_picker,
            on_individual_file_complete=lambda s, p, f: None,
            on_batch_complete=self._handle_files_uploaded,
            upload_dir=UPLOAD_TEMP_DIR,
            allowed_extensions=["pdf"] # , "txt", "docx", "csv", "xlsx"]
        )

    def _create_panel(self, title: str, content: ft.Control, visible: bool = False) -> ft.ExpansionPanelList:
        """Cria um painel expansível padronizado, igual ao da nc_analyze_view."""
        return ft.ExpansionPanelList(
            controls=[
                ft.ExpansionPanel(
                    header=ft.ListTile(title=ft.Text(title, weight=ft.FontWeight.BOLD)), 
                    content=content
                )
            ],
            elevation=1,
            divider_color=ft.Colors.TRANSPARENT,
            expanded_header_padding=ft.padding.all(1),
            visible=visible
        )
    
    def _build_layout(self):
        """Constrói a estrutura visual da view de chat."""
        top_bar = ft.Row(
            [
                self.upload_button, 
                self.optimize_button,
                self.anonymize_button,
                ft.Container(expand=True),
                self.clear_chat_button,
                self.settings_button,
            ],
            alignment=ft.MainAxisAlignment.START
        )
        
        input_bar = ft.Row(
            [self.user_input_field, self.send_button],
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )

        main_content_column = ft.Column(
            [
                self.file_list_panel,
                self.metrics_panel,
                ft.Divider(height=1),
                ft.Container(content=self.chat_history_view, expand=True), # Permite que o ListView expanda
            ],
            expand=True, spacing=10
        )

        # Layout principal com drawer lateral
        main_layout_with_drawer = ft.Row(
            [
                ft.Container(main_content_column, expand=True, padding=ft.padding.only(right=8)),
                self.settings_drawer_container
            ],
            expand=True, vertical_alignment=ft.CrossAxisAlignment.START
        )

        self.controls = [
            top_bar,
            ft.Divider(height=1),
            main_layout_with_drawer, # Substitui a coluna de conteúdo direto
            ft.Divider(height=1),
            ft.Row([
                ft.Container(expand=1),
                ft.Container(content=input_bar, padding=ft.padding.symmetric(vertical=5, horizontal=10), expand=8),
                ft.Container(expand=1),
            ])
        ]

    def _show_initial_greeting(self):
        """Adiciona uma mensagem inicial de boas-vindas ao chat."""
        initial_message = { "id": time.time(), "author": "IA", 
                           "text": "Olá! Após o carregamento dos documentos que você deseja analisar, poderemos interagir sobre o conteúdo correspondente." }
        self.messages.append(initial_message)
        self._update_chat_display()

    def _update_chat_display(self):
        """Limpa e recria a lista de mensagens na UI."""
        self.chat_history_view.controls.clear()
        is_last_message_from_ia = self.messages and self.messages[-1]["author"] == "IA"
        
        for i, msg in enumerate(self.messages):
            # print(f"[DEBUG] _create_message_bubble nº {i+1}/{len(self.messages)}")
            is_last_message_in_list = (i == len(self.messages) - 1)
            is_rerun_visible = (not msg["author"] == "User" and is_last_message_from_ia and is_last_message_in_list)
            bubble = self._create_message_bubble(msg, is_rerun_visible)
            self.chat_history_view.controls.append(bubble)
            # if is_last_message_in_list: print(f'[DEBUG] última msg: {msg["text"][:160]}...')
        
        if self.page and self.chat_history_view.page:
            self.chat_history_view.update()

    def _create_message_bubble(self, message: Dict[str, Any], is_rerun_visible: bool) -> ft.Row:
        """Cria um componente visual para uma única mensagem no chat."""
        is_user = message["author"] == "User"
        msg_id = message["id"]
        is_last_message_in_list = self.messages and self.messages[-1]["id"] == msg_id
        
        avatar = ft.CircleAvatar(content=ft.Icon(ft.Icons.PERSON_OUTLINE if is_user else ft.Icons.ASSISTANT_OUTLINED))
        content_placeholder = ft.Container(expand=True)

        actions_popup = ft.PopupMenuButton(
            icon=ft.Icons.MORE_VERT,
            tooltip="Mais ações",
            visible=False, height=38, width=38,
            items=[
                ft.PopupMenuItem(text="Copiar", icon=ft.Icons.COPY_ALL_OUTLINED, data="copy", on_click=lambda e: self._handle_message_action(e, msg_id)),
                ft.PopupMenuItem(text="Editar", icon=ft.Icons.EDIT_OUTLINED, data="edit", on_click=lambda e: self._handle_message_action(e, msg_id)),
                ft.PopupMenuItem(text="Excluir", icon=ft.Icons.DELETE_OUTLINE, data="delete", on_click=lambda e: self._handle_message_action(e, msg_id))
            ]
        )

        if not is_last_message_in_list:
            actions_popup.items.append(ft.PopupMenuItem(text="Retomar daqui", icon=ft.Icons.RESTART_ALT, data="resume", on_click=lambda e: self._handle_message_action(e, msg_id)))
        if is_rerun_visible:
            actions_popup.items.append(ft.PopupMenuItem(text="Regenerar resposta", icon=ft.Icons.REPLAY, data="rerun", on_click=lambda e: self._handle_message_action(e, msg_id)))

        progressing_status = True if is_rerun_visible and not message['text'].replace('\n', ' ').split() else False
        self._render_message_content(content_placeholder, message, progressing_status)

        stack_actions_popup = ft.Stack([ft.Container(height=38, width=38), actions_popup])
        message_row_int = ft.Row([content_placeholder, stack_actions_popup], vertical_alignment=ft.CrossAxisAlignment.START, 
                                 alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        bubble_container = ft.Container(
            content=message_row_int, padding=12, border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE) if is_user else ft.Colors.with_opacity(0.08, theme.PRIMARY),
            on_hover=lambda e, tb=actions_popup: self._handle_bubble_hover(e, tb, msg_id),
            expand=True
        )
        
        message_row = ft.Row(
            controls=[
                ft.Container(expand=1),  # 10% esquerda
                ft.Row(
                    controls=[
                        avatar if not is_user else ft.Container(),
                        bubble_container,
                        avatar if is_user else ft.Container()
                    ],
                    expand=8  # 80% centro
                ),
                ft.Container(expand=1)  # 10% direita
            ]
        )
        return message_row

    def _render_message_content(self, container: ft.Container, message: Dict[str, Any], progressing_status: bool = False):
        """Renderiza o conteúdo de uma mensagem, seja como Markdown ou como campo de edição."""
        msg_id = message["id"]
        is_editing = self.editing_message_id == msg_id
        texto_formatado = message["text"].replace("\n", "  \n")

        if is_editing:
            edit_field = ft.TextField(value=texto_formatado, multiline=True, expand=True, min_lines=1, max_lines=15, border_radius=8, autofocus=True)
            container.content = ft.Column([
                edit_field,
                ft.Row([
                    ft.IconButton(icon=ft.Icons.CANCEL_OUTLINED, icon_color=theme.COLOR_ERROR, tooltip="Cancelar", on_click=lambda _, mid=msg_id: self._handle_cancel_edit(mid)),
                    ft.IconButton(icon=ft.Icons.CHECK_CIRCLE_OUTLINED, icon_color=theme.COLOR_SUCCESS, tooltip="Salvar", on_click=lambda _, mid=msg_id, tf=edit_field: self._handle_save_edit(mid, tf.value)),
                ], alignment=ft.MainAxisAlignment.END)
            ])
        elif progressing_status:
            container.content = ft.Row([ft.ProgressRing(height=24, width=24), ft.Container(expand=True)])
        else:
            container.content = ft.Markdown(texto_formatado, selectable=True, extension_set=ft.MarkdownExtensionSet.COMMON_MARK)

    # --- Handlers de Ações ---

    def _handle_upload_click(self, e: ft.ControlEvent):
        # Limpa o contexto antigo antes de carregar novos arquivos
        if self.page.session.contains_key(KEY_SESSION_CHAT_DOCUMENT_CONTEXT):
            self.page.session.remove(KEY_SESSION_CHAT_DOCUMENT_CONTEXT)
        
        show_loading_overlay(self.page, "Abrindo seletor de arquivos...")
        self.managed_file_picker.pick_files(allow_multiple=True)

    def _handle_files_uploaded(self, batch_results: List[Dict[str, Any]]):
        """Callback do ManagedFilePicker após o término do upload."""
        hide_loading_overlay(self.page)
        successful_files = [f for f in batch_results if f.get("success")]
        if not successful_files:
            show_snackbar(self.page, "Nenhum arquivo válido foi carregado.", color=theme.COLOR_WARNING)
            return

        self.page.session.set(KEY_SESSION_CHAT_FILES, successful_files)
        logger.debug(f"Carregados {len(successful_files)} arquivos: {successful_files}")
        self.file_list_view.controls.clear()
        for f in successful_files:
            self.file_list_view.controls.append(ft.ListTile(title=ft.Text(f["name"]), leading=ft.Icon(ft.Icons.DESCRIPTION_OUTLINED), dense=True))
        
        self.file_list_panel.visible = True
        self.optimize_button.disabled = False
        self.anonymize_button.disabled = False
        self.user_input_field.disabled = False
        self.send_button.disabled = False
        
        show_snackbar(self.page, f"{len(successful_files)} documento(s) carregado(s). Otimização de páginas recomendada.", color=theme.COLOR_SUCCESS)
        self.file_list_panel.update()
        self.optimize_button.update()
        self.anonymize_button.update()
        self.user_input_field.update()
        self.send_button.update()

    def _handle_optimize_click(self, e: ft.ControlEvent):
        """Inicia o pré-processamento opcional dos documentos."""
        successful_files = self.page.session.get(KEY_SESSION_CHAT_FILES)
        if not successful_files:
            show_snackbar(self.page, "Nenhum arquivo carregado para otimizar.", color=theme.COLOR_WARNING)
            return

        show_loading_overlay(self.page, "Otimizando documentos...")
        pdf_paths = [f["path_or_message"] for f in successful_files]
        self.optimize_button.disabled = True
        self.optimize_button.update()
        threading.Thread(target=self._preprocess_documents, args=(pdf_paths, successful_files), daemon=True).start()

    def _preprocess_documents(self, pdf_paths: list[str], successful_files: list[dict]):
        """
        Usa o PDFDocumentAnalyzer para extrair e consolidar o texto dos arquivos.
        Este é o processo de OTIMIZAÇÃO. Executado em uma thread separada.
        """
        try:
            # Reutiliza a lógica de pré-processamento do nc_analyzer
            from src.core.pdf_processor import PDFDocumentAnalyzer
            analyzer = PDFDocumentAnalyzer()

            # Pipeline de análise de PDF
            processed_data, ordered_keys, emb_vectors, tfidf_vectors, tfidf_scores = analyzer.analyze_pdf_documents(pdf_paths)
            relevant_indices, _, _ = analyzer.filter_and_classify_pages(
                processed_data, ordered_keys, emb_vectors, tfidf_vectors, tfidf_scores
            )
            
            # Usamos um limite de tokens alto para manter o contexto completo
            token_limit = 180_000 # TODO: vincular parâmetro ao drawer
            _, aggregated_text, _, _ = analyzer.group_texts_by_relevance_and_token_limit(
                processed_data, relevant_indices, token_limit
            )

            if not aggregated_text.strip():
                raise ValueError("Nenhum texto relevante foi extraído dos documentos.")

            # Salva o contexto na sessão
            self.page.session.set(KEY_SESSION_CHAT_DOCUMENT_CONTEXT, aggregated_text)

            # Atualiza a UI na thread principal
            def update_ui_after_processing():
                hide_loading_overlay(self.page)
                self.file_list_view.controls.clear()
                for f in successful_files:
                    self.file_list_view.controls.append(ft.ListTile(title=ft.Text(f["name"]), leading=ft.Icon(ft.Icons.DESCRIPTION_OUTLINED), dense=True))
                self.file_list_panel.visible = True
                self.file_list_panel.update()
                show_snackbar(self.page, f"{len(successful_files)} documento(s) processado(s) e pronto(s) para o chat.", color=theme.COLOR_SUCCESS)
                self.optimize_button.icon = ft.Icons.CHECK_CIRCLE
                self.optimize_button.text = "Páginas Otimizadas"
                self.optimize_button.update()
                show_snackbar(self.page, f"Documentos otimizados. O chat usará o conteúdo filtrado.", color=theme.COLOR_SUCCESS)

            self.page.run_thread(update_ui_after_processing)

        except Exception as e:
            logger.error(f"Erro ao pré-processar documentos para o chat: {e}", exc_info=True)
            def update_ui_on_error():
                hide_loading_overlay(self.page)
                show_snackbar(self.page, f"Erro ao processar documentos: {e}", color=theme.COLOR_ERROR)
            self.page.run_thread(update_ui_on_error)

    def _get_raw_document_context(self) -> str:
        """
        Extrai e concatena o texto bruto de todas as páginas de todos os arquivos carregados.
        Este é o fallback para quando a otimização não é executada.
        """
        from src.core.pdf_processor import PDFDocumentAnalyzer
        analyzer = PDFDocumentAnalyzer()
        all_texts = []
        files_to_process = self.page.session.get(KEY_SESSION_CHAT_FILES) or []
        pdf_paths = [f["path_or_message"] for f in files_to_process]

        for pdf_path in pdf_paths:
            try:
                # Extrai texto de todas as páginas, sem filtro
                pages = analyzer.extractor.extract_texts_from_pages(pdf_path)
                all_texts.extend([page_text for _, page_text in pages])
            except Exception as e:
                logger.error(f"Erro ao extrair texto bruto de '{pdf_path}': {e}")
        
        return "\n\n".join(all_texts)

    def _handle_anonymize_click(self, e: ft.ControlEvent):
        """Handler para o botão de anonimização (ainda não implementado)."""
        show_snackbar(
            self.page,
            "A funcionalidade de anonimização de dados ainda não está disponível.",
            color=theme.COLOR_WARNING
        )
        self._update_chat_display()

    def _handle_send_message(self, e: ft.ControlEvent):
        if self.is_processing_response: 
            return
        
        user_text = self.user_input_field.value # .strip()
        if not user_text:
            return

        # A verificação correta é se existem arquivos para processar.
        # A lógica de obter/criar o contexto foi movida para _get_context_and_call_ai
        if not self.page.session.get(KEY_SESSION_CHAT_FILES):
            show_snackbar(self.page, "Carregue um documento antes da interação inicial.", color=theme.COLOR_WARNING)
            return

        self._set_processing_state(True, clear_input=True)
        self.messages.append({"id": time.time(), "author": "User", "text": user_text})
        logger.info('[DEBUG] Enviando mensagem do usuário ao Chat...')
        self._update_chat_display()
        self.chat_history_view.scroll_to(offset=-1, duration=300, curve=ft.AnimationCurve.EASE_OUT)
        
        # Inicia a geração da resposta da IA em uma thread
        threading.Thread(target=self._get_context_and_call_ai, args=(user_text,), daemon=True).start()

    def _get_context_and_call_ai(self, user_question: str):
        """
        Determina qual contexto usar (otimizado ou bruto) e chama a IA.
        """
        document_context = self.page.session.get(KEY_SESSION_CHAT_DOCUMENT_CONTEXT)

        if not document_context:
            logger.info("Contexto otimizado não encontrado. Extraindo texto bruto de todos os arquivos.")
            self.page.run_thread(lambda: show_loading_overlay(self.page, "Extraindo texto completo..."))
            try:
                document_context = self._get_raw_document_context()
                # Salva o contexto bruto na sessão para não reprocessar na mesma conversa
                self.page.session.set(KEY_SESSION_CHAT_DOCUMENT_CONTEXT, document_context)
            except Exception as e:
                logger.error(f"Falha ao extrair contexto bruto: {e}", exc_info=True)
                self.page.run_thread(lambda: hide_loading_overlay(self.page))
                self.page.run_thread(lambda: show_snackbar(self.page, f"Erro ao ler documentos: {e}", color=theme.COLOR_ERROR))
                self.page.run_thread(lambda: self._set_processing_state(False))
                return
            finally:
                self.page.run_thread(lambda: hide_loading_overlay(self.page))

        self._handle_ai_response(document_context, user_question)

    def _handle_ai_response(self, document_context: str, user_question: str):
        """
        Gerencia a chamada ao orquestrador e o streaming da resposta para a UI.
        """       
        # Prepara parâmetros para a IA
        settings = self.page.session.get(KEY_SESSION_ANALYSIS_SETTINGS) or {}
        api_key = self.page.session.get(f"decrypted_api_key_{settings.get('llm_provider', DEFAULT_LLM_PROVIDER)}") 
        
        if not api_key:
            error_msg = "Chave API não configurada. Por favor, configure-a no menu 'Provedores LLM'."
            self.messages[-1]["text"] = error_msg
            self.page.run_thread(self._update_chat_display)
            self.page.run_thread(lambda: self._set_processing_state(False))
            return

        # O orquestrador agora insere o contexto. Passamos apenas o histórico da conversa.
        history_for_api = [
            {"role": "assistant" if msg["author"] == "IA" else "user", 
             "content": msg["text"]}
            # Passa as mensagens anteriores, excluindo a pergunta atual do usuário e a mensagem "pensando"
            for msg in self.messages[:-2] if msg["author"] in ["User", "IA"]
        ]

        # Mensagem de "pensando..."
        # thinking_message = {"id": time.time(), "author": "IA", "text": "▍..."}
        thinking_message = {"id": time.time(), "author": "IA", "text": ""}
        self.messages.append(thinking_message)
        self.page.run_thread(self._update_chat_display)
        self.page.run_thread(self.chat_history_view.scroll_to(offset=-1, duration=300, curve=ft.AnimationCurve.EASE_OUT))

        try:
            model_name = "gpt-5-mini" # settings.get('llm_model', DEFAULT_LLM_MODEL)
            response_generator = self.orchestrator.generate_response(
                api_key=api_key,
                model_name=model_name,
                document_context=document_context,
                instructions=system_prompt_flexivel,
                history=history_for_api,
                user_question=user_question,
                loaded_llm_providers=self.page.session.get(KEY_SESSION_LOADED_LLM_PROVIDERS) or [],
                temperature=settings.get('llm_temperature', DEFAULT_TEMPERATURE) 
                # TODO:  incluir parâmetros de reasoning e vebosity
            )

            for response_part in response_generator:
                if response_part["type"] == "chunk":
                    self.messages[-1]["text"] += response_part["content"]
                    logger.info(f"[DEBUG] Chunk Msg LLM by model {model_name}: {response_part['content'][:160]}...")
                    self.page.run_thread(self._update_chat_display)
                elif response_part["type"] == "final_metrics":
                    self.page.run_thread(lambda data=response_part["data"]: self._update_metrics_display(data))
                elif response_part["type"] == "error":
                    self.messages[-1]["text"] = f"**Erro:** {response_part['content']}"
                    self.page.run_thread(self._update_chat_display)
                    break
        finally:
            self.page.run_thread(lambda: self._set_processing_state(False))
            self.page.run_thread(lambda: self.chat_history_view.scroll_to(offset=-1, duration=300, curve=ft.AnimationCurve.EASE_OUT))


    def _set_processing_state(self, is_processing: bool, clear_input: bool = False):
        if clear_input:
            self.user_input_field.value = ""
        
        self.is_processing_response     = is_processing
        self.user_input_field.disabled  = is_processing
        self.send_button.disabled       = is_processing
        self.user_input_field.update()
        self.send_button.update()
        if not is_processing:
            self.user_input_field.focus()

    def _update_metrics_display(self, metrics_data: dict):
        """Atualiza o painel de métricas com os dados da última resposta."""
        # TODO: O display de métricas deve exibir os tokens acumulados da sessão, em vez de somente da última requisição.
        self.metrics_content.controls = [
            ft.Row([ft.Text("Custo da Resposta:", weight=ft.FontWeight.BOLD), ft.Text(f"U$ {metrics_data.get('total_cost_usd', 0):.4f}")]),
            ft.Row([ft.Text("Tokens de Entrada:", weight=ft.FontWeight.BOLD), ft.Text(f"{metrics_data.get('input_tokens', 0)}")]),
            ft.Row([ft.Text("Tokens de Cache:", weight=ft.FontWeight.BOLD), ft.Text(f"{metrics_data.get('cached_tokens', 0)}")]),
            ft.Row([ft.Text("Tokens de Saída:", weight=ft.FontWeight.BOLD), ft.Text(f"{metrics_data.get('output_tokens', 0)}")]),
        ]
        self.metrics_panel.visible = True
        self.metrics_panel.update()

    def _handle_message_action(self, e: ft.ControlEvent, message_id: float):
        """Handler central para ações do PopupMenuButton da mensagem."""
        action = e.control.data
        message_text = next((msg["text"] for msg in self.messages if msg["id"] == message_id), "")

        if action == "copy": self.page.set_clipboard(message_text)
        elif action == "edit": self._handle_edit_message(message_id)
        elif action == "delete": self._handle_delete_message(message_id)
        elif action == "resume": self._handle_resume_from(message_id)
        elif action == "rerun": self._handle_rerun(message_id)

    def _handle_delete_message(self, message_id: float):
        self.messages = [msg for msg in self.messages if msg["id"] != message_id]
        self._update_chat_display()

    def _handle_edit_message(self, message_id: float):
        self.editing_message_id = message_id
        self._update_chat_display()

    def _handle_save_edit(self, message_id: float, new_text: str):
        for msg in self.messages:
            if msg["id"] == message_id:
                msg["text"] = new_text
                break
        self.editing_message_id = None
        self._update_chat_display()

    def _handle_cancel_edit(self, message_id: float):
        self.editing_message_id = None
        self._update_chat_display()

    def _handle_resume_from(self, message_id: float):
        try:
            index = next(i for i, msg in enumerate(self.messages) if msg["id"] == message_id)
            self.messages = self.messages[:index + 1]
            self._update_chat_display()
            self.chat_history_view.scroll_to(offset=-1, duration=300, curve=ft.AnimationCurve.EASE_OUT)
        except StopIteration:
            logger.error(f"Não foi possível encontrar a mensagem com ID {message_id} para retomar.")
            
    def _handle_rerun(self, message_id: float):
        last_user_message = next((msg for msg in reversed(self.messages) if msg['author'] == 'User'), None)
        if last_user_message:
            user_question = last_user_message['text']
            self.messages = [msg for msg in self.messages if msg["id"] != message_id]
            self._update_chat_display()
            self._set_processing_state(True)
            threading.Thread(target=self._get_context_and_call_ai, args=(user_question,), daemon=True).start()
        else:
            logger.warning("Nenhuma mensagem de usuário encontrada para refazer a pergunta.")

    def _handle_clear_chat(self, e: ft.ControlEvent):
        def confirm_action():
            self.messages.clear()
            self.file_list_panel.visible = False
            self.metrics_panel.visible = False
            self.file_list_panel.update()
            self.metrics_panel.update()
            if self.page.session.contains_key(KEY_SESSION_CHAT_FILES):
                self.page.session.remove(KEY_SESSION_CHAT_FILES)
            self._show_initial_greeting()
        
        show_confirmation_dialog(
            self.page, title="Limpar Conversa",
            content=ft.Text("Tem certeza que deseja abandonar esta conversa? Atualmente o histórico de chat não é recuperável."),
            on_confirm=confirm_action
        )

    def _handle_toggle_settings_drawer(self, e: Optional[ft.ControlEvent] = None):
        self._is_drawer_open = not self._is_drawer_open
        self.settings_drawer_container.width = 320 if self._is_drawer_open else 0
        
        if self._is_drawer_open:
            self.settings_drawer_container.border = ft.border.only(left=ft.border.BorderSide(2, theme.PRIMARY))
            self.settings_button.bgcolor = ft.Colors.with_opacity(0.1, theme.PRIMARY)
        else:
            self.settings_drawer_container.border = None
            self.settings_button.bgcolor = None

        self.settings_drawer_container.update()
        self.settings_button.update()

    def _handle_bubble_hover(self, e: ft.HoverEvent, toolbar: ft.Row, message_id: float):
        """Mostra ou esconde a barra de ferramentas de ações da mensagem."""
        if self.editing_message_id != message_id:
            toolbar.visible = e.data == "true"
            toolbar.update()

def create_chat_view_content(page: ft.Page) -> ft.Control:
    """Função de fábrica para criar a view de Chat com Documentos."""
    return ChatViewContent(page)

'''
FLUXOs principais da View:

_handle_upload_click 	-> _handle_files_uploaded -> self.page.session.set(KEY_SESSION_CHAT_FILES, successful_files)


_handle_optimize_click 	-> _preprocess_documents -> self.page.session.set(KEY_SESSION_CHAT_DOCUMENT_CONTEXT, aggregated_text)


_handle_send_message 	-> THREAD: _get_context_and_call_ai -> Se texto ainda não processado: _get_raw_document_context -> _handle_ai_response -> _set_processing_state(False)
						-> _set_processing_state(True)

'''

