import flet as ft
from typing import List, Dict, Any, Optional, Callable, Type

from .layout import show_snackbar, show_confirmation_dialog

from src.logger.logger import LoggerSetup
logger = LoggerSetup.get_logger(__name__)

# Define o tipo para a função de callback que será chamada ao selecionar/cancelar
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

    
import unicodedata, re
def _normalize_key(text: str) -> str:
    """
    Normaliza uma string para ser usada como chave:
    - Remove acentos.
    - Converte para minúsculas.
    - Substitui espaços e caracteres não alfanuméricos por underscore.
    - Remove underscores duplicados.
    """
    if not isinstance(text, str):
        text = str(text)
    # Converte para minúsculas
    text = text.lower()
    #
    text = text.replace('(%)', 'percentual')
    text = text.replace('(kg)', '').strip()
    if text.endswith('_id'):
        text = text[:-3]
    # Remove acentos (compatibilidade NFKD)
    nfkd_form = unicodedata.normalize('NFKD', text)
    text = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    # Substitui espaços e não alfanuméricos por underscore
    text = re.sub(r'[^a-z0-9]+', '_', text)
    # Remove underscores no início/fim e múltiplos underscores
    text = re.sub(r'_+', '_', text).strip('_')
    return text

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
            _normalize_key(col.label.value if isinstance(col.label, ft.Text) else str(col.label)): col
            for col in columns
        }
        # Cria um mapeamento de label original para chave normalizada
        self.original_label_to_normalized: Dict[str, str] = {
             (col.label.value if isinstance(col.label, ft.Text) else str(col.label)) : _normalize_key(col.label.value if isinstance(col.label, ft.Text) else str(col.label))
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
             label="Buscar...", prefix_icon=ft.icons.SEARCH, on_change=self.handle_search_change,
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
             icon=ft.icons.KEYBOARD_ARROW_LEFT, on_click=self.prev_page, tooltip="Página Anterior", disabled=True
        )
        self.page_info = ft.Text(f"Página {self.current_page}/1")
        self.next_button = ft.IconButton( # ... (como antes) ...
             icon=ft.icons.KEYBOARD_ARROW_RIGHT, on_click=self.next_page, tooltip="Próxima Página", disabled=True
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
                               if _normalize_key(data_k) == normalized_label_key:
                                   key_in_data = data_k
                                   break
                           if key_in_data:
                                value = item_data.get(key_in_data)

                 # Se ainda assim não encontrar, usa string vazia
                 cells.append(ft.DataCell(ft.Text(str(value if value is not None else ''))))

            # Adiciona botões de ação
            if self.action_buttons:
                if self.on_edit_callback: cells.append(ft.DataCell(ft.IconButton(icon=ft.icons.EDIT_OUTLINED, tooltip="Editar Item", data=item_id, on_click=self.handle_edit_click)))
                if self.on_delete_callback: cells.append(ft.DataCell(ft.IconButton(icon=ft.icons.DELETE_OUTLINE, tooltip="Excluir Item", icon_color=ft.colors.RED_ACCENT_400, data=item_id, on_click=self.handle_delete_click)))

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

