# src/flet_ui/views/analyze_pdf_view.py
from ast import main
import flet as ft
import os, threading
from typing import Optional

# Imports do projeto
from src.flet_ui.components import (
    show_snackbar,
    show_loading_overlay,
    hide_loading_overlay,
    ManagedFilePicker # Usaremos o componente robusto
)
from src.flet_ui import theme
# Imports do Core (Backend)
from src.core.pdf_processor import PDFDocumentAnalyzer
from src.core.ai_orchestrator import analyze_text_with_llm

from src.settings import UPLOAD_TEMP_DIR

from src.logger.logger import LoggerSetup
_logger = LoggerSetup.get_logger(__name__)

# Estado da View (para manter referência ao arquivo e resultados)
# Como não temos uma classe de View, podemos usar page.session ou page.client_storage
# de forma mais granular ou, para estado de "sessão de análise", page.session é adequado.
# Ou, para simplicidade neste exemplo, variáveis no escopo do módulo se a view for
# recriada a cada navegação (o que acontece com a abordagem de content_only).
# Para compartilhar o PDF entre `/analyze_pdf` e `/chat_pdf`, `page.session` é o ideal.

KEY_SESSION_CURRENT_PDF_PATH = "current_pdf_path_for_analysis"
KEY_SESSION_CURRENT_PDF_NAME = "current_pdf_name_for_analysis"
KEY_SESSION_PDF_ANALYZER_DATA = "pdf_analyzer_processed_page_data"
KEY_SESSION_PDF_CLASSIFIED_INDICES = "pdf_classified_indices_data"
KEY_SESSION_PDF_AGGREGATED_TEXT_INFO = "pdf_aggregated_text_info" # Substitui KEY_SESSION_PDF_PROCESSED_TEXT
KEY_SESSION_PDF_LAST_LLM_RESPONSE = "pdf_last_llm_response"


def create_analyze_pdf_content(page: ft.Page) -> ft.Control:
    _logger.info("Criando conteúdo da view de Análise de PDF.")

    # Recupera a instância global do FilePicker
    file_picker_instance = page.data.get("global_file_picker")
    if not file_picker_instance:
        # Fallback ou erro se não estiver em page.data (improvável se app.py configurou)
        _logger.error("Instância global do FilePicker não encontrada em page.data!")
        return ft.Text("Erro: FilePicker não inicializado.", color=theme.COLOR_ERROR)

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

    selected_file_text = ft.Text("Nenhum arquivo PDF selecionado.", italic=True)
    status_extraction_text = ft.Text("", italic=True, size=12)
    status_text_analysis = ft.Text("", italic=True, size=12)
    status_llm_text = ft.Text("", italic=True, size=12)

    # --- Controles da UI ---
    upload_button = ft.ElevatedButton(
        "Carregar PDF",
        icon=ft.Icons.UPLOAD_FILE,
        #on_click=handle_upload_pdf_click
    )
    analyze_button = ft.ElevatedButton(
        "Analisar PDF",
        icon=ft.Icons.TEXT_SNIPPET_OUTLINED,
        #on_click=handle_analyze_pdf_click,
        tooltip="Processa o PDF carregado e envia para análise pela LLM",
        disabled=True
    )
    copy_button = ft.IconButton(
        icon=ft.Icons.COPY_ALL_OUTLINED,
        tooltip="Copiar Resultado",
        #on_click=handle_copy_result_click
    )

    def clear_pdf_session_data():
        """Limpa todos os dados de sessão relacionados ao PDF atual."""
        keys_to_clear = [
            KEY_SESSION_CURRENT_PDF_PATH, KEY_SESSION_CURRENT_PDF_NAME,
            KEY_SESSION_PDF_ANALYZER_DATA, KEY_SESSION_PDF_CLASSIFIED_INDICES,
            KEY_SESSION_PDF_AGGREGATED_TEXT_INFO, KEY_SESSION_PDF_LAST_LLM_RESPONSE
        ]
        for k in keys_to_clear:
            if page.session.contains_key(k):
                page.session.remove(k)
        _logger.debug("Dados de sessão do PDF anterior limpos.")

    # --- Funções de Callback ---
    def on_file_upload_complete(
        success: bool,
        file_path_or_message: str,
        file_name: Optional[str]
    ):
        hide_loading_overlay(page)
        upload_button.disabled = False
        analyze_button.disabled = not success
        #page.update(upload_button, analyze_button)

        if success and file_path_or_message and file_name:
            _logger.info(f"Upload do PDF '{file_name}' concluído. Caminho: {file_path_or_message}")
            show_snackbar(page, f"PDF '{file_name}' carregado com sucesso!", color=theme.COLOR_SUCCESS)
            selected_file_text.value = f"Arquivo selecionado: {file_name}"
            status_extraction_text.value = ""
            status_text_analysis.value = "PDF carregado. Clique em 'Analisar PDF' para processar."
            result_textfield.value = "" # Limpa resultado anterior

            clear_pdf_session_data() # Limpa dados de um PDF anterior ANTES de setar novos
            page.session.set(KEY_SESSION_CURRENT_PDF_PATH, file_path_or_message)
            page.session.set(KEY_SESSION_CURRENT_PDF_NAME, file_name)
            
            analyze_button.disabled = False
        elif file_path_or_message == "Seleção cancelada": # Identifica o cancelamento
            selected_file_text.value = "Seleção de arquivo cancelada."
            analyze_button.disabled = True # Mantém desabilitado
            _logger.info("Upload cancelado pelo usuário.")
        else:
            _logger.error(f"Falha no upload do arquivo: {file_path_or_message} (Nome: {file_name})")
            show_snackbar(page, f"Erro no upload: {file_path_or_message}", color=theme.COLOR_ERROR, duration=7000)
            selected_file_text.value = "Falha ao carregar o arquivo."
            clear_pdf_session_data() # Limpa se o upload falhou
            analyze_button.disabled = True # Mantém/Desabilita análise
        
        page.update(upload_button, analyze_button, selected_file_text, status_extraction_text, status_text_analysis, result_textfield) # Garante que tudo atualize

    def handle_upload_pdf_click(e):
        _logger.debug("Botão 'Carregar PDF' clicado.")
        
        upload_button.disabled = True
        analyze_button.disabled = True
        selected_file_text.value = "Selecionando arquivo..."
        status_extraction_text.value = "Aguardando para extração de textos..." # Feedback inicial
        status_text_analysis.value = ""
        status_llm_text.value = ""
        result_textfield.value = ""
        
        page.update(
            upload_button, analyze_button, selected_file_text,
            status_extraction_text, status_text_analysis, status_llm_text,
            result_textfield
        )

        clear_pdf_session_data() # Limpa dados de um PDF anterior
        
        managed_file_picker.pick_files(allow_multiple=False, dialog_title_override="Selecione o PDF para análise")

    # O on_upload_progress pode ser usado para mudar status_extraction_text para "Enviando..."
    def on_upload_progress_handler(file_name: str, progress: float):
        if progress == 0.0:
            status_extraction_text.value = f"Enviando '{file_name}'..."
        else:
            status_extraction_text.value = f"Enviando '{file_name}': {progress*100:.0f}%"
        page.update(status_extraction_text)

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
        pdf_path = page.session.get(KEY_SESSION_CURRENT_PDF_PATH)
        pdf_name = page.session.get(KEY_SESSION_CURRENT_PDF_NAME)

        if not pdf_path or not pdf_name:
            show_snackbar(page, "Nenhum arquivo PDF carregado para análise.", color=theme.COLOR_WARNING)
            return

        _logger.info(f"Iniciando processamento do PDF: {pdf_name}")
        show_loading_overlay(page, f"A processar Leitura, Extração e Classificação do conteúdo \nPDF '{pdf_name}'...")

        # Limpa status e resultados anteriores
        result_textfield.value = "Análise em progresso..."
        result_textfield.text_style = ft.TextStyle(weight=ft.FontWeight.NORMAL, color=None) # Reset
        result_textfield.border_color = theme.PRIMARY # Reset

        status_extraction_text.value = f"Fase 1: Extraindo e pré-processando texto de '{pdf_name}'..."
        status_text_analysis.value = ""
        status_llm_text.value = ""
        #status_text_analysis.value = f"Analisando..."
        #result_textfield.value = "Processando documento e consultando LLM..."
        page.update()

        def analysis_thread_func():
            nonlocal pdf_path, pdf_name # Importante para threads
            try:
                pdf_analyzer = PDFDocumentAnalyzer()

                # --- Fase 1A: Verificar Cache para processed_page_data ---
                processed_page_data = page.session.get(KEY_SESSION_PDF_ANALYZER_DATA)
                if processed_page_data:
                    _logger.info(f"Dados processados do PDF '{pdf_name}' encontrados na sessão (cache). Pulando Fase 1 e 2.")

                    # Atualiza UI para indicar que pulou
                    page.run_thread(update_text_status, status_extraction_text, f"Fase 1 e 2 (Extração/Análise PDF) carregadas do cache.")
                    page.run_thread(update_text_status, status_text_analysis, f"{len(processed_page_data)} páginas processadas.")
                    page.run_thread(update_text_status, status_llm_text, "Fase 3: Classificando páginas (usando cache)...")
                
                else:
                    # --- Fase 1: Extração e Pré-processamento ---
                    actual_indices, texts_for_storage, texts_for_analysis = \
                        pdf_analyzer.extract_texts_and_preprocess(pdf_path)

                    if not actual_indices:
                        raise ValueError("Nenhum texto extraível encontrado no PDF.")

                    # Atualiza UI após Fase 1 (da thread)
                    page.run_thread(update_text_status, status_extraction_text, f"Fase 1 concluída: {len(actual_indices)} páginas com texto extraído.")
                    page.run_thread(update_text_status, status_text_analysis, "Fase 2: Analisando similaridade e relevância das páginas...")
                    # page.update() será chamado implicitamente por page.run_threadsafe se o controle for parte da UI

                    # --- Fase 2: Análise de Similaridade e Relevância ---
                    processed_page_data = pdf_analyzer.analyze_similarity_and_relevance(
                        pdf_path, actual_indices, texts_for_storage, texts_for_analysis
                    )
                    if not processed_page_data: # Deve ser raro se a Fase 1 passou
                        raise ValueError("Falha na análise de similaridade/relevância.")

                    # Atualiza UI após Fase 2
                    page.run_thread(update_text_status, status_text_analysis, "Fase 2 concluída: Páginas processadas.")
                    page.run_thread(update_text_status, status_llm_text, "Fase 3: Classificando páginas e preparando para LLM...")
                    
                    page.session.set(KEY_SESSION_PDF_ANALYZER_DATA, processed_page_data) # SALVA NO CACHE

                classified_data = page.session.get(KEY_SESSION_PDF_CLASSIFIED_INDICES)
                if classified_data:
                    _logger.info(f"Dados de classificação do PDF '{pdf_name}' encontrados na sessão (cache). Pulando classificação.")
                    relevant_indices, unintelligible_indices, count_selected, \
                    count_discarded_similarity, count_discarded_unintelligible = classified_data
                    
                    info_classificacao = ( # Recria a string de informação
                        f"\nPágs. Relevantes: {count_selected}, "
                        f"\nIninteligíveis: {count_discarded_unintelligible}, "
                        f"\nSimilares: {count_discarded_similarity}"
                    )
                    page.run_thread(update_text_status, status_llm_text, f"Classificação carregada do cache: {info_classificacao}. \nAgregando texto...")
                
                else:
                    # --- Fase 3: Classificação e Agregação ---
                    (relevant_indices, unintelligible_indices, count_selected,
                    count_discarded_similarity, count_discarded_unintelligible) = \
                        pdf_analyzer.filter_and_classify_pages(processed_page_data)

                    # (Opcional) Mostrar contagens na UI
                    info_classificacao = (
                        f"\nPágs. Relevantes: {count_selected}, "
                        f"\nDescartadas (Ininteligíveis): {count_discarded_unintelligible}, "
                        f"\nDescartadas (Similares): {count_discarded_similarity}"
                    )
                    page.run_thread(update_text_status, status_llm_text, f"Classificação: {info_classificacao}. \nAgregando texto...")
                    page.session.set(KEY_SESSION_PDF_CLASSIFIED_INDICES, (relevant_indices, unintelligible_indices, count_selected, count_discarded_similarity, count_discarded_unintelligible))    

                if not relevant_indices:
                    raise ValueError("Nenhuma página relevante encontrada no PDF após filtragem.")
                
                # --- Fase 4A: Verificar Cache para aggregated_text_info ---
                aggregated_info = page.session.get(KEY_SESSION_PDF_AGGREGATED_TEXT_INFO)

                if aggregated_info:
                    _logger.info(f"Texto agregado do PDF '{pdf_name}' encontrado na sessão (cache). Pulando agregação.")
                    str_pages_considered, aggregated_text, tokens_antes, tokens_depois = aggregated_info
                    
                else:
                    # TODO: O token_limit pode vir de configurações do usuário/LLM no futuro
                    token_limit_for_aggregation = 180000 # TODO: Passar como parâmetro
                    str_pages_considered, aggregated_text, tokens_antes, tokens_depois = \
                        pdf_analyzer.group_texts_by_relevance_and_token_limit(
                            processed_page_data=processed_page_data,
                            relevant_page_indices=relevant_indices,
                            token_limit=token_limit_for_aggregation
                        )
                    _logger.info(f"Texto agregado. Páginas: {str_pages_considered}. Tokens Antes: {tokens_antes}, Depois: {tokens_depois}")
                    
                    page.session.set(KEY_SESSION_PDF_AGGREGATED_TEXT_INFO, (str_pages_considered, aggregated_text, tokens_antes, tokens_depois))

                page.run_thread(update_text_status, status_llm_text, f"Classificação: {info_classificacao}, \n\nTexto final agregado das págs {str_pages_considered}.\n Consultando LLM...")
                
                hide_loading_overlay(page)
                show_loading_overlay(page, f"PDF '{pdf_name}'.. \nInteragindo com modelo de LLM...")

                # --- Fase 4: Chamada LLM ---
                llm_response = analyze_text_with_llm(
                    page=page,
                    processed_text=aggregated_text,
                    provider="openai",
                    model_name="gpt-4.1-nano" # TODO: Obter das configurações selecionadas pelo usuário!
                )

                # Atualiza UI final
                page.run_thread(hide_loading_overlay, page) # Esconde o overlay global
                if llm_response:
                    page.session.set(KEY_SESSION_PDF_LAST_LLM_RESPONSE, llm_response) # SALVA NO CACHE
                    _logger.info(f"Resposta da LLM para '{pdf_name}' salva na sessão.")
                    page.run_thread(update_text_status, result_textfield, llm_response, {"format": "normal"})
                    page.run_thread(update_text_status, status_llm_text, f"Classificação: {info_classificacao}. \n\nTexto final agregado das págs {str_pages_considered}. \n\nAnálise de '{pdf_name}' concluída pela LLM.")
                    page.run_thread(show_snackbar, page, "Análise LLM concluída!", theme.COLOR_SUCCESS)
                else:
                    page.run_thread(update_text_status, result_textfield, "Falha ao obter resposta da LLM.", {"format": "error"})
                    page.run_thread(update_text_status, status_llm_text, "Erro na LLM.")
                    page.run_thread(show_snackbar, page, "Erro na LLM.", theme.COLOR_ERROR)
                    # Se a resposta da LLM for None (erro), remove qualquer resposta antiga da sessão
                    if page.session.contains_key(KEY_SESSION_PDF_LAST_LLM_RESPONSE):
                        page.session.remove(KEY_SESSION_PDF_LAST_LLM_RESPONSE)

            except Exception as ex_thread:
                _logger.error(f"Erro na thread de análise do PDF '{pdf_name}': {ex_thread}", exc_info=True)
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
                # Limpeza do arquivo temporário
                if pdf_path and UPLOAD_TEMP_DIR in pdf_path and os.path.exists(pdf_path):
                    try:
                        os.remove(pdf_path)
                        _logger.info(f"Arquivo PDF temporário '{pdf_path}' removido (thread).")
                    except Exception as e_remove:
                        _logger.warning(f"Não foi possível remover o arquivo PDF temporário '{pdf_path}' (thread): {e_remove}")
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

    # Instância do ManagedFilePicker
    managed_file_picker = ManagedFilePicker(
        page=page,
        file_picker_instance=file_picker_instance,
        on_upload_complete=on_file_upload_complete,
        upload_dir=UPLOAD_TEMP_DIR, # Use o caminho absoluto
        allowed_extensions=["pdf"],
        on_upload_progress=on_upload_progress_handler # Passa o handler de progresso
    )

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
            selected_file_text,
            status_extraction_text,
            status_text_analysis,
            status_llm_text,
            ft.Divider(height=20),
            ft.Row([ft.Text("Resultado da Análise:", style=ft.TextThemeStyle.TITLE_MEDIUM), copy_button],
                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(
                result_textfield,
                border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
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
    last_llm_response_on_session = page.session.get(KEY_SESSION_PDF_LAST_LLM_RESPONSE)
    if pdf_name_on_session:
        selected_file_text.value = f"Arquivo carregado: {pdf_name_on_session}"
        
        processed_page_data = page.session.get(KEY_SESSION_PDF_ANALYZER_DATA)
        if processed_page_data:    
            status_extraction_text.value = f"Fase 1 e 2 (Extração/Análise PDF) carregadas do cache."
        
        classified_data = page.session.get(KEY_SESSION_PDF_CLASSIFIED_INDICES)
        aggregated_info = page.session.get(KEY_SESSION_PDF_AGGREGATED_TEXT_INFO)
        if classified_data and aggregated_info:
            relevant_indices, unintelligible_indices, count_selected, \
            count_discarded_similarity, count_discarded_unintelligible = classified_data
            
            info_classificacao = ( # Recria a string de informação
                f"\nPágs. Relevantes: {count_selected}, "
                f"\nIninteligíveis: {count_discarded_unintelligible}, "
                f"\nSimilares: {count_discarded_similarity}"
            )
            str_pages_considered, aggregated_text, tokens_antes, tokens_depois = aggregated_info

            status_llm_text.value = f"Classificação: {info_classificacao}. \n\nTexto final agregado das págs {str_pages_considered}."
        
        if last_llm_response_on_session:
            result_textfield.value = last_llm_response_on_session
            _logger.info(f"Última resposta da LLM para '{pdf_name_on_session}' carregada da sessão.")
        else:
            selected_file_text.value += "\nClique em 'Analisar PDF' para processar."

        analyze_button.disabled = False
        # Poderia também recarregar o resultado se estiver salvo, mas pode ser custoso/complexo
    else:
        selected_file_text.value = "Nenhum arquivo PDF selecionado."
        analyze_button.disabled = True

    return content_column


def create_chat_pdf_content(page: ft.Page) -> ft.Control:
    _logger.info("Criando conteúdo da view Chat com PDF.")

    current_pdf_name = page.session.get(KEY_SESSION_CURRENT_PDF_NAME)
    aggregated_info = page.session.get(KEY_SESSION_PDF_AGGREGATED_TEXT_INFO)
    
    processed_text_for_chat = None
    if aggregated_info:
        # A ordem na tupla é (str_pages_considered, aggregated_text, tokens_antes, tokens_depois)
        processed_text_for_chat = aggregated_info[1] 

    show_snackbar(
        page,
        "Chat com PDFs: Seção ainda não programada.",
        color=theme.COLOR_WARNING, # Ou uma cor neutra/informativa
        duration=5000
    )

    main_content = ft.Column(
        [
            ft.Icon(ft.icons.CONSTRUCTION, size=80, opacity=0.3),
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
        title = ft.Row([ft.Text(f"Chat com: {current_pdf_name}", style=ft.TextThemeStyle.HEADLINE_SMALL)], alignment=ft.MainAxisAlignment.START, expand=True)
        
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

