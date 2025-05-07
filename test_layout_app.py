# test_layout_app.py (coloque na raiz do projeto Repo/)

'''
TODO: 
1) Parece estar havendo um conflito entre esses dois IconButtons. MENU Não está surtindo efeito, e BRIGHTNESS_4_OUTLINED às vezes abre o drawer, às vezes troca o tema.

'''

import flet as ft
import sys
import os
import time
import shutil # Para ManagedFilePicker clear_upload_directory
from typing import List, Dict, Any, Optional, Callable, Type

# --- Configuração do Caminho para Importação ---
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root_candidate = script_dir
src_path = os.path.join(project_root_candidate, "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)
# --- Fim da Configuração do Caminho ---

from src.flet_ui import layout as app_layout # Renomeado para evitar conflito
from src.flet_ui import theme as app_theme
from src.flet_ui import components # Importa todos os seus componentes
# from src.utils import normalize_key # Já importado por components.DataTableWrapper

# --- Mocks e Dados de Exemplo ---

# Mock para SelectionDialog (SQLAlchemy)
class MockSQLAlchemyModel:
    def __init__(self, id: int, name: str, description: str):
        self.id = id
        self.name = name
        self.description = description
        self.category = f"Categoria {id % 3}"

    def __repr__(self):
        return f"<MockModel(id={self.id}, name='{self.name}')>"

mock_db_items: List[MockSQLAlchemyModel] = [
    MockSQLAlchemyModel(i, f"Item {i}", f"Descrição detalhada do item número {i}") for i in range(1, 25)
]

# Dados para DataTableWrapper
sample_table_columns = [
    ft.DataColumn(ft.Text("ID")),
    ft.DataColumn(ft.Text("Nome do Produto"), numeric=False),
    ft.DataColumn(ft.Text("Preço"), numeric=True),
    ft.DataColumn(ft.Text("Em Estoque"), numeric=True),
]
sample_table_data = [
    {"ID": "P001", "Nome do Produto": "Laptop Gamer X", "Preço": 7500.00, "Em Estoque": 15, "Categoria": "Eletrônicos"},
    {"ID": "P002", "Nome do Produto": "Mouse Óptico", "Preço": 89.90, "Em Estoque": 120, "Categoria": "Acessórios"},
    {"ID": "P003", "Nome do Produto": "Teclado Mecânico RGB", "Preço": 350.00, "Em Estoque": 45, "Categoria": "Acessórios"},
    {"ID": "P004", "Nome do Produto": "Monitor Ultrawide 34\"", "Preço": 2200.00, "Em Estoque": 8, "Categoria": "Eletrônicos"},
    {"ID": "P005", "Nome do Produto": "Cadeira Gamer Confort", "Preço": 950.00, "Em Estoque": 22, "Categoria": "Móveis"},
    {"ID": "P006", "Nome do Produto": "SSD NVMe 1TB", "Preço": 650.00, "Em Estoque": 50, "Categoria": "Componentes"},
    {"ID": "P007", "Nome do Produto": "Webcam Full HD", "Preço": 180.00, "Em Estoque": 30, "Categoria": "Acessórios"},
    {"ID": "P008", "Nome do Produto": "Headset Surround 7.1", "Preço": 420.00, "Em Estoque": 18, "Categoria": "Acessórios"},
    {"ID": "P009", "Nome do Produto": "Placa de Vídeo RTX 4070", "Preço": 4500.00, "Em Estoque": 5, "Categoria": "Componentes"},
    {"ID": "P010", "Nome do Produto": "Mesa Digitalizadora", "Preço": 300.00, "Em Estoque": 12, "Categoria": "Arte Digital"},
    {"ID": "P011", "Nome do Produto": "Impressora Multifuncional", "Preço": 550.00, "Em Estoque": 25, "Categoria": "Periféricos"},
    {"ID": "P012", "Nome do Produto": "Roteador Wi-Fi 6", "Preço": 380.00, "Em Estoque": 33, "Categoria": "Redes"},
    {"ID": "P013", "Nome do Produto": "HD Externo 2TB", "Preço": 280.00, "Em Estoque": 40, "Categoria": "Armazenamento"},
    {"ID": "P014", "Nome do Produto": "Cooler para Notebook", "Preço": 95.00, "Em Estoque": 60, "Categoria": "Acessórios"},
    {"ID": "P015", "Nome do Produto": "Fonte ATX 750W", "Preço": 410.00, "Em Estoque": 17, "Categoria": "Componentes"},
]

# --- Instâncias Globais para Teste (se necessário) ---
# Para ManagedFilePicker
global_file_picker_instance: Optional[ft.FilePicker] = None
# Para SearchableDropdown (se precisar referenciar o container de overlay)
# searchable_dropdown_overlay_container: Optional[ft.Container] = None

# --- Área de Conteúdo Principal ---
main_content_area = ft.Column(
    controls=[ft.Text("Bem-vindo! Navegue usando o menu lateral ou superior.")],
    alignment=ft.MainAxisAlignment.START,
    horizontal_alignment=ft.CrossAxisAlignment.START,
    expand=True,
    spacing=20,
)

def update_main_content_for_route(page: ft.Page, route: str):
    main_content_area.controls.clear()
    main_content_area.controls.append(
        ft.Text(f"Conteúdo da Rota: {route}", size=24, weight=ft.FontWeight.BOLD)
    )
    main_content_area.controls.append(
        ft.Text(f"Índice de navegação base detectado: {app_layout._find_nav_index_for_route(route)}")
    )
    # Adiciona botões para testar a navegação para sub-rotas específicas
    if route.startswith("/products"):
        main_content_area.controls.append(
            ft.ElevatedButton("Ir para /products/list", on_click=lambda _: page.go("/products/list"))
        )
    #main_content_area.update()


# --- Funções de Callback para Componentes ---
def on_generic_confirm(component_name: str):
    print(f"Callback de CONFIRMAÇÃO para {component_name} disparado.")
    # A página é passada para show_snackbar no local da chamada
    # components.show_snackbar(page, f"{component_name}: Ação confirmada!", color=app_theme.COLOR_SUCCESS)

def on_generic_cancel(component_name: str):
    print(f"Callback de CANCELAR para {component_name} disparado.")

# --- Construtor da View de Teste de Componentes ---
def create_components_test_view(page: ft.Page) -> ft.Column:
    """Cria a coluna de conteúdo para testar os componentes."""
    
    components_column = ft.Column(scroll=ft.ScrollMode.ADAPTIVE, expand=True, spacing=20)
    components_column.controls.append(ft.Text("Demonstração de Componentes", size=30, weight=ft.FontWeight.BOLD))

    # 1. SnackBar
    components_column.controls.append(ft.Text("1. SnackBar Global", size=18, weight=ft.FontWeight.BOLD))
    sb_buttons = ft.Row([
        ft.ElevatedButton("Info SB", on_click=lambda _: components.show_snackbar(page, "Esta é uma informação.", color=app_theme.COLOR_INFO)),
        ft.ElevatedButton("Erro SB", on_click=lambda _: components.show_snackbar(page, "Isto é um erro!", color=app_theme.COLOR_ERROR, duration=3000)),
        ft.ElevatedButton("Sucesso SB", on_click=lambda _: components.show_snackbar(page, "Operação bem-sucedida!", color=app_theme.COLOR_SUCCESS)),
    ])
    components_column.controls.append(sb_buttons)
    components_column.controls.append(ft.Divider())

    # 2. ConfirmationDialog
    components_column.controls.append(ft.Text("2. Diálogo de Confirmação", size=18, weight=ft.FontWeight.BOLD))
    def _show_conf_dialog(e):
        components.show_confirmation_dialog(
            page,
            title="Confirmar Ação?",
            content="Você tem certeza que deseja prosseguir com esta operação perigosa?",
            on_confirm=lambda: (
                on_generic_confirm("ConfirmationDialog"),
                components.show_snackbar(page, "Dialog: Confirmado!", color=app_theme.COLOR_SUCCESS)
            )
        )
    components_column.controls.append(ft.ElevatedButton("Abrir Diálogo de Confirmação", on_click=_show_conf_dialog))
    components_column.controls.append(ft.Divider())

    # 3. SelectionDialog (Mockado)
    components_column.controls.append(ft.Text("3. SelectionDialog (Mockado)", size=18, weight=ft.FontWeight.BOLD))
    selected_item_text = ft.Text("Nenhum item selecionado do SelectionDialog.")
    
    def _on_item_selected_from_dialog(selected_item: Optional[MockSQLAlchemyModel]):
        if selected_item:
            message = f"Item selecionado: ID {selected_item.id}, Nome: {selected_item.name}"
            selected_item_text.value = message
            components.show_snackbar(page, message, color=app_theme.COLOR_INFO)
        else:
            selected_item_text.value = "Seleção cancelada."
            components.show_snackbar(page, "Seleção do diálogo cancelada.", color=app_theme.COLOR_WARNING)
        selected_item_text.update()

    # Mock do SelectionDialog, já que ele espera um modelo SQLAlchemy
    # Em um teste real, você poderia ter um mock mais elaborado da query
    class MockSelectionDialog: # Para simular a interface se o original não puder ser instanciado
        def __init__(self, page_ref, model, title, search_fields, display_attrs, on_select, initial_query=None):
            self.page = page_ref
            self.title = title
            self.search_fields = search_fields
            self.display_attrs = display_attrs
            self.on_select = on_select
            self.all_items = mock_db_items # Usando os dados mockados
            self.dialog = None

        def _filter_items(self, search_term: str):
            if not search_term: return self.all_items
            term = search_term.lower()
            return [
                item for item in self.all_items
                if any(term in str(getattr(item, field, "")).lower() for field in self.search_fields)
            ]

        def _update_dialog_content(self, search_term: str = ""):
            filtered = self._filter_items(search_term)
            list_view_items = []
            if not filtered:
                list_view_items.append(ft.ListTile(title=ft.Text("Nenhum item encontrado.")))
            else:
                for item in filtered[:10]: # Limita a 10 para exibição
                    display_text = " - ".join([str(getattr(item, attr, "")) for attr in self.display_attrs])
                    list_view_items.append(
                        ft.ListTile(title=ft.Text(display_text), data=item, on_click=self._confirm_selection)
                    )
            self.dialog.content.controls[1].controls = list_view_items # Assume estrutura do diálogo
            self.page.update()


        def _confirm_selection(self, e):
            self.dialog.open = False
            self.page.overlay.remove(self.dialog)
            self.page.update()
            self.on_select(e.control.data)

        def _cancel_selection(self, e):
            self.dialog.open = False
            self.page.overlay.remove(self.dialog)
            self.page.update()
            self.on_select(None)
            
        def open(self):
            search_bar = ft.TextField(label="Buscar item...", on_change=lambda e: self._update_dialog_content(e.control.value))
            items_list_view = ft.ListView(expand=True, spacing=5)
            
            self.dialog = ft.AlertDialog(
                modal=True, title=ft.Text(self.title),
                content=ft.Container(
                    ft.Column([search_bar, items_list_view], tight=True, height=300, width=400),
                    padding=5
                ),
                actions=[ft.TextButton("Cancelar", on_click=self._cancel_selection)],
            )
            self.page.overlay.append(self.dialog)
            self._update_dialog_content() # Popula inicialmente
            self.dialog.open = True
            self.page.update()

    # Usando o MockSelectionDialog (ou o original se você conseguir mockar SQLAlchemy query)
    # Tentar usar o original, mas pode dar erro se `initial_query` for essencial
    try:
        selection_dialog_instance = components.SelectionDialog(
            page=page,
            model=MockSQLAlchemyModel, # Passa a classe Mock
            title="Selecionar Item (Mock DB)",
            search_fields=["name", "description"],
            display_attrs=["id", "name"],
            on_select=_on_item_selected_from_dialog,
            # initial_query pode ser problemático sem um Session real.
            # Se o seu componente lida com initial_query=None, ok. Senão, use o MockSelectionDialog.
        )
        components_column.controls.append(ft.ElevatedButton("Abrir SelectionDialog", on_click=lambda _: selection_dialog_instance.open()))
    except Exception as e:
        print(f"Não foi possível instanciar components.SelectionDialog original: {e}. Usando mock simples.")
        mock_selection_dialog_instance = MockSelectionDialog(
             page, MockSQLAlchemyModel, "Selecionar Item (Mock Simples)", ["name"], ["id", "name"], _on_item_selected_from_dialog
        )
        components_column.controls.append(ft.ElevatedButton("Abrir SelectionDialog (Mock Simples)", on_click=lambda _: mock_selection_dialog_instance.open()))
        
    components_column.controls.append(selected_item_text)
    components_column.controls.append(ft.Divider())

    # 4. DataTableWrapper
    components_column.controls.append(ft.Text("4. DataTableWrapper", size=18, weight=ft.FontWeight.BOLD))
    dt_data = sample_table_data[:] # Cópia para permitir modificação
    
    def handle_dt_edit(item_id: str):
        components.show_snackbar(page, f"DataTable: Editar item {item_id}", color=app_theme.COLOR_INFO)
    
    def handle_dt_delete(item_id: str):
        global dt_data # Para modificar a lista original
        dt_data = [item for item in dt_data if item.get("ID") != item_id]
        data_table_wrapper.update_data(dt_data) # Atualiza a tabela com os dados modificados
        components.show_snackbar(page, f"DataTable: Excluir item {item_id}. Item removido da fonte de dados.", color=app_theme.COLOR_SUCCESS)

    data_table_wrapper = components.DataTableWrapper(
        page=page,
        columns=sample_table_columns,
        data=dt_data,
        item_id_key="ID", # Chave original nos dados
        search_keys=["Nome do Produto", "Categoria"], # Chaves originais para busca
        on_edit=handle_dt_edit,
        on_delete=handle_dt_delete,
        items_per_page=5
    )
    components_column.controls.append(data_table_wrapper)
    # Botão para adicionar dados dinamicamente (exemplo)
    def add_new_data_to_table(e):
        global dt_data
        new_id = f"P{len(dt_data)+1:03d}"
        dt_data.append({"ID": new_id, "Nome do Produto": f"Novo Produto {new_id}", "Preço": 10.00, "Em Estoque": 1, "Categoria":"Novidades"})
        data_table_wrapper.update_data(dt_data)
        components.show_snackbar(page, "Novo item adicionado à tabela.", color=app_theme.COLOR_INFO)
    components_column.controls.append(ft.ElevatedButton("Adicionar Item à Tabela", on_click=add_new_data_to_table))
    components_column.controls.append(ft.Divider())

    # 5. LoadingOverlay
    components_column.controls.append(ft.Text("5. LoadingOverlay", size=18, weight=ft.FontWeight.BOLD))
    def _show_loading_with_delay(e):
        components.show_loading_overlay(page, "Carregando dados importantes...")
        def hide_after_delay():
            time.sleep(3) # Simula uma operação demorada
            components.hide_loading_overlay(page)
            components.show_snackbar(page, "Carregamento concluído!", color=app_theme.COLOR_SUCCESS)
        # Executar em uma thread para não bloquear a UI
        import threading
        threading.Thread(target=hide_after_delay, daemon=True).start()
    components_column.controls.append(ft.ElevatedButton("Mostrar Loading (3s)", on_click=_show_loading_with_delay))
    components_column.controls.append(ft.Divider())

    # 6. ValidatedTextField & PasswordField
    components_column.controls.append(ft.Text("6. ValidatedTextField & PasswordField", size=18, weight=ft.FontWeight.BOLD))
    
    def validate_not_empty(value: str) -> Optional[str]:
        if not value: return "Campo obrigatório."
        if len(value) < 3: return "Mínimo 3 caracteres."
        return None
    
    def on_validated_change(value: str):
        print(f"ValidatedTF (change_validated): {value}")

    v_textfield = components.ValidatedTextField(
        label="Nome (obrigatório, min 3)",
        validator=validate_not_empty,
        on_change_validated=on_validated_change,
        hint_text="Digite seu nome completo"
    )
    
    # PasswordField (usa seu próprio validador de força por padrão)
    p_field = components.PasswordField(
        label="Nova Senha",
        min_length=6, require_special_char=False # Configurações do validador padrão
    )
    
    submit_button_validated_fields = ft.ElevatedButton("Submeter Formulário")
    def _submit_validated_form(e):
        is_v_valid = v_textfield.validate(show_error=True) # Força validação e mostra erro
        is_p_valid = p_field.validate(show_error=True)
        if is_v_valid and is_p_valid:
            components.show_snackbar(page, f"Formulário Válido! Nome: {v_textfield.value}, Senha: {p_field.value}", color=app_theme.COLOR_SUCCESS)
        else:
            components.show_snackbar(page, "Formulário Inválido. Verifique os campos.", color=app_theme.COLOR_ERROR)
    submit_button_validated_fields.on_click = _submit_validated_form

    components_column.controls.extend([v_textfield, p_field, submit_button_validated_fields])
    components_column.controls.append(ft.Divider())

    # 7. ManagedFilePicker
    components_column.controls.append(ft.Text("7. ManagedFilePicker", size=18, weight=ft.FontWeight.BOLD))
    # A instância do FilePicker deve ser adicionada ao overlay da página (feito em main_test_layout)
    # global global_file_picker_instance # Já declarado no topo
    if global_file_picker_instance is None:
         components_column.controls.append(ft.Text("FilePicker global não inicializado!", color=app_theme.COLOR_ERROR))
    else:
        upload_status_text = ft.Text("Status do Upload: Nenhum arquivo selecionado.")
        upload_progress_bar = ft.ProgressBar(value=0, width=200, visible=False)

        def on_upload_completed(success: bool, path_or_error: str, filename: Optional[str]):
            upload_progress_bar.visible = False
            if success:
                msg = f"Upload de '{filename}' completo! Salvo em: {path_or_error}"
                upload_status_text.value = msg
                components.show_snackbar(page, msg, color=app_theme.COLOR_SUCCESS)
                # Em uma app real, você processaria o arquivo aqui e depois o removeria de temp_uploads
                # Ex: if os.path.exists(path_or_error): os.remove(path_or_error)
            else:
                msg = f"Falha no upload de '{filename}': {path_or_error}"
                upload_status_text.value = msg
                components.show_snackbar(page, msg, color=app_theme.COLOR_ERROR)
            upload_status_text.update()
            upload_progress_bar.update()

        def on_upload_progress_update(filename: str, progress_value: float):
            upload_progress_bar.visible = True
            upload_progress_bar.value = progress_value
            upload_status_text.value = f"Enviando '{filename}': {int(progress_value * 100)}%"
            upload_status_text.update()
            upload_progress_bar.update()

        # Garante que o diretório exista (deve ser criado manualmente ou por script antes)
        temp_upload_dir = os.path.join(project_root_candidate, "temp_uploads")
        if not os.path.exists(temp_upload_dir):
            try:
                os.makedirs(temp_upload_dir, exist_ok=True)
            except OSError:
                 components_column.controls.append(ft.Text(f"ERRO: Não foi possível criar {temp_upload_dir}", color=app_theme.COLOR_ERROR))


        managed_picker = components.ManagedFilePicker(
            page=page,
            file_picker_instance=global_file_picker_instance,
            on_upload_complete=on_upload_completed,
            upload_dir=temp_upload_dir, # Diretório na raiz do projeto
            allowed_extensions=["txt", "csv", "json", "png", "jpg"],
            on_upload_progress=on_upload_progress_update
        )
        
        picker_buttons = ft.Row([
            ft.ElevatedButton("Selecionar Arquivo Único (.txt, .png)", on_click=lambda _: managed_picker.pick_files(allow_multiple=False)),
            ft.ElevatedButton("Limpar Diretório de Uploads", on_click=lambda _: (
                managed_picker.clear_upload_directory(),
                components.show_snackbar(page, "Diretório de uploads temporários limpo.", color=app_theme.COLOR_INFO)
            ))
        ])
        components_column.controls.extend([upload_status_text, upload_progress_bar, picker_buttons])
    components_column.controls.append(ft.Divider())

    # 8. Diálogos Aninhados
    components_column.controls.append(ft.Text("8. Diálogos Aninhados", size=18, weight=ft.FontWeight.BOLD))
    parent_dialog_ref = ft.Ref[ft.AlertDialog]()
    child_dialog_ref = ft.Ref[ft.AlertDialog]()
    nested_dialog_status = ft.Text("Status diálogos aninhados: Nenhum aberto.")

    def open_child_dialog_action():
        nested_dialog_status.value = "Diálogo filho aberto."
        nested_dialog_status.update()
        if child_dialog_ref.current:
            page.overlay.append(child_dialog_ref.current) # Adiciona antes de abrir
            child_dialog_ref.current.open = True
            page.update() # Abre o diálogo filho

    def close_child_and_reopen_parent(e):
        nested_dialog_status.value = "Filho fechado, reabrindo pai..."
        nested_dialog_status.update()
        if child_dialog_ref.current:
            child_dialog_ref.current.open = False
            # page.overlay.remove(child_dialog_ref.current) # Importante remover
            page.update()
            # Lógica antes de reabrir (ex: pegar um valor do filho)
            def logic_for_parent():
                print("Lógica executada antes de reabrir o pai.")
                parent_dialog_ref.current.content = ft.Text(f"Retornou do filho! {time.time()}")

            # Reabre o pai usando o utilitário
            components.reopen_parent_dialog(page, parent_dialog_ref.current, logic_before_reopen_callable=logic_for_parent)
            # O reopen_parent_dialog já lida com adicionar ao overlay e update
    
    # Definir o diálogo filho
    child_dialog_ref.current = ft.AlertDialog(
        ref=child_dialog_ref,
        modal=True, title=ft.Text("Diálogo Filho"),
        content=ft.Text("Conteúdo do diálogo filho. Clique para fechar e retornar ao pai."),
        actions=[ft.TextButton("Fechar Filho e Voltar", on_click=close_child_and_reopen_parent)]
    )
    
    def open_parent_then_child(e):
        nested_dialog_status.value = "Diálogo pai aberto."
        nested_dialog_status.update()
        if parent_dialog_ref.current:
            page.overlay.append(parent_dialog_ref.current)
            parent_dialog_ref.current.open = True
            page.update()

    # Definir o diálogo pai
    parent_dialog_ref.current = ft.AlertDialog(
        ref=parent_dialog_ref,
        modal=True, title=ft.Text("Diálogo Pai"),
        content=ft.Text("Conteúdo do diálogo pai. Clique abaixo para abrir o filho."),
        actions=[
            ft.TextButton("Abrir Filho", on_click=lambda _: components.open_nested_dialog(page, parent_dialog_ref.current, open_child_dialog_action)),
            ft.TextButton("Fechar Pai", on_click=lambda e: (setattr(parent_dialog_ref.current, 'open', False), page.update()))
        ]
    )
    components_column.controls.append(ft.ElevatedButton("Testar Diálogos Aninhados", on_click=open_parent_then_child))
    components_column.controls.append(nested_dialog_status)
    components_column.controls.append(ft.Divider())

    # 9. CardWithHeader
    components_column.controls.append(ft.Text("9. CardWithHeader", size=18, weight=ft.FontWeight.BOLD))
    card_header_actions = [
        ft.IconButton(ft.Icons.EDIT, tooltip="Editar Card", on_click=lambda _: components.show_snackbar(page, "Ação: Editar Card", app_theme.COLOR_INFO)),
        ft.IconButton(ft.Icons.SETTINGS, tooltip="Configurar Card"),
    ]
    card_content_column = ft.Column([ft.Text("Conteúdo inicial do card."), ft.TextField(label="Um campo no card")])
    card_with_header = components.CardWithHeader(
        title="Título do Card Personalizado",
        content=card_content_column,
        header_actions=card_header_actions,
        card_elevation=4
    )
    components_column.controls.append(card_with_header)
    card_update_buttons = ft.Row([
        ft.ElevatedButton("Mudar Título Card", on_click=lambda _: card_with_header.update_title(f"Novo Título {time.time():.0f}")),
        ft.ElevatedButton("Mudar Conteúdo Card", on_click=lambda _: card_with_header.update_content(ft.Text(f"Novo conteúdo aleatório: {time.time()}"))),
    ])
    components_column.controls.append(card_update_buttons)
    components_column.controls.append(ft.Divider())

    # 10. SectionCollapsible
    components_column.controls.append(ft.Text("10. SectionCollapsible", size=18, weight=ft.FontWeight.BOLD))
    collapsible_content = ft.Column([
        ft.Text("Este é um conteúdo que pode ser escondido."),
        ft.Checkbox(label="Opção 1"), ft.Checkbox(label="Opção 2")
    ])
    section_collapsible = components.SectionCollapsible(
        title="Seção Expansível",
        content=collapsible_content,
        initially_expanded=False,
        header_bgcolor=app_theme.SURFACE_VARIANT, # Para destacar o header
        on_toggle=lambda is_expanded: print(f"SectionCollapsible toggled: {is_expanded}")
    )
    components_column.controls.append(section_collapsible)
    components_column.controls.append(
        ft.ElevatedButton("Toggle Seção Programaticamente", on_click=lambda _: setattr(section_collapsible, 'is_expanded', not section_collapsible.is_expanded))
    )
    components_column.controls.append(ft.Divider())

    # 11. KeyValueDisplay
    components_column.controls.append(ft.Text("11. KeyValueDisplay", size=18, weight=ft.FontWeight.BOLD))
    kv_data = {"Nome": "João Silva", "Email": "joao.silva@example.com", "Telefone": "(11) 98765-4321", "Status": "Ativo"}
    key_value_display = components.KeyValueDisplay(data=kv_data, value_selectable=True)
    components_column.controls.append(key_value_display)
    def update_kv_data(e):
        new_kv_data = {"Cidade": "São Paulo", "País": "Brasil", "ID Usuário": f"USR{int(time.time() % 1000)}", "Último Login": time.ctime()}
        key_value_display.update_data(new_kv_data)
    components_column.controls.append(ft.ElevatedButton("Atualizar KeyValue Data", on_click=update_kv_data))
    components_column.controls.append(ft.Divider())

    # 12. SearchableDropdown
    components_column.controls.append(ft.Text("12. SearchableDropdown", size=18, weight=ft.FontWeight.BOLD))
    dropdown_options = [
        ft.dropdown.Option(key="apple", text="Maçã"), ft.dropdown.Option(key="banana", text="Banana"),
        ft.dropdown.Option(key="orange", text="Laranja"), ft.dropdown.Option(key="grape", text="Uva"),
        ft.dropdown.Option(key="mango", text="Manga"), ft.dropdown.Option(key="pineapple", text="Abacaxi"),
    ]
    searchable_dd_status = ft.Text("SearchableDropdown: Nenhum valor selecionado.")

    def on_searchable_dd_change(selected_key: Optional[str]):
        text_to_show = "Nenhum valor"
        if selected_key:
            # Encontra o texto da opção selecionada
            selected_opt_text = next((opt.text for opt in dropdown_options if opt.key == selected_key), "Chave não encontrada")
            text_to_show = f"Chave: {selected_key}, Texto: {selected_opt_text}"
        searchable_dd_status.value = f"SearchableDropdown: {text_to_show}"
        searchable_dd_status.update()
        components.show_snackbar(page, f"SearchableDropdown mudou para: {text_to_show}", color=app_theme.COLOR_INFO)

    searchable_dropdown = components.SearchableDropdown(
        page=page,
        label="Escolha uma Fruta",
        options=dropdown_options,
        on_change=on_searchable_dd_change,
        width=300,
        hint_text="Busque sua fruta..."
    )
    components_column.controls.append(searchable_dropdown)
    components_column.controls.append(searchable_dd_status)
    
    new_options_for_dd = [
        ft.dropdown.Option(key="car", text="Carro"), ft.dropdown.Option(key="bike", text="Bicicleta"),
        ft.dropdown.Option(key="bus", text="Ônibus")
    ]
    update_options_button = ft.ElevatedButton(
        "Atualizar Opções do Dropdown",
        on_click=lambda _: (
            searchable_dropdown.update_options(new_options_for_dd),
            components.show_snackbar(page, "Opções do SearchableDropdown atualizadas!", color=app_theme.COLOR_INFO)
        )
    )
    set_value_button = ft.ElevatedButton(
        "Definir Dropdown para 'Laranja' (se existir)",
        on_click=lambda _: setattr(searchable_dropdown, 'value', 'orange')
    )
    components_column.controls.append(ft.Row([update_options_button, set_value_button]))
    components_column.controls.append(ft.Divider())

    # 13. ProgressSteps
    components_column.controls.append(ft.Text("13. ProgressSteps", size=18, weight=ft.FontWeight.BOLD))
    step_names = ["Carrinho", "Endereço", "Pagamento", "Confirmação", "Concluído"]
    progress_steps_status = ft.Text(f"Progresso Atual: Passo 0 - {step_names[0]}")

    def on_step_changed_callback(index: int, name: str):
        progress_steps_status.value = f"Progresso Atual: Passo {index} - {name}"
        progress_steps_status.update()
        progress_steps_component.current_step_index = index # O componente precisa ser atualizado
        components.show_snackbar(page, f"Progresso mudou para: {name}", color=app_theme.COLOR_INFO)

    progress_steps_component = components.ProgressSteps(
        steps=step_names,
        current_step_index=0,
        on_step_change=on_step_changed_callback, # Para testar clicabilidade
        step_clickable=True # Permite cliques nos passos
    )
    components_column.controls.append(progress_steps_component)
    components_column.controls.append(progress_steps_status)
    
    progress_buttons = ft.Row([
        ft.ElevatedButton("Anterior", on_click=lambda _: progress_steps_component.previous_step()),
        ft.ElevatedButton("Próximo", on_click=lambda _: progress_steps_component.next_step()),
        ft.ElevatedButton("Ir para Pagamento (idx 2)", on_click=lambda _: setattr(progress_steps_component, 'current_step_index', 2)),
    ])
    components_column.controls.append(progress_buttons)
    components_column.controls.append(ft.Divider())


    # Placeholder para garantir que haja algo se a lista estiver vazia
    if not components_column.controls:
        components_column.controls.append(ft.Text("Nenhum componente para exibir nesta seção de teste."))

    return components_column

# --- Modificações no Router e Layout de Teste ---

# Adicionar a nova rota ao layout (para este teste, faremos localmente)
# Copiando e modificando as estruturas de navegação do layout original
test_icones_navegacao = app_layout.icones_navegacao[:] + [
    {
        "label": "Componentes",
        "icon": ft.Icons.WIDGETS_OUTLINED,
        "selected_icon": ft.Icons.WIDGETS,
        "route": "/components_test"
    }
]
test_route_to_base_nav_index = app_layout.route_to_base_nav_index.copy()
test_route_to_base_nav_index["/components_test"] = len(app_layout.icones_navegacao) # Novo índice

# Sobrescrever _find_nav_index_for_route para usar o mapeamento de teste
def _test_find_nav_index_for_route(route: str) -> int:
    selected_index = 0 
    best_match_len = 0
    if route == "/": best_match_len = 1

    for base_route, index in test_route_to_base_nav_index.items():
        if base_route == "/" and route != "/": continue
        is_exact_match = (route == base_route)
        is_prefix_match = (base_route != "/" and route.startswith(base_route + "/"))
        if is_exact_match or is_prefix_match:
            current_match_len = len(base_route)
            if current_match_len > best_match_len:
                best_match_len = current_match_len
                selected_index = index
            elif current_match_len == best_match_len and is_exact_match and selected_index != index:
                 selected_index = index
    return selected_index

# Função principal
def main_test_layout(page: ft.Page):
    page.title = "Teste de Layout e Componentes Flet"
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.horizontal_alignment = ft.CrossAxisAlignment.START

    app_theme.configure_theme(page)

    # Para ManagedFilePicker e outros componentes que usam overlay de forma global
    global global_file_picker_instance
    global_file_picker_instance = ft.FilePicker()
    page.overlay.append(global_file_picker_instance)
    
    # Para SearchableDropdown - é melhor que ele mesmo adicione/remova seu overlay
    # global searchable_dropdown_overlay_container
    # searchable_dropdown_overlay_container = ft.Container(visible=False) # Inicialmente invisível
    # page.overlay.append(searchable_dropdown_overlay_container)


    def app_router(route_event: ft.RouteChangeEvent):
        current_route = page.route
        print(f"Navegando para: {current_route}")
        page.views.clear()

        # Usar o _find_nav_index_for_route modificado para este teste
        current_nav_index = _test_find_nav_index_for_route(current_route)

        # AppBar (do layout original)
        app_bar = app_layout.create_app_bar(page, app_title="Demonstração Flet")

        # NavigationDrawer (modificado para usar as rotas de teste)
        # Precisamos recriar os destinos do drawer ou passar os test_icones_navegacao
        # Para simplificar, vamos usar a lógica do layout.py mas com _test_find_nav_index_for_route
        temp_drawer_tiles = []
        for i, modulo in enumerate(test_icones_navegacao): # USA OS ÍCONES DE TESTE
            is_selected = (current_nav_index == i)
            temp_drawer_tiles.append(
                ft.ListTile(
                    title=ft.Text(modulo["label"]),
                    leading=ft.Icon(modulo["selected_icon"] if is_selected else modulo["icon"]),
                    on_click=lambda _, route=modulo["route"]: (
                        setattr(page.drawer, 'open', False), page.go(route)
                    ),
                    selected=is_selected,
                )
            )
        page.drawer = ft.NavigationDrawer(controls=temp_drawer_tiles)


        if page.drawer:
            app_bar.leading = ft.IconButton(
                ft.Icons.MENU,
                tooltip="Abrir menu de navegação",
                on_click=lambda _: setattr(page.drawer, "open", True)
            )
            app_bar.leading_width = 50

        # NavigationRail (modificado para usar as rotas de teste)
        temp_nav_rail_destinations = [
            ft.NavigationRailDestination(
                icon=mod["icon"], selected_icon=mod["selected_icon"], label=mod["label"]
            ) for mod in test_icones_navegacao # USA OS ÍCONES DE TESTE
        ]
        nav_rail = ft.NavigationRail(
            selected_index=current_nav_index, # Usa o índice calculado com rotas de teste
            label_type=ft.NavigationRailLabelType.ALL, min_width=100, min_extended_width=200,
            destinations=temp_nav_rail_destinations,
            on_change=lambda e: page.go(test_icones_navegacao[e.control.selected_index]["route"])
        )
        
        view_content = None
        if current_route == "/components_test":
            view_content = create_components_test_view(page)
        else:
            # Para outras rotas, usa o main_content_area padrão
            update_main_content_for_route(page, current_route)
            view_content = main_content_area # Usa a área de conteúdo global

        page.views.append(
            ft.View(
                route=current_route,
                controls=[
                    ft.Row(
                        [nav_rail, ft.VerticalDivider(width=1), view_content],
                        expand=True, vertical_alignment=ft.CrossAxisAlignment.START,
                    )
                ],
                appbar=app_bar,
                drawer=page.drawer,
                bottom_appbar=app_layout.create_footer(page)
            )
        )
        page.update()

    page.on_route_change = app_router
    initial_route = page.route if page.route and page.route != "/" else "/home"
    page.go(initial_route)


def run_test_desktop():
    print("Iniciando teste em modo Desktop...")
    ft.app(target=main_test_layout)

def run_test_web(port_number=8550):
    print(f"Iniciando teste em modo Web. Acesse http://localhost:{port_number}")
    # Para uploads no modo web, Flet precisa de um diretório 'assets' ou 'upload_dir' configurado
    # O 'upload_dir' do ManagedFilePicker é para onde o Flet Server move os arquivos.
    # Não é o 'assets_dir' do ft.app, mas sim onde seus arquivos estarão *após* o upload.
    ft.app(
        target=main_test_layout,
        view=ft.WEB_BROWSER,
        port=port_number,
        # assets_dir="assets" # Se você tiver assets estáticos
        # upload_dir=os.path.join(project_root_candidate, "temp_uploads") # O Flet Server usa isso internamente.
                                                                       # A configuração do ManagedFilePicker já cuida do destino.
    )

if __name__ == "__main__":
    print("Selecione o modo de execução do teste de layout e componentes:")
    print("  1. Modo Desktop")
    print("  2. Modo Web")
    choice = input("Digite sua escolha (1 ou 2): ")

    if choice == "1":
        run_test_desktop()
    elif choice == "2":
        run_test_web(port_number=8551)
    else:
        print("Escolha inválida. Encerrando.")
