# src/flet_ui/views/chat_view.py
import flet as ft
import time
import threading
from typing import List, Dict, Any, Optional

from src.flet_ui import theme
from src.flet_ui.components import (
    show_confirmation_dialog,
    ManagedFilePicker,
    show_loading_overlay,
    hide_loading_overlay
)
# Importa o novo componente de drawer refatorado
from src.flet_ui.settings_drawer import SettingsDrawerManager

from src.settings import UPLOAD_TEMP_DIR

import logging
logger = logging.getLogger(__name__)

# Chave de sessão para os arquivos carregados no chat
KEY_SESSION_CHAT_FILES = "chat_view_loaded_files"

class ChatViewContent(ft.Column):
    """
    Componente principal da interface de usuário para o chat com documentos.
    Gerencia o layout, o histórico de mensagens e a interação do usuário.
    """
    def __init__(self, page: ft.Page):
        super().__init__(expand=True, spacing=10)
        self.page = page
        
        # Estado da UI
        self.messages: List[Dict[str, Any]] = []
        self.is_processing_response = False
        self.editing_message_id: Optional[float] = None
        self._is_drawer_open = False

        # Controles da UI
        self.upload_button = ft.ElevatedButton("Carregar Arquivos", icon=ft.Icons.UPLOAD_FILE, on_click=self._handle_upload_click)
        self.anonymize_switch = ft.Switch(label="Habilitar Anonimização", value=False)
        self.clear_chat_button = ft.IconButton(icon=ft.Icons.DELETE_SWEEP_OUTLINED, tooltip="Limpar Conversa", on_click=self._handle_clear_chat)
        self.settings_button = ft.IconButton(icon=ft.Icons.TUNE_ROUNDED, tooltip="Configurações", on_click=self._handle_toggle_settings_drawer)
        
        self.file_list_view = ft.ListView(expand=False, spacing=3)
        self.file_list_panel = self._create_panel("Arquivos Carregados", self.file_list_view, visible=False)
        
        self.metrics_content = ft.Column()
        self.metrics_panel = self._create_panel("Métricas da Sessão", self.metrics_content, visible=False)
        
        self.chat_history_view = ft.ListView(expand=True, spacing=15, auto_scroll=False)
        
        self.user_input_field = ft.TextField(
            hint_text="Digite sua pergunta...",
            expand=True, multiline=True, min_lines=2, max_lines=15,
            filled=True, border_radius=8, on_submit=self._handle_send_message
        )
        
        self.send_button = ft.IconButton(icon=ft.Icons.SEND_ROUNDED, tooltip="Enviar Mensagem", on_click=self._handle_send_message)
        
        self.managed_file_picker = self._initialize_file_picker()
        
        # Drawer de Configurações (agora um container lateral)
        self.settings_drawer_component = SettingsDrawerManager(self.page)
        self.settings_drawer_container = ft.Container(
            content=self.settings_drawer_component, padding=10, width=0,
            animate=ft.Animation(300, ft.AnimationCurve.EASE_OUT_QUART)
            # (offset=-1, duration=300, curve=ft.AnimationCurve.EASE_OUT)
        )

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
            allowed_extensions=["pdf", "txt", "docx", "csv", "xlsx"]
        )

    def _build_layout(self):
        """Constrói a estrutura visual da view de chat."""
        top_bar = ft.Row(
            [
                self.upload_button, 
                ft.Container(expand=True),
                self.anonymize_switch,
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

    def _show_initial_greeting(self):
        """Adiciona uma mensagem inicial de boas-vindas ao chat."""
        initial_message = { "id": time.time(), "author": "IA", 
                           "text": "Olá! Por favor, carregue os documentos que você gostaria de analisar. Após o carregamento, você poderá fazer perguntas sobre o conteúdo deles." }
        self.messages.append(initial_message)
        self._update_chat_display()

    def _update_chat_display(self):
        """Limpa e recria a lista de mensagens na UI."""
        self.chat_history_view.controls.clear()
        is_last_message_from_ia = self.messages and self.messages[-1]["author"] == "IA"
        
        for i, msg in enumerate(self.messages):
            is_last_message_in_list = i == len(self.messages) - 1
            is_rerun_visible = not msg["author"] == "User" and is_last_message_from_ia and is_last_message_in_list
            bubble = self._create_message_bubble(msg, is_rerun_visible)
            self.chat_history_view.controls.append(bubble)
        
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
            visible=False, height=38,
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

        self._render_message_content(content_placeholder, message)

        container_min_height = ft.Container(height=38)
        message_row_int = ft.Row([content_placeholder, container_min_height, actions_popup], vertical_alignment=ft.CrossAxisAlignment.START)

        bubble_container = ft.Container(
            content=message_row_int, padding=12, border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE) if is_user else ft.Colors.with_opacity(0.08, theme.PRIMARY),
            on_hover=lambda e, tb=actions_popup: self._handle_bubble_hover(e, tb, msg_id),
            expand=True
        )
        
        message_layout = ft.Row([
            avatar, bubble_container
        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.START, expand=True)
        
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

    def _render_message_content(self, container: ft.Container, message: Dict[str, Any]):
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
        else:
            container.content = ft.Markdown(texto_formatado, selectable=True, extension_set=ft.MarkdownExtensionSet.COMMON_MARK)

    # --- Handlers de Ações ---

    def _handle_upload_click(self, e: ft.ControlEvent):
        show_loading_overlay(self.page, "Abrindo seletor de arquivos...")
        self.managed_file_picker.pick_files(allow_multiple=True)
        # hide_loading_overlay será chamado no callback do picker

    def _handle_files_uploaded(self, batch_results: List[Dict[str, Any]]):
        """Callback do ManagedFilePicker após o término do upload."""
        hide_loading_overlay(self.page)
        successful_files = [f for f in batch_results if f.get("success")]
        if not successful_files: return

        self.page.session.set(KEY_SESSION_CHAT_FILES, successful_files)
        self.file_list_view.controls.clear()
        for f in successful_files:
            self.file_list_view.controls.append(ft.ListTile(title=ft.Text(f["name"]), leading=ft.Icon(ft.Icons.DESCRIPTION_OUTLINED), dense=True))
        
        self.file_list_panel.visible = True
        self.file_list_panel.update()

    def _handle_send_message(self, e: ft.ControlEvent):
        if self.is_processing_response: 
            return
        
        user_text = self.user_input_field.value # .strip()
        if not user_text:
            return

        self._set_processing_state(True, clear_input=True)
        self.messages.append({"id": time.time(), "author": "User", "text": user_text})
        self._update_chat_display()
        self.chat_history_view.scroll_to(offset=-1, duration=300, curve=ft.AnimationCurve.EASE_OUT)
        self._simulate_ai_response()

    def _simulate_ai_response(self):
        thinking_message = {"id": time.time(), "author": "IA", "text": "Processando..."}
        self.messages.append(thinking_message)
        self._update_chat_display()
        self.chat_history_view.scroll_to(offset=-1, duration=300, curve=ft.AnimationCurve.EASE_OUT)

        def generate_dummy_response():
            self.messages.pop()
            dummy_response = {"id": time.time(), "author": "IA", "text": f"Resposta simulada.\nTimestamp: `{time.time()}`"}
            self.messages.append(dummy_response)
            
            self.page.run_thread(lambda: (
                self._set_processing_state(False),
                self._update_chat_display(),
                self._simulate_metrics_update()
            ))

        threading.Timer(1.5, generate_dummy_response).start()

    def _set_processing_state(self, is_processing: bool, clear_input: bool = False):
        if clear_input:
            self.user_input_field.value = ""
        
        self.is_processing_response = is_processing
        self.user_input_field.disabled = is_processing
        self.send_button.disabled = is_processing
        self.user_input_field.update()
        self.send_button.update()
        if not is_processing:
            self.user_input_field.focus()

    def _simulate_metrics_update(self):
        self.metrics_content.controls = [
            ft.Row([ft.Text("Custo da Sessão:", weight=ft.FontWeight.BOLD), ft.Text(f"U$ {time.time() % 1:.4f}")]),
            ft.Row([ft.Text("Tokens Utilizados:", weight=ft.FontWeight.BOLD), ft.Text(f"{int(time.time() % 10000)}")]),
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
            self.messages = [msg for msg in self.messages if msg["id"] != message_id]
            self._update_chat_display()
            self._set_processing_state(True)
            self._simulate_ai_response()
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
            content=ft.Text("Tem certeza que deseja apagar o histórico e remover os arquivos desta sessão?"),
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

