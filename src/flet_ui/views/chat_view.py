# src/flet_ui/views/chat_view.py
from math import e
import flet as ft
import time, threading, os, secrets
from typing import List, Dict, Any, Optional
from time import perf_counter
from datetime import datetime

from scipy import optimize

from src import app_cache
from src.flet_ui import theme
from src.flet_ui.components.file_list_manager import FileListManager
from src.flet_ui.components.settings_drawer import ChatSettingsDrawer
from src.flet_ui.components.components import (
    show_confirmation_dialog,
    ManagedFilePicker,
    show_loading_overlay, hide_loading_overlay,
    show_snackbar, CompactKeyValueTable
)
# Adiciona import do novo orquestrador e settings
from src.core.chat_llm_orchestrator import ChatLLMOrchestrator
from src.settings import FALLBACK_ANALYSIS_SETTINGS, cotacao_dolar_to_real
from src.settings import (UPLOAD_TEMP_DIR, KEY_SESSION_ANALYSIS_SETTINGS, 
                          KEY_SESSION_LOADED_LLM_PROVIDERS, DEFAULT_LLM_PROVIDER,
                          DEFAULT_LLM_MODEL, DEFAULT_TEMPERATURE,
                          KEY_SESSION_CHAT_PROMPT_ACTIVE_KEY, KEY_SESSION_CHAT_PROMPT_STRICT,
                          KEY_SESSION_CHAT_PROMPT_FLEXIBLE, KEY_SESSION_CHAT_PROMPT_CUSTOM)

from src.utils import format_seconds_to_min_sec, get_user_cache, clear_user_cache
from src.services.local_db_manager import LocalDBManager
from src.services.firebase_client import FirebaseClientFirestore

import logging
logger = logging.getLogger(__name__)

# --- Constantes de Chave de Sessão/Cache Local para CHAT_VIEW ---
KEY_SESSION_CHAT_FILES = "chat_view_loaded_files"
KEY_SESSION_CHAT_RAW_PAGES_TEXT = "chat_view_raw_pages_text"
KEY_SESSION_CHAT_DOCUMENT_CONTEXT = "chat_view_document_context"
KEY_SESSION_CHAT_MESSAGES = "chat_view_messages"
KEY_SESSION_CHAT_METRICS = "chat_view_metrics"
KEY_SESSION_CHAT_HAS_OPTIMIZED = "chat_view_has_optimized"
KEY_SESSION_CHAT_SESSION_ID = "chat_view_session_id"
KEY_SESSION_PROCESSING_METADATA = "chat_view_processing_metadata"
# ----------------------------------------------------------------


class ChatViewContent(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__(expand=True, spacing=10)
        self.page = page
        self.user_cache = get_user_cache(self.page)

        self.orchestrator = ChatLLMOrchestrator()
        self.db_manager = LocalDBManager()
        self.firestore_client = FirebaseClientFirestore()
        
        # Estado da UI
        self.metrics_history: List[Dict[str, Any]] = []
        self.last_used_prompt_text: Optional[str] = None
        self.chat_session_id: Optional[str] = None
        self.is_processing_response = False
        self.editing_message_id: Optional[float] = None
        self._is_drawer_open = False

        width_btn_bar = 180

        # Controles da UI 
        self.upload_button = ft.ElevatedButton("Carregar Arquivo(s)", icon=ft.Icons.UPLOAD_FILE_ROUNDED, 
                                               on_click=self._handle_upload_click, width=width_btn_bar)
        self.extract_button = ft.ElevatedButton("Extrair Texto(s)", icon=ft.Icons.PLAY_CIRCLE_OUTLINE, 
                                                on_click=self._handle_process_extract, disabled=True, width=width_btn_bar,
                                                tooltip="Extrai o texto dos documentos carregados para iniciar o chat.") 
        self.optimize_button = ft.ElevatedButton("Otimizar Conteúdo", icon=ft.Icons.FILTER_LIST, on_click=self._handle_optimize_click, disabled=True, 
                                                 tooltip="Filtra páginas irrelevantes para economizar tokens e melhorar o foco da IA.", width=width_btn_bar)
        self.anonymize_button = ft.ElevatedButton("Anonimizar Dados", icon=ft.Icons.PRIVACY_TIP_OUTLINED, on_click=self._handle_anonymize_click, 
                                                    disabled=True, tooltip="Identifica e oculta dados e entidades antes de enviar à IA.", width=width_btn_bar)
        self.metrics_button = ft.TextButton(text="Total Tokens: 0", icon=ft.Icons.QUERY_STATS, on_click=self._show_metrics_dialog, 
                                                tooltip="Ver detalhes do consumo de tokens", width=200)

        self.clear_chat_button_1 = ft.IconButton(icon=ft.Icons.DELETE_SWEEP_OUTLINED, tooltip="Limpar Conversa e reiniciar", on_click=self._handle_clear_chat, disabled=True)
        self.clear_chat_button_2 = ft.ElevatedButton(text="Encerrar Chat", icon=ft.Icons.DELETE_SWEEP_OUTLINED, tooltip="Limpar Conversa e reiniciar", on_click=self._handle_clear_chat, disabled=False)
        self.clear_chat_button = ft.Container(content = self.clear_chat_button_1)
        
        self.settings_button = ft.IconButton(icon=ft.Icons.TUNE_ROUNDED, tooltip="Configurações", on_click=self._handle_toggle_settings_drawer)
        
        self.chat_history_view = ft.ListView(expand=True, spacing=15, auto_scroll=False)
        
        self.user_input_field = ft.TextField(
            hint_text="Digite sua pergunta...",
            expand=True, multiline=True, min_lines=2, max_lines=15,
            filled=True, border_radius=8, on_submit=self._handle_send_message,
            disabled=True # Inicia desabilitado
        )
        self.send_button = ft.IconButton(icon=ft.Icons.SEND_ROUNDED, tooltip="Enviar Mensagem", on_click=self._handle_send_message, disabled=True)
        
        self._initialize_file_picker()
        self.file_list_manager = self._initialize_file_list_manager()
        
        # Drawer de Configurações (agora um container lateral)
        self.settings_drawer_component = ChatSettingsDrawer(self.page) # Usa o drawer específico do Chat
        self.settings_drawer_container = ft.Container(content=self.settings_drawer_component, padding=10, width=0, animate=ft.Animation(300, ft.AnimationCurve.EASE_OUT_QUART))
        
        self._build_layout()
        
        # self.messages: List[Dict[str, Any]] = []
        self._restore_state_from_session()

    def _initialize_file_picker(self):
        """Inicializa e retorna uma instância do ManagedFilePicker."""
        global_picker = self.page.data.get("global_file_picker")
        if not global_picker:
            raise RuntimeError("FilePicker global não foi inicializado no app principal.")

        self.managed_file_picker = ManagedFilePicker(
            page=self.page,
            upload_dir=UPLOAD_TEMP_DIR,
            allowed_extensions=["pdf"] # "txt", "docx", "csv", "xlsx"
        )

    def _initialize_file_list_manager(self) -> FileListManager:
        return FileListManager(
            page=self.page,
            session_key_files_ordered=KEY_SESSION_CHAT_FILES,
            managed_file_picker=self.managed_file_picker,
            on_list_changed=self._on_file_list_changed
        )
    
    def _build_layout(self):
        """Constrói a estrutura visual da view de chat."""
        title_bar = ft.Text("Chat com Documentos",
                             style=ft.TextThemeStyle.HEADLINE_SMALL,
                             text_align=ft.TextAlign.CENTER)
        action_buttons_bar = ft.Row(
            [
                ft.Row([
                    self.upload_button, 
                    self.extract_button,
                    self.optimize_button,
                    self.anonymize_button,
                    self.metrics_button], wrap=True),
                #ft.Row([ft.Container(expand=True)]),
                ft.Row([
                    self.clear_chat_button,
                    self.settings_button], wrap=True)
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            wrap=True, width=self.page.width*0.9 # spacing=10
        )
        
        input_bar = ft.Row(
            [self.user_input_field, self.send_button],
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )

        main_content_column = ft.Column(
            [
                self.file_list_manager,
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
            title_bar,
            action_buttons_bar,
            ft.Divider(height=1),
            main_layout_with_drawer, # Substitui a coluna de conteúdo direto
            ft.Divider(height=1),
            ft.Row([
                ft.Container(expand=2),
                ft.Container(content=input_bar, padding=ft.padding.symmetric(vertical=5, horizontal=10), expand=96),
                ft.Container(expand=2),
            ])
        ]

    def _save_state_to_session(self):
        """Salva o estado atual do chat (mensagens, métricas) na sessão."""
        messages = self.chat_history_view.controls
        if messages:
            # Extrai os dados relevantes dos controles para serialização
            message_data = [c.data for c in self.chat_history_view.controls if hasattr(c, 'data')]
            self.user_cache[KEY_SESSION_CHAT_MESSAGES] = message_data

        self.user_cache[KEY_SESSION_CHAT_METRICS] = self.metrics_history

    def _start_new_chat_session(self):
        """Gera um novo ID de sessão de chat e o armazena."""
        self.chat_session_id = f"chat_{int(time.time())}_{secrets.token_hex(4)}"
        self.page.session.set(KEY_SESSION_CHAT_SESSION_ID, self.chat_session_id)
        logger.info(f"Nova sessão de chat iniciada com ID: {self.chat_session_id}")

    def _restore_state_from_session(self):
        """Restaura o estado do chat a partir da sessão ao carregar a view."""
        
        files = self.page.session.get(KEY_SESSION_CHAT_FILES) or []
        if files:
            self.file_list_manager.update_display(files)

        # Restaura mensagens
        messages = self.user_cache.get(KEY_SESSION_CHAT_MESSAGES) or []
        if messages:
            self.chat_history_view.controls.clear()
            for msg_data in messages:
                # Realiza o append diretamente em vez de chamar _add_message_to_view, pois não precisa chamar _save_state_to_session:
                bubble = self._create_message_bubble(msg_data)
                self.chat_history_view.controls.append(bubble) 
            self._update_message_actions()
        else:
            self._show_initial_greeting()

        # Restaura métricas
        self.metrics_history = self.user_cache.get(KEY_SESSION_CHAT_METRICS) or []
        self._update_metrics_summary_button()

        # Restaura ou cria o ID da sessão de chat
        self.chat_session_id = self.page.session.get(KEY_SESSION_CHAT_SESSION_ID)
        if not self.chat_session_id:
            self._start_new_chat_session()

        # self.page.update()
        self._update_button_states()
        self._update_processing_metadata_display()

    # --- Métodos relacionados ao containeir chat_history_view ---

    def _show_initial_greeting(self):
        """Adiciona uma mensagem inicial de boas-vindas ao chat."""
        if not self.chat_history_view.controls:
            initial_message = { "id": time.time(), "author": "IA", 
                                "text": "Olá! Carregue um ou mais documentos para iniciar a conversa." }
            self._add_message_to_view(initial_message)

    def _add_message_to_view(self, message_data: Dict[str, Any]):
        """Adiciona uma bolha de mensagem à lista de visualização e salva o estado."""
        bubble = self._create_message_bubble(message_data)
        self.chat_history_view.controls.append(bubble)
        if self.page and self.chat_history_view.page: 
            self._update_message_actions()
            self._save_state_to_session()
            self.page.update()

    def _update_last_message_text(self, text_chunk: str, append: bool = True):
        """Atualiza o texto da última mensagem na view."""
        if not self.chat_history_view.controls: 
            return
        last_bubble = self.chat_history_view.controls[-1]
        if append:
            last_bubble.data["text"] += text_chunk
        else:
            last_bubble.data["text"] = text_chunk

        # Re-renderiza apenas o conteúdo do último balão para eficiência
        content_placeholder = last_bubble.controls[1].controls[1].content.controls[0] # TODO: melhorar esse mapeamento
        self._render_message_content(content_placeholder, last_bubble.data)
        threading.Timer(0.1, content_placeholder.update).start()
        self._save_state_to_session()

    def _rebuild_chat_display(self):
        # Esta função agora apenas reconstrói os controles. A atualização das ações é centralizada.
        current_message_data = [c.data for c in self.chat_history_view.controls]
        self.chat_history_view.controls.clear()
        for data in current_message_data:
            self.chat_history_view.controls.append(self._create_message_bubble(data))
        
        self._update_message_actions()

        if self.chat_history_view.page:
            self.chat_history_view.update()

    def _create_message_bubble(self, message: Dict[str, Any]) -> ft.Row:
        """Cria um componente visual para uma única mensagem no chat."""
        is_user = message.get("author") == "User"
        msg_id = message.get("id")
                
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

        # is_last_message_in_list = self.chat_history_view.controls and self.chat_history_view.controls[-1].data.get("id") == msg_id
        # if not is_last_message_in_list:
        #     actions_popup.items.append(ft.PopupMenuItem(text="Retomar daqui", icon=ft.Icons.RESTART_ALT, data="resume", on_click=lambda e: self._handle_message_action(e, msg_id)))
        # 
        # is_rerun_visible = True if not is_user and is_last_message_in_list else False
        # if is_rerun_visible:
        #     actions_popup.items.append(ft.PopupMenuItem(text="Regenerar resposta", icon=ft.Icons.REPLAY, data="rerun", on_click=lambda e: self._handle_message_action(e, msg_id)))

        progressing_status = not is_user and not message['text'].strip()
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
                ft.Container(expand=2),  # 5% esquerda
                ft.Row(
                    controls=[
                        avatar if not is_user else ft.Container(),
                        bubble_container,
                        avatar if is_user else ft.Container()
                    ],
                    expand=96  # 90% centro
                ),
                ft.Container(expand=2)  # 5% direita
            ]
        )
        message_row.data = message # Anexa os dados diretamente na Row principal
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

    def _update_message_actions(self):
        """
        Atualiza os itens de menu contextuais (Regenerar, Retomar) para todas as mensagens.
        Deve ser chamado sempre que o histórico do chat for alterado.
        """
        if not self.chat_history_view.controls:
            return
        
        last_index = len(self.chat_history_view.controls) - 1

        # Itera sobre todas as bolhas de mensagem para ajustar seus menus
        for i, bubble in enumerate(self.chat_history_view.controls):
            # Acessa o PopupMenuButton dentro da estrutura do bubble
            # bubble (Row) -> controls[1] (Row interna) -> controls[1] (Container) -> content (Row) -> controls[1] (Stack) -> content (PopupMenuButton)
            popup_menu = bubble.controls[1].controls[1].content.controls[1].controls[1]
            
            # Remove itens de menu condicionais existentes para evitar duplicação
            popup_menu.items = [item for item in popup_menu.items if item.data not in ("rerun", "resume")]

            # Adiciona "Regenerar resposta" se for a última mensagem da conversa (seja do usuário ou da IA)
            if i == last_index:
                popup_menu.items.append(
                    ft.PopupMenuItem(text="Regenerar resposta", icon=ft.Icons.REPLAY, data="rerun", on_click=lambda e, mid=bubble.data["id"]: self._handle_message_action(e, mid))
                )

            # Adiciona "Retomar daqui" se não for a última mensagem de todas
            if i < last_index:
                popup_menu.items.append(
                    ft.PopupMenuItem(text="Retomar daqui", icon=ft.Icons.RESTART_ALT, data="resume", on_click=lambda e, mid=bubble.data["id"]: self._handle_message_action(e, mid))
                )

    # --- Handlers e Lógica de Negócio ---

    def _scroll_to_last_message(self):
        if self.chat_history_view.page:
            self.chat_history_view.scroll_to(offset=-1, duration=300, curve=ft.AnimationCurve.EASE_OUT)

    def _handle_send_message(self, e: ft.ControlEvent):
        if self.is_processing_response: 
            return
        
        user_text = self.user_input_field.value # .strip()
        if not user_text:
            return
        
        document_context = self.user_cache.get(KEY_SESSION_CHAT_DOCUMENT_CONTEXT)

        if not document_context:
            #show_snackbar(self.page, "Aguarde a extração de texto ser concluída ou carregue um arquivo.", color=theme.COLOR_WARNING)
            show_snackbar(self.page, "Para iniciar o chat é necessário extrair o conteúdo do(s) documento(s) carregados.", color=theme.COLOR_WARNING)
            self.page.run_thread(lambda: self._set_processing_state(False))
            return
        
        history_for_api = [ # Antes de adicionar a mensagem do usuário e a thinking message;
            {"role": "assistant" if msg["author"] == "IA" else "user", 
            "content": msg["text"]}
            for msg in [c.data for c in self.chat_history_view.controls] if msg.get("author") in ["User", "IA"]
        ]
        
        self._set_processing_state(True, clear_input=True)
        user_message = {"id": time.time(), "author": "User", "text": user_text}
        self._add_message_to_view(user_message)
        logger.info('[DEBUG] Enviando mensagem do usuário ao Chat...')
        self._scroll_to_last_message()

        self.file_list_manager.collapse_container()
        thinking_message_data = {"id": time.time(), "author": "IA", "text": ""}
        self._add_message_to_view(thinking_message_data)
        self._scroll_to_last_message()

        # Inicia a geração da resposta da IA em uma thread, passando o histórico já preparado
        threading.Thread(target=self._handle_ai_response, args=(document_context, history_for_api, user_text), daemon=True).start()

    def _handle_ai_response(self, document_context: str, history_for_api: List[Dict[str, str]], user_question: str):
        """
        Gerencia a chamada ao orquestrador e o streaming da resposta para a UI.
        """       
        # Prepara parâmetros para a IA
        settings = self.page.session.get(KEY_SESSION_ANALYSIS_SETTINGS) or {}
        api_key = self.page.session.get(f"decrypted_api_key_{settings.get('llm_provider', DEFAULT_LLM_PROVIDER)}") 
        
        if not api_key:
            error_msg = "Chave API não configurada. Por favor, configure-a no menu 'Provedores LLM'."
            logger.error(error_msg)
            self.page.run_thread(lambda: self._update_last_message_text(error_msg, append=False))
            self.page.run_thread(lambda: self._set_processing_state(False))
            return
        
        try:
            # Pega as instruções atuais
            instructions = self._get_active_system_prompt()

            # Verifica se o prompt mudou desde a última chamada 
            if self.last_used_prompt_text is None or self.last_used_prompt_text != instructions:
                logger.info("Detectada mudança no prompt de sistema. Resetando histórico da conversa para a IA.")
                self.orchestrator.reset_conversation_history()
            
            # Atualiza o último prompt usado para a próxima verificação
            self.last_used_prompt_text = instructions

            model_name = settings.get('llm_model', DEFAULT_LLM_MODEL) 
            response_generator = self.orchestrator.generate_response(
                api_key=api_key,
                model_name=model_name,
                document_context=document_context,
                instructions=instructions,
                history=history_for_api,
                user_question=user_question,
                loaded_llm_providers=self.page.session.get(KEY_SESSION_LOADED_LLM_PROVIDERS) or [],
                temperature=settings.get('llm_temperature', DEFAULT_TEMPERATURE),
                reasoning_mode=settings.get('reasoning_effort'),
                verbosity_level=settings.get('verbosity_level')
            )

            for response_part in response_generator:
                if response_part["type"] == "chunk":
                    self.page.run_thread(lambda chunk=response_part["content"]: self._update_last_message_text(chunk, append=True))
                    logger.info(f"[DEBUG] Chunk Msg LLM by model {model_name}: {response_part['content'][:160]}...")
                elif response_part["type"] == "final_metrics":
                    response_part["data"]["timestamp"] = datetime.now()                    
                    response_part["data"]["model_name"] = model_name
                    self.page.run_thread(lambda data=response_part["data"]: self._log_and_update_request_metrics(data))
                elif response_part["type"] == "error":
                    error_text = f"**Erro:** {response_part['content']}"
                    self.page.run_thread(lambda: self._update_last_message_text(error_text, append=False))
                    break
        finally:
            self.page.run_thread(lambda: self._set_processing_state(False))
            self.page.run_thread(lambda: self._scroll_to_last_message())

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

    def _get_active_system_prompt(self) -> str:
        """
        Retorna o texto do prompt de sistema ativo lendo diretamente da sessão.
        A responsabilidade de carregar os prompts (do Firestore ou fallback)
        é do ChatSettingsDrawer.
        """
        from src.flet_ui.components.settings_drawer import DEFAULT_PROMPTS
        DEFAULT_KEY = "flexivel"

        prompt_key_map = {
            "estrito": KEY_SESSION_CHAT_PROMPT_STRICT,
            "flexivel": KEY_SESSION_CHAT_PROMPT_FLEXIBLE,
            "custom": KEY_SESSION_CHAT_PROMPT_CUSTOM,
        }
        
        active_key = self.page.session.get(KEY_SESSION_CHAT_PROMPT_ACTIVE_KEY) or DEFAULT_KEY
        session_key = prompt_key_map.get(active_key)
        if session_key:
            if not self.user_cache.get(session_key):
                self.settings_drawer_component.load_default_prompts_from_firestore_or_fallback()

            instructions_in_session = self.user_cache.get(session_key)
            instructions_hardcoded = DEFAULT_PROMPTS.get(active_key, "")
            
            if instructions_in_session:
                logger.info(f"Instruction_Prompt obtido da sessão: {instructions_in_session[:60]}...")
            elif instructions_hardcoded:
                logger.warning(f"Instruction_Prompt não encontrado na sessão. Utilizando Default_Prompt hardcoded: {instructions_hardcoded[:60]}...")
            
            return instructions_in_session or instructions_hardcoded
        
        # Fallback final se a chave for desconhecida
        logger.warning(f"Instruction_Prompt sem chave mapeada! Utilizando fallback hardcoded: {DEFAULT_PROMPTS[DEFAULT_KEY][:60]}...")
        return DEFAULT_PROMPTS[DEFAULT_KEY]

    def _handle_message_action(self, e: ft.ControlEvent, message_id: float):
        """Handler central para ações do PopupMenuButton da mensagem."""
        action = e.control.data
        # all_messages_data = [c.data for c in self.chat_history_view.controls]
        # message_text = next((msg["text"] for msg in reversed(all_messages_data) if msg.get('if') == message_id), "")
        message_text = next((c.data["text"] for c in self.chat_history_view.controls if c.data.get('id') == message_id), "")

        if action == "copy": self.page.set_clipboard(message_text)
        elif action == "edit": self._handle_edit_message(message_id)
        elif action == "delete": self._handle_delete_message(message_id)
        elif action == "resume": self._handle_resume_from(message_id)
        elif action == "rerun": self._handle_rerun(message_id)

    def _handle_delete_message(self, message_id: float):
        self.chat_history_view.controls = [c for c in self.chat_history_view.controls if c.data["id"] != message_id]
        self._update_message_actions()
        self.chat_history_view.update()
        self._save_state_to_session()

    def _handle_edit_message(self, message_id: float):
        self.editing_message_id = message_id
        self._rebuild_chat_display()

    def _handle_save_edit(self, message_id: float, new_text: str):
        for control in self.chat_history_view.controls:
            if control.data["id"] == message_id:
                control.data["text"] = new_text
                break
        self.editing_message_id = None
        self._rebuild_chat_display()
        self._save_state_to_session()

    def _handle_cancel_edit(self, message_id: float):
        self.editing_message_id = None
        self._rebuild_chat_display()

    def _handle_resume_from(self, message_id: float):
        index = next((i for i, c in enumerate(self.chat_history_view.controls) if c.data["id"] == message_id), -1)
        if index != -1:
            self.chat_history_view.controls = self.chat_history_view.controls[:index + 1]
            self.orchestrator.reset_conversation_history() # Força o reenvio do contexto
            self._update_message_actions() # Apenas atualiza as ações, não precisa reconstruir
            self._save_state_to_session()
            self.page.run_thread(lambda: self._scroll_to_last_message())
            
    def _handle_rerun(self, message_id: float):
        rerun_index = next((i for i, c in enumerate(self.chat_history_view.controls) if c.data.get("id") == message_id), -1)
        if rerun_index == -1:
            logger.error(f"Não foi possível encontrar a mensagem com id {message_id} para regenerar.")
            return        
        
        rerun_control = self.chat_history_view.controls[rerun_index]
        author = rerun_control.data.get("author")

        if author == "IA":
            # Caso 1: Regenerando uma resposta da IA
            if rerun_index == 0: return # Não pode regenerar a primeira mensagem se for da IA
            self.orchestrator.reset_conversation_history() # Força o reenvio do contexto
            user_question = self.chat_history_view.controls[rerun_index - 1].data["text"]
            history_controls = self.chat_history_view.controls[:rerun_index - 1]
            self.chat_history_view.controls.pop(rerun_index) # Remove a resposta antiga da IA

        elif author == "User":
            # Caso 2: Gerando resposta para a última mensagem do usuário (após "Retomar daqui")
            self.orchestrator.reset_conversation_history() # Força o reenvio do contexto
            user_question = rerun_control.data["text"]
            history_controls = self.chat_history_view.controls[:rerun_index]
        else:
            return # Não faz nada se a mensagem não for do usuário ou da IA

        self._set_processing_state(True, clear_input=False)

        # Prepara o histórico para a API        
        history_for_api = [
            {"role": "assistant" if c.data["author"] == "IA" else "user", "content": c.data["text"]}
            for c in history_controls if c.data.get("author") in ["User", "IA"]
        ]

        thinking_message_data = {"id": time.time(), "author": "IA", "text": ""}
        self._add_message_to_view(thinking_message_data)

        document_context = self.user_cache.get(KEY_SESSION_CHAT_DOCUMENT_CONTEXT)
        if not document_context:
            show_snackbar(self.page, "Contexto do documento não encontrado para regenerar a resposta.", color=theme.COLOR_ERROR)
            return

        threading.Thread(target=self._handle_ai_response, args=(document_context, history_for_api, user_question), daemon=True).start()
    
    def _handle_clear_chat(self, e: ft.ControlEvent):
        def confirm_action():
            # Salva o resumo da sessão antes de limpar
            self._log_session_summary_metric()            
            # Limpa todas as chaves de sessão relacionadas ao chat
            for key in (KEY_SESSION_CHAT_FILES, KEY_SESSION_CHAT_HAS_OPTIMIZED, KEY_SESSION_PROCESSING_METADATA):
                if self.page.session.contains_key(key):
                    self.page.session.remove(key)

            clear_user_cache(self.page)
            self.user_cache = get_user_cache(self.page)

            self.chat_history_view.controls.clear()
            self.metrics_history.clear()
            self.last_used_prompt_text = None # Reseta o prompt rastreado
            self._start_new_chat_session() # Inicia uma nova sessão de chat com novo ID
            self.orchestrator.reset_conversation_history() # Limpa o ID da resposta anterior
            self._update_metrics_summary_button()
                
            self._update_processing_metadata_display()

            self._show_initial_greeting()
            self._on_file_list_changed() # Aciona o reset completo da UI

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
            self.settings_button.bgcolor = bgcolor=ft.Colors.with_opacity(0.40, theme.COLOR_ERROR)
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

    def _update_button_states_by_chat(self):
        if self.metrics_history:
            # Se há histórico de métricas: implica que o chat começou
            self.upload_button.disabled = True
            self.clear_chat_button.content = self.clear_chat_button_2 # ElevatedButton
            self.file_list_manager.disable_interactions()
        else:
            self.upload_button.disabled = False
            self.clear_chat_button.content = self.clear_chat_button_1 # Iconbutton
            self.file_list_manager.enable_interactions()
        
        if self.upload_button.page:
            self.page.update(self.upload_button, self.clear_chat_button)
            
    def _update_button_states(self):
        """Centraliza a lógica de habilitação/desabilitação de botões e campos."""
        has_files = bool(self.page.session.get(KEY_SESSION_CHAT_FILES))
        has_context = bool(self.user_cache.get(KEY_SESSION_CHAT_DOCUMENT_CONTEXT))
        has_optimized = self.page.session.get(KEY_SESSION_CHAT_HAS_OPTIMIZED) or False

        self._update_button_states_by_chat()

        # Botão de Processar: habilitado se há arquivos e o contexto ainda não foi extraído.
        self.extract_button.disabled = not has_files or has_context

        # Botão de otimização: habilitado se há arquivos e o contexto ainda não foi otimizado
        self.optimize_button.disabled = not has_files or has_optimized
        
        # self.anonymize_button.disabled = not has_context # Ainda não habilitada a função

        # Campos de Chat: habilitados desde o carregamento de arquivos.
        self.clear_chat_button.content.disabled = not has_files

        self.user_input_field.disabled = not has_files
        self.send_button.disabled = not has_files # not has_context

        if has_context:
            self.extract_button.text = "Texto extraído"
            self.extract_button.icon = ft.Icons.CHECK_CIRCLE
        else:
            self.extract_button.text = "Extrair Texto(s)"
            self.extract_button.icon = ft.Icons.PLAY_CIRCLE_OUTLINE

        if has_optimized:
            self.optimize_button.text = "Conteúdo otimizado"
            self.optimize_button.icon = ft.Icons.CHECK_CIRCLE
        else:
            self.optimize_button.text = "Otimizar Conteúdo"
            self.optimize_button.icon = ft.Icons.FILTER_LIST
            
        hide_loading_overlay(self.page)
        self.page.update()

    # --- Handlers de Ações ---

    def _get_current_analysis_settings(self) -> Dict[str, Any]:
        """
        Busca as configurações de análise atuais da sessão, com fallback.
        """
        settings = self.page.session.get(KEY_SESSION_ANALYSIS_SETTINGS)
        if not isinstance(settings, dict):
            return FALLBACK_ANALYSIS_SETTINGS.copy()
        
        # Garante que os tipos numéricos estejam corretos
        current_settings = settings.copy()
        try:
            current_settings['llm_input_token_limit'] = int(current_settings.get('llm_input_token_limit', FALLBACK_ANALYSIS_SETTINGS['llm_input_token_limit']))
        except (ValueError, TypeError):
            current_settings['llm_input_token_limit'] = FALLBACK_ANALYSIS_SETTINGS['llm_input_token_limit']
        
        return current_settings

    def _handle_upload_click(self, e: ft.ControlEvent):
        # Limpa o contexto antigo antes de carregar novos arquivos
        self.user_cache.pop(KEY_SESSION_CHAT_DOCUMENT_CONTEXT, None)
        
        show_loading_overlay(self.page, "Abrindo seletor de arquivos...")
        
        self.managed_file_picker.pick_files(allow_multiple=True,
                                            # on_individual_file_complete=lambda s, p, f: None,
                                            on_batch_complete=self._handle_files_uploaded)

    def _handle_files_uploaded(self, batch_results: List[Dict[str, Any]]):
        """Callback do ManagedFilePicker após o término do upload."""
        hide_loading_overlay(self.page)
        successful_files = [f for f in batch_results if f.get("success")]
        if not successful_files:
            logger.info("Nenhum arquivo carregado.")
            show_snackbar(self.page, "Nenhum arquivo válido foi carregado.", color=theme.COLOR_WARNING)
            return
        
        self._update_processing_metadata_display()
        self.file_list_manager.expand_container()

        self.page.session.set(KEY_SESSION_CHAT_FILES, successful_files)
        self.file_list_manager.update_display(successful_files)
        
        logger.info(f"Carregados {len(successful_files)} arquivos: {successful_files}")
        self._update_button_states()

        show_snackbar(self.page, f"{len(successful_files)} documento(s) carregado(s). Clique em 'Extrair Texto' para continuar.", color=theme.COLOR_SUCCESS)

    def _on_file_list_changed(self):
        """Callback do FileListManager para a view de Chat."""
        # Se a lista de arquivos mudar, o contexto extraído anteriormente é invalidado.

        # Caso já haja interação com LLM ativa, em vez de incluir aqui um confirmation_dialog para redirecinar para handle_clear_chat,
        # Opto por tornar disabled os componentes que alteram a lista de arquivos, forçando o usuário a limpar a conversa primeiro.

        self.user_cache.pop(KEY_SESSION_CHAT_DOCUMENT_CONTEXT, None)
        self.user_cache.pop(KEY_SESSION_CHAT_RAW_PAGES_TEXT, None)
        if self.page.session.contains_key(KEY_SESSION_CHAT_HAS_OPTIMIZED, KEY_SESSION_PROCESSING_METADATA):
            self.page.session.remove(KEY_SESSION_CHAT_HAS_OPTIMIZED) # Invalida a otimização
        logger.info("Contexto do chat invalidado devido à alteração na lista de arquivos.")
        self._update_processing_metadata_display()
        self.file_list_manager.update_display() # Apenas atualiza a própria UI
        self._update_button_states() # Reavalia o estado dos botões

    def _handle_process_extract(self, e: ft.ControlEvent, optimize_too: bool = False):
        """Inicia a extração de texto dos arquivos carregados."""
        files = self.page.session.get(KEY_SESSION_CHAT_FILES)
        if not files:
            show_snackbar(self.page, "Nenhum arquivo para processar.", color=theme.COLOR_WARNING)
            return

        # Se o chat já começou, esta ação não deve ser permitida; Mas em vez de incluir um return aqui, 
        # opto por tornar disabled o botão de processar quando o chat já começou.

        show_loading_overlay(self.page, "Extraindo texto dos documentos...")
        threading.Thread(target=self._extract_raw_context_from_files, args=(files, optimize_too), daemon=True).start()

    def _handle_optimize_click(self, e: ft.ControlEvent):
        """Inicia o pré-processamento opcional dos documentos."""
        raw_pages_text = self.user_cache.get(KEY_SESSION_CHAT_RAW_PAGES_TEXT) or {}
        if not raw_pages_text:
            self._handle_process_extract(None, optimize_too=True)
            #show_snackbar(self.page, "Aguarde a extração inicial do texto antes de otimizar.", color=theme.COLOR_WARNING)
            return
        
        # Aqui deve haver o mesmo bloqueio que temos em _handle_process_click.

        show_loading_overlay(self.page, "Otimizando páginas relevantes...")
        threading.Thread(target=self._preprocess_documents, args=(raw_pages_text,), daemon=True).start()

    def _preprocess_documents(self, pre_extracted_texts):
        """
        Usa o PDFDocumentAnalyzer para extrair e consolidar o texto dos arquivos.
        Este é o processo de OTIMIZAÇÃO. Executado em uma thread separada.
        """
        try:

            # Usa os textos pré-extraídos
            files_info = self.page.session.get(KEY_SESSION_CHAT_FILES) or []
            pdf_paths_ordered = [f['path_or_message'] for f in files_info]

            # Reutiliza a lógica de pré-processamento do nc_analyzer
            from src.core.pdf_processor import PDFDocumentAnalyzer
            analyzer = PDFDocumentAnalyzer()

            # Pipeline de análise de PDF
            # processed_data, ordered_keys, emb_vectors, tfidf_vectors, tfidf_scores = analyzer.analyze_pdf_documents(pdf_paths)
            processed_data, ordered_keys, emb_vectors, tfidf_vectors, tfidf_scores = analyzer.analyze_pre_extracted_texts(pre_extracted_texts, pdf_paths_ordered)

            relevant_indices, _, _ = analyzer.filter_and_classify_pages(
                processed_data, ordered_keys, emb_vectors, tfidf_vectors, tfidf_scores
            )
            
            # Usamos um limite de tokens alto para manter o contexto completo
            settings = self._get_current_analysis_settings()
            token_limit = settings.get("llm_input_token_limit", FALLBACK_ANALYSIS_SETTINGS["llm_input_token_limit"])
            _, aggregated_text, _, final_tokens  = analyzer.group_texts_by_relevance_and_token_limit(
                processed_data, relevant_indices, token_limit
            )

            processing_metadata = {
                "Modo": "Otimizado / Filtrado",
                "Páginas Totais": len(ordered_keys),
                "Páginas Relevantes": len(relevant_indices),
                "Tokens para LLM": f"{final_tokens:,}".replace(",", ".")
            }

            self.page.session.set(KEY_SESSION_PROCESSING_METADATA, processing_metadata)

            if not aggregated_text.strip():
                raise ValueError("Nenhum texto relevante foi extraído dos documentos.")

            # Salva o contexto na sessão
            self.page.run_thread(self._update_processing_metadata_display, processing_metadata)
            self.user_cache[KEY_SESSION_CHAT_DOCUMENT_CONTEXT] = aggregated_text
            self.page.session.set(KEY_SESSION_CHAT_HAS_OPTIMIZED, True)
            self._log_file_processing_metrics(optimized=True, total_pages=len(ordered_keys), relevant_pages=len(relevant_indices))

            # Atualiza a UI na thread principal
            def update_ui_after_processing():
                hide_loading_overlay(self.page)                
                show_snackbar(self.page, f"{len(pdf_paths_ordered)} documento(s) processado(s) e pronto(s) para o chat.", color=theme.COLOR_SUCCESS)
                self._update_button_states() # Atualiza todos os botões e a UI geral           
                show_snackbar(self.page, f"Conteúdo otimizado (filtrado) a ser utilizado no Chat.", color=theme.COLOR_SUCCESS)     

            self.page.run_thread(update_ui_after_processing)

        except Exception as e:
            logger.error(f"Erro ao pré-processar documentos para o chat: {e}", exc_info=True)
            def update_ui_on_error(e: Exception):
                hide_loading_overlay(self.page)
                msg_error = f"Erro ao processar documentos: {e}"
                logger.error(msg_error, exc_info=True)
                show_snackbar(self.page, msg_error, color=theme.COLOR_ERROR)
            self.page.run_thread(update_ui_on_error(e))

    def _extract_raw_context_from_files(self, files: List[Dict[str, Any]], optimize_too: bool = False):
        """
        Extrai e concatena o texto bruto de todas as páginas de todos os arquivos carregados.
        Este é o fallback para quando a otimização não é executada.
        """
        try:
            from src.core.pdf_processor import PDFDocumentAnalyzer
            analyzer = PDFDocumentAnalyzer()
            raw_pages_text_map = {}
            all_texts_concatenated = []

            start_time_proc = perf_counter()
            total_pages_raw = 0
            for file_info in files:
                pdf_path = file_info["path_or_message"]
                pages = analyzer.extractor.extract_texts_from_pages(pdf_path)
                total_pages_raw += len(pages)
                raw_pages_text_map[pdf_path] = pages
                all_texts_concatenated.extend([text for _, text in pages])

            processing_metadata = {
                "Modo": "Completo / Não otimizado",
                "Total de Páginas": total_pages_raw,
                "Tempo de Extração": format_seconds_to_min_sec(perf_counter() - start_time_proc),
            }
            self.page.session.set(KEY_SESSION_PROCESSING_METADATA, processing_metadata)
            self.page.run_thread(self._update_processing_metadata_display, processing_metadata)

            self._log_file_processing_metrics(optimized=False, total_pages=total_pages_raw)
            self.user_cache[KEY_SESSION_CHAT_RAW_PAGES_TEXT] = raw_pages_text_map
            self.user_cache[KEY_SESSION_CHAT_DOCUMENT_CONTEXT] = " ".join(all_texts_concatenated)            
            self.page.run_thread(lambda: show_snackbar(self.page, "Extração de texto concluída.", color=theme.COLOR_SUCCESS))
            self.page.run_thread(self._update_button_states)

            if optimize_too:
                self.page.run_thread(lambda: self._handle_optimize_click(None))

        except Exception as e:
            def update_ui_on_error(e):
                hide_loading_overlay(self.page)
                msg_error = f"Erro ao extrair texto: {e}"
                logger.error(msg_error, exc_info=True)
                show_snackbar(self.page, msg_error, color=theme.COLOR_ERROR)
            self.page.run_thread(update_ui_on_error(e))

    def _update_processing_metadata_display(self, proc_meta: Dict[str, Any] = None):
        """Atualiza a exibição de metadados no FileListManager."""
        
        data_to_display = proc_meta or self.page.session.get(KEY_SESSION_PROCESSING_METADATA)

        if not data_to_display:
            self.file_list_manager.update_metadata_display(None)
            return

        data_rows = []
        for key, value in data_to_display.items():
            data_rows.append((f"{key}:", str(value)))

        if data_rows:
            metadata_table = CompactKeyValueTable(
                data=data_rows,
                key_col_width=160,  # Ajuste a largura da coluna de chaves
                value_col_width=None, 
                row_spacing=4, col_spacing=8,      
                default_text_size=14                
            )
            
            final_metadata_content = ft.Column([
                ft.Container(height=5),
                ft.Container(ft.Text("Dados do Processamento:", weight=ft.FontWeight.BOLD, size=14), padding=ft.padding.only(left=12)),
                ft.Container(metadata_table, padding=ft.padding.only(left=30, top=10, bottom=10)),
            ])
            
            self.file_list_manager.update_metadata_display(final_metadata_content)
        else:
            self.file_list_manager.update_metadata_display(None)

    def _handle_anonymize_click(self, e: ft.ControlEvent):
        """Handler para o botão de anonimização (ainda não implementado)."""
        show_snackbar(
            self.page,
            "A funcionalidade de anonimização de dados ainda não está disponível.",
            color=theme.COLOR_WARNING
        )

    def _log_and_update_request_metrics(self, metrics_data: dict):
        """
        Adiciona os dados da última resposta ao histórico de métricas,
        salva a métrica individual no Firestore e atualiza a UI.
        """
        self.metrics_history.append(metrics_data)
        self._update_button_states_by_chat()
        self._save_state_to_session()
        self._update_metrics_summary_button()

        # Envia a métrica desta requisição específica para o Firestore
        self._log_single_request_metric(metrics_data)        

    def _update_metrics_summary_button(self):
        """Calcula o total de tokens de input e atualiza o botão na barra superior."""
        total_tokens = sum(m.get('total_tokens', 0) for m in self.metrics_history)
        self.metrics_button.text = f"Total Tokens: {total_tokens:,}".replace(",", ".")
        if self.metrics_button.page:
            self.metrics_button.update()

    def _show_metrics_dialog(self, e: ft.ControlEvent):
        """Exibe um diálogo com a tabela detalhada de uso de tokens."""
        
        total_input_tokens = sum(m.get('input_tokens', 0) for m in self.metrics_history)
        if not total_input_tokens:
            return
                
        total_cost_usd = 0
        metric_rows = []
        for metric in sorted(self.metrics_history, key=lambda x: x.get('timestamp'), reverse=True):
            cost_usd = metric.get('total_cost_usd', 0)
            cost_brl = cost_usd * cotacao_dolar_to_real
            total_cost_usd += cost_usd
            timestamp = metric.get('timestamp', datetime.now())
            metric_rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(timestamp.strftime("%d/%m/%Y - %H:%M:%S"))),
                    ft.DataCell(ft.Text(metric.get('model_name', 'N/A'))),
                    ft.DataCell(ft.Text(str(metric.get('input_tokens', 0)))),
                    ft.DataCell(ft.Text('(' + str(metric.get('cached_tokens', 0)) + ')')),
                    ft.DataCell(ft.Text(str(metric.get('output_tokens', 0)))),
                    ft.DataCell(ft.Text('(' + str(metric.get('reasoning_tokens', 0)) + ')')),
                    ft.DataCell(ft.Text(f"U$ {cost_usd:.6f}")),
                    ft.DataCell(ft.Text(f"R$ {cost_brl:.6f}")),
                ])
            )

        total_cost_brl = total_cost_usd * cotacao_dolar_to_real

        dialog_content = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Data/Hora")),
                ft.DataColumn(ft.Text("Modelo")),
                ft.DataColumn(ft.Text("Input")),
                ft.DataColumn(ft.Text("Cache")),
                ft.DataColumn(ft.Text("Output")),
                ft.DataColumn(ft.Text("Reasoning")),
                ft.DataColumn(ft.Text("Custo (USD)")),
                ft.DataColumn(ft.Text("Custo (BRL)")),
            ],
            rows=metric_rows, column_spacing=20,
        )

        footer_row = ft.DataRow(cells=[
            ft.DataCell(ft.Text("")),
            ft.DataCell(ft.Text("Total estimado", weight=ft.FontWeight.BOLD)),
            ft.DataCell(ft.Text("")), ft.DataCell(ft.Text("")), 
            ft.DataCell(ft.Text("")), ft.DataCell(ft.Text("")),
            ft.DataCell(ft.Text(f"U$ {total_cost_usd:.6f}", weight=ft.FontWeight.BOLD)),
            ft.DataCell(ft.Text(f"R$ {total_cost_brl:.6f}", weight=ft.FontWeight.BOLD)),
        ])

        dialog_content.rows.append(footer_row)

        metrics_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Detalhamento de Consumo de Tokens por Requisição"),
            content=ft.Column([dialog_content], height=self.page.height*0.6, scroll=ft.ScrollMode.ADAPTIVE),
            actions=[ft.TextButton("Fechar", on_click=lambda _: self._close_dialog(metrics_dialog))],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self.page.overlay.append(metrics_dialog)
        metrics_dialog.open = True
        self.page.update()

    def _close_dialog(self, dialog: ft.AlertDialog):
        dialog.open = False
        self.page.update()
        self.page.overlay.remove(dialog)
    

    # --- Métodos de Logging de Métricas ---
    def _get_valid_user_context(self) -> Optional[tuple[str, str]]:
        from src.flet_ui.app import check_and_refresh_token_if_needed
        if not check_and_refresh_token_if_needed(self.page): return None
        
        user_token = self.page.session.get("auth_id_token")
        user_id = self.page.session.get("auth_user_id")

        if not user_token or not user_id:
            logger.error("Contexto de usuário inválido para logging de métricas.")
            return None
        return user_token, user_id

    def _log_file_processing_metrics(self, optimized: bool, total_pages: int, relevant_pages: Optional[int] = None):
        context = self._get_valid_user_context()
        if not context: return
        user_token, user_id = context

        files = self.page.session.get(KEY_SESSION_CHAT_FILES) or []
        filenames = [f.get('name', 'N/A') for f in files]
        
        processing_data = {
            "was_optimized": optimized,
            "total_pages_in_docs": total_pages
        }        
        if relevant_pages is not None:
            processing_data["relevant_pages_after_optimization"] = relevant_pages

        metric_payload = {
            "chat_session_id": self.chat_session_id,
            "start_timestamp": datetime.now().isoformat(),
            "files_info": {
                "count": len(filenames),
                "names": filenames
            },
            "processing_info": processing_data
        }
        
        doc_path = f"user_metrics/{user_id}/chat_sessions/{self.chat_session_id}"
        self.firestore_client.set_document_data(user_token, doc_path, metric_payload) # Cria o documento

    def _log_single_request_metric(self, request_metric: Dict[str, Any]):
        context = self._get_valid_user_context()
        if not context: return
        user_token, user_id = context

        request_timestamp = request_metric.get("timestamp", datetime.now())
        request_id = f"req_{request_timestamp.strftime('%Y%m%d%H%M%S%f')}"

        # Cria um dicionário aninhado. A chave 'requests' conterá um mapa,
        # e estamos adicionando/atualizando um campo (request_id) dentro desse mapa.

        metric_payload = {
            "requests": {
                request_id: {
                    "timestamp": request_timestamp.isoformat(),
                    "model_name": request_metric.get("model_name"),
                    "input_tokens": request_metric.get("input_tokens"),
                    "cached_tokens": request_metric.get("cached_tokens"),
                    "output_tokens": request_metric.get("output_tokens"),
                    "reasoning_tokens": request_metric.get("reasoning_tokens"),
                    "total_cost_usd": request_metric.get("total_cost_usd"),
                }
            }
        }
        
        doc_path = f"user_metrics/{user_id}/chat_sessions/{self.chat_session_id}"
        self.firestore_client.set_document_data(user_token, doc_path, metric_payload, merge=True)

    def _log_session_summary_metric(self):
        context = self._get_valid_user_context()
        if not context or not self.metrics_history: return
        user_token, user_id = context

        total_input = sum(m.get('input_tokens', 0) for m in self.metrics_history)
        total_output = sum(m.get('output_tokens', 0) for m in self.metrics_history)
        total_cost = sum(m.get('total_cost_usd', 0) for m in self.metrics_history)

        summary_payload = {
            "chat_session_id": self.chat_session_id,
            "end_timestamp": datetime.now().isoformat(),
            "summary": {
                "total_requests": len(self.metrics_history),
                "total_input_tokens": total_input,
                "total_output_tokens": total_output,
                "total_session_cost_usd": total_cost,
            }
        }
        
        doc_path = f"user_metrics/{user_id}/chat_sessions/{self.chat_session_id}"
        
        self.firestore_client.set_document_data(user_token, doc_path, summary_payload, merge=True)


def create_chat_view_content(page: ft.Page) -> ft.Control:
    """Função de fábrica para criar a view de Chat com Documentos."""

    # Aguarda o pré-carregamento dos módulos pesados ser concluído
    if not app_cache.heavy_imports_loading_event.is_set():
        logger.info("Aguardando conclusão do pré-carregamento de módulos...")
        # Define um timeout para não travar a aplicação indefinidamente
        app_cache.heavy_imports_loading_event.wait(timeout=180)
    else:
        logger.debug("Pré-carregamento de módulos já concluído.")

    logger.info("View Chat_Docs: Iniciando criação (nova estrutura).")
    
    # A verificação de user_cache com prompts_instructions é feita no building com DrawerSettings
    
    start_time_p = perf_counter()
    retorno = ChatViewContent(page)
    execution_time_p = perf_counter() - start_time_p
    logger.info(f"[DEBUG] Create_analyze_pdf_content em {execution_time_p:.4f}s")
    
    return retorno

