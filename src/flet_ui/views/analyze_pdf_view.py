# src/flet_ui/views/analyze_pdf_view.py
import flet as ft
import os, threading
from typing import Optional, Dict, Any, List, Tuple

from src.flet_ui.components import (
    show_snackbar,
    show_loading_overlay,
    hide_loading_overlay,
    ManagedFilePicker 
)
from src.flet_ui import theme
from src.core.pdf_processor import PDFDocumentAnalyzer
from src.core.ai_orchestrator import analyze_text_with_llm

from src.settings import UPLOAD_TEMP_DIR

from src.logger.logger import LoggerSetup
_logger = LoggerSetup.get_logger(__name__)

KEY_SESSION_CURRENT_PDF_NAME = "current_pdf_name_for_analysis"
KEY_SESSION_CURRENT_PDF_FILES_ORDERED = "current_pdf_files_ordered_for_analysis"
KEY_SESSION_PDF_ANALYZER_DATA = "pdf_analyzer_processed_page_data"
KEY_SESSION_PDF_CLASSIFIED_INDICES = "pdf_classified_indices_data"
KEY_SESSION_PDF_AGGREGATED_TEXT_INFO = "pdf_aggregated_text_info" 
KEY_SESSION_PDF_LAST_LLM_RESPONSE = "pdf_last_llm_response"

# --- Bloco 1: Criação dos Elementos da UI ---
def _create_gui_elements() -> Dict[str, ft.Control]:
    """Cria e retorna um dicionário com os principais elementos da UI."""
    _logger.info("Criando elementos base da UI para Análise inicial de PDF.")
    controls = {
        "selected_files_list_view": ft.ListView(expand=False, spacing=5, height=150), # Altura inicial
        
        "current_batch_name_text": ft.Text("Nenhum arquivo PDF selecionado.", italic=True),
        "status_extraction_text": ft.Text("", italic=True, size=12),
        "status_text_analysis": ft.Text("", italic=True, size=12),
        "status_llm_text": ft.Text("", italic=True, size=12),
        "text_reordenar": ft.Text("Arquivos para Análise (arraste para reordenar):", style=ft.TextThemeStyle.LABEL_MEDIUM, visible=False),
        
        "result_textfield": ft.TextField(
            label="...", multiline=True, read_only=True, min_lines=10,
            max_lines=25, expand=True, border_color=theme.PRIMARY, text_size=14
        ),

        "upload_button": ft.ElevatedButton("Carregar PDF", icon=ft.Icons.UPLOAD_FILE),
        "analyze_button": ft.ElevatedButton(
            "Analisar PDF", icon=ft.Icons.TEXT_SNIPPET_OUTLINED,
            tooltip="Processa o PDF carregado e envia para análise pela LLM", disabled=True
        ),
        "copy_button": ft.IconButton(icon=ft.Icons.COPY_ALL_OUTLINED, tooltip="Copiar Resultado")
    }
    return controls

# --- Bloco 2: Lógica de Gerenciamento da Lista de Arquivos ---
class FileListManager:
    """Encapsula a lógica de exibição e manipulação da lista de arquivos."""
    def __init__(self, page: ft.Page, gui_controls: Dict[str, ft.Control], managed_file_picker_ref:List[ManagedFilePicker]):
        self.page = page
        self.selected_files_list_view = gui_controls["selected_files_list_view"]
        self.current_batch_name_text = gui_controls["current_batch_name_text"]
        self.analyze_button = gui_controls["analyze_button"]
        self.status_extraction_text = gui_controls["status_extraction_text"]
        self.status_text_analysis = gui_controls["status_text_analysis"]
        self.status_llm_text = gui_controls["status_llm_text"]
        self.text_reordenar = gui_controls["text_reordenar"]
        self.result_textfield = gui_controls["result_textfield"]
        self.managed_file_picker = managed_file_picker_ref[0] # Referência para chamar clear_upload_state

    def clear_cached_analysis_results(self):
        """Limpa caches relacionados aos resultados da análise combinada."""
        keys_to_clear = [
            KEY_SESSION_PDF_ANALYZER_DATA, KEY_SESSION_PDF_CLASSIFIED_INDICES,
            KEY_SESSION_PDF_AGGREGATED_TEXT_INFO, KEY_SESSION_PDF_LAST_LLM_RESPONSE
        ]
        if self.page.session.contains_key(KEY_SESSION_PDF_LAST_LLM_RESPONSE):
            self.status_extraction_text.value = "Lista de arquivos modificada. Reanálise necessária."
        else:
            self.status_extraction_text.value = ""
        
        for k in keys_to_clear:
            if self.page.session.contains_key(k): 
                self.page.session.remove(k)
        _logger.debug("Caches de resultados de análise (combinada) limpos.")
        
        
        self.status_text_analysis.value = ""
        self.status_llm_text.value = ""
        self.result_textfield.value = ""
        # CHECK: A atualização da página será feita pelo chamador ou em um ponto consolidado
        self.page.update(self.status_extraction_text, self.status_text_analysis, self.status_llm_text, self.result_textfield, self.text_reordenar)

    def update_selected_files_display(self, files_ordered: Optional[List[Dict[str, Any]]] = None):
        self.selected_files_list_view.controls.clear()
        _files = files_ordered or self.page.session.get(KEY_SESSION_CURRENT_PDF_FILES_ORDERED) or []

        if not isinstance(_files, list): 
            _files = []

        if not _files:
            self.current_batch_name_text.value = "Nenhum arquivo PDF selecionado."
            self.selected_files_list_view.height = 0 # Esconde se vazio
            self.analyze_button.disabled = True
            self.page.update(self.current_batch_name_text, self.selected_files_list_view, self.analyze_button)
            self.text_reordenar.visible = False
            self.clear_cached_analysis_results() # Limpa se a lista ficar vazia
            self.status_extraction_text.value = ""
            self.page.update(self.status_extraction_text)
        else:
            for idx, file_info in enumerate(_files):
                if not isinstance(file_info, dict):
                    error_tile = ft.ListTile(title=ft.Text(f"Erro: Item inválido na lista - {file_info}", color=theme.COLOR_ERROR))
                    self.selected_files_list_view.controls.append(error_tile)
                    continue

                on_will_accept, on_accept, on_leave = self._create_drag_handlers_for_item(idx)

                file_name_text = ft.Text(
                    value=file_info.get('name', 'Nome Indisponível'),
                    expand=True, # Permite que o texto do nome expanda e empurre os botões
                    overflow=ft.TextOverflow.ELLIPSIS, # Adiciona "..." se o nome for muito longo
                    #tooltip=file_info.get('name', 'Nome Indisponível') 
                )
                action_buttons = ft.Row([
                        ft.IconButton(ft.Icons.ARROW_UPWARD, 
                                      on_click=lambda _, i=idx: self.move_file_in_list(i, -1), 
                                      disabled=(idx==0), icon_size=18, padding=3),
                        ft.IconButton(ft.Icons.ARROW_DOWNWARD, 
                                      on_click=lambda _, i=idx: self.move_file_in_list(i, 1), 
                                      disabled=(idx==len(_files)-1), icon_size=18, padding=3),
                        ft.IconButton(ft.Icons.DELETE_OUTLINE, 
                                      on_click=lambda _, i=idx: self.remove_file_from_list(i), 
                                      icon_color=theme.COLOR_ERROR, icon_size=18, padding=3)
                    ], spacing=0, 
                    alignment=ft.MainAxisAlignment.END, 
                    width=100) # Necessário definir width aqui devido concorrência de espaço indevido com file_name_text no ListTile 

                list_tile = ft.ListTile(
                    title=file_name_text, # Usa o Text com expand=True
                    leading=ft.Icon(ft.Icons.PICTURE_AS_PDF),
                    trailing=action_buttons,
                    # dense=True, # Torna o ListTile um pouco mais compacto
                    # visual_density=ft.VisualDensity.COMPACT # Outra opção para compactar
                ) 
                item_container = ft.Container(
                    content=list_tile, # O ListTile é o conteúdo visual principal
                    # padding=ft.padding.symmetric(vertical=2),
                    # border=ft.border.all(1, ft.colors.OUTLINE_VARIANT), # Borda de depuração
                    # border_radius=5
                )
                draggable_item = ft.Draggable(
                    group="pdf_files",
                    content=item_container, # O container (com o ListTile dentro) é arrastável
                    data=str(idx)
                )
                drop_target_item = ft.DragTarget(
                    group="pdf_files",
                    content=draggable_item,
                    on_will_accept=on_will_accept,
                    on_accept=on_accept,         
                    on_leave=on_leave,
                    # on_move=None, # Removido ou pode ser usado para outros feedbacks visuais durante o arraste sobre o alvo
                )
                 
                _logger.info(f"VIEW_DEBUG: Criado file_name_text com value: '{file_name_text.value}' para idx {idx}")
                self.selected_files_list_view.controls.append(drop_target_item)

            if len(_files) == 1: 
                self.current_batch_name_text.value = f"Arquivo selecionado: {_files[0]['name']}"
                self.text_reordenar.visible = False
            else: 
                self.current_batch_name_text.value = f"Arquivos selecionados: {_files[0]['name']} e Outros {len(_files)-1}"
                self.text_reordenar.visible = True
            
            self.selected_files_list_view.height = min(len(_files) * 65, 300)
            self.analyze_button.disabled = False
        
        self.page.session.set(KEY_SESSION_CURRENT_PDF_NAME, self.current_batch_name_text.value)
        # A atualização da página (page.update) será feita de forma mais global
        # self.page.update(self.current_batch_name_text, self.selected_files_list_view, self.analyze_button)

    def _create_drag_handlers_for_item(self, target_item_idx: int) -> Tuple[callable, callable, callable]:
        def on_drag_will_accept(e: ft.ControlEvent):
            e.control.content.border = ft.border.all(2, ft.colors.PINK_ACCENT_200 if e.data == "true" else ft.colors.BLACK26)
            e.control.update()

        def on_drag_leave(e: ft.ControlEvent): 
            e.control.content.border = None
            e.control.update()
        
        def on_drag_accept_handler(e: ft.DragTargetEvent): 
            e.control.content.border = None
            dragged_ctrl = e.page.get_control(e.src_id)
            src_idx = None
            if dragged_ctrl and hasattr(dragged_ctrl, 'data'):
                try: 
                    src_idx = int(dragged_ctrl.data)
                except ValueError: 
                    _logger.error(f"ON_ACCEPT: Erro ao converter src_idx '{dragged_ctrl.data}'")
            else: 
                _logger.error(f"ON_ACCEPT: Dados do Draggable não encontrados (src_id: {e.src_id}).")

            if src_idx is None: 
                return # Simplesmente retorna se não puder processar

            dest_idx = target_item_idx
            current_files = list(self.page.session.get(KEY_SESSION_CURRENT_PDF_FILES_ORDERED) or [])
            
            if 0 <= src_idx < len(current_files) and 0 <= dest_idx < len(current_files) and src_idx != dest_idx:
                dragged_file = current_files.pop(src_idx)
                current_files.insert(dest_idx, dragged_file)
                self.page.session.set(KEY_SESSION_CURRENT_PDF_FILES_ORDERED, current_files)
                self.update_selected_files_display(current_files) # Re-renderiza com a nova ordem
                self.clear_cached_analysis_results()
            elif src_idx == dest_idx:
                _logger.debug("Item solto sobre si mesmo.")
                self.update_selected_files_display(current_files)
            else:
                _logger.warning(f"Índices inválidos on_accept: src={src_idx}, dest={dest_idx}, len={len(current_files)}")
                self.update_selected_files_display(current_files)

            # A atualização da UI mais ampla (page.update) deveria ser feita fora deste handler específico
            # para evitar múltiplas atualizações pequenas. O update_selected_files_display já agenda um redraw.
            self.page.update(self.current_batch_name_text, self.selected_files_list_view) # CHECK

        return on_drag_will_accept, on_drag_accept_handler, on_drag_leave

    def move_file_in_list(self, index: int, direction: int):
        current_files = list(self.page.session.get(KEY_SESSION_CURRENT_PDF_FILES_ORDERED) or [])
        
        # if not (0 <= index < len(current_files)): return
        new_index = index + direction
        if not (0 <= index < len(current_files) and 0 <= new_index < len(current_files)): 
            return
        
        current_files.insert(new_index, current_files.pop(index))
        self.page.session.set(KEY_SESSION_CURRENT_PDF_FILES_ORDERED, current_files)
        self.update_selected_files_display(current_files)
        self.clear_cached_analysis_results()
        self.page.update(self.current_batch_name_text, self.selected_files_list_view) # Atualiza a UI aqui

    def remove_file_from_list(self, index: int):
        current_files = list(self.page.session.get(KEY_SESSION_CURRENT_PDF_FILES_ORDERED) or [])
        
        if not (0 <= index < len(current_files)): return
        
        removed_file_info = current_files.pop(index)
        removed_file_name = removed_file_info['name'] 

        self.page.session.set(KEY_SESSION_CURRENT_PDF_FILES_ORDERED, current_files)
        
        if self.managed_file_picker: 
            self.managed_file_picker.clear_upload_state_for_file(removed_file_name)
        
        self.update_selected_files_display(current_files)
        self.clear_cached_analysis_results()
        self.page.update(self.current_batch_name_text, self.selected_files_list_view) # Atualiza a UI aqui

# --- Bloco 3: Lógica de Upload de Arquivos ---
def _setup_file_uploader(page: ft.Page, file_list_manager: FileListManager) -> ManagedFilePicker:
    """Configura e retorna o ManagedFilePicker."""
    
    def individual_file_upload_complete(success: bool, path_or_msg: str, file_name: Optional[str]):
        if success and file_name and path_or_msg:
            _logger.info(f"Upload individual de '{file_name}' OK. Path: {path_or_msg}")
            current_files = page.session.get(KEY_SESSION_CURRENT_PDF_FILES_ORDERED) or []
            if not isinstance(current_files, list): current_files = [] # Garantia
            
            if not any(f['name'] == file_name and f['path'] == path_or_msg for f in current_files):
                new_file_entry = {
                    "name": file_name, # file_name é string
                    "path": path_or_msg, # string
                    "original_index": len(current_files) # int
                }
                current_files.append(new_file_entry) 
                page.session.set(KEY_SESSION_CURRENT_PDF_FILES_ORDERED, current_files)
        elif path_or_msg == "Seleção cancelada": 
            _logger.info("Seleção de arquivos cancelada.")
        else: 
            _logger.error(f"Falha no upload de '{file_name}': {path_or_msg}")
            # Não mostra snackbar individual aqui.

    def batch_upload_complete(batch_results: List[Dict[str, Any]]):
        _logger.info(f"Upload_Batch Completo: Lote finalizado com {len(batch_results)} resultados.")
        hide_loading_overlay(page)
        
        successful_uploads = [r for r in batch_results if r['success']]
        failed_count = len(batch_results) - len(successful_uploads)

        final_message = ""
        final_color = theme.COLOR_INFO

        if successful_uploads and not failed_count:
            final_message = f"{len(successful_uploads)} arquivo(s) carregado(s) com sucesso!"
            final_color = theme.COLOR_SUCCESS
        elif successful_uploads and failed_count:
            final_message = f"{len(successful_uploads)} carregado(s), {failed_count} falha(s)."
            final_color = theme.COLOR_WARNING
        elif not successful_uploads and failed_count:
            final_message = f"Todos os {failed_count} uploads falharam."
            final_color = theme.COLOR_ERROR
        elif not batch_results: # Ex: seleção cancelada
             final_message = "Nenhum arquivo foi selecionado ou processado."
             final_color = theme.COLOR_WARNING
        
        if final_message:
            show_snackbar(page, final_message, color=final_color, duration=5000)
        
        file_list_manager.update_selected_files_display() # Atualiza a lista
        if successful_uploads: 
            # Invalida se o CONTEÚDO da lista de sucesso mudou o lote
            file_list_manager.clear_cached_analysis_results()
        
        page.update(file_list_manager.current_batch_name_text, 
                    file_list_manager.selected_files_list_view, 
                    file_list_manager.analyze_button) 

    file_picker_instance = page.data.get("global_file_picker") # Supondo que está em page.data
    if not file_picker_instance:
        _logger.error("FilePicker global não encontrado!")
        raise RuntimeError("FilePicker global não configurado. A funcionalidade de upload não pode ser inicializada.")

    managed_file_picker = ManagedFilePicker(
        page=page,
        file_picker_instance=file_picker_instance,
        on_individual_file_complete=individual_file_upload_complete,
        upload_dir=UPLOAD_TEMP_DIR,
        on_batch_complete=batch_upload_complete,
        allowed_extensions=["pdf"]
        # on_upload_progress=on_upload_progress_handler
    )
    return managed_file_picker

# --- Bloco 4: Lógica de Análise do PDF ---
class AnalysisController:
    def __init__(self, page: ft.Page, gui_controls: Dict[str, ft.Control]):
        self.page = page
        self.gui_controls = gui_controls # Contém status_texts, result_textfield, etc.
        self.pdf_analyzer = PDFDocumentAnalyzer() # Instancia o analisador

    def _update_status(self, control_key: str, text: str, style_args: Optional[Dict] = None):
        control = self.gui_controls.get(control_key)
        if control:
            control.value = text
            if style_args:
                if "format" in style_args: # Adaptado da sua função update_text_status
                    if style_args["format"] == 'normal':
                        control.text_style = ft.TextStyle(weight=ft.FontWeight.NORMAL, color=None)
                        control.border_color = theme.PRIMARY 
                    elif style_args["format"] == 'error':
                        control.text_style = ft.TextStyle(weight=ft.FontWeight.BOLD, color=theme.COLOR_ERROR)
                        control.border_color = theme.COLOR_ERROR
            self.page.update(control) # page.run_thread cuidará disso # Check

    def _analysis_thread_func(self, pdf_paths_ordered: List[str], batch_display_name: str):
        try:
            cache_key_segment = "_".join(os.path.basename(p) for p in pdf_paths_ordered)
        
            # FASE 1A: Cache para processed_page_data
            CACHE_KEY_ANALYZER_DATA_BATCH = f"{KEY_SESSION_PDF_ANALYZER_DATA}_{cache_key_segment}"
            processed_page_data_combined = self.page.session.get(CACHE_KEY_ANALYZER_DATA_BATCH)
        
            if processed_page_data_combined:
                _logger.info(f"Dados processados do lote '{batch_display_name}' encontrados no cache.")
                self.page.run_thread(self._update_status, "status_extraction_text", f"Fase 1: Extração carregada do cache.")
                self.page.run_thread(self._update_status, "status_text_analysis", f"Fase 2: {len(processed_page_data_combined)} páginas processadas.")
            else:
                # FASE 1: Extração e Pré-processamento
                self.page.run_thread(self._update_status, "status_extraction_text", f"Fase 1: Extraindo de '{batch_display_name}'...")
                valid_pdf_paths = [p for p in pdf_paths_ordered if os.path.exists(p)]
                if not valid_pdf_paths: 
                    raise FileNotFoundError("Nenhum arquivo PDF válido encontrado.")

                processed_files_metadata, all_indices, all_storage, all_analysis_texts = \
                    self.pdf_analyzer.extract_texts_and_preprocess_files(valid_pdf_paths)

                if not processed_files_metadata: 
                    raise ValueError("Nenhum texto extraível encontrado.")
                
                processed_page_data_combined, all_global_page_keys_ordered = \
                    self.pdf_analyzer._build_combined_page_data(processed_files_metadata, all_indices, all_storage)

                if not processed_page_data_combined: 
                    raise ValueError("Falha ao construir dados combinados.")

                self.page.run_thread(self._update_status, "status_extraction_text", f"Fase 1 OK: Textos extraídos.")
                self.page.run_thread(self._update_status, "status_text_analysis", "Fase 2: Analisando similaridade...")

                # FASE 2: Similaridade e Relevância
                processed_page_data_combined = self.pdf_analyzer.analyze_similarity_and_relevance_files(
                    processed_page_data_combined, all_global_page_keys_ordered, all_analysis_texts)
                
                self.page.run_thread(self._update_status, "status_text_analysis", f"Fase 2 OK: {len(processed_page_data_combined)} páginas processadas.")
                self.page.session.set(CACHE_KEY_ANALYZER_DATA_BATCH, processed_page_data_combined)
                self.page.session.set(KEY_SESSION_PDF_ANALYZER_DATA, processed_page_data_combined) # Também chave genérica

            # FASE 3: Classificação (com cache)
            CACHE_KEY_CLASSIFIED_BATCH = f"{KEY_SESSION_PDF_CLASSIFIED_INDICES}_{cache_key_segment}"
            classified_data_batch = self.page.session.get(CACHE_KEY_CLASSIFIED_BATCH)

            if classified_data_batch:
                _logger.info(f"Dados de classificação do(s) PDF(s) '{batch_display_name}' encontrados na sessão (cache). Pulando classificação.")
                relevant_indices, unintelligible_indices, count_selected, \
                count_discarded_similarity, count_discarded_unintelligible = classified_data_batch
                
                info_classificacao = (
                    f"\nPáginas Relevantes: {count_selected}, "
                    f"\nIrrelevantes por similaridade: {count_discarded_similarity},"
                    f"\nDescartadas (Ininteligíveis): {count_discarded_unintelligible}. "
                )
                self.page.run_thread(self._update_status, "status_llm_text", f"Classificação carregada do cache: {info_classificacao}. \nAgregando texto...")
            
            else:
                classified_data_batch  = self.pdf_analyzer.filter_and_classify_pages(processed_page_data_combined)
                
                relevant_indices, unintelligible_indices, count_selected, \
                count_discarded_similarity, count_discarded_unintelligible = classified_data_batch
                
                self.page.session.set(CACHE_KEY_CLASSIFIED_BATCH, classified_data_batch)
                self.page.session.set(KEY_SESSION_PDF_CLASSIFIED_INDICES, classified_data_batch)

                # (Opcional) Mostrar contagens na UI
                info_classificacao = (
                    f"\nPáginas Relevantes: {count_selected}, "
                    f"\nIrrelevantes por similaridade: {count_discarded_similarity},"
                    f"\nDescartadas (Ininteligíveis): {count_discarded_unintelligible}. "
                )
                self.page.run_thread(self._update_status, "status_llm_text", f"Classificação: {info_classificacao}. \nAgregando texto...")

            if not relevant_indices: 
                raise ValueError("Nenhuma página relevante encontrada.")

            # FASE 4A: Agregação de Texto (com cache)
            CACHE_KEY_AGGREGATED_TEXT_INFO_BATCH = f"{KEY_SESSION_PDF_AGGREGATED_TEXT_INFO}_{cache_key_segment}"
            aggregated_info = self.page.session.get(CACHE_KEY_AGGREGATED_TEXT_INFO_BATCH)

            if aggregated_info:
                _logger.info(f"Texto agregado do(s) PDF(s) '{batch_display_name}' encontrado na sessão (cache). Pulando agregação.")
                str_pages_considered, aggregated_text, tokens_antes, tokens_depois = aggregated_info
            else:
                token_limit_for_aggregation = 180000 
                # TODO: O token_limit pode vir de configurações do usuário/LLM no futuro

                str_pages_considered, aggregated_text, tokens_antes, tokens_depois = \
                    self.pdf_analyzer.group_texts_by_relevance_and_token_limit(
                        processed_page_data=processed_page_data_combined,
                        relevant_page_indices=relevant_indices, # Esta é List[str] agora
                        token_limit=token_limit_for_aggregation
                    )
                _logger.info(f"Texto agregado. Páginas: {str_pages_considered}. Tokens Antes: {tokens_antes}, Depois: {tokens_depois}")
                
                self.page.session.set(CACHE_KEY_AGGREGATED_TEXT_INFO_BATCH, (str_pages_considered, aggregated_text, tokens_antes, tokens_depois))
                self.page.session.set(KEY_SESSION_PDF_AGGREGATED_TEXT_INFO, (str_pages_considered, aggregated_text, tokens_antes, tokens_depois))
                
            self.page.run_thread(self._update_status, "status_llm_text", f"Classificação: {info_classificacao}, \n\nTexto final agregado das págs {str_pages_considered}.\n Consultando LLM...")
            
            # FASE 4B: Chamada LLM
            hide_loading_overlay(self.page) # Esconde overlay de processamento PDF
            show_loading_overlay(self.page, f"Interagindo com LLM para PDF(s) '{batch_display_name}'...")
            
            llm_response = analyze_text_with_llm(self.page, aggregated_text, 
                                                 "openai", "gpt-4.1-nano") # TODO: Obter das configurações selecionadas pelo usuário!

            CACHE_KEY_PDF_LAST_LLM_RESPONSE = f"{KEY_SESSION_PDF_LAST_LLM_RESPONSE}_{cache_key_segment}"
            hide_loading_overlay(self.page)

            if llm_response:
                self.page.session.set(CACHE_KEY_PDF_LAST_LLM_RESPONSE, llm_response)
                self.page.session.set(KEY_SESSION_PDF_LAST_LLM_RESPONSE, llm_response)
                self.page.run_thread(self._update_status, "result_textfield", llm_response, {"format": "normal"})
                self.page.run_thread(self._update_status, "status_llm_text", 
                                     f"Classificação: {info_classificacao}. \n\nTexto final agregado das págs {str_pages_considered}. \n\nAnálise de '{batch_display_name}' concluída pela LLM.")
                self.page.run_thread(show_snackbar, self.page, "Análise LLM concluída!", theme.COLOR_SUCCESS)
            else:
                self.page.run_thread(self._update_status, "result_textfield", "Falha ao obter resposta da LLM.", {"format": "error"})
                self.page.run_thread(self._update_status, "status_llm_text", "Erro na LLM.")
                self.page.run_thread(show_snackbar, self.page, "Erro na LLM.", theme.COLOR_ERROR)
                # Se a resposta da LLM for None (erro), remove qualquer resposta antiga da sessão
                if self.page.session.contains_key(CACHE_KEY_PDF_LAST_LLM_RESPONSE):
                    self.page.session.remove(CACHE_KEY_PDF_LAST_LLM_RESPONSE)

        except Exception as ex_thread:
            _logger.error(f"Erro na thread de análise '{batch_display_name}': {ex_thread}", exc_info=True)
            hide_loading_overlay(self.page)
            error_message_thread = f"Erro no processamento: {ex_thread}"
            self.page.run_thread(self._update_status, "result_textfield", error_message_thread, {"format": "error"})
            
             # Tenta atualizar os status da UI para refletir onde parou, se possível
            self.page.run_thread(self._update_status, "status_extraction_text", "")
            self.page.run_thread(self._update_status, "status_text_analysis", f"Falha geral: {ex_thread}")
            self.page.run_thread(self._update_status, "status_llm_text", "")
            self.page.run_thread(show_snackbar, self.page, f"Erro: {ex_thread}", theme.COLOR_ERROR, 7000)
            
        finally:
            for pdf_path in pdf_paths_ordered:
                if pdf_path and UPLOAD_TEMP_DIR in pdf_path and os.path.exists(pdf_path):
                    try: 
                        os.remove(pdf_path)
                    except Exception as e_rem: 
                        _logger.warning(f"Falha ao remover temp '{pdf_path}': {e_rem}")

    def start_analysis(self):
        ordered_files = self.page.session.get(KEY_SESSION_CURRENT_PDF_FILES_ORDERED)
        if not ordered_files:
            show_snackbar(self.page, "Nenhum PDF carregado.", color=theme.COLOR_WARNING)
            return

        pdf_paths = [f['path'] for f in ordered_files]
        batch_name = self.gui_controls["current_batch_name_text"].value
        batch_name = batch_name.replace('Arquivo selecionado: ', '').replace('Arquivos selecionados: ', '').replace('.pdf', '')

        _logger.info(f"Iniciando processamento do lote: {batch_name}")
        show_loading_overlay(self.page, f"A processar Leitura, Extração e Classificação do conteúdo \nPDF(s) '{batch_name}'...")
        
        # Limpa UI
        self.gui_controls["result_textfield"].value = "Análise em progresso..."
        self.gui_controls["status_extraction_text"].value = f"Fase 1: Extraindo e pré-processando textos do(s) PDF(s) '{batch_name}'..."
        self.gui_controls["status_text_analysis"].value = ""
        self.gui_controls["status_llm_text"].value = ""

        self.page.update(self.gui_controls["result_textfield"], 
                         self.gui_controls["status_extraction_text"], 
                         self.gui_controls["status_text_analysis"], 
                         self.gui_controls["status_llm_text"]) # Update inicial da UI

        thread = threading.Thread(target=self._analysis_thread_func, args=(pdf_paths, batch_name), daemon=True)
        thread.start()

# --- Bloco 5: Construção do Layout e Restauração de Estado ---
def _build_view_layout(gui_controls: Dict[str, ft.Control]) -> ft.Column:
    """Constrói e retorna o layout da coluna principal da view."""
    return ft.Column(
        [
            ft.Text("Análise inicial de Notícias-Crime e Outros", style=ft.TextThemeStyle.HEADLINE_MEDIUM), 
            ft.Text("Faça upload de PDFs para extração, análise e consulta à IA."), 
            ft.Divider(),

            ft.Row([gui_controls["upload_button"], gui_controls["analyze_button"]], 
                   alignment=ft.MainAxisAlignment.START, spacing=10),

            gui_controls["current_batch_name_text"],
            gui_controls["text_reordenar"],
            ft.Container(gui_controls["selected_files_list_view"], expand=True), # ListView precisa estar em Container com expand

            gui_controls["status_extraction_text"],
            gui_controls["status_text_analysis"],
            gui_controls["status_llm_text"],
            ft.Divider(height=20),
            
            ft.Row([ft.Text("Resultado da Análise:", style=ft.TextThemeStyle.TITLE_MEDIUM), gui_controls["copy_button"]],
                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            
            ft.Container(gui_controls["result_textfield"], border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
                         border_radius=5, padding=5, expand=True)
        ],
        spacing=15, expand=True,
        #scroll=ft.ScrollMode.ADAPTIVE # Adicionar scroll se necessário
    )

def _restore_gui_state(page: ft.Page, gui_controls: Dict[str, ft.Control], file_list_manager: FileListManager):
    """Restaura o estado da UI a partir da sessão da página."""
    # Recarregar o estado da UI se um PDF já estiver na sessão
    # (Ex: usuário navegou para outra aba e voltou)
    pdf_name_session = page.session.get(KEY_SESSION_CURRENT_PDF_NAME)
    
    processed_page_data = page.session.get(KEY_SESSION_PDF_ANALYZER_DATA)
    classified_data = page.session.get(KEY_SESSION_PDF_CLASSIFIED_INDICES)
    aggregated_info = page.session.get(KEY_SESSION_PDF_AGGREGATED_TEXT_INFO)
    last_llm_response_on_session = page.session.get(KEY_SESSION_PDF_LAST_LLM_RESPONSE)

    if pdf_name_session:
        gui_controls["current_batch_name_text"].value = pdf_name_session

        if processed_page_data:    
            gui_controls["status_extraction_text"].value = f"Fase 1 e 2 (Extração/Análise PDF) carregadas do cache."
            gui_controls["status_text_analysis"].value = f"{len(processed_page_data)} páginas processadas."
        
        if classified_data and aggregated_info:
            _, _, count_selected, count_discarded_similarity, count_discarded_unintelligible = classified_data
            
            info_classificacao = (
                f"\nPáginas Relevantes: {count_selected}, "
                f"\nIrrelevantes por similaridade: {count_discarded_similarity},"
                f"\nDescartadas (Ininteligíveis): {count_discarded_unintelligible}. "
            )
            str_pages_considered, _, _, _ = aggregated_info

            gui_controls["status_llm_text"].value = f"Classificação: {info_classificacao}. \n\nTexto final agregado das págs {str_pages_considered}."
        
        if last_llm_response_on_session:
            batch_display_name_str = pdf_name_session.replace('Arquivo selecionado: ', '').replace('Arquivos selecionados: ', '').replace('.pdf', '')
            gui_controls["status_llm_text"].value = f"Classificação: {info_classificacao}. \n\nTexto final agregado das págs {str_pages_considered}. \n\nAnálise de '{batch_display_name_str}' concluída pela LLM."
            gui_controls["result_textfield"].value = last_llm_response_on_session
            _logger.info(f"Última resposta da LLM para '{pdf_name_session}' carregada da sessão.")

        else:
            gui_controls["status_llm_text"].value += "\n\nClique em 'Analisar PDF' para processar."

        gui_controls["analyze_button"].disabled = False
    else:
        gui_controls["current_batch_name_text"].value = "Nenhum arquivo PDF selecionado."
        gui_controls["analyze_button"].disabled = True
    
    file_list_manager.update_selected_files_display() # Fundamental para recarregar a lista de arquivos
    # page.update() será chamado no final de create_analyze_pdf_content


# --- Função Principal da View ---
def create_analyze_pdf_content(page: ft.Page) -> ft.Control:
    _logger.info("View Análise de PDF: Iniciando criação.")

    gui_controls = _create_gui_elements()
    
    # Instanciar FileListManager primeiro, pois ManagedFilePicker pode precisar dele (ou de um callback dele)
    # O ManagedFilePicker precisa de uma referência ao FileListManager para o clear_upload_state_for_file
    # Isto é um pouco circular. Talvez o clear_upload_state possa ser um callback passado ao FileListManager
    # Ou o ManagedFilePicker pode ser passado para o FileListManager após a criação.
    # Por ora, vamos passar a instância do ManagedFilePicker para o FileListManager.
    # Esta parte pode precisar de ajuste dependendo da implementação exata de ManagedFilePicker.
    
    # Placeholder para managed_file_picker, será criado depois
    managed_file_picker_instance = [None] # Usar lista para passar por referência mutável

    file_list_manager = FileListManager(page, gui_controls, managed_file_picker_instance)

    managed_file_picker = _setup_file_uploader(page, file_list_manager)
    managed_file_picker_instance[0] = managed_file_picker # Agora a referência está correta

    analysis_controller = AnalysisController(page, gui_controls)

    def handle_upload_button_click_with_overlay(e: ft.ControlEvent):
        _logger.info("Botão 'Carregar PDF' clicado, mostrando overlay.")
        show_loading_overlay(page, "A carregar arquivo(s)...") 
        # O pick_files é assíncrono. O overlay será escondido no callback batch_upload_complete do ManagedFilePicker.
        managed_file_picker.pick_files(
            allow_multiple=True,
            dialog_title_override="Selecione PDF(s) para análise"
        )

    # Configurar Handlers de Eventos
    gui_controls["upload_button"].on_click = handle_upload_button_click_with_overlay  
    gui_controls["analyze_button"].on_click = lambda e: analysis_controller.start_analysis()
    gui_controls["copy_button"].on_click = lambda e: page.set_clipboard(gui_controls["result_textfield"].value) # Simplificado

    view_layout = _build_view_layout(gui_controls)
    _restore_gui_state(page, gui_controls, file_list_manager)
    
    # Uma atualização final para garantir que todos os estados restaurados e iniciais sejam refletidos
    # page.update(*gui_controls.values()) # Atualiza todos os controles de uma vez

    _logger.info("View Análise de PDF: Criação concluída.")
    return view_layout


### Mover creator abaixo para novo módulo:....................................................

def create_chat_pdf_content(page: ft.Page) -> ft.Control:
    _logger.info("Criando conteúdo da view Chat com PDF.")

    current_pdf_name = page.session.get(KEY_SESSION_CURRENT_PDF_NAME)
    processed_text_for_chat = None

    show_snackbar(
        page,
        "Chat com PDFs: Seção ainda não programada.",
        color=theme.COLOR_WARNING, # Ou uma cor neutra/informativa
        duration=5000
    )

    main_content = ft.Column(
        [
            ft.Icon(ft.Icons.CONSTRUCTION, size=80, opacity=0.3),
            ft.Text(
                "Chat com PDFs",
                style=ft.TextThemeStyle.HEADLINE_MEDIUM,
                text_align=ft.TextAlign.CENTER,
                opacity=0.7
            ),
            ft.Text(
                "Esta funcionalidade estará disponível na próxima versão.",
                style=ft.TextThemeStyle.BODY_LARGE,
                text_align=ft.TextAlign.CENTER,
                opacity=0.7
            ),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True,
        spacing=20
    )

    #aggregated_info = page.session.get(KEY_SESSION_PDF_AGGREGATED_TEXT_INFO)
    
    #if aggregated_info:
    #    # A ordem na tupla é (str_pages_considered, aggregated_text, tokens_antes, tokens_depois)
    #    processed_text_for_chat = aggregated_info[1] 

    #if not current_pdf_name or not processed_text_for_chat:
    #    info_text = ft.Text(
    #        "Nenhum PDF carregado para o chat. Por favor, vá para a seção 'Análise PDF', "
    #        "carregue e analise um documento primeiro.",
    #        style=ft.TextThemeStyle.TITLE_MEDIUM,
    #        text_align=ft.TextAlign.CENTER
    #    )
    #    go_to_analyze_button = ft.ElevatedButton(
    #        "Ir para Análise PDF",
    #        icon=ft.Icons.FIND_IN_PAGE,
    #        on_click=lambda _: page.go("/analyze_pdf")
    #    )
    #    return ft.Column(
    #        [info_text, ft.Container(height=20), go_to_analyze_button],
    #        alignment=ft.MainAxisAlignment.CENTER,
    #        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    #        expand=True,
    #        spacing=20
    #    )

    # --- Conteúdo da view Chat com PDF (se PDF estiver carregado) ---
    if current_pdf_name and processed_text_for_chat:
        title = ft.Row([ft.Text(f"Chat com: {current_pdf_name}", style=ft.TextThemeStyle.HEADLINE_SMALL)], alignment=ft.MainAxisAlignment.START)
        
        # Placeholder para a interface de chat (será implementada na Fase 2 - Objetivo 2.5)
        chat_placeholder = ft.Column(
            [
                ft.Icon(ft.Icons.CHAT_BUBBLE_OUTLINE, size=80, opacity=0.3),
                ft.Text(
                    "Funcionalidade de Chat com PDF",
                    style=ft.TextThemeStyle.HEADLINE_MEDIUM,
                    text_align=ft.TextAlign.CENTER,
                    opacity=0.7
                ),
                ft.Text(
                    "Esta seção será implementada na Fase 2 (RAG e Interação com PDF).",
                    style=ft.TextThemeStyle.BODY_LARGE,
                    text_align=ft.TextAlign.CENTER,
                    opacity=0.7
                ),
                ft.Text(
                    f"O texto processado do PDF '{current_pdf_name}' estará disponível para esta funcionalidade.",
                    italic=True,
                    opacity=0.5,
                    text_align=ft.TextAlign.CENTER
                ),
                ft.ProgressRing(width=30, height=30, opacity=0.5) # Simula trabalho futuro
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True,
            spacing=20
        )

        return ft.Column(
            [
                title,
                ft.Divider(),
                chat_placeholder
            ],
            alignment=ft.MainAxisAlignment.START,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True, #spacing=15,
        )
    
    return main_content

