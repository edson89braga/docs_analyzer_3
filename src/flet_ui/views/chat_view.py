# src/flet_ui/views/chat_view.py
import flet as ft
import time
import threading
from typing import List, Dict, Any, Optional

from src.flet_ui import theme
from src.flet_ui.components import show_confirmation_dialog, CardWithHeader

import logging
logger = logging.getLogger(__name__)

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

        # Controles da UI
        self.anonymize_switch = ft.Switch(label="Habilitar Anonimização", value=False)
        self.upload_button = ft.ElevatedButton("Carregar Arquivos", icon=ft.Icons.UPLOAD_FILE)
        self.clear_chat_button = ft.IconButton(
            icon=ft.Icons.DELETE_SWEEP_OUTLINED,
            tooltip="Limpar Conversa",
            on_click=self._handle_clear_chat
        )
        self.settings_button = ft.IconButton(
            icon=ft.Icons.TUNE_ROUNDED,
            tooltip="Configurações do Chat",
            on_click=self._handle_open_settings_drawer
        )
        
        self.file_list_panel = self._create_placeholder_panel("Arquivos Carregados", visible=False)
        self.metrics_panel = self._create_placeholder_panel("Métricas da Sessão", visible=False)
        
        self.chat_history_view = ft.ListView(
            expand=True, 
            spacing=15, 
            auto_scroll=True,
            padding=ft.padding.symmetric(horizontal=15)
        )
        
        self.user_input_field = ft.TextField(
            hint_text="Digite sua pergunta (Ctrl+Enter para enviar)...",
            expand=True,
            multiline=True,
            min_lines=1,
            max_lines=15,
            filled=True,
            border_radius=8,
            on_submit=self._handle_send_message
        )
        
        self.send_button = ft.IconButton(
            icon=ft.Icons.SEND_ROUNDED,
            tooltip="Enviar Mensagem",
            on_click=self._handle_send_message
        )
        
        self._build_layout()
        self._build_settings_drawer()
        self._show_initial_greeting()

    def _build_layout(self):
        """Constrói a estrutura visual da view de chat."""
        top_bar = ft.Row(
            [
                self.upload_button, 
                ft.Container(expand=True), # Espaçador
                self.anonymize_switch,
                self.clear_chat_button,
                self.settings_button,
            ],
            alignment=ft.MainAxisAlignment.START
        )
        
        input_bar = ft.Row(
            [self.user_input_field, self.send_button],
            vertical_alignment=ft.CrossAxisAlignment.END
        )

        self.controls = [
            top_bar,
            self.file_list_panel,
            self.metrics_panel,
            ft.Divider(height=1),
            self.chat_history_view,
            ft.Divider(height=1),
            ft.Container(
                content=input_bar,
                padding=ft.padding.symmetric(vertical=5, horizontal=10)
            )
        ]

    def _build_settings_drawer(self):
        """Constrói o Drawer de configurações."""
        self.page.drawer = ft.NavigationDrawer(
            controls=[
                ft.Container(
                    ft.Text("Configurações do Chat", style=ft.TextThemeStyle.HEADLINE_SMALL),
                    padding=15
                ),
                ft.Divider(),
                ft.Container(
                    ft.TextField(
                        label="System Prompt",
                        value="Você é um assistente especializado em análise de documentos. Responda apenas com base no conteúdo dos arquivos fornecidos.",
                        multiline=True,
                        min_lines=3,
                        max_lines=8,
                    ),
                    padding=15
                ),
                ft.Container(
                    ft.TextField(
                        label="Termos para Anonimização Customizada",
                        hint_text="Separe os termos por vírgula ou ponto e vírgula",
                        multiline=True,
                        min_lines=2,
                        max_lines=5,
                    ),
                    padding=15
                ),
            ]
        )

    def _create_placeholder_panel(self, title: str, visible: bool = False) -> ft.ExpansionPanelList:
        """Cria um painel expansível de placeholder."""
        return ft.ExpansionPanelList(
            controls=[
                ft.ExpansionPanel(
                    header=ft.ListTile(title=ft.Text(title)),
                    content=ft.Container(
                        ft.Text("Nenhum dado para exibir ainda.", italic=True),
                        padding=15
                    )
                )
            ],
            elevation=1,
            divider_color=ft.Colors.TRANSPARENT,
            visible=visible
        )

    def _show_initial_greeting(self):
        """Adiciona uma mensagem inicial de boas-vindas ao chat."""
        initial_message = {
            "id": time.time(),
            "author": "IA",
            "text": "Olá! Por favor, carregue os documentos que você gostaria de analisar. Após o carregamento, você poderá fazer perguntas sobre o conteúdo deles.",
        }
        self.messages.append(initial_message)
        self._update_chat_display()

    def _update_chat_display(self):
        """Limpa e recria a lista de mensagens na UI a partir do estado `self.messages`."""
        self.chat_history_view.controls.clear()
        for i, msg in enumerate(self.messages):
            is_last_message = i == len(self.messages) - 1
            bubble = self._create_message_bubble(msg, is_last_message)
            self.chat_history_view.controls.append(bubble)
        
        if self.page and self.chat_history_view.page and self.page.client_storage is not None:
            self.chat_history_view.update()
            if self.chat_history_view.controls:
                self.chat_history_view.scroll_to(offset=-1, duration=300, curve=ft.AnimationCurve.EASE_OUT)

    def _create_message_bubble(self, message: Dict[str, Any], is_last_message: bool) -> ft.Row:
        """Cria um componente visual para uma única mensagem no chat."""
        is_user = message["author"] == "User"
        msg_id = message["id"]
        
        avatar = ft.CircleAvatar(
            content=ft.Icon(ft.Icons.PERSON_OUTLINE if is_user else ft.Icons.ASSISTANT_OUTLINED),
            # bgcolor=theme.PRIMARY if is_user else ft.Colors.BLUE_GREY_700,
        )

        message_content_area = ft.Markdown(
            message["text"],
            selectable=True,
            extension_set=ft.MarkdownExtensionSet.COMMON_MARK,
            code_theme="atom-one-dark"
        )

        actions_toolbar = ft.Row([
            ft.IconButton(ft.Icons.COPY_ALL_OUTLINED, on_click=lambda _, t=message["text"]: self._handle_copy_message(t), icon_size=14, tooltip="Copiar"),
            ft.IconButton(ft.Icons.EDIT_OUTLINED, on_click=lambda _, mid=msg_id: self._handle_edit_message(mid), icon_size=14, tooltip="Editar"), 
            ft.IconButton(ft.Icons.DELETE_OUTLINE, on_click=lambda _, mid=msg_id: self._handle_delete_message(mid), icon_size=14, tooltip="Excluir"),
            ft.IconButton(ft.Icons.RESTART_ALT, on_click=lambda _, mid=msg_id: self._handle_resume_from(mid), icon_size=14, tooltip="Retomar chat a partir daqui", visible= not is_last_message),
            ft.IconButton(ft.Icons.REPLAY, on_click=lambda _, mid=msg_id: self._handle_rerun(mid), icon_size=14, tooltip="Gerar nova resposta", visible=not is_user and is_last_message),
        ], spacing=0, visible=False) # Inicia invisível

        message_column = ft.Column([
            message_content_area,
            actions_toolbar
        ], spacing=5)

        bubble_container = ft.Container(
            content=message_column,
            padding=12,
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE) if is_user else ft.Colors.with_opacity(0.08, theme.PRIMARY),
            on_hover=self._handle_bubble_hover,
            data=actions_toolbar, # Passa a referência da toolbar para o handler
            expand=True
        )
        
        alignment = ft.MainAxisAlignment.END if is_user else ft.MainAxisAlignment.START

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
    
    # --- Handlers de Ações ---
    def _handle_send_message(self, e: ft.ControlEvent):
        """Lida com o envio de uma nova mensagem pelo usuário."""
        if self.is_processing_response:
            return
            
        user_text = self.user_input_field.value.strip()
        if not user_text:
            return

        self.is_processing_response = True
        self.user_input_field.disabled = True
        self.send_button.disabled = True
        self.user_input_field.update()
        self.send_button.update()
        
        self.messages.append({"id": time.time(), "author": "User", "text": user_text})
        self.user_input_field.value = ""
        self._update_chat_display()

        self._simulate_ai_response()

    def _simulate_ai_response(self):
        """Simula a geração de uma resposta pela IA com um delay."""
        thinking_message = {"id": time.time(), "author": "IA", "text": "Processando..."}
        self.messages.append(thinking_message)
        self._update_chat_display()

        def generate_dummy_response():
            self.messages.pop()
            dummy_response = {
                "id": time.time(),
                "author": "IA",
                "text": f"Esta é uma resposta simulada para a sua pergunta. A lógica real de RAG será implementada aqui.\n\nTimestamp: `{time.time()}`",
            }
            self.messages.append(dummy_response)
            
            # Reabilita a UI na thread principal
            def update_ui_on_main_thread():
                self.is_processing_response = False
                self.user_input_field.disabled = False
                self.send_button.disabled = False
                self._update_chat_display()
                self.user_input_field.focus()
                self.user_input_field.update()
                self.send_button.update()
            
            self.page.run_thread(update_ui_on_main_thread)

        threading.Timer(1.5, generate_dummy_response).start()

    def _handle_delete_message(self, message_id: float):
        self.messages = [msg for msg in self.messages if msg["id"] != message_id]
        self._update_chat_display()

    def _handle_edit_message(self, message_id: float):
        logger.warning(f"Ação de edição para a mensagem ID {message_id} ainda não implementada.")
        
    def _handle_copy_message(self, text: str):
        self.page.set_clipboard(text)
        
    def _handle_resume_from(self, message_id: float):
        try:
            index = next(i for i, msg in enumerate(self.messages) if msg["id"] == message_id)
            self.messages = self.messages[:index + 1]
            self._update_chat_display()
        except StopIteration:
            logger.error(f"Não foi possível encontrar a mensagem com ID {message_id} para retomar.")
            
    def _handle_rerun(self, message_id: float):
        last_user_message = next((msg for msg in reversed(self.messages) if msg['author'] == 'User'), None)
        if last_user_message:
            self.messages = [msg for msg in self.messages if msg["id"] != message_id]
            self._update_chat_display()
            self._simulate_ai_response()
        else:
            logger.warning("Nenhuma mensagem de usuário encontrada para refazer a pergunta.")

    def _handle_clear_chat(self, e: ft.ControlEvent):
        """Abre um diálogo de confirmação para limpar o chat."""
        def confirm_action():
            self.messages.clear()
            self._show_initial_greeting()
        
        show_confirmation_dialog(
            self.page,
            title="Limpar Conversa",
            content=ft.Text("Tem certeza que deseja apagar todo o histórico desta conversa?"),
            on_confirm=confirm_action
        )

    def _handle_open_settings_drawer(self, e: ft.ControlEvent):
        """Abre o drawer de configurações."""
        self.page.drawer.open = True
        self.page.drawer.update()

    def _handle_bubble_hover(self, e: ft.HoverEvent):
        """Mostra ou esconde a barra de ferramentas de ações da mensagem."""
        actions_toolbar: ft.Row = e.control.data
        actions_toolbar.visible = e.data == "true"
        actions_toolbar.update()


def create_chat_view_content(page: ft.Page) -> ft.Control:
    """Função de fábrica para criar a view de Chat com Documentos."""
    return ChatViewContent(page)

