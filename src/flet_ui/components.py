'''
Componentes de UI Reutilizáveis: Contém classes ou funções que criam componentes customizados ou combinações de componentes Flet.
'''
import flet as ft
from typing import List, Dict, Any, Optional, Callable, Type, Union
import os, shutil, time, threading

from src.flet_ui import theme

from src.logger.logger import LoggerSetup
logger = LoggerSetup.get_logger(__name__)

### SnackBar global: ---------------------------------------------------------------------------------------

_global_snackbar_instance: Optional[ft.SnackBar] = None

def show_snackbar(page: ft.Page, message: str, color: str = theme.COLOR_INFO, duration: int = 5000):
    """
    Exibe uma mensagem no SnackBar, adicionando-o temporariamente ao overlay.

    Args:
        page: A instância da página Flet.
        message: A mensagem a ser exibida.
        color: A cor de fundo do SnackBar.
        duration: Duração em milissegundos.
    """
    global _global_snackbar_instance
    
    # Verifica se o SnackBar global já foi criado e adicionado à página
    snackbar_added_key = "_global_snackbar_added"
    
    # AttributeError: 'Page' object has no attribute 'client_data'
    if _global_snackbar_instance is None:
        # Cria a instância global na primeira vez
        _global_snackbar_instance = ft.SnackBar(
            content=ft.Text(""),
            duration=duration,
            show_close_icon = True, # action="OK" Ou "Fechar"
            action_color=ft.Colors.WHITE
        )
    # Adiciona a instância global ao overlay da página ATUAL
    # Fazemos isso apenas uma vez por sessão de página (page)
    if _global_snackbar_instance not in page.overlay:
        page.overlay.append(_global_snackbar_instance)

    snackbar = _global_snackbar_instance
    if not snackbar:
        print("ERRO: Instância global do SnackBar não está definida!")
        return # Sai se algo deu errado
    
    # Abre o SnackBar
    snackbar.content.value = message
    snackbar.bgcolor = color
    snackbar.duration = duration
    snackbar.open = True
    #threading.Timer(0.1, page.update).start()
    page.update() # Atualiza para efetivamente mostrar

### Dialog in Overlay: ---------------------------------------------------------------------------------------

def show_confirmation_dialog(
    page: ft.Page,
    title: str,
    content: ft.Control | str,
    confirm_text: str = "Confirmar",
    cancel_text: str = "Cancelar",
    on_confirm: Optional[Callable[[], None]] = None # Callback se confirmado
):
    """Exibe um diálogo de confirmação padrão."""
    confirm_dialog = None # Declara antes para ser acessível no close_dialog

    def close_dialog(e):
        confirm_dialog.open = False
        page.update()
        page.overlay.remove(confirm_dialog) # Remove do overlay ao fechar
        if hasattr(e.control, 'data') and e.control.data == "confirm" and on_confirm:
            on_confirm() # Chama o callback de confirmação

    confirm_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text(title),
        content=content if isinstance(content, ft.Control) else ft.Text(content),
        actions=[
            ft.TextButton(confirm_text, on_click=close_dialog, data="confirm"),
            ft.TextButton(cancel_text, on_click=close_dialog, data="cancel"),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    page.overlay.append(confirm_dialog) # Adiciona ao overlay
    confirm_dialog.open = True
    page.update() # Abre o diálogo

### SelectionDialog: ---------------------------------------------------------------------------------------

SelectionCallback = Callable[[Optional[Any]], None]

class SelectionDialog:
    """
    Gerencia um AlertDialog para buscar e selecionar um item de um modelo SQLAlchemy.
    Esta classe não é um ft.Control, mas gerencia um ft.AlertDialog.
    """

    def __init__(
        self,
        page: ft.Page,
        model: Type[Any], # O modelo SQLAlchemy (ex: Cliente, Ferragem)
        title: str,
        search_fields: List[str], # Nomes dos atributos do *modelo* para buscar
        display_attrs: List[str], # Nomes dos atributos do *modelo* a exibir na lista
        on_select: SelectionCallback, # Callback chamado com o item selecionado ou None
        initial_query: Optional[Any] = None # Query SQLAlchemy base opcional
    ):
        """
        Inicializa o SelectionDialog.

        Args:
            page: A instância da página Flet.
            model: O modelo SQLAlchemy a ser pesquisado.
            title: O título do diálogo.
            search_fields: Lista de nomes de atributos do modelo para usar na busca.
            display_attrs: Lista de nomes de atributos do modelo para exibir nos resultados.
            on_select: Função callback a ser chamada quando um item é selecionado ou cancelado.
                       Recebe o objeto SQLAlchemy selecionado ou None.
            initial_query: Uma query SQLAlchemy opcional para pré-filtrar os itens.
        """
        ...

### DataTableWrapper: ---------------------------------------------------------------------------------------

from src.utils import normalize_key   
class DataTableWrapper(ft.Column):
    """
    Um wrapper para ft.DataTable que inclui busca, paginação básica e botões de ação.
    Usa normalização de chave para mapear colunas e dados.
    """
    def __init__(
        self,
        page: ft.Page, # Passa a referência da página para navegação/diálogos
        columns: List[ft.DataColumn],
        data: List[Dict[str, Any]], # Lista de dicionários, onde cada dict é uma linha
        item_id_key: str, # Chave no dicionário 'data' que contém o ID único do item
        search_keys: List[str], # Chaves no dicionário 'data' para buscar
        items_per_page: int = 10,
        on_edit: Optional[Callable[[str], None]] = None, # Callback ao clicar em Editar (recebe item_id)
        on_delete: Optional[Callable[[str], None]] = None, # Callback ao clicar em Excluir (recebe item_id)
        action_buttons: bool = True, # Define se adiciona colunas de Editar/Excluir
        expand: bool | int | None = True, # Permite controlar a expansão da coluna
        *args, **kwargs
    ):
        # Chama o __init__ de ft.Column, passando 'expand' e outros args/kwargs
        # Configura a coluna para ocupar espaço e ter scroll interno se necessário
        super().__init__(expand=expand, scroll=ft.ScrollMode.ADAPTIVE, *args, **kwargs)
        self.page = page
        # Armazena as colunas originais
        self.original_columns = columns
        # Cria um mapeamento de label normalizado para coluna original
        self.normalized_column_map: Dict[str, ft.DataColumn] = {
            normalize_key(col.label.value if isinstance(col.label, ft.Text) else str(col.label)): col
            for col in columns
        }
        # Cria um mapeamento de label original para chave normalizada
        self.original_label_to_normalized: Dict[str, str] = {
             (col.label.value if isinstance(col.label, ft.Text) else str(col.label)) : normalize_key(col.label.value if isinstance(col.label, ft.Text) else str(col.label))
            for col in columns
        }

        self.all_data = data
        self.item_id_key = item_id_key # Chave *original* no dict de dados
        self.search_keys = search_keys # Chaves *originais* para busca
        self.items_per_page = items_per_page
        self.on_edit_callback = on_edit
        self.on_delete_callback = on_delete
        self.action_buttons = action_buttons

        self.current_page = 1
        self.search_term = ""
        self.filtered_data = self.all_data[:]

        # --- Controles Internos ---
        self.search_field = ft.TextField( # ... (como antes) ...
             label="Buscar...", prefix_icon=ft.Icons.SEARCH, on_change=self.handle_search_change,
             dense=True, filled=True, border_radius=5, capitalization=ft.TextCapitalization.CHARACTERS,
        )
        self.data_table = ft.DataTable( # ... (como antes) ...
             columns=self._get_table_columns(), rows=[], column_spacing=20,
             divider_thickness=0.5, expand=True,
        )
        self.table_container = ft.Column( # ... (como antes) ...
            [self.data_table], scroll=ft.ScrollMode.ADAPTIVE, expand=True
        )
        self.prev_button = ft.IconButton( # ... (como antes) ...
             icon=ft.Icons.KEYBOARD_ARROW_LEFT, on_click=self.prev_page, tooltip="Página Anterior", disabled=True
        )
        self.page_info = ft.Text(f"Página {self.current_page}/1")
        self.next_button = ft.IconButton( # ... (como antes) ...
             icon=ft.Icons.KEYBOARD_ARROW_RIGHT, on_click=self.next_page, tooltip="Próxima Página", disabled=True
        )
        self.pagination_controls = ft.Row( # ... (como antes) ...
             [self.prev_button, self.page_info, self.next_button], alignment=ft.MainAxisAlignment.END
        )

        # --- Define os controles filhos desta Coluna ---
        self.controls = [ # ... (como antes) ...
            self.search_field, ft.Divider(height=1), self.table_container,
            ft.Divider(height=1), self.pagination_controls,
        ]

    def did_mount(self):
        self._apply_filter_and_pagination()

    def _get_table_columns(self) -> List[ft.DataColumn]:
        # Retorna as colunas originais + ações
        cols = self.original_columns[:]
        if self.action_buttons:
            if self.on_edit_callback: cols.append(ft.DataColumn(ft.Text("Editar", weight=ft.FontWeight.BOLD)))
            if self.on_delete_callback: cols.append(ft.DataColumn(ft.Text("Excluir", weight=ft.FontWeight.BOLD)))
        return cols

    def _get_paginated_data(self) -> List[Dict[str, Any]]:
        # ... (como antes) ...
        start_index = (self.current_page - 1) * self.items_per_page
        end_index = start_index + self.items_per_page
        return self.filtered_data[start_index:end_index]

    def _update_table(self):
        paginated_data = self._get_paginated_data()
        total_pages = (len(self.filtered_data) + self.items_per_page - 1) // self.items_per_page
        total_pages = max(1, total_pages)

        new_rows = []
        for item_data in paginated_data:
            cells = []
            item_id = str(item_data.get(self.item_id_key, ''))

            # Itera sobre as colunas *originais* para manter a ordem
            for original_col in self.original_columns:
                 original_label = original_col.label.value if isinstance(original_col.label, ft.Text) else str(original_col.label)
                 # Tenta obter o valor usando a chave original (case sensitive)
                 value = item_data.get(original_label)
                 # Se não encontrar, tenta obter usando a chave normalizada
                 if value is None:
                      normalized_label_key = self.original_label_to_normalized.get(original_label)
                      if normalized_label_key:
                           # Procura a chave normalizada nos dados
                           # Idealmente, os dados também teriam chaves normalizadas,
                           # mas vamos tentar encontrar a chave original que corresponde
                           key_in_data = None
                           for data_k in item_data.keys():
                               if normalize_key(data_k) == normalized_label_key:
                                   key_in_data = data_k
                                   break
                           if key_in_data:
                                value = item_data.get(key_in_data)

                 # Se ainda assim não encontrar, usa string vazia
                 cells.append(ft.DataCell(ft.Text(str(value if value is not None else ''))))

            # Adiciona botões de ação
            if self.action_buttons:
                if self.on_edit_callback: cells.append(ft.DataCell(ft.IconButton(icon=ft.Icons.EDIT_OUTLINED, tooltip="Editar Item", data=item_id, on_click=self.handle_edit_click)))
                if self.on_delete_callback: cells.append(ft.DataCell(ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, tooltip="Excluir Item", icon_color=ft.Colors.RED_ACCENT_400, data=item_id, on_click=self.handle_delete_click)))

            new_rows.append(ft.DataRow(cells=cells))

        self.data_table.rows = new_rows
        self.page_info.value = f"Página {self.current_page}/{total_pages}"
        self.prev_button.disabled = self.current_page == 1
        self.next_button.disabled = self.current_page == total_pages

        if self.page:
            self.update()

    # --- Métodos restantes (filtros, handlers, update_data) ---
    # A busca agora usa as chaves originais fornecidas
    def _apply_filter_and_pagination(self):
        if not self.search_term:
            self.filtered_data = self.all_data[:]
        else:
            term = self.search_term.lower() # Termo de busca em minúsculas
            self.filtered_data = [
                item for item in self.all_data
                # Compara o termo com o valor *original* nas chaves de busca especificadas
                if any(str(item.get(key, '')).lower().find(term) != -1 for key in self.search_keys)
            ]
        self.current_page = 1
        self._update_table()

    def handle_search_change(self, e):
        self.search_term = e.control.value # Não força mais para maiúsculas aqui
        self._apply_filter_and_pagination()

    # prev_page, next_page, handle_edit_click, handle_delete_click, update_data
    # permanecem como antes
    def prev_page(self, e):
        if self.current_page > 1:
            self.current_page -= 1
            self._update_table()

    def next_page(self, e):
        total_pages = (len(self.filtered_data) + self.items_per_page - 1) // self.items_per_page
        total_pages = max(1, total_pages)
        if self.current_page < total_pages:
            self.current_page += 1
            self._update_table()

    def handle_edit_click(self, e):
        """Chamado quando o botão Editar é clicado."""
        item_id = e.control.data
        if self.on_edit_callback:
            # show_snackbar(self.page, f"Editando item {item_id}", color=theme.COLOR_INFO) # Removido daqui, pode ser chamado no callback externo
            self.on_edit_callback(item_id) # Chama o callback original passado

    def handle_delete_click(self, e):
        """Chamado quando o botão Excluir é clicado."""
        item_id = e.control.data
        if self.on_delete_callback:
            # Define a função a ser chamada se a confirmação for positiva
            def perform_delete():
                # Chama o callback de exclusão original passado para o Wrapper
                self.on_delete_callback(item_id)
                # Mostra snackbar de sucesso APÓS a exclusão ser processada no callback
                # (O callback handle_delete na view de teste fará a atualização da UI)
                # show_snackbar(self.page, f"Item {item_id} excluído com sucesso.", color=theme.COLOR_SUCCESS)

            # Usa a função global show_confirmation_dialog
            show_confirmation_dialog(
                page=self.page,
                title="Confirmar Exclusão",
                content=f"Tem certeza que deseja excluir o item ID {item_id}?",
                on_confirm=perform_delete # Passa a função a ser executada na confirmação
            )

    def update_data(self, new_data: List[Dict[str, Any]]):
        """Permite atualizar externamente os dados da tabela."""
        self.all_data = new_data
        # Reaplica filtro e paginação com os novos dados
        self._apply_filter_and_pagination()

### LoadingIndicator: ---------------------------------------------------------------------------------------

_loading_overlay_instance: Optional[ft.Container] = None
_loading_text_instance: Optional[ft.Text] = None

def show_loading_overlay(page: ft.Page, message: str = "Processando, aguarde..."):
    global _loading_overlay_instance, _loading_text_instance
    if _loading_overlay_instance is None:
        _loading_text_instance = ft.Text(message, size=16, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER)
        _loading_overlay_instance = ft.Container(
            content=ft.Column(
                [
                    ft.ProgressRing(),
                    ft.Container(height=10), # Espaçador
                    _loading_text_instance,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                tight=True,
            ),
            alignment=ft.alignment.center,
            expand=True, # Ocupa toda a página
            bgcolor=ft.Colors.with_opacity(0.5, ft.Colors.BLACK), # Fundo semitransparente
        )
    
    _loading_text_instance.value = message # Atualiza a mensagem
    if _loading_overlay_instance not in page.overlay:
        page.overlay.append(_loading_overlay_instance)
    _loading_overlay_instance.visible = True
    #threading.Timer(0.1, page.update).start()
    page.update()

def hide_loading_overlay(page: ft.Page):
    global _loading_overlay_instance
    if _loading_overlay_instance is not None:
        _loading_overlay_instance.visible = False
        # Não removemos do overlay para reutilização, apenas escondemos
        # Se a remoção for desejada, seria:
        # if _loading_overlay_instance in page.overlay:
        #     page.overlay.remove(_loading_overlay_instance)
        # _loading_overlay_instance = None 
        # _loading_text_instance = None
        #threading.Timer(0.1, page.update).start()
        page.update()

### ValidatedTextField: ---------------------------------------------------------------------------------------

ValidatorCallable = Callable[[str], Optional[str]] # Recebe valor, retorna msg de erro ou None
OnChangeValidatedCallable = Callable[[str], None]   # Recebe valor validado

class ValidatedTextField(ft.Column):
    """
    Um ft.TextField com lógica de validação embutida e exibição de mensagem de erro.
    Herda de ft.Column para agrupar o TextField e a mensagem de erro.
    """
    def __init__(
        self,
        label: str,
        validator: ValidatorCallable,
        on_change_validated: Optional[OnChangeValidatedCallable] = None,
        # Parâmetros do ft.TextField
        hint_text: Optional[str] = None,
        value: Optional[str] = None,
        password: Optional[bool] = None,
        can_reveal_password: Optional[bool] = None,
        keyboard_type: Optional[ft.KeyboardType] = None,
        capitalization: Optional[ft.TextCapitalization] = None,
        max_length: Optional[int] = None,
        read_only: Optional[bool] = False,
        disabled: Optional[bool] = False,
        autofocus: Optional[bool] = False,
        # Parâmetros de layout para o ft.Column
        expand: Union[None, bool, int] = None,
        col: Optional[Dict[str, Union[int, float]]] = None,
        on_submit: Optional[Callable] = None,
        # ... outros parâmetros de ft.TextField ou ft.Column podem ser adicionados
    ):
        super().__init__(spacing=1, expand=expand, col=col) # Pouco espaçamento entre textfield e erro
        self._validator = validator
        self._on_change_validated = on_change_validated
        self._is_valid = True

        self.text_field = ft.TextField(
            label=label,
            hint_text=hint_text,
            value=value,
            password=password,
            can_reveal_password=can_reveal_password,
            keyboard_type=keyboard_type,
            capitalization=capitalization,
            max_length=max_length,
            read_only=read_only,
            disabled=disabled,
            autofocus=autofocus,
            on_submit=on_submit,
            on_change=self._handle_change,
            on_blur=self._handle_blur, # Validar também no on_blur
            # error_style=ft.TextStyle(color=theme.COLOR_ERROR) # O Flet já tem um estilo padrão
        )
        self.error_text_control = ft.Text(
            "",
            color=theme.COLOR_ERROR,
            size=12,
            visible=False
        )
        self.controls = [self.text_field, self.error_text_control]

        # Validação inicial se houver valor
        if value is not None:
            self.validate(show_error=False) # Valida, mas não mostra erro inicialmente se já tiver valor

    def _handle_change(self, e: ft.ControlEvent):
        self.validate()
        if self._is_valid and self._on_change_validated:
            self._on_change_validated(self.text_field.value or "")

    def _handle_blur(self, e: ft.ControlEvent):
        self.validate(show_error=True) # Sempre mostra o erro no blur se inválido

    def validate(self, show_error: bool = True) -> bool:
        """
        Executa a validação do campo.

        Args:
            show_error (bool): Se True, exibe a mensagem de erro visualmente.

        Returns:
            bool: True se o campo for válido, False caso contrário.
        """
        current_value = self.text_field.value or ""
        error_message = self._validator(current_value)

        if error_message:
            self._is_valid = False
            if show_error:
                self.text_field.error_text = error_message # Usa o error_text nativo do TextField
                self.error_text_control.value = "" # Ou pode usar este se preferir um Text customizado
                self.error_text_control.visible = False
            else: # Não mostra erro, mas campo está inválido
                self.text_field.error_text = None # Limpa se não for pra mostrar
        else:
            self._is_valid = True
            self.text_field.error_text = None
            self.error_text_control.value = ""
            self.error_text_control.visible = False

        # Atualiza o TextField para mostrar/limpar o error_text
        if self.page and show_error : # Evita erro se não estiver na página ainda
             self.text_field.update()
             # self.error_text_control.update() # Se usar o Text customizado

        return self._is_valid

    @property
    def value(self) -> Optional[str]:
        return self.text_field.value

    @value.setter
    def value(self, new_value: Optional[str]):
        self.text_field.value = new_value
        self.validate(show_error=False) # Valida ao setar programaticamente, mas não mostra erro
        if self.page:
            self.text_field.update()

    @property
    def is_valid(self) -> bool:
        return self._is_valid

    def focus(self):
        self.text_field.focus()

### ManagedFilePicker: ---------------------------------------------------------------------------------------

FileUploadCompleteCallback = Callable[[bool, str, Optional[str]], None] # Para cada arquivo
FileBatchUploadCompleteCallback = Callable[[List[Dict[str, Any]]], None] # NOVO: Para o lote
FileUploadProgressCallback = Callable[[str, float], None]

class ManagedFilePicker: 
    """
    Gerencia um ft.FilePicker para simplificar o upload de arquivos,
    especialmente no modo web, lidando com URLs de upload, progresso e
    verificação de arquivo no servidor.

    É recomendado que a instância de `ft.FilePicker` seja adicionada ao
    `page.overlay` uma única vez na inicialização da aplicação. Esta classe
    requer que essa instância seja passada.
    """
    def __init__(
        self,
        page: ft.Page,
        file_picker_instance: ft.FilePicker,
        on_individual_file_complete: FileUploadCompleteCallback, # Renomeado para clareza
        upload_dir: str,
        on_batch_complete: Optional[FileBatchUploadCompleteCallback] = None, # NOVO CALLBACK
        allowed_extensions: Optional[List[str]] = None,
        pick_dialog_title: str = "Selecionar arquivo",
        on_upload_progress: Optional[FileUploadProgressCallback] = None,
        upload_url_expiry_seconds: int = 300,
    ):
        self.page = page
        self.file_picker = file_picker_instance
        self.on_individual_file_complete  = on_individual_file_complete 
        self.on_batch_complete = on_batch_complete
        self.upload_dir = os.path.abspath(upload_dir)
        self.allowed_extensions = [ext.lower().lstrip('.') for ext in allowed_extensions] if allowed_extensions else None
        self.pick_dialog_title = pick_dialog_title
        self.on_upload_progress = on_upload_progress
        self.upload_url_expiry_seconds = upload_url_expiry_seconds

        # Atribui os métodos internos aos eventos do FilePicker
        self.file_picker.on_result = self._handle_picker_result
        self.file_picker.on_upload = self._handle_picker_upload

        self._is_uploading_map: Dict[str, bool] = {}
        self.files_to_process_queue: List[ft.FilePickerFile] = []

        self._current_batch_results: List[Dict[str, Any]] = [] # Para acumular resultados do lote atual
        self._files_expected_in_current_batch = 0

        if not os.path.exists(self.upload_dir):
            try:
                os.makedirs(self.upload_dir, exist_ok=True)
                logger.info(f"Diretório de upload criado: {self.upload_dir}")
            except OSError as e:
                logger.error(f"Falha ao criar diretório de upload {self.upload_dir}: {e}")

    def pick_files(
        self,
        allow_multiple: bool = False,
        allowed_extensions_override: Optional[List[str]] = None,
        dialog_title_override: Optional[str] = None
    ):
        """Abre o diálogo do FilePicker para o usuário selecionar arquivos."""
        current_allowed_extensions_normalized = [
            ext.lower().lstrip('.') for ext in allowed_extensions_override
        ] if allowed_extensions_override else self.allowed_extensions
        
        current_dialog_title = dialog_title_override or self.pick_dialog_title

        logger.info(f"[DEBUG] Abrindo FilePicker: title='{current_dialog_title}', multiple={allow_multiple}, ext={current_allowed_extensions_normalized}")
        self.file_picker.pick_files(
            dialog_title=current_dialog_title,
            allow_multiple=allow_multiple,
            allowed_extensions=current_allowed_extensions_normalized
        )

    def _handle_picker_result(self, e: ft.FilePickerResultEvent):
        """Callback para o evento on_result do FilePicker."""
        if not e.files:
            logger.warning("Seleção de arquivo cancelada pelo usuário.")
            self.on_individual_file_complete (False, "Seleção cancelada", None)
            if self.on_batch_complete: # Se não há arquivos, o "lote" (vazio) está completo
                self.on_batch_complete([])
            return

        logger.info(f"--- ManagedFilePicker: FilePicker retornou {len(e.files)} arquivo(s) ---")
        for i, f_obj in enumerate(e.files):
            logger.info(f"[DEBUG]   Arquivo {i}: Nome='{f_obj.name}', Tamanho={f_obj.size}, PathCliente='{f_obj.path}'")

        # Inicia um novo lote
        self.files_to_process_queue = list(e.files)
        self._current_batch_results = []
        self._files_expected_in_current_batch = len(e.files)

        # Adiciona os novos arquivos à fila
        # Se a fila já tiver itens de uma seleção anterior não processada, esta lógica adicionará.
        # Normalmente, a fila deve estar vazia se todos os uploads anteriores foram concluídos.
        is_processing_active = bool(self.files_to_process_queue) # Verifica se já há algo na fila

        for f_obj in e.files:
            self.files_to_process_queue.append(f_obj)
        
        logger.info(f"{len(e.files)} arquivo(s) adicionado(s) à fila. Total agora: {len(self.files_to_process_queue)}")

        if self.files_to_process_queue: # and not is_processing_active
            # Se não havia processamento ativo e agora há arquivos na fila,
            # inicia o processamento do primeiro arquivo imediatamente.
            logger.info("[DEBUG] Iniciando processamento da fila (primeiro arquivo sem delay).")
            self._process_one_file_from_queue(is_first_call_in_batch=True)
        #elif is_processing_active: logger.info("[DEBUG] Processamento da fila já estava ativo. Novos arquivos foram enfileirados.")
        elif self.on_batch_complete: # Se por algum motivo a fila ficou vazia
             self.on_batch_complete([])

    def _record_file_result_and_check_batch_completion(self, success: bool, message: str, file_name: Optional[str]):
        """Chamado internamente após cada tentativa de processamento de arquivo."""
        if file_name: # Só registra se tiver nome
            self._current_batch_results.append({
                "name": file_name,
                "success": success,
                "path_or_message": message
            })
        
        # Chama o callback individual
        self.on_individual_file_complete(success, message, file_name)

        # Verifica se o lote terminou
        if len(self._current_batch_results) >= self._files_expected_in_current_batch:
            logger.info(f"Lote de {self._files_expected_in_current_batch} arquivos processado.")
            if self.on_batch_complete:
                self.on_batch_complete(list(self._current_batch_results)) # Passa uma cópia
            self._current_batch_results = [] # Reseta para o próximo lote
            self._files_expected_in_current_batch = 0
            
    def _process_one_file_from_queue(self, is_first_call_in_batch: bool = False):
        """
        Processa um único arquivo da fila.
        Aplica delay para arquivos subsequentes em um lote.
        """
        if not self.files_to_process_queue:
            logger.info("[DEBUG] Fila de processamento de arquivos está vazia. Nada a fazer.")
            return

        def _execute_logic():
            # Esta função interna contém a lógica de processamento de UM arquivo
            if not self.files_to_process_queue: # Verificação dupla
                logger.info("[DEBUG] Fila esvaziou antes da execução agendada/imediata.")
                return

            selected_file = self.files_to_process_queue.pop(0)
            file_name = selected_file.name
            original_file_path_on_client = selected_file.path

            logger.info(f"Processando da fila: '{file_name}', Path cliente: '{original_file_path_on_client}'")

            if self._is_uploading_map.get(file_name):
                logger.warning(f"Upload de '{file_name}' já está em progresso (skip).")
                #self.on_individual_file_complete (False, f"Tentativa de upload duplicado para '{file_name}'", file_name)
                self._record_file_result_and_check_batch_completion(False, f"Tentativa de upload duplicado para '{file_name}'", file_name)
                self._process_one_file_from_queue() # Agenda o próximo (com delay implícito)
                return

            if self.allowed_extensions:
                _root, ext_with_dot = os.path.splitext(file_name)
                normalized_ext = ext_with_dot.lower().lstrip('.')
                if normalized_ext not in self.allowed_extensions:
                    display_allowed = [f".{ae}" for ae in self.allowed_extensions] if self.allowed_extensions else []
                    err_msg = f"Tipo de arquivo inválido: '{ext_with_dot}'. Permitidos: {', '.join(display_allowed)}"
                    logger.error(err_msg)
                    #self.on_individual_file_complete (False, err_msg, file_name)
                    self._record_file_result_and_check_batch_completion(False, err_msg, file_name)
                    self._process_one_file_from_queue() # Agenda o próximo (com delay implícito)
                    return

            if original_file_path_on_client: # MODO DESKTOP
                logger.info(f"Modo Desktop para '{file_name}'.")
                if self.on_upload_progress: self.on_upload_progress(file_name, 1.0)
                #self.on_individual_file_complete (True, original_file_path_on_client, file_name)
                self._record_file_result_and_check_batch_completion(True, original_file_path_on_client, file_name)
                self._process_one_file_from_queue() # Agenda o próximo (com delay implícito)
            else: # MODO WEB
                logger.info(f"Modo Web. Preparando upload para: {file_name}")
                self._is_uploading_map[file_name] = True

                server_target_path = os.path.join(self.upload_dir, file_name)
                if os.path.exists(server_target_path):
                    try: os.remove(server_target_path)
                    except OSError as e_rem: logger.warning(f"Não foi possível remover arquivo anterior '{server_target_path}': {e_rem}")

                try:
                    upload_url = self.page.get_upload_url(file_name, self.upload_url_expiry_seconds)
                    if not upload_url: raise ValueError("URL de upload vazia.")
                    
                    if self.on_upload_progress: self.on_upload_progress(file_name, 0.0)
                    
                    self.file_picker.upload([ft.FilePickerUploadFile(name=file_name, upload_url=upload_url)])
                    self.page.update()
                    logger.info(f"page.update() chamado após file_picker.upload() para '{file_name}'.")
                except Exception as ex:
                    logger.error(f"Erro ao preparar/iniciar upload para '{file_name}': {ex}", exc_info=True)
                    self._is_uploading_map.pop(file_name, None)
                    #self.on_individual_file_complete (False, f"Erro no preparo do upload: {ex}", file_name)
                    self._record_file_result_and_check_batch_completion(False, f"Erro no preparo: {ex}", file_name)
                    self._process_one_file_from_queue() # Agenda o próximo (com delay implícito)
        
        # Lógica de Delay
        if is_first_call_in_batch:
            logger.info("[DEBUG]Processando primeiro arquivo do lote/trigger imediatamente.")
            _execute_logic()
        else:
            delay = 0.1 # Segundos
            logger.info(f"[DEBUG] Agendando processamento do próximo arquivo ('{self.files_to_process_queue[0].name if self.files_to_process_queue else 'fila vazia'}') com delay de {delay}s.")
            threading.Timer(delay, _execute_logic).start()

    def _handle_picker_upload(self, e: ft.FilePickerUploadEvent):
        """Callback para o evento on_upload do FilePicker."""
        logger.info(f"Evento _handle_picker_upload: File='{e.file_name}', Prog={e.progress}, Err='{e.error}', Tracked={self._is_uploading_map.get(e.file_name)}")

        # Mesmo se não estiver no _is_uploading_map, se houver erro, precisamos reportar e tentar o próximo.
        if e.error:
            logger.error(f"Erro no evento de upload para '{e.file_name}': {e.error}")
            self._is_uploading_map.pop(e.file_name, None) # Limpa se estava lá
            #self.on_individual_file_complete (False, f"Erro no upload: {e.error}", e.file_name)
            self._record_file_result_and_check_batch_completion(False, f"Erro no upload: {e.error}", e.file_name)
            self._process_one_file_from_queue() # Agenda o próximo (com delay implícito)
            return

        # Se não estiver rastreando e não há erro, pode ser um evento tardio de um upload já tratado/cancelado.
        if not self._is_uploading_map.get(e.file_name):
            logger.warning(f"Evento de upload para '{e.file_name}' (Prog: {e.progress}) recebido, mas não estava sendo ativamente rastreado. Ignorando.")
            return

        if e.progress is not None and e.progress < 1.0:
            logger.info(f"[DEBUG] Progresso do upload para '{e.file_name}': {e.progress*100:.1f}%")
            if self.on_upload_progress:
                self.on_upload_progress(e.file_name, e.progress)
            return # Aguarda próximo evento

        # Upload para Flet concluído (progress é 1.0 ou None, sem erro)
        logger.info(f"Upload para Flet de '{e.file_name}' parece concluído. Verificando no servidor...")
        server_final_path = os.path.join(self.upload_dir, e.file_name)
        file_found_on_server = False
        max_retries = 5
        retry_delay_seconds = 0.3

        for attempt in range(max_retries):
            if os.path.exists(server_final_path):
                file_found_on_server = True
                logger.info(f"Arquivo '{e.file_name}' confirmado no servidor (tentativa {attempt + 1}). Path: {server_final_path}")
                break
            logger.warning(f"Arquivo '{e.file_name}' ainda não no servidor (tentativa {attempt + 1}). Aguardando...")
            time.sleep(retry_delay_seconds)

        self._is_uploading_map.pop(e.file_name, None) # Limpa rastreamento
        logger.info(f"[DEBUG] '{e.file_name}' removido do rastreamento _is_uploading_map.")

        if file_found_on_server:
            #self.on_individual_file_complete (True, server_final_path, e.file_name)
            self._record_file_result_and_check_batch_completion(True, server_final_path, e.file_name)
        else:
            errMsg = f"Arquivo '{e.file_name}' não encontrado em '{server_final_path}' após upload."
            logger.error(errMsg)
            #self.on_individual_file_complete (False, errMsg, e.file_name)
            self._record_file_result_and_check_batch_completion(False, errMsg, e.file_name)
            
        self._process_one_file_from_queue() # Agenda o próximo (com delay implícito)

    def clear_upload_state_for_file(self, file_name: str):
        """Remove um arquivo do mapa de rastreamento de uploads."""
        if file_name in self._is_uploading_map:
            del self._is_uploading_map[file_name]
            logger.info(f"Estado de upload para '{file_name}' limpo do ManagedFilePicker.")
            
    def clear_upload_directory(self):
        """Remove todos os arquivos e subdiretórios do diretório de upload."""
        if not self.upload_dir or not os.path.exists(self.upload_dir):
            logger.warning(f"Diretório de upload '{self.upload_dir}' não existe ou não configurado. Nada a limpar.")
            return
        try:
            for filename in os.listdir(self.upload_dir):
                file_path = os.path.join(self.upload_dir, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    logger.error(f"Falha ao remover {file_path} do diretório de upload: {e}")
            logger.info(f"Diretório de upload '{self.upload_dir}' limpo.")
        except Exception as e:
            logger.error(f"Erro ao tentar limpar o diretório de upload '{self.upload_dir}': {e}")
    
    ### MÉTODOS PARA TESTE ISOLADO :
    '''
    def _on_file_picker_result(self, e: ft.FilePickerResultEvent):
        if not e.files:
            logger.warning("Seleção de arquivo cancelada (TESTE SIMPLES).")
            self.on_upload_complete(False, "Seleção cancelada", None) # Notifica a view
            return

        selected_file = e.files[0]
        self.current_test_file_name = selected_file.name # Armazena para _on_file_picker_upload
        logger.info(f"TESTE SIMPLES: Arquivo selecionado: {self.current_test_file_name}")

        if selected_file.path: # Modo Desktop
            logger.info("TESTE SIMPLES: Modo Desktop.")
            self.on_upload_complete(True, selected_file.path, self.current_test_file_name)
            return
        else: # Modo Web
            logger.info("TESTE SIMPLES: Modo Web.")
            try:
                upload_url = self.page.get_upload_url(self.current_test_file_name, 300)
                logger.info(f"TESTE SIMPLES: URL de Upload: {upload_url}")
                if not upload_url:
                    self.on_upload_complete(False, "URL de upload vazia (TESTE SIMPLES)", self.current_test_file_name)
                    return

                # Sem snackbar, sem timer, chamada direta
                logger.info("TESTE SIMPLES: Chamando file_picker.upload() diretamente...")
                self.file_picker.upload([
                    ft.FilePickerUploadFile(name=self.current_test_file_name, upload_url=upload_url)
                ])
                logger.info("TESTE SIMPLES: Comando de upload enviado ao Flet.")
                # Adicionando um update aqui para ver se ajuda
                self.page.update()
                logger.info("TESTE SIMPLES: self.page.update() chamado após upload.")

            except Exception as ex:
                logger.error(f"TESTE SIMPLES: Erro em _on_file_picker_result: {ex}", exc_info=True)
                self.on_upload_complete(False, f"Erro: {ex}", self.current_test_file_name)

    def _on_file_picker_upload(self, e: ft.FilePickerUploadEvent):
        logger.critical(f"TESTE SIMPLES: _on_file_picker_upload ACIONADO! File: {e.file_name}, Prog: {e.progress}, Err: {e.error}")
        
        # Lógica mínima para chamar on_upload_complete
        if e.error:
            self.on_upload_complete(False, e.error, e.file_name)
            return
        
        if e.progress is not None and e.progress < 1.0:
            # Não fazer nada com on_upload_progress por enquanto
            return

        # Supondo que e.progress == 1.0 ou é None (sem erro) = completo
        # No teste simplificado, vamos assumir que o arquivo está lá se não houve erro.
        server_final_path = os.path.join(self.upload_dir, e.file_name)
        
        # VERIFICAÇÃO SIMPLES DE ARQUIVO NO SERVIDOR (com retry curto)
        file_exists_on_server = False
        for i in range(3): # Tenta por ~1 segundo
            if os.path.exists(server_final_path):
                file_exists_on_server = True
                logger.info(f"TESTE SIMPLES: Arquivo {e.file_name} encontrado no servidor.")
                break
            time.sleep(0.3)
        
        if file_exists_on_server:
            self.on_upload_complete(True, server_final_path, e.file_name)
        else:
            logger.error(f"TESTE SIMPLES: Arquivo {e.file_name} NÃO encontrado no servidor após upload.")
            self.on_upload_complete(False, "Arquivo não encontrado no servidor após upload (TESTE SIMPLES)", e.file_name)
    '''

### Diálogos Aninhados: ---------------------------------------------------------------------------------------

def open_nested_dialog(
    page: ft.Page,
    parent_dialog: ft.AlertDialog,
    child_dialog_open_callable: Callable[[], None], # Função que efetivamente abre o diálogo filho
    delay: float = 0.2 # Segundos
):
    """
    Fecha visualmente um diálogo pai, aguarda um pequeno delay, e então
    chama uma função para abrir um diálogo filho.
    Útil para transições suaves entre diálogos aninhados.
    """
    logger.info(f"[DEBUG] Fechando diálogo pai (Título: {parent_dialog.title.value if isinstance(parent_dialog.title, ft.Text) else 'N/A'}) para abrir filho.")
    parent_dialog.open = False
    page.update(parent_dialog) # Atualiza só o pai para fechar

    def _open_child():
        logger.info("[DEBUG] Delay concluído. Abrindo diálogo filho.")
        child_dialog_open_callable() # Esta função deve conter child.open=True e page.update()

    threading.Timer(delay, _open_child).start()

def reopen_parent_dialog(
    page: ft.Page,
    parent_dialog: ft.AlertDialog,
    # child_dialog_ref: ft.AlertDialog, # Não precisa mais da ref do filho aqui
    # Opcional: uma função para executar lógica antes de reabrir o pai
    # (ex: atualizar campos no pai com base na seleção do filho)
    logic_before_reopen_callable: Optional[Callable[[], None]] = None,
    delay: float = 0.2 # Segundos
):
    """
    Reabre um diálogo pai após um diálogo filho ter sido fechado.
    Assume-se que o diálogo filho já foi tratado (fechado, removido do overlay)
    pela sua própria lógica de fechamento e callback (possivelmente com Timer).
    Este utilitário apenas agenda a reabertura do pai.

    Args:
        page: A instância da página Flet.
        parent_dialog: A instância do AlertDialog pai a ser reaberta.
        logic_before_reopen_callable: Função opcional a ser executada ANTES de reabrir o pai.
        delay: Pequeno atraso antes de tentar reabrir o pai.
    """
    logger.info(f"[DEBUG] Agendando reabertura do diálogo pai (Título: {parent_dialog.title.value if isinstance(parent_dialog.title, ft.Text) else 'N/A'}).")

    def _reopen_parent_action():
        if logic_before_reopen_callable:
            logger.info("[DEBUG] Executando lógica customizada antes de reabrir o diálogo pai.")
            try:
                logic_before_reopen_callable()
            except Exception as e:
                logger.error(f"Erro na 'logic_before_reopen_callable' ao reabrir diálogo pai: {e}", exc_info=True)
                # Decide se continua ou aborta. Por segurança, continua a reabrir.

        logger.info(f"[DEBUG] Delay concluído. Reabrindo diálogo pai.")
        if parent_dialog not in page.overlay: # Garante que está no overlay
             page.overlay.append(parent_dialog)

        parent_dialog.open = True
        page.update() # Atualiza a página inteira para garantir que o pai e quaisquer mudanças sejam renderizadas.

    threading.Timer(delay, _reopen_parent_action).start()


# --- Novas Implementações ------------------------------------------------------------------------------------------

class CardWithHeader(ft.Card):
    """
    Um Card que inclui uma seção de cabeçalho com título e ações opcionais,
    e um corpo para conteúdo customizável.
    """
    def __init__(
        self,
        title: str,
        content: ft.Control,
        header_actions: Optional[List[ft.Control]] = None,
        header_bgcolor: Optional[str] = theme.SURFACE_VARIANT, # Cor de fundo do cabeçalho
        header_title_weight: ft.FontWeight = ft.FontWeight.BOLD,
        header_padding: Union[None, ft.PaddingValue] = ft.padding.symmetric(horizontal=16, vertical=8),
        card_elevation: Optional[float] = 2,
        card_margin: Union[None, ft.PaddingValue] = 5,
        expand: Union[None, bool, int] = None,
        # ... outros parâmetros de ft.Card
        **kwargs
    ):
        super().__init__(elevation=card_elevation, margin=card_margin, expand=expand, **kwargs)

        self.title_text = ft.Text(title, weight=header_title_weight, expand=True) # Título expande para empurrar ações
        _header_actions_row = ft.Row(spacing=0) # Ações sem muito espaço entre elas
        if header_actions:
            _header_actions_row.controls.extend(header_actions)

        self.header_container = ft.Container(
            content=ft.Row(
                controls=[
                    self.title_text,
                    _header_actions_row
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=header_bgcolor,
            padding=header_padding,
            #border_radius=ft.border_radius.only(top_left=self.border_radius.top_left if self.border_radius else 5, top_right=self.border_radius.top_right if self.border_radius else 5)
        )

        self.main_content = content

        # A propriedade 'content' do ft.Card recebe a estrutura completa
        self.content = ft.Column(
            controls=[
                self.header_container,
                ft.Container( # Container para o conteúdo principal, para adicionar padding, etc.
                    content=self.main_content,
                    padding=16 # Padding padrão para o conteúdo do card
                )
            ],
            spacing=0 # Sem espaço entre header e content_container
        )

    def update_title(self, new_title: str):
        """Atualiza o título do card."""
        self.title_text.value = new_title
        if self.page:
            self.title_text.update()

    def update_content(self, new_content: ft.Control):
        """Substitui o conteúdo principal do card."""
        self.main_content = new_content
        # Acessa o container do conteúdo para substituí-lo
        if isinstance(self.content, ft.Column) and len(self.content.controls) > 1:
            content_container = self.content.controls[1]
            if isinstance(content_container, ft.Container):
                content_container.content = new_content
                if self.page:
                    content_container.update()
            else:
                logger.warning("Estrutura interna do CardWithHeader inesperada ao tentar atualizar conteúdo.")
        else:
             logger.warning("Estrutura interna do CardWithHeader não encontrada ao tentar atualizar conteúdo.")


class SectionCollapsible(ft.Column):
    """
    Uma seção de conteúdo que pode ser expandida ou recolhida, com um título clicável.
    """
    def __init__(
        self,
        title: str,
        content: ft.Control,
        initially_expanded: bool = True,
        icon_expanded: str = ft.Icons.EXPAND_LESS,
        icon_collapsed: str = ft.Icons.EXPAND_MORE,
        header_bgcolor: Optional[str] = None, # Para destacar o cabeçalho
        header_padding: Union[None, ft.PaddingValue] = ft.padding.all(8),
        on_toggle: Optional[Callable[[bool], None]] = None, # Callback (is_expanded)
        expand: Union[None, bool, int] = None,
        **kwargs
    ):
        super().__init__(spacing=0, expand=expand, **kwargs) # Sem espaço entre header e content
        self._is_expanded = initially_expanded
        self._on_toggle = on_toggle

        self.title_text = ft.Text(title, weight=ft.FontWeight.BOLD, expand=True)
        self.toggle_icon = ft.IconButton(
            icon=icon_expanded if self._is_expanded else icon_collapsed,
            on_click=self._toggle_section,
            icon_size=20,
            tooltip="Expandir/Recolher"
        )

        self.header = ft.Container(
            content=ft.Row(
                [self.title_text, self.toggle_icon],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            on_click=self._toggle_section, # Torna todo o header clicável
            bgcolor=header_bgcolor,
            padding=header_padding,
            border_radius=5, # Opcional
            ink=True # Efeito visual ao clicar
        )

        self.content_control = content
        self.content_control.visible = self._is_expanded

        self.controls = [
            self.header,
            self.content_control # Adiciona diretamente, visibilidade controla
        ]

    def _toggle_section(self, e: Optional[ft.ControlEvent] = None): # e pode ser None se chamado programaticamente
        self._is_expanded = not self._is_expanded
        self.toggle_icon.icon = ft.Icons.EXPAND_LESS if self._is_expanded else ft.Icons.EXPAND_MORE
        self.content_control.visible = self._is_expanded

        if self.page:
            self.toggle_icon.update()
            self.content_control.update()
            # Se o tamanho da SectionCollapsible muda, pode ser necessário atualizar ela mesma ou o pai.
            # self.update()

        if self._on_toggle:
            self._on_toggle(self._is_expanded)

    @property
    def is_expanded(self) -> bool:
        return self._is_expanded

    @is_expanded.setter
    def is_expanded(self, value: bool):
        if self._is_expanded != value:
            self._toggle_section()


class KeyValueDisplay(ft.Column):
    """
    Exibe pares de chave-valor de forma consistente.
    """
    def __init__(
        self,
        data: Dict[str, Any],
        key_style: Optional[ft.TextStyle] = None,
        value_style: Optional[ft.TextStyle] = None,
        item_spacing: int = 8, # Espaçamento entre os pares
        key_weight: ft.FontWeight = ft.FontWeight.BOLD,
        value_selectable: bool = False, # Se o texto do valor pode ser selecionado
        expand: Union[None, bool, int] = None,
        **kwargs
    ):
        super().__init__(spacing=item_spacing, expand=expand, **kwargs)

        self._default_key_style = ft.TextStyle(weight=key_weight)
        self._key_style = key_style or self._default_key_style
        self._value_style = value_style

        self._build_display(data, value_selectable)

    def _build_display(self, data: Dict[str, Any], value_selectable: bool):
        self.controls.clear()
        for key, value in data.items():
            self.controls.append(
                ft.Row(
                    [
                        ft.Text(f"{key}:", style=self._key_style),
                        ft.SelectionArea( # Permite seleção se habilitado
                            content=ft.Text(str(value), style=self._value_style),
                            #disabled=not value_selectable
                        ) if value_selectable else ft.Text(str(value), style=self._value_style)
                    ],
                    spacing=5, # Espaço entre chave e valor
                    vertical_alignment=ft.CrossAxisAlignment.START
                )
            )

    def update_data(self, new_data: Dict[str, Any], value_selectable: Optional[bool] = None):
        """Atualiza os dados exibidos."""
        _value_selectable = value_selectable if value_selectable is not None else \
                            (not self.controls[0].controls[1].disabled if self.controls and len(self.controls[0].controls) > 1 and isinstance(self.controls[0].controls[1], ft.SelectionArea) else False)

        self._build_display(new_data, _value_selectable)
        if self.page:
            self.update()


class PasswordField(ValidatedTextField):
    """
    Um campo de senha especializado que herda de ValidatedTextField,
    com configurações padrão para senhas e validação opcional de força.
    """
    def __init__(
        self,
        label: str = "Senha",
        validator: Optional[ValidatorCallable] = None, # Permite validator customizado
        validate_strength: bool = True, # Se True, usa um validador de força de senha padrão
        min_length: int = 8,
        require_uppercase: bool = True,
        require_lowercase: bool = True,
        require_digit: bool = True,
        require_special_char: bool = False, # Pode ser True para mais segurança
        on_change_validated: Optional[OnChangeValidatedCallable] = None,
        # ... outros parâmetros de ValidatedTextField/ft.TextField
        **kwargs
    ):
        _validator = validator
        if not _validator and validate_strength:
            def default_strength_validator(value: str) -> Optional[str]:
                if not value: return "Senha é obrigatória."
                if len(value) < min_length: return f"Mínimo {min_length} caracteres."
                if require_uppercase and not any(c.isupper() for c in value): return "Requer maiúscula."
                if require_lowercase and not any(c.islower() for c in value): return "Requer minúscula."
                if require_digit and not any(c.isdigit() for c in value): return "Requer dígito."
                if require_special_char and not any(not c.isalnum() for c in value): return "Requer caractere especial."
                return None
            _validator = default_strength_validator
        elif not _validator: # Se validate_strength for False e nenhum validator for passado
             _validator = lambda val: None # Validador que sempre passa

        super().__init__(
            label=label,
            validator=_validator,
            on_change_validated=on_change_validated,
            password=True,
            can_reveal_password=True,
            **kwargs
        )


class SearchableDropdown(ft.Column):
    """
    Um Dropdown que permite ao usuário digitar para filtrar as opções.
    Este é um componente mais complexo devido ao gerenciamento do overlay.
    """
    def __init__(
        self,
        page: ft.Page, # Necessário para gerenciar o overlay da lista
        label: str,
        options: List[ft.dropdown.Option], # Usa o mesmo tipo de Option do ft.Dropdown
        on_change: Optional[Callable[[Optional[str]], None]] = None, # Callback com o valor da opção selecionada
        selected_value: Optional[str] = None,
        width: Optional[Union[int, float]] = None,
        max_visible_items: int = 5,
        dropdown_height_factor: float = 40, # Altura aproximada por item
        empty_search_message: str = "Nenhum resultado",
        hint_text: Optional[str] = "Digite para buscar...",
        text_field_bgcolor: Optional[str] = None,
        expand: Union[None, bool, int] = None,
    ):
        super().__init__(spacing=2, width=width, expand=expand)
        self.page = page
        self.label = label
        self.all_options = options[:] # Copia a lista
        self.on_change_callback = on_change
        self._selected_option: Optional[ft.dropdown.Option] = None
        self._is_open = False
        self.max_visible_items = max_visible_items
        self.dropdown_height_factor = dropdown_height_factor
        self.empty_search_message = empty_search_message

        # Encontra a opção selecionada inicial, se houver
        if selected_value:
            for opt in self.all_options:
                if opt.key == selected_value:
                    self._selected_option = opt
                    break

        self.text_field = ft.TextField(
            label=self.label,
            value=self._selected_option.text if self._selected_option else "",
            hint_text=hint_text,
            on_change=self._on_search_text_change,
            on_focus=self._open_dropdown_list,
            on_blur=self._on_textfield_blur, # Para fechar se clicar fora
            suffix=ft.IconButton(
                ft.Icons.ARROW_DROP_DOWN,
                on_click=self._toggle_dropdown_list, # Abre/fecha com o ícone
                icon_size=20
            ),
            read_only=False, # Permite digitar para buscar
            bgcolor=text_field_bgcolor,
            # width=width # O Column pai já controla a largura
        )

        self.filtered_options_list = ft.ListView(
            expand=False, # A altura será controlada
            spacing=1,
            padding=0
        )

        self.dropdown_container = ft.Container(
            content=self.filtered_options_list,
            bgcolor=ft.Colors.SURFACE, # Cor de fundo padrão
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=5,
            margin=ft.margin.only(top=-5), # Sobrepõe um pouco o TextField
            visible=False, # Começa invisível
            # A posição (left, top) e width serão definidas dinamicamente
            # quando adicionado ao overlay da página.
            # Animação opcional:
            # animate_opacity=ft.Animation(duration=100, curve=ft.AnimationCurve.EASE_IN_OUT),
            # animate_offset=ft.Animation(duration=100, curve=ft.AnimationCurve.EASE_IN_OUT),
            # offset=ft.transform.Offset(0,0.1),
            # opacity=0,
        )
        self.controls = [self.text_field] # O dropdown_container vai para o overlay

        # Adiciona o container ao overlay da página uma única vez
        # if self.dropdown_container not in self.page.overlay:
        #     self.page.overlay.append(self.dropdown_container)
        # Melhor adicionar dinamicamente e remover quando não necessário.

        self._populate_filtered_list(self.all_options) # Popula com todos inicialmente

    def _get_dropdown_position_and_size(self):
        """Calcula a posição e tamanho do container da lista de opções."""
        if not self.text_field.page: # Ainda não montado
            return None, None, None

        # Tenta obter as coordenadas globais do TextField
        # Nota: Flet não tem uma API direta e fácil para obter coordenadas globais
        # de um controle após a renderização como no DOM web.
        # Esta é uma limitação. Uma solução seria usar um Stack em volta do
        # TextField e do dropdown_container, mas isso complica o layout externo.
        #
        # Para uma abordagem com overlay, assumimos que sabemos aproximadamente
        # onde o TextField está ou que o overlay será posicionado manualmente
        # ou por aproximação.
        #
        # Alternativa: Se o SearchableDropdown *sempre* for usado em uma posição
        # conhecida ou se a página não tiver scroll vertical significativo acima dele,
        # podemos tentar uma estimativa.
        #
        # A solução mais robusta e complexa envolveria JavaScript no Flet Web
        # para obter as coordenadas, o que está fora do escopo aqui.

        # Solução simplificada: Adicionar ao overlay e posicionar relativo ao TextField
        # (se o TextField for o 'self')
        # Se este SearchableDropdown (ft.Column) tem seu próprio 'uid', podemos tentar.
        # No entanto, posicionar um overlay perfeitamente abaixo de um controle dinâmico
        # é um dos desafios em Flet sem acesso direto a coordenadas renderizadas.

        # Vamos usar uma abordagem mais simples: o container do dropdown aparecerá
        # como parte do `self.controls` temporariamente quando aberto.
        # Isso é menos ideal que um overlay verdadeiro, pois empurrará o conteúdo abaixo.
        # Para um overlay verdadeiro, precisaríamos de mais hacks ou Stack.

        # Para este exemplo, vamos manter o dropdown_container no self.controls
        # e apenas controlar sua visibilidade. Isso é mais simples de implementar.
        # Revisitando: O enunciado pedia overlay. Vamos tentar o overlay dinâmico.

        # Coordenadas do TextField (aproximação - pode não ser preciso com scrolls complexos)
        # tf_offset = self.text_field.get_offset() # get_offset não existe
        # tf_size = self.text_field.get_size()     # get_size não existe

        # Para simplificar, vamos assumir que o width do dropdown é o mesmo do TextField
        # e a altura é baseada no número de itens.
        num_items = len(self.filtered_options_list.controls)
        if num_items == 0: num_items = 1 # Para mensagem de "nenhum resultado"
        height = min(num_items, self.max_visible_items) * self.dropdown_height_factor
        return height

    def _populate_filtered_list(self, options_to_show: List[ft.dropdown.Option]):
        self.filtered_options_list.controls.clear()
        if not options_to_show:
            self.filtered_options_list.controls.append(
                ft.ListTile(title=ft.Text(self.empty_search_message), disabled=True, dense=True)
            )
        else:
            for opt in options_to_show:
                is_selected = self._selected_option and self._selected_option.key == opt.key
                self.filtered_options_list.controls.append(
                    ft.ListTile(
                        title=ft.Text(opt.text),
                        data=opt,
                        on_click=self._on_option_selected,
                        selected=is_selected,
                        dense=True,
                        bgcolor=ft.Colors.PRIMARY_CONTAINER if is_selected else None,
                        # leading=ft.Icon(ft.Icons.CHECK) if is_selected else None
                    )
                )
        height = self._get_dropdown_position_and_size()
        if height: self.dropdown_container.height = height

        if self.dropdown_container.page: # Se já está na página (overlay)
            self.dropdown_container.update()
            self.filtered_options_list.update()

    def _on_search_text_change(self, e: ft.ControlEvent):
        search_term = e.control.value.lower()
        if not self._is_open:
            self._open_dropdown_list() # Abre se estava fechado e começou a digitar

        if not search_term and self._selected_option and e.control.value == self._selected_option.text:
            # Se o texto do campo corresponde ao texto da opção selecionada, não filtre (mostre todos)
            # ou apenas a selecionada, dependendo do comportamento desejado.
            # Aqui, vamos mostrar todos se o campo for limpo manualmente.
             filtered = self.all_options
        elif not search_term:
            filtered = self.all_options
        else:
            filtered = [
                opt for opt in self.all_options if search_term in opt.text.lower()
            ]
        self._populate_filtered_list(filtered)

        # Se o texto não corresponde mais a uma opção selecionada, desmarque
        if self._selected_option and e.control.value != self._selected_option.text:
            # Não vamos desmarcar aqui, pois o usuário pode estar digitando
            # para encontrar uma nova opção. O desmarque acontece ao selecionar outra.
            pass


    def _on_option_selected(self, e: ft.ControlEvent):
        selected_opt: ft.dropdown.Option = e.control.data
        self._selected_option = selected_opt
        self.text_field.value = selected_opt.text
        # self.text_field.read_only = True # Opcional: Travar após seleção

        self._close_dropdown_list() # Fecha a lista
        self.text_field.update() # Atualiza valor do TextField

        if self.on_change_callback:
            self.on_change_callback(selected_opt.key)

        # Repopula a lista para destacar a seleção
        # self._populate_filtered_list(self.all_options) # Ou a lista filtrada atual


    def _open_dropdown_list(self, e: Optional[ft.ControlEvent] = None):
        if self._is_open: return
        self._is_open = True
        # self.text_field.read_only = False # Garante que pode digitar

        # Adiciona ao overlay da PÁGINA, não aos controles do componente
        if self.dropdown_container not in self.page.overlay:
            self.page.overlay.append(self.dropdown_container)

        # Tentar posicionar o dropdown_container abaixo do text_field
        # Esta é a parte mais difícil sem coordenadas globais precisas.
        # Assumimos que o width do dropdown é o mesmo do text_field.
        # A posição 'left' e 'top' são relativas ao Page.
        # Se o SearchableDropdown está em um Container com offset, isso complica.
        # Uma abordagem seria colocar o SearchableDropdown dentro de um Stack
        # e o dropdown_container seria o segundo elemento do Stack, posicionado.
        #
        # Solução com overlay exige que o componente saiba sua posição na página.
        # Para este exemplo, vamos simplificar e adicionar aos controles do próprio componente,
        # o que é menos ideal mas mais simples de implementar sem JS.
        #
        # REVERTENDO para adicionar ao overlay e tentar posicionar:
        # A melhor prática é definir `left`, `top`, `width` no `dropdown_container`
        # ANTES de torná-lo visível e adicioná-lo ao overlay.
        # Como obter left/top é o desafio. Flet não provê `get_global_bounds()`.
        #
        # Compromisso: Usar o comportamento de `ft.PopupMenuButton` como inspiração.
        # Ele se posiciona próximo ao botão. Vamos adicionar ao overlay sem
        # posicionamento explícito inicialmente, o que pode não ser ideal.

        height = self._get_dropdown_position_and_size()
        if height: self.dropdown_container.height = height
        self.dropdown_container.width = self.text_field.width or self.width # Tenta usar a largura do TF
        self.dropdown_container.visible = True
        # self.dropdown_container.offset = ft.transform.Offset(0,0)
        # self.dropdown_container.opacity = 1

        # Atualiza a lista com base no texto atual (pode ser todos se vazio)
        current_text = self.text_field.value or ""
        if not current_text:
            self._populate_filtered_list(self.all_options)
        else:
             self._populate_filtered_list([
                opt for opt in self.all_options if current_text.lower() in opt.text.lower()
            ])

        if self.page:
            self.page.update() # Atualiza a página para mostrar o overlay

    def _close_dropdown_list(self):
        if not self._is_open: return
        self._is_open = False
        self.dropdown_container.visible = False
        # self.dropdown_container.opacity = 0
        # self.dropdown_container.offset = ft.transform.Offset(0,0.1)

        if self.dropdown_container in self.page.overlay:
            self.page.overlay.remove(self.dropdown_container)

        if self.page:
            self.page.update() # Atualiza para remover/esconder o overlay

    def _toggle_dropdown_list(self, e: ft.ControlEvent):
        if self._is_open:
            self._close_dropdown_list()
        else:
            self._open_dropdown_list()
            self.text_field.focus() # Foca para permitir digitação

    def _on_textfield_blur(self, e: ft.ControlEvent):
        # Fecha o dropdown se o foco sair do textfield E não for para o dropdown em si.
        # O Flet não nos dá o 'relatedTarget' do evento blur como no JS.
        # Uma forma de lidar com isso é fechar após um pequeno delay,
        # e se uma opção for clicada nesse meio tempo, o clique cancela o fechamento
        # ou o fechamento ocorre mas a seleção já foi processada.
        # Solução mais simples: se o texto não corresponder a uma opção selecionada, limpe.
        if self._is_open:
            # Usar um pequeno delay para permitir cliques na lista de opções
            # threading.Timer(0.15, self._close_dropdown_list_if_not_focused_on_list).start()
            # Por ora, uma solução mais simples, mas pode ser abrupta:
            # Se o valor atual do campo de texto não é o texto de uma opção válida,
            # e temos uma opção selecionada, reverta para o texto da opção selecionada.
            # Se não temos opção selecionada, o campo pode ficar com o texto digitado.
            if self._selected_option and self.text_field.value != self._selected_option.text:
                # O usuário digitou algo, mas não selecionou.
                # Se quisermos forçar uma seleção, podemos limpar ou reverter.
                # self.text_field.value = self._selected_option.text # Reverte
                # self.text_field.update()
                pass # Deixa o texto como está, o usuário pode não querer selecionar nada
            elif not self._selected_option and self.text_field.value:
                # Digitou algo, mas não selecionou e não havia seleção anterior
                pass

            # A lista de dropdown deve fechar ao perder o foco.
            self._close_dropdown_list()


    @property
    def value(self) -> Optional[str]:
        """Retorna a CHAVE (key) da opção selecionada."""
        return self._selected_option.key if self._selected_option else None

    @value.setter
    def value(self, new_key: Optional[str]):
        """Define a opção selecionada pela CHAVE (key)."""
        new_selected_opt = None
        for opt in self.all_options:
            if opt.key == new_key:
                new_selected_opt = opt
                break

        if self._selected_option != new_selected_opt:
            self._selected_option = new_selected_opt
            self.text_field.value = self._selected_option.text if self._selected_option else ""
            if self.page:
                self.text_field.update()
            if self.on_change_callback:
                self.on_change_callback(new_key)
        # Atualiza a lista para refletir a seleção (se estiver aberta)
        if self._is_open:
            self._populate_filtered_list(self.filtered_options_list.controls) # Passar a lista atual

    def update_options(self, new_options: List[ft.dropdown.Option]):
        """Atualiza a lista de todas as opções disponíveis."""
        self.all_options = new_options[:]
        # Se o item atualmente selecionado não existir mais nas novas opções, desmarque-o.
        current_key = self.value
        if current_key:
            found = any(opt.key == current_key for opt in self.all_options)
            if not found:
                self.value = None # Isso vai limpar o texto e chamar o callback
        # Se o dropdown estiver aberto, atualize a lista filtrada.
        if self._is_open:
            self._on_search_text_change(ft.ControlEvent(target=self.text_field.uid, name="change", data=self.text_field.value, control=self.text_field, page=self.page))


class ProgressSteps(ft.Row):
    """
    Exibe uma sequência de passos, indicando o passo atual.
    Pode ser clicável para navegação se um callback on_step_change for fornecido.
    """
    def __init__(
        self,
        steps: List[str], # Lista de nomes dos passos
        current_step_index: int = 0,
        on_step_change: Optional[Callable[[int, str], None]] = None, # index, step_name
        completed_step_icon: str = ft.Icons.CHECK_CIRCLE,
        current_step_icon: str = ft.Icons.RADIO_BUTTON_CHECKED, # Ou ft.Icons.EDIT
        pending_step_icon: str = ft.Icons.RADIO_BUTTON_UNCHECKED, # Ou ft.Icons.CIRCLE_OUTLINED
        completed_color: str = theme.COLOR_SUCCESS,
        current_color: str = theme.PRIMARY,
        pending_color: str = ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE), # Cinza claro
        connector_color: str = ft.Colors.OUTLINE_VARIANT,
        step_clickable: bool = True, # Se os passos são clicáveis (requer on_step_change)
        # ... outros parâmetros de ft.Row
        **kwargs
    ):
        super().__init__(
            alignment=ft.MainAxisAlignment.SPACE_AROUND,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            wrap=True, # Permite quebrar linha se não couber
            **kwargs
        )
        self.steps_data = steps
        self._current_step_index = max(0, min(current_step_index, len(steps) - 1))
        self.on_step_change_callback = on_step_change
        self.step_clickable = step_clickable and (on_step_change is not None)

        self.completed_icon = completed_step_icon
        self.current_icon = current_step_icon
        self.pending_icon = pending_step_icon
        self.completed_color = completed_color
        self.current_color = current_color
        self.pending_color = pending_color
        self.connector_color = connector_color

        self._build_steps()

    def _build_steps(self):
        self.controls.clear()
        for i, step_name in enumerate(self.steps_data):
            is_completed = i < self._current_step_index
            is_current = i == self._current_step_index
            # is_pending = i > self._current_step_index # Não usado diretamente, mas implícito

            icon_name = self.pending_icon
            icon_color = self.pending_color
            text_weight = ft.FontWeight.NORMAL
            text_color = self.pending_color

            if is_completed:
                icon_name = self.completed_icon
                icon_color = self.completed_color
                text_color = self.completed_color
            elif is_current:
                icon_name = self.current_icon
                icon_color = self.current_color
                text_color = self.current_color
                text_weight = ft.FontWeight.BOLD

            step_icon = ft.Icon(name=icon_name, color=icon_color)
            step_text = ft.Text(step_name, weight=text_weight, color=text_color, size=12)

            step_control = ft.Container(
                content=ft.Column(
                    [step_icon, step_text],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=2,
                    tight=True
                ),
                data={"index": i, "name": step_name}, # Armazena dados no container
                on_click=self._handle_step_click if self.step_clickable else None,
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                border_radius=5,
                ink=self.step_clickable, # Efeito visual ao clicar se for clicável
            )
            self.controls.append(step_control)

            # Adiciona conector (linha) entre os passos, exceto para o último
            if i < len(self.steps_data) - 1:
                connector = ft.Container(
                    width=50, # Largura do conector
                    height=2,
                    bgcolor=self.connector_color,
                    alignment=ft.alignment.center,
                    margin=ft.margin.symmetric(horizontal=5) # Pequena margem
                )
                # Opcional: mudar a cor do conector se o passo anterior estiver completo
                # if is_completed or is_current:
                #     connector.bgcolor = self.completed_color
                self.controls.append(ft.Row([connector], expand=True, alignment=ft.MainAxisAlignment.CENTER)) # Para centralizar

        if self.page:
            self.update()

    def _handle_step_click(self, e: ft.ControlEvent):
        clicked_index = e.control.data["index"]
        clicked_name = e.control.data["name"]

        # Permite clicar para ir para um passo anterior, ou o próximo se o atual for válido.
        # Ou, se o callback permitir, qualquer passo.
        # Para este exemplo, vamos permitir clicar em qualquer um se on_step_change existir.
        if self.on_step_change_callback:
            # Atualiza o estado interno ANTES de chamar o callback,
            # ou deixa o callback ser responsável por chamar `self.current_step_index = ...`
            # É melhor que o callback decida se a mudança é válida e então atualize o componente.
            # Aqui, vamos apenas chamar o callback.
            self.on_step_change_callback(clicked_index, clicked_name)
            # O chamador DEVE atualizar self.current_step_index = novo_indice
            # para que o visual do ProgressSteps seja atualizado.

    @property
    def current_step_index(self) -> int:
        return self._current_step_index

    @current_step_index.setter
    def current_step_index(self, new_index: int):
        clamped_index = max(0, min(new_index, len(self.steps_data) - 1))
        if self._current_step_index != clamped_index:
            self._current_step_index = clamped_index
            self._build_steps() # Reconstrói a UI dos passos

    def next_step(self):
        """Avança para o próximo passo, se houver."""
        if self._current_step_index < len(self.steps_data) - 1:
            self.current_step_index += 1
            if self.on_step_change_callback:
                self.on_step_change_callback(self._current_step_index, self.steps_data[self._current_step_index])


    def previous_step(self):
        """Retorna para o passo anterior, se houver."""
        if self._current_step_index > 0:
            self.current_step_index -= 1
            if self.on_step_change_callback:
                self.on_step_change_callback(self._current_step_index, self.steps_data[self._current_step_index])


class ManagedAlertDialog(ft.AlertDialog):
    """
    Um ft.AlertDialog que gerencia seu fechamento de forma desacoplada
    e permite executar um callback após o fechamento visual e a execução de uma ação.
    """
    def __init__(
        self,
        page_ref: ft.Page,
        title: Optional[Union[str, ft.Control]] = None,
        content: Optional[ft.Control] = None,
        actions: Optional[List[ft.Control]] = None, # Botões de ação
        # Callback a ser executado DEPOIS que o diálogo for completamente fechado
        # e uma ação interna (se houver) for concluída.
        # Recebe o 'result_data' do botão que fechou o diálogo.
        on_dialog_fully_closed: Optional[Callable[[Any], None]] = None,
        close_delay_seconds: float = 0.15,
        modal: bool = True,
        **kwargs 
    ):
        # Converte título string para ft.Text se necessário
        title_control = ft.Text(title) if isinstance(title, str) else title

        super().__init__(
            title=title_control,
            content=content,
            actions=actions, # Os on_click dos botões serão reconfigurados
            modal=modal,
            actions_alignment=ft.MainAxisAlignment.END, # Padrão
            **kwargs
        )
        self.page_ref = page_ref
        self.on_dialog_fully_closed = on_dialog_fully_closed
        self.close_delay_seconds = close_delay_seconds
        self._result_data_for_callback: Any = None

        # Reconfigurar os on_click dos botões de ação fornecidos
        if self.actions:
            for action_button in self.actions:
                if isinstance(action_button, (ft.TextButton, ft.ElevatedButton, ft.IconButton)) and \
                   hasattr(action_button, 'on_click') and action_button.on_click is not None:
                    
                    original_button_on_click = action_button.on_click
                    button_data_attribute = getattr(action_button, 'data', None)

                    # Criar um novo handler que primeiro executa a ação original do botão
                    # e depois fecha o diálogo.
                    def create_extended_on_click(orig_click, btn_data):
                        def extended_handler(e: ft.ControlEvent):
                            action_result = None
                            should_close_dialog_after_action = True # Por padrão, fecha
                            try:
                                # Executa a lógica original do botão (ex: salvar_configuracoes)
                                # Essa lógica original pode retornar algo para indicar se o diálogo deve fechar
                                # ou qual resultado passar para on_dialog_fully_closed.
                                # Ex: return True (fecha, sucesso), False (não fecha), "dados_especificos" (fecha, passa dados)
                                action_result = orig_click(e)

                                if isinstance(action_result, bool):
                                    should_close_dialog_after_action = action_result
                                    # Se for bool, os dados para o callback principal serão os 'data' do botão
                                    self._result_data_for_callback = btn_data 
                                elif action_result is not None: # Se retornou algo que não é bool, usa como dados
                                    self._result_data_for_callback = action_result
                                    should_close_dialog_after_action = True # Assume que deve fechar
                                else: # Se retornou None (ou não retornou nada), usa o 'data' do botão
                                     self._result_data_for_callback = btn_data
                                     should_close_dialog_after_action = True


                            except Exception as ex_orig_click:
                                logger.error(f"Erro ao executar ação original do botão '{getattr(action_button, 'text', 'BTN')}': {ex_orig_click}", exc_info=True)
                                show_snackbar(self.page_ref, f"Erro ao processar ação.", color=theme.COLOR_ERROR)
                                should_close_dialog_after_action = False # Não fecha se a ação interna deu erro

                            if should_close_dialog_after_action:
                                self._trigger_close_with_timer()
                            # Se não deve fechar, o diálogo permanece aberto para o usuário corrigir.
                        return extended_handler

                    action_button.on_click = create_extended_on_click(original_button_on_click, button_data_attribute)
                # Adicionar else para botões que não são de ação (ex: ft.Container(expand=True)) se necessário
                # ou garantir que apenas botões clicáveis sejam processados.
        self.actions = [ft.Row(
            [*self.actions],
            alignment=ft.MainAxisAlignment.SPACE_AROUND
        )]

    def _trigger_close_with_timer(self):
        """Fecha visualmente e agenda _finish_close_action."""
        if self.open:
            self.open = False
            self.page_ref.update(self) # Atualiza apenas o diálogo para processar o open=False
            logger.info(f"[DEBUG] ManagedAlertDialog: Fechamento visual iniciado. Agendando finalização.")
            threading.Timer(self.close_delay_seconds, self._finish_close_action).start()
        else:
             logger.info("[DEBUG] ManagedAlertDialog: _trigger_close_with_timer chamado, mas diálogo já estava fechado.")


    def _finish_close_action(self):
        """Executado pelo timer após o fechamento visual."""
        logger.info(f"[DEBUG] ManagedAlertDialog: Timer finalizado.")
        if self in self.page_ref.overlay: # Remove do overlay
            self.page_ref.overlay.remove(self)
            # Não chamar page_ref.update() aqui se on_dialog_fully_closed vai fazer (via snackbar etc.)

        if self.on_dialog_fully_closed:
            try:
                logger.info(f"[DEBUG] ManagedAlertDialog: Chamando on_dialog_fully_closed com dados: {self._result_data_for_callback}")
                self.on_dialog_fully_closed(self._result_data_for_callback)
            except Exception as e:
                logger.error(f"ManagedAlertDialog: Erro ao executar on_dialog_fully_closed: {e}", exc_info=True)
                show_snackbar(self.page_ref, "Ocorreu um erro após fechar o diálogo.", color=theme.COLOR_ERROR)
        elif self in self.page_ref.overlay: # Se foi removido e não há callback, um update pode ser necessário
             self.page_ref.update()


    def show(self):
        """Adiciona ao overlay (se não estiver) e abre o diálogo."""
        if self not in self.page_ref.overlay:
            self.page_ref.overlay.append(self)
        self.open = True
        self.page_ref.update() # Atualiza para mostrar/trazer para frente
        logger.info(f"ManagedAlertDialog '{self.title.value if isinstance(self.title, ft.Text) else ''}' ABERTO.")

    # Método para fechar programaticamente sem passar por um botão (ex: de um callback interno)
    def close_programmatically(self, result_data_for_callback: Any = None):
        self._result_data_for_callback = result_data_for_callback
        self._trigger_close_with_timer()




