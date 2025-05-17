# src/flet_ui/views/analyze_pdf_view.py
import flet as ft
import os, threading
from typing import Optional, Dict, Any, List

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

def create_analyze_pdf_content(page: ft.Page) -> ft.Control:
    _logger.info("Criando conteúdo da view de Análise de PDF.")

    # ListView para exibir e ordenar arquivos selecionados
    selected_files_list_view = ft.ListView(expand=False, spacing=5, height=150) # Altura inicial
    
    current_batch_name_text = ft.Text("Nenhum arquivo PDF selecionado.", italic=True)

    status_extraction_text = ft.Text("", italic=True, size=12)
    status_text_analysis = ft.Text("", italic=True, size=12)
    status_llm_text = ft.Text("", italic=True, size=12)

    result_textfield = ft.TextField(
        label="...",
        multiline=True,
        read_only=True,
        min_lines=10,
        max_lines=25,
        expand=True,
        # value="Aguardando análise...", # Placeholder
        border_color=theme.PRIMARY,
        text_size=14
    )

    # --- Controles da UI ---
    upload_button = ft.ElevatedButton(
        "Carregar PDF",
        icon=ft.Icons.UPLOAD_FILE,
    )
    analyze_button = ft.ElevatedButton(
        "Analisar PDF",
        icon=ft.Icons.TEXT_SNIPPET_OUTLINED,
        tooltip="Processa o PDF carregado e envia para análise pela LLM",
        disabled=True
    )
    copy_button = ft.IconButton(
        icon=ft.Icons.COPY_ALL_OUTLINED,
        tooltip="Copiar Resultado",
    )

    def update_selected_files_display(files_ordered: Optional[List[Dict[str, Any]]] = None):
        """Atualiza a ListView de arquivos selecionados e o nome do lote."""
        selected_files_list_view.controls.clear()
        
        _files_from_arg = files_ordered
        _files_from_session = page.session.get(KEY_SESSION_CURRENT_PDF_FILES_ORDERED)
        
        _logger.debug(f"VIEW_DEBUG: Em update_selected_files_display - files_ordered (arg): {_files_from_arg} (tipo: {type(_files_from_arg)})")
        _logger.debug(f"VIEW_DEBUG: Em update_selected_files_display - _files_from_session: {_files_from_session} (tipo: {type(_files_from_session)})")

        _files = _files_from_arg or _files_from_session or []
        
        _logger.debug(f"VIEW_DEBUG: Em update_selected_files_display - _files FINAL (tipo: {type(_files)}): {_files}")

        if not isinstance(_files, list):
            _logger.error(f"VIEW_DEBUG: _files em update_selected_files_display NÃO é uma lista! Tipo: {type(_files)}. Conteúdo: {_files}. Resetando para lista vazia para UI.")
            _files = [] # Evita erro na iteração

        if not _files:
            current_batch_name_text.value = "Nenhum arquivo PDF selecionado."
            selected_files_list_view.height = 0 # Esconde se vazio
            analyze_button.disabled = True
            clear_cached_analysis_results()
        else:
            for idx, file_info in enumerate(_files):
                _logger.debug(f"VIEW_DEBUG: Iterando em update_selected_files_display - idx: {idx}, file_info_item: {file_info} (tipo: {type(file_info)})")

                if not isinstance(file_info, dict):
                    _logger.error(f"VIEW_DEBUG: file_info_item NÃO é um dicionário! É {type(file_info)}. Conteúdo: {file_info}")
                    # Adiciona um placeholder de erro na UI para este item
                    error_tile = ft.ListTile(title=ft.Text(f"Erro: Item inválido na lista - {file_info}", color=theme.COLOR_ERROR))
                    selected_files_list_view.controls.append(error_tile)
                    continue # Pula para o próximo item

                # --- Lógica de Drag and Drop (on_drop corrigido para usar e_drag.page.get_control) ---
                def create_drag_handler(target_item_idx):
                    def on_drag_will_accept(e: ft.ControlEvent):
                        _logger.debug(f"ON_DRAG_WILL_ACCEPT: e.control={e.control}, e.data='{e.data}'")
                                                
                        if e.data == "true": # O Flet está indicando que este alvo pode aceitar
                            e.control.content.border = ft.border.all(2, ft.colors.PINK_ACCENT_200)
                        else:
                            e.control.content.border = ft.border.all(2, ft.colors.BLACK26) # Exemplo de borda "não aceita"
                        e.control.update()

                    def on_drag_leave(e: ft.ControlEvent): 
                        _logger.debug(f"ON_DRAG_LEAVE: e.control={e.control}")
                        e.control.content.border = None
                        e.control.update()
                    
                    # Handler para quando um Draggable é SOLTO sobre o DragTarget
                    # Este é o ft.DragTarget.on_accept
                    def on_drag_accept_handler(e: ft.DragTargetEvent): 
                        _logger.debug(f"ON_ACCEPT (on_drop): e.control={e.control}, e.src_id='{e.src_id}'")
                        e.control.content.border = None # Limpa a borda do DragTarget

                        dragged_draggable_control = e.page.get_control(e.src_id)
                        
                        if dragged_draggable_control and hasattr(dragged_draggable_control, 'data'):
                            src_idx_str = dragged_draggable_control.data
                            try:
                                src_idx = int(src_idx_str)
                            except ValueError:
                                _logger.error(f"ON_ACCEPT: Não foi possível converter src_idx_str '{src_idx_str}' para int.")
                                # Não chamar e.control.update() aqui
                                return # Simplesmente retorna se não puder processar
                        else:
                            _logger.error(f"ON_ACCEPT: Não foi possível obter dados do Draggable (src_id: {e.src_id}).")
                            #e.control.update()
                            return

                        dest_idx = target_item_idx
                        _logger.debug(f"Item do índice {src_idx} solto sobre o item de índice {dest_idx}")

                        current_files_data = page.session.get(KEY_SESSION_CURRENT_PDF_FILES_ORDERED)
                        current_files = list(current_files_data) if current_files_data else []
                        
                        if 0 <= src_idx < len(current_files) and 0 <= dest_idx < len(current_files) and src_idx != dest_idx:
                            dragged_file_info = current_files.pop(src_idx)
                            current_files.insert(dest_idx, dragged_file_info)
                            page.session.set(KEY_SESSION_CURRENT_PDF_FILES_ORDERED, current_files)
                            update_selected_files_display(current_files)
                            clear_cached_analysis_results()
                        elif src_idx == dest_idx:
                            _logger.debug("Item solto sobre si mesmo.")
                            update_selected_files_display(current_files)
                        else:
                            _logger.warning(f"Índices inválidos on_accept: src={src_idx}, dest={dest_idx}, len={len(current_files)}")
                            update_selected_files_display(current_files)
                        
                        page.update(current_batch_name_text, selected_files_list_view)
                        #e.control.update() # Atualiza o DragTarget

                    return on_drag_will_accept, on_drag_accept_handler, on_drag_leave

                on_will_accept_handler, on_accept_handler, on_leave_handler = create_drag_handler(idx)

                # --- Ajustes no ListTile e seus componentes para melhor layout ---
                file_name_text = ft.Text(
                    value=file_info.get('name', 'Nome Indisponível'),
                    expand=True, # Permite que o texto do nome expanda e empurre os botões
                    overflow=ft.TextOverflow.ELLIPSIS, # Adiciona "..." se o nome for muito longo
                    #tooltip=file_info.get('name', 'Nome Indisponível') 
                )
                _logger.info(f"VIEW_DEBUG: Criado file_name_text com value: '{file_name_text.value}' para idx {idx}")

                action_buttons = ft.Row(
                    [
                        ft.IconButton(ft.Icons.ARROW_UPWARD, on_click=lambda _, i=idx: move_file_in_list(i, -1), disabled=(idx==0), tooltip="Mover para Cima", icon_size=18, padding=ft.padding.all(3)),
                        ft.IconButton(ft.Icons.ARROW_DOWNWARD, on_click=lambda _, i=idx: move_file_in_list(i, 1), disabled=(idx==len(_files)-1), tooltip="Mover para Baixo", icon_size=18, padding=ft.padding.all(3)),
                        ft.IconButton(ft.Icons.DELETE_OUTLINE, on_click=lambda _, i=idx: remove_file_from_list(i), icon_color=theme.COLOR_ERROR, tooltip="Remover da Lista", icon_size=18, padding=ft.padding.all(3))
                    ],
                    spacing=0, # Reduz o espaçamento entre os botões de ação
                    alignment=ft.MainAxisAlignment.END, 
                    width=100 # Necessário definir width aqui devido concorrência de espaço indevido com file_name_text no ListTile
                )

                list_tile_itself = ft.ListTile(
                    title=file_name_text, # Usa o Text com expand=True
                    leading=ft.Icon(ft.Icons.PICTURE_AS_PDF),
                    trailing=action_buttons,
                    # dense=True, # Torna o ListTile um pouco mais compacto
                    # visual_density=ft.VisualDensity.COMPACT # Outra opção para compactar
                )
                # Log para verificar o title do ListTile
                _logger.debug(f"VIEW_DEBUG: ListTile criado. Title object: {list_tile_itself.title}, Title value: {getattr(list_tile_itself.title, 'value', 'N/A')}")
                
                item_container_for_drag_target = ft.Container(
                    content=list_tile_itself, # O ListTile é o conteúdo visual principal
                    # padding=ft.padding.symmetric(vertical=2),
                    # border=ft.border.all(1, ft.colors.OUTLINE_VARIANT), # Borda de depuração
                    # border_radius=5
                )

                draggable_item = ft.Draggable(
                    group="pdf_files",
                    content=item_container_for_drag_target, # O container (com o ListTile dentro) é arrastável
                    data=str(idx)
                )
                
                drop_target_item = ft.DragTarget(
                    group="pdf_files",
                    content=draggable_item,
                    on_will_accept=on_will_accept_handler,
                    on_accept=on_accept_handler,         
                    on_leave=on_leave_handler,
                    # on_move=None, # Removido ou pode ser usado para outros feedbacks visuais durante o arraste sobre o alvo
                )
                selected_files_list_view.controls.append(drop_target_item)

            if len(_files) == 1:
                current_batch_name_text.value = f"Arquivo selecionado: {_files[0]['name']}"
            else:
                current_batch_name_text.value = f"Arquivos selecionados: {_files[0]['name']} e outros {len(_files)-1} (ordene abaixo)."
            
            selected_files_list_view.height = min(len(_files) * 65, 300) # Altura dinâmica, max 300px
            analyze_button.disabled = False
        
        page.session.set(KEY_SESSION_CURRENT_PDF_NAME, current_batch_name_text.value)
        #page.update(current_batch_name_text, selected_files_list_view, analyze_button) A chamada deve ser garantida pelo chamador.

    def move_file_in_list(index: int, direction: int):
        current_files_data = page.session.get(KEY_SESSION_CURRENT_PDF_FILES_ORDERED)
        current_files = list(current_files_data) if current_files_data else []

        if not (0 <= index < len(current_files)): return
        
        new_index = index + direction
        if not (0 <= new_index < len(current_files)): return

        current_files.insert(new_index, current_files.pop(index))
        page.session.set(KEY_SESSION_CURRENT_PDF_FILES_ORDERED, current_files)
        update_selected_files_display(current_files)
        clear_cached_analysis_results()
        page.update(current_batch_name_text, selected_files_list_view)

    def remove_file_from_list(index: int):
        current_files_data = page.session.get(KEY_SESSION_CURRENT_PDF_FILES_ORDERED)
        current_files = list(current_files_data) if current_files_data else []

        if not (0 <= index < len(current_files)): return
        
        removed_file_info = current_files.pop(index)
        removed_file_name = removed_file_info['name'] # Obter o nome do arquivo removido

        _logger.info(f"Arquivo '{removed_file_name}' removido da lista de análise.")
        page.session.set(KEY_SESSION_CURRENT_PDF_FILES_ORDERED, current_files)

        if managed_file_picker: # Garante que a instância existe
            managed_file_picker.clear_upload_state_for_file(removed_file_name)

        update_selected_files_display(current_files)
        clear_cached_analysis_results() # Remover um arquivo invalida o cache de análise conjunta
        page.update(current_batch_name_text, selected_files_list_view)

    def clear_cached_analysis_results():
        """Limpa caches relacionados aos resultados da análise combinada."""
        keys_to_clear = [
            KEY_SESSION_PDF_ANALYZER_DATA,
            KEY_SESSION_PDF_CLASSIFIED_INDICES,
            KEY_SESSION_PDF_AGGREGATED_TEXT_INFO,
            KEY_SESSION_PDF_LAST_LLM_RESPONSE
        ]
        for k in keys_to_clear:
            if page.session.contains_key(k):
                page.session.remove(k)
        _logger.debug("Caches de resultados de análise (combinada) limpos devido a mudança na lista de arquivos.")
        # Também reseta a UI de resultados
        status_extraction_text.value = "Lista de arquivos modificada. Reanálise necessária."
        status_text_analysis.value = ""
        status_llm_text.value = ""
        result_textfield.value = ""
        page.update(result_textfield, status_extraction_text, status_text_analysis, status_llm_text)

    _uploaded_file_accumulator: List[Dict[str, Any]] = []
    _expected_file_count = 0

    # --- Funções de Callback ---

    def individual_file_upload_complete_handler(success: bool, file_path_or_message: str, file_name: Optional[str]):
        # Este callback é chamado para CADA arquivo.
        _logger.info(f"VIEW_CALLBACK: individual_file_upload_complete para '{file_name}', Success: {success}, Msg: {file_path_or_message}")
        
        if success and file_name and file_path_or_message:
            _logger.info(f"Upload individual de '{file_name}' OK. Path: {file_path_or_message}")
            
            current_files = page.session.get(KEY_SESSION_CURRENT_PDF_FILES_ORDERED) or []
            # Evitar duplicatas se o mesmo arquivo for selecionado novamente em outro lote
            if not any(f['name'] == file_name and f['path'] == file_path_or_message for f in current_files):
                _logger.debug(f"VIEW_DEBUG: Em individual_file_upload_complete - current_files ANTES do append (tipo: {type(current_files)}): {current_files}")
                new_file_entry = {
                    "name": file_name, # file_name é string
                    "path": file_path_or_message, # string
                    "original_index": len(current_files) # int
                }
                
                # GARANTIR QUE current_files É UMA LISTA
                if not isinstance(current_files, list):
                    _logger.error(f"VIEW_DEBUG: current_files não é uma lista ANTES do append! Tipo: {type(current_files)}. Resetando para lista vazia.")
                    current_files = [] # Medida de segurança
                
                current_files.append(new_file_entry) # Adiciona um DICIONÁRIO à lista
                _logger.debug(f"VIEW_DEBUG: Em individual_file_upload_complete - current_files DEPOIS do append (tipo: {type(current_files)}, len: {len(current_files)}): {current_files}")

                page.session.set(KEY_SESSION_CURRENT_PDF_FILES_ORDERED, current_files)
                _logger.debug(f"VIEW_DEBUG: Salvo na sessão {KEY_SESSION_CURRENT_PDF_FILES_ORDERED}: {page.session.get(KEY_SESSION_CURRENT_PDF_FILES_ORDERED)}")

                current_batch_cache_key_segment = "_".join(os.path.basename(f_info['path']) for f_info in current_files)
                CACHE_KEY_PDF_LAST_LLM_RESPONSE_BATCH = f"{KEY_SESSION_PDF_LAST_LLM_RESPONSE}_{current_batch_cache_key_segment}"
                if page.session.contains_key(CACHE_KEY_PDF_LAST_LLM_RESPONSE_BATCH):
                    page.session.remove(CACHE_KEY_PDF_LAST_LLM_RESPONSE_BATCH)
                
                # Não chamar update_selected_files_display aqui, pois o batch_upload_complete_handler o fará
        
        elif file_path_or_message == "Seleção cancelada":
            _logger.info("Seleção de arquivos cancelada.")
        else: 
            _logger.error(f"Falha no upload de '{file_name}': {file_path_or_message}")
            # Não mostra snackbar individual aqui.

    def batch_upload_complete_handler(batch_results: List[Dict[str, Any]]):
        _logger.info(f"VIEW_BATCH_COMPLETE: Lote finalizado com {len(batch_results)} resultados.")
        hide_loading_overlay(page) # Se houver algum global

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

        # Atualiza a exibição final da lista de arquivos (que já foi sendo atualizada individualmente)
        update_selected_files_display() 
        page.update(current_batch_name_text, selected_files_list_view, analyze_button)
        # Se houve sucesso em algum upload, pode ser necessário invalidar caches
        if successful_uploads:
            clear_cached_analysis_results() # Invalida se o CONTEÚDO da lista de sucesso mudou o lote

    # Recupera a instância global do FilePicker
    file_picker_instance = page.data.get("global_file_picker")
    if not file_picker_instance:
        # Fallback ou erro se não estiver em page.data (improvável se app.py configurou)
        _logger.error("Instância global do FilePicker não encontrada em page.data!")
        return ft.Text("Erro: FilePicker não inicializado.", color=theme.COLOR_ERROR)

    managed_file_picker = ManagedFilePicker(
        page=page,
        file_picker_instance=file_picker_instance,
        on_individual_file_complete=individual_file_upload_complete_handler,
        upload_dir=UPLOAD_TEMP_DIR,
        on_batch_complete=batch_upload_complete_handler,
        allowed_extensions=["pdf"]
        #on_upload_progress=on_upload_progress_handler
    )

    def handle_upload_pdf_click(e):
        nonlocal _uploaded_file_accumulator, _expected_file_count
        _logger.debug("Botão 'Carregar PDF' clicado.")
        
        analyze_button.disabled = True
        page.update(analyze_button)
        
        _uploaded_file_accumulator = [] # Reseta acumulador para este lote de seleção
        _expected_file_count = 0 # Será definido pelo número de arquivos em FilePickerResultEvent

        # A função pick_files do FilePicker quando allow_multiple=True
        # vai disparar on_result UMA VEZ com e.files contendo a lista de todos os arquivos selecionados.
        # O ManagedFilePicker precisa ser ajustado para lidar com isso.
        
        # Ajuste necessário no ManagedFilePicker._on_file_picker_result para lidar com e.files > 1
        # e chamar on_upload_complete para cada um, ou ter um callback para o lote.
        # A chamada abaixo a pick_files com allow_multiple=True já está correta.
        managed_file_picker.pick_files(
            allow_multiple=True, # PERMITE MÚLTIPLOS
            dialog_title_override="Selecione um ou mais PDFs para análise conjunta"
        )

    def update_text_status(text_field, texto, format: str=None):
        text_field.value = texto
        if format == 'normal':
            text_field.text_style = ft.TextStyle(weight=ft.FontWeight.NORMAL, color=None) # Reseta para padrão
            text_field.border_color = theme.PRIMARY # Reseta borda
        elif format == 'error':
            text_field.text_style = ft.TextStyle(weight=ft.FontWeight.BOLD, color=theme.COLOR_ERROR)
            text_field.border_color = theme.COLOR_ERROR
        page.update(text_field)

    def handle_analyze_pdf_click(e):
        ordered_files_to_analyze = page.session.get(KEY_SESSION_CURRENT_PDF_FILES_ORDERED)
        if not ordered_files_to_analyze:
            show_snackbar(page, "Nenhum arquivo PDF carregado para análise.", color=theme.COLOR_WARNING)
            return

        # Extrai apenas os caminhos dos arquivos na ordem correta
        pdf_paths_ordered = [file_info['path'] for file_info in ordered_files_to_analyze]
        batch_display_name = current_batch_name_text.value # Usa o nome do lote já formatado

        _logger.info(f"Iniciando processamento do lote: {batch_display_name}")
        show_loading_overlay(page, f"A processar Leitura, Extração e Classificação do conteúdo \nPDF(s) '{batch_display_name}'...")

        # Limpa status e resultados anteriores
        result_textfield.value = "Análise em progresso..."
        result_textfield.text_style = ft.TextStyle(weight=ft.FontWeight.NORMAL, color=None) # Reset
        result_textfield.border_color = theme.PRIMARY # Reset

        status_extraction_text.value = f"Fase 1: Extraindo e pré-processando texto de '{batch_display_name}'..."
        status_text_analysis.value = ""
        status_llm_text.value = ""
        #status_text_analysis.value = f"Analisando..."
        #result_textfield.value = "Processando documento e consultando LLM..."
        page.update()

        def analysis_thread_func():
            nonlocal pdf_paths_ordered, batch_display_name # Importante para threads
            try:
                pdf_analyzer = PDFDocumentAnalyzer()
                # --- Fase 1A: Verificar Cache para processed_page_data ---
                # O cache agora precisa ser baseado no CONJUNTO ORDENADO de arquivos.
                # Uma forma é criar uma chave de cache a partir dos nomes dos arquivos e suas ordens.
                cache_key_segment = "_".join(os.path.basename(p) for p in pdf_paths_ordered)
                CACHE_KEY_ANALYZER_DATA_BATCH = f"{KEY_SESSION_PDF_ANALYZER_DATA}_{cache_key_segment}"
                processed_page_data_combined = page.session.get(CACHE_KEY_ANALYZER_DATA_BATCH)

                if processed_page_data_combined:
                    _logger.info(f"Dados processados do lote '{batch_display_name}' encontrados no cache.")
                    # Atualiza UI para indicar que pulou
                    page.run_thread(update_text_status, status_extraction_text, f"Fase 1 e 2 (Extração/Análise PDF) carregadas do cache.")
                    page.run_thread(update_text_status, status_text_analysis, f"{len(processed_page_data_combined)} páginas processadas.")
                    page.run_thread(update_text_status, status_llm_text, "Fase 3: Classificando páginas (usando cache)...")
                
                else:
                    # --- Fase 1: Extração e Pré-processamento ---
                    # pdf_analyzer receberá a lista de caminhos e retornará um único processed_page_data_combined
                    # onde as chaves dos dicionários de página serão prefixadas (ex: "file0_page0", "file1_page0")
                    
                    _logger.info(f"[DEBUG] ANALYSIS_THREAD: Iniciando com pdf_paths_ordered: {pdf_paths_ordered}")
                    # VERIFICAÇÃO ADICIONAL ANTES DE CHAMAR O PROCESSADOR
                    valid_pdf_paths_for_processor = []
                    for p_path in pdf_paths_ordered:
                        if os.path.exists(p_path):
                            valid_pdf_paths_for_processor.append(p_path)
                        else:
                            _logger.error(f"ANALYSIS_THREAD: Arquivo {p_path} NÃO encontrado no disco ANTES de chamar pdf_processor.")
                    
                    if not valid_pdf_paths_for_processor:
                        _logger.error("ANALYSIS_THREAD: Nenhum arquivo PDF válido encontrado no disco para processar.")
                        # Você pode querer levantar um erro aqui ou retornar/mostrar uma mensagem de erro
                        raise FileNotFoundError("Nenhum dos arquivos selecionados pôde ser encontrado para processamento.")

                    processed_files_metadata, all_indices_in_batch, all_texts_for_storage_combined, all_texts_for_analysis_combined = \
                        pdf_analyzer.extract_texts_and_preprocess_files(valid_pdf_paths_for_processor) # USA A LISTA VALIDADA

                    if not processed_files_metadata or not all_texts_for_analysis_combined:
                        raise ValueError("Nenhum texto extraível encontrado nos PDFs do lote.")
                    
                    processed_page_data_combined, all_global_page_keys_ordered = pdf_analyzer._build_combined_page_data(processed_files_metadata, 
                                                                            all_indices_in_batch, all_texts_for_storage_combined)

                    # Atualiza UI após Fase 1 (da thread)
                    page.run_thread(update_text_status, status_extraction_text, f"Fase 1 concluída: {len(processed_page_data_combined)} páginas com texto extraído.")
                    page.run_thread(update_text_status, status_text_analysis, "Fase 2: Analisando similaridade e relevância das páginas...")
                    # page.update() será chamado implicitamente por page.run_threadsafe se o controle for parte da UI

                    # --- Fase 2: Análise de Similaridade e Relevância ---
                    processed_page_data_combined = pdf_analyzer.analyze_similarity_and_relevance_files(
                        processed_page_data_combined, all_global_page_keys_ordered, all_texts_for_analysis_combined)

                    if not processed_page_data_combined: # Deve ser raro se a Fase 1 passou
                        raise ValueError("Falha na análise de similaridade/relevância.")

                    # Atualiza UI após Fase 2
                    page.run_thread(update_text_status, status_text_analysis, "Fase 2 concluída: Páginas processadas.")
                    page.run_thread(update_text_status, status_llm_text, "Fase 3: Classificando páginas e preparando para LLM...")
                    
                    page.session.set(CACHE_KEY_ANALYZER_DATA_BATCH, processed_page_data_combined) # SALVA NO CACHE
                    page.session.set(KEY_SESSION_PDF_ANALYZER_DATA, processed_page_data_combined)

                CACHE_KEY_CLASSIFIED_BATCH = f"{KEY_SESSION_PDF_CLASSIFIED_INDICES}_{cache_key_segment}"
                classified_data_batch = page.session.get(CACHE_KEY_CLASSIFIED_BATCH)
                
                if classified_data_batch:
                    _logger.info(f"Dados de classificação do(s) PDF(s) '{batch_display_name}' encontrados na sessão (cache). Pulando classificação.")
                    relevant_indices, unintelligible_indices, count_selected, \
                    count_discarded_similarity, count_discarded_unintelligible = classified_data_batch
                    
                    info_classificacao = (
                        f"\nPáginas Relevantes: {count_selected}, "
                        f"\nIrrelevantes por similaridade: {count_discarded_similarity},"
                        f"\nDescartadas (Ininteligíveis): {count_discarded_unintelligible} "
                    )
                    page.run_thread(update_text_status, status_llm_text, f"Classificação carregada do cache: {info_classificacao}. \nAgregando texto...")
                
                else:
                    # --- Fase 3: Classificação e Agregação ---
                    classified_data_batch  = pdf_analyzer.filter_and_classify_pages(processed_page_data_combined)
                    page.session.set(CACHE_KEY_CLASSIFIED_BATCH, classified_data_batch)
                    page.session.set(KEY_SESSION_PDF_CLASSIFIED_INDICES, classified_data_batch)

                    (relevant_indices, unintelligible_indices, count_selected,
                    count_discarded_similarity, count_discarded_unintelligible) = classified_data_batch

                    # (Opcional) Mostrar contagens na UI
                    info_classificacao = (
                        f"\nPáginas Relevantes: {count_selected}, "
                        f"\nIrrelevantes por similaridade: {count_discarded_similarity},"
                        f"\nDescartadas (Ininteligíveis): {count_discarded_unintelligible} "
                    )
                    page.run_thread(update_text_status, status_llm_text, f"Classificação: {info_classificacao}. \nAgregando texto...")

                if not relevant_indices:
                    raise ValueError("Nenhuma página relevante encontrada no(s) PDF(s) após filtragem.")
                
                # --- Fase 4A: Verificar Cache para aggregated_text_info ---
                CACHE_KEY_AGGREGATED_TEXT_INFO_BATCH = f"{KEY_SESSION_PDF_AGGREGATED_TEXT_INFO}_{cache_key_segment}"
                aggregated_info = page.session.get(CACHE_KEY_AGGREGATED_TEXT_INFO_BATCH)

                if aggregated_info:
                    _logger.info(f"Texto agregado do PDF '{batch_display_name}' encontrado na sessão (cache). Pulando agregação.")
                    str_pages_considered, aggregated_text, tokens_antes, tokens_depois = aggregated_info
                    
                else:
                    # TODO: O token_limit pode vir de configurações do usuário/LLM no futuro
                    token_limit_for_aggregation = 180000 
                    str_pages_considered, aggregated_text, tokens_antes, tokens_depois = \
                        pdf_analyzer.group_texts_by_relevance_and_token_limit(
                            processed_page_data=processed_page_data_combined,
                            relevant_page_indices=relevant_indices,
                            token_limit=token_limit_for_aggregation
                        )
                    _logger.info(f"Texto agregado. Páginas: {str_pages_considered}. Tokens Antes: {tokens_antes}, Depois: {tokens_depois}")
                    
                    page.session.set(CACHE_KEY_AGGREGATED_TEXT_INFO_BATCH, (str_pages_considered, aggregated_text, tokens_antes, tokens_depois))
                    page.session.set(KEY_SESSION_PDF_AGGREGATED_TEXT_INFO, (str_pages_considered, aggregated_text, tokens_antes, tokens_depois))

                page.run_thread(update_text_status, status_llm_text, f"Classificação: {info_classificacao}, \n\nTexto final agregado das págs {str_pages_considered}.\n Consultando LLM...")
                
                hide_loading_overlay(page)
                show_loading_overlay(page, f"PDF(s) '{batch_display_name}'.. \nInteragindo com modelo de LLM...")

                # --- Fase 4: Chamada LLM ---
                llm_response = analyze_text_with_llm(
                    page=page,
                    processed_text=aggregated_text,
                    provider="openai",
                    model_name="gpt-4.1-nano" # TODO: Obter das configurações selecionadas pelo usuário!
                )

                # Atualiza UI final
                CACHE_KEY_PDF_LAST_LLM_RESPONSE = f"{KEY_SESSION_PDF_LAST_LLM_RESPONSE}_{cache_key_segment}"
                page.run_thread(hide_loading_overlay, page) # Esconde o overlay global
                if llm_response:
                    page.session.set(CACHE_KEY_PDF_LAST_LLM_RESPONSE, llm_response) # SALVA NO CACHE
                    page.session.set(KEY_SESSION_PDF_LAST_LLM_RESPONSE, llm_response)
                    _logger.info(f"Resposta da LLM para '{batch_display_name}' salva na sessão.")
                    page.run_thread(update_text_status, result_textfield, llm_response, {"format": "normal"})
                    page.run_thread(update_text_status, status_llm_text, f"Classificação: {info_classificacao}. \n\nTexto final agregado das págs {str_pages_considered}. \n\nAnálise de '{batch_display_name}' concluída pela LLM.")
                    page.run_thread(show_snackbar, page, "Análise LLM concluída!", theme.COLOR_SUCCESS)
                else:
                    page.run_thread(update_text_status, result_textfield, "Falha ao obter resposta da LLM.", {"format": "error"})
                    page.run_thread(update_text_status, status_llm_text, "Erro na LLM.")
                    page.run_thread(show_snackbar, page, "Erro na LLM.", theme.COLOR_ERROR)
                    # Se a resposta da LLM for None (erro), remove qualquer resposta antiga da sessão
                    if page.session.contains_key(CACHE_KEY_PDF_LAST_LLM_RESPONSE):
                        page.session.remove(CACHE_KEY_PDF_LAST_LLM_RESPONSE)

            except Exception as ex_thread:
                _logger.error(f"Erro na thread de análise do(s) PDF(s) '{batch_display_name}': {ex_thread}", exc_info=True)
                page.run_thread(hide_loading_overlay, page)

                error_message_thread = f"Erro no processamento: {ex_thread}"
                page.run_thread(update_text_status, result_textfield, error_message_thread, {"format": "error"})

                # Tenta atualizar os status da UI para refletir onde parou, se possível
                if 'status_extraction_text' in locals() and not status_text_analysis.value: # Falhou na extração
                    page.run_thread(update_text_status, status_extraction_text, f"Falha na extração: {ex_thread}")
                elif 'status_analysis_text' in locals() and not status_llm_text.value: # Falhou na análise
                    page.run_thread(update_text_status, status_text_analysis, f"Falha na análise interna: {ex_thread}")
                else: # Falha em outro ponto
                    page.run_thread(update_text_status, status_llm_text, f"Falha geral: {ex_thread}")
                page.run_thread(show_snackbar, page, f"Erro: {ex_thread}", theme.COLOR_ERROR, 7000)
            finally:
                # A limpeza de arquivos temporários agora itera sobre pdf_paths_ordered
                for pdf_path_item in pdf_paths_ordered:
                    if pdf_path_item and UPLOAD_TEMP_DIR in pdf_path_item and os.path.exists(pdf_path_item):
                        try:
                            os.remove(pdf_path_item)
                            _logger.info(f"Arquivo PDF temporário '{pdf_path_item}' removido.")
                        except Exception as e_remove:
                            _logger.warning(f"Não removeu PDF temporário '{pdf_path_item}': {e_remove}")
                # Não precisa de page.update() aqui, pois page.run_threadsafe já cuida disso.
                # Não limpar o pdf_path da sessão aqui, pois pode ser usado pelo chat_pdf
        page.update()

        thread = threading.Thread(target=analysis_thread_func, daemon=True)
        thread.start()
    
    def handle_copy_result_click(e):
        if result_textfield.value:
            page.set_clipboard(result_textfield.value)
            show_snackbar(page, "Resultado copiado para a área de transferência!", color=theme.COLOR_INFO)
        else:
            show_snackbar(page, "Nenhum resultado para copiar.", color=theme.COLOR_WARNING)

    upload_button.on_click = handle_upload_pdf_click
    analyze_button.on_click=handle_analyze_pdf_click
    copy_button.on_click=handle_copy_result_click

    # Layout do conteúdo
    content_column = ft.Column(
        [
            ft.Text("Análise inicial de Notícias-Crime e Outros", style=ft.TextThemeStyle.HEADLINE_MEDIUM),
            ft.Text("Faça o upload de um arquivo PDF para extrair o texto, processá-lo e enviar para análise pela IA-Assistente."),
            ft.Divider(),
            ft.Row([upload_button, analyze_button], alignment=ft.MainAxisAlignment.START, spacing=10),
            
            current_batch_name_text,
            ft.Text("Arquivos para Análise (arraste para reordenar):", style=ft.TextThemeStyle.LABEL_MEDIUM),
            ft.Container(selected_files_list_view, expand=True), 
            
            status_extraction_text,
            status_text_analysis,
            status_llm_text,
            ft.Divider(height=20),
            ft.Row([ft.Text("Resultado da Análise:", style=ft.TextThemeStyle.TITLE_MEDIUM), copy_button],
                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(
                result_textfield,
                border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                border_radius=5,
                padding=5,
                expand=True # Faz o container do TextField expandir
            )
        ],
        spacing=15,
        expand=True, # Permite que a coluna principal expanda
        #scroll=ft.ScrollMode.ADAPTIVE # Adicionar scroll se necessário
    )
    
    # Recarregar o estado da UI se um PDF já estiver na sessão
    # (Ex: usuário navegou para outra aba e voltou)
    pdf_name_on_session = page.session.get(KEY_SESSION_CURRENT_PDF_NAME)
    
    processed_page_data = page.session.get(KEY_SESSION_PDF_ANALYZER_DATA)
    classified_data = page.session.get(KEY_SESSION_PDF_CLASSIFIED_INDICES)
    aggregated_info = page.session.get(KEY_SESSION_PDF_AGGREGATED_TEXT_INFO)
    last_llm_response_on_session = page.session.get(KEY_SESSION_PDF_LAST_LLM_RESPONSE)
    
    if pdf_name_on_session:
        current_batch_name_text.value = pdf_name_on_session
        
        if processed_page_data:    
            status_extraction_text.value = f"Fase 1 e 2 (Extração/Análise PDF) carregadas do cache."
            status_text_analysis.value = f"{len(processed_page_data)} páginas processadas."
        
        if classified_data and aggregated_info:
            _, _, count_selected, count_discarded_similarity, count_discarded_unintelligible = classified_data
            
            info_classificacao = (
                f"\nPáginas Relevantes: {count_selected}, "
                f"\nIrrelevantes por similaridade: {count_discarded_similarity},"
                f"\nDescartadas (Ininteligíveis): {count_discarded_unintelligible} "
            )
            str_pages_considered, _, _, _ = aggregated_info

            status_llm_text.value = f"Classificação: {info_classificacao}. \n\nTexto final agregado das págs {str_pages_considered}."
        
        if last_llm_response_on_session:
            status_llm_text.value = f"Classificação: {info_classificacao}. \n\nTexto final agregado das págs {str_pages_considered}. \n\nAnálise de '{pdf_name_on_session}' concluída pela LLM."
            result_textfield.value = last_llm_response_on_session
            _logger.info(f"Última resposta da LLM para '{pdf_name_on_session}' carregada da sessão.")

        else:
            status_llm_text.value += "\nClique em 'Analisar PDF' para processar."

        analyze_button.disabled = False

    else:
        current_batch_name_text.value = "Nenhum arquivo PDF selecionado."
        analyze_button.disabled = True

    update_selected_files_display() 
    return content_column


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

