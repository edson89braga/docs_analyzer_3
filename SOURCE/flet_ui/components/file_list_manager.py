# src\flet_ui\components\file_list_manager.py

import logging
from typing import List, Dict, Any, Optional, Callable, Tuple
import flet as ft

from SOURCE.flet_ui import theme
from SOURCE.flet_ui.components.components import ManagedFilePicker, safe_control_update

logger = logging.getLogger(__name__)

class FileListManager(ft.Column):
    """
    Componente de GUI reutilizável que gerencia uma lista de arquivos.

    Encapsula a exibição, reordenação e remoção de arquivos,
    comunicando-se com a view pai através de um callback.
    """

    def __init__(
        self,
        page: ft.Page,
        session_key_files_ordered: str,
        managed_file_picker: ManagedFilePicker,
        on_list_changed: Callable[[], None]
    ):
        super().__init__(spacing=5, visible=False, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        self.page = page
        self.session_key_files_ordered = session_key_files_ordered
        self.managed_file_picker = managed_file_picker
        self.on_list_changed = on_list_changed

        self.title_text = ft.Text("Nenhum arquivo carregado.", weight=ft.FontWeight.BOLD)
        self.file_list_view = ft.ListView(expand=False, spacing=3)
        self.metadata_content = ft.Column(spacing=5, visible=False)

        header_container = ft.Container(
            content=ft.Container(self.title_text, padding=ft.padding.only(left=20)),
            expand=True, alignment=ft.alignment.center_left
        )
        content_container = ft.Container(
            content=ft.Column(
                [self.file_list_view, self.metadata_content],
                spacing=10
            ),
            expand=True
        )

        expansion_panel = ft.ExpansionPanel(
            header=header_container,
            content=content_container,
            can_tap_header=True,
            expanded=False,
            bgcolor = ft.Colors.ON_INVERSE_SURFACE
        )

        self.panel_list = ft.ExpansionPanelList(
            controls=[expansion_panel],
            expand_icon_color=theme.PRIMARY,
            divider_color=ft.Colors.TRANSPARENT, 
            elevation=1,
            expanded_header_padding=ft.padding.all(1),
        )
        self.controls.append(self.panel_list)

    def update_display(self, files_ordered: Optional[List[Dict[str, Any]]] = None):
        """Atualiza a exibição da lista de arquivos na UI."""
        self.file_list_view.controls.clear()
        if files_ordered is not None:
            _files = files_ordered
        elif self.page:
            _files = self.page.session.get(self.session_key_files_ordered) or []
        else:
            # Componente já desmontado (Flet anula 'page'): não há sessão para consultar.
            _files = []

        if not _files:
            self.title_text.value = "Nenhum arquivo carregado."
            self.visible = False
            # Limpa metadados se a lista de arquivos estiver vazia
            self.update_metadata_display(None)            
        else:
            self.visible = True
            # self.panel_list.controls[0].expanded = True
            for idx, file_info in enumerate(_files):
                file_name_display = ft.Text(
                    value=file_info.get('name', 'Nome Indisponível'),
                    overflow=ft.TextOverflow.ELLIPSIS,
                    width=700,
                )
                action_buttons = ft.Row([
                    ft.IconButton(ft.Icons.ARROW_UPWARD_ROUNDED, on_click=lambda _, i=idx: self._move_file_in_list(i, -1), disabled=(idx == 0), icon_size=18, padding=3, tooltip="Mover para Cima"),
                    ft.IconButton(ft.Icons.ARROW_DOWNWARD_ROUNDED, on_click=lambda _, i=idx: self._move_file_in_list(i, 1), disabled=(idx == len(_files) - 1), icon_size=18, padding=3, tooltip="Mover para Baixo"),
                    ft.IconButton(ft.Icons.DELETE_OUTLINE_ROUNDED, on_click=lambda _, i=idx: self._remove_file_from_list(i), icon_color=theme.COLOR_ERROR, icon_size=18, padding=3, tooltip="Remover Arquivo")
                ], spacing=0, alignment=ft.MainAxisAlignment.START, width=110)

                list_tile = ft.ListTile(
                    title=file_name_display,
                    leading=ft.Icon(ft.Icons.PICTURE_AS_PDF_ROUNDED),
                    trailing=action_buttons,
                )
                self.file_list_view.controls.append(list_tile)

            if len(_files) == 1:
                self.title_text.value = f"Arquivo selecionado: {_files[0]['name']}"
            else:
                self.title_text.value = f"Arquivos selecionados: {_files[0]['name']} e Outros {len(_files)-1}"

        safe_control_update(self)

    def _move_file_in_list(self, index: int, direction: int):
        """Move um arquivo na lista e aciona o callback de alteração."""
        current_files = list(self.page.session.get(self.session_key_files_ordered) or [])
        new_index = index + direction
        if not (0 <= index < len(current_files) and 0 <= new_index < len(current_files)):
            return

        current_files.insert(new_index, current_files.pop(index))
        self.page.session.set(self.session_key_files_ordered, current_files)
        
        if self.on_list_changed:
            self.on_list_changed()

    def _remove_file_from_list(self, index: int):
        """Remove um arquivo da lista e aciona o callback de alteração."""
        current_files = list(self.page.session.get(self.session_key_files_ordered) or [])
        if not (0 <= index < len(current_files)):
            return

        removed_file_info = current_files.pop(index)
        self.page.session.set(self.session_key_files_ordered, current_files)

        self.managed_file_picker.clear_upload_state_for_file(removed_file_info['name'])

        if self.on_list_changed:
            self.on_list_changed()

    def update_metadata_display(self, metadata_control: Optional[ft.Control]):
        """Atualiza a seção de metadados dentro do painel."""
        self.metadata_content.controls.clear()
        if metadata_control:
            self.metadata_content.controls.append(ft.Divider(height=1))
            self.metadata_content.controls.append(metadata_control)
            self.metadata_content.visible = True
        else:
            self.metadata_content.visible = False

        safe_control_update(self.metadata_content)

    def collapse_container(self):
        if self.panel_list.controls:
            self.panel_list.controls[0].expanded = False
        safe_control_update(self.panel_list)

    def expand_container(self):
        if self.panel_list.controls:
            self.panel_list.controls[0].expanded = True
        safe_control_update(self.panel_list)

    def disable_interactions(self):
        if self.file_list_view.page and self.file_list_view.uid:
            for tile in self.file_list_view.controls:
                # tile.leading.disabled = True
                for btn in tile.trailing.controls:
                    btn.disabled = True
            safe_control_update(self.file_list_view)

    def enable_interactions(self):
        if self.file_list_view.page and self.file_list_view.uid:
            for tile in self.file_list_view.controls:
                # tile.leading.disabled = False
                for btn in tile.trailing.controls:
                    btn.disabled = False
            safe_control_update(self.file_list_view)
