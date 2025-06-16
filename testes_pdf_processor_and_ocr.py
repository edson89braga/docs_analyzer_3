
### Func OCR #########################################################################################
import easyocr
from pdf2image import convert_from_path
from pdf2image.exceptions import PDFPageCountError, PDFSyntaxError, PDFInfoNotInstalledError

@timing_decorator()
def extrair_texto_pdf(
    pdf_path: str,
    paginas_alvo: Optional[List[int]] = None,
    dpi: int = 300,
    poppler_path: Optional[str] = r'C:\Users\edson.eab\OneDrive - Polícia Federal\Scripts Python\Proj_App   -- LLM-API - Docs_Analyzer_3\poppler-22.04.0\Library\bin',
    ocr_model_dir: str = 'modelos_ocr',
    language_codes: List[str] = ['pt'], # Ex: ['en', 'pt']
    gpu_enabled: bool = True
) -> Dict[int, str]:
    """
    Extrai texto de páginas específicas de um PDF usando OCR com EasyOCR.

    Args:
        pdf_path (str): Caminho para o arquivo PDF.
        paginas_alvo (Optional[List[int]]): Lista de números de páginas para extrair 
                                           (índice 0-based). Se None, extrai todas as páginas.
        dpi (int): Resolução para conversão do PDF para imagem (pontos por polegada).
        poppler_path (Optional[str]): Caminho para o diretório bin do Poppler.
                                      Se None, pdf2image tentará encontrar o Poppler no PATH.
        ocr_model_dir (str): Pasta para armazenar/carregar modelos EasyOCR.
        language_codes (List[str]): Códigos de idioma para EasyOCR (ex: ['pt'], ['en']).
        gpu_enabled (bool): Se True, tenta usar GPU para EasyOCR.

    Returns:
        Dict[int, str]: Dicionário onde a chave é o número da página (1-based) e 
                        o valor é o texto extraído.
    
    Raises:
        FileNotFoundError: Se o pdf_path não existir.
        ImportError: Se easyocr ou pdf2image não estiverem instalados.
        PDFInfoNotInstalledError: Se o Poppler não for encontrado.
        Exception: Para outros erros de OCR ou conversão de PDF.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Arquivo PDF não encontrado: {pdf_path}")

    if easyocr is None or convert_from_path is None:
        logger.error("EasyOCR ou pdf2image não estão instalados. A extração de OCR não pode prosseguir.")
        raise ImportError("Dependências EasyOCR ou pdf2image não estão instaladas.")

    # Garante que o diretório de modelos OCR exista
    os.makedirs(ocr_model_dir, exist_ok=True)

    # Inicializa o EasyOCR Reader.
    # Considerar inicializar o reader uma vez fora desta função se for chamada frequentemente.
    logger.info(f"Inicializando EasyOCR reader com idiomas: {language_codes}, GPU: {gpu_enabled}. Modelos em: {ocr_model_dir}")
    try:
        reader = easyocr.Reader(
            lang_list=language_codes,
            gpu=gpu_enabled,
            model_storage_directory=ocr_model_dir,
            download_enabled=True, # Permite baixar modelos se não existirem
            # recog_network='crnn' # Exemplo de configuração de modelo específico
        )
    except Exception as e:
        logger.error(f"Falha ao inicializar o EasyOCR Reader: {e}", exc_info=True)
        raise

    resultados_finais: Dict[int, str] = {}
    
    try:
        # Obter informações sobre o PDF (número total de páginas)
        # pdfinfo = pdfinfo_from_path(pdf_path, poppler_path=poppler_path) # Alternativa para pegar total de páginas
        # total_pages_pdf = pdfinfo['pages']

        imagens_para_ocr: List[Tuple[int, Any]] = [] # (original_page_index_0_based, image_object)

        if paginas_alvo is not None:
            if not paginas_alvo: # Lista vazia
                logger.info("Lista 'paginas_alvo' está vazia. Nenhuma página será processada por OCR.")
                return resultados_finais
            
            # Valida e normaliza os índices das páginas alvo (0-based)
            paginas_alvo_unicas_ordenadas = sorted(list(set(int(p) for p in paginas_alvo if isinstance(p, int) and p >= 0)))
            
            if not paginas_alvo_unicas_ordenadas:
                logger.warning("Nenhuma página alvo válida após validação.")
                return resultados_finais

            min_idx_alvo = paginas_alvo_unicas_ordenadas[0]
            max_idx_alvo = paginas_alvo_unicas_ordenadas[-1]

            logger.info(f"Convertendo páginas do PDF (range {min_idx_alvo+1} a {max_idx_alvo+1}) para imagens com DPI {dpi}.")
            paginas_convertidas_bloco = convert_from_path(
                pdf_path,
                dpi=dpi,
                first_page=min_idx_alvo + 1, # 1-based
                last_page=max_idx_alvo + 1,  # 1-based
                poppler_path=poppler_path,
                fmt='jpeg', # Formato da imagem, pode ser 'png', 'ppm', etc.
                thread_count=2 # Otimização para conversão
            )
            
            for target_page_idx_0_based in paginas_alvo_unicas_ordenadas:
                idx_no_bloco = target_page_idx_0_based - min_idx_alvo
                if 0 <= idx_no_bloco < len(paginas_convertidas_bloco):
                    imagens_para_ocr.append((target_page_idx_0_based, paginas_convertidas_bloco[idx_no_bloco]))
                else:
                    logger.warning(f"Índice {idx_no_bloco} fora dos limites para página alvo {target_page_idx_0_based+1}. Imagem não encontrada no bloco convertido.")
        
        else: # Processar todas as páginas
            logger.info(f"Convertendo todas as páginas do PDF para imagens com DPI {dpi}.")
            paginas_convertidas_bloco = convert_from_path(
                pdf_path,
                dpi=dpi,
                poppler_path=poppler_path,
                fmt='jpeg',
                thread_count=2
            )
            for idx, img in enumerate(paginas_convertidas_bloco):
                imagens_para_ocr.append((idx, img)) # idx é o índice da página (0-based)

        logger.info(f"Total de {len(imagens_para_ocr)} imagens prontas para OCR.")

        # Processar cada imagem selecionada com OCR
        for original_page_idx_0_based, imagem_obj in imagens_para_ocr:
            num_pagina_real_1_based = original_page_idx_0_based + 1
            logger.debug(f"Aplicando OCR na página {num_pagina_real_1_based}...")
            
            # Aplicar OCR na imagem da página
            # Para converter o objeto de imagem PIL para algo que o EasyOCR aceita (como bytes ou ndarray):
            # import numpy as np
            # imagem_array = np.array(imagem_obj)
            # resultados_ocr = reader.readtext(imagem_array, ...)
            # OU, se o EasyOCR aceitar diretamente o objeto PIL (testar):
            resultados_ocr_pagina = reader.readtext(
                image=imagem_obj, # EasyOCR geralmente aceita caminhos de arquivo, bytes, ou numpy array.
                                    # Objetos PIL Image podem precisar de conversão.
                                    # Se `imagem_obj` for um objeto PIL.Image:
                                    # import numpy
                                    # image=numpy.array(imagem_obj)
                detail=0,       # detail=0 retorna apenas o texto
                paragraph=True, # Tenta agrupar texto em parágrafos
                batch_size=8,  # Ajustar conforme a VRAM da GPU ou capacidade da CPU
                # y_ths=0.5, # Ajustes finos de detecção de linha
                # low_text=0.4 # Limite inferior de confiança do texto
                # contrast_ths=0.1, # Ajuste de contraste (se necessário, geralmente não)
                # adjust_contrast=0.5 # Fator de ajuste de contraste (se necessário)
            )
            texto_pagina_ocr = "\n".join(resultados_ocr_pagina).strip()
            
            resultados_finais[num_pagina_real_1_based] = texto_pagina_ocr
            logger.debug(f"Página {num_pagina_real_1_based} OCRizada. Texto (primeiros 50 chars): '{texto_pagina_ocr[:50].replace('\n', ' ')}...'")

    except PDFInfoNotInstalledError:
        logger.error("Poppler não está instalado ou não foi encontrado no PATH. Verifique a instalação do Poppler.", exc_info=True)
        raise
    except (PDFPageCountError, PDFSyntaxError) as e:
        logger.error(f"Erro ao processar o PDF com pdf2image: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Ocorreu um erro durante a extração de texto com OCR: {e}", exc_info=True)
        raise
    
    logger.info(f"Extração OCR concluída. {len(resultados_finais)} página(s) processada(s).")
    return resultados_finais

r'''
Exemplo de uso:
pdf_path = r'C:\Users\edson.eab\Downloads\PDFs-Testes\08500.014141_2025-47.pdf'  # 199-203
pdf_path = r'C:\Users\edson.eab\Downloads\PDFs-Testes\08500.014072_2025-71.pdf'  # 16 e 6

Extrair apenas as páginas 2, 5 e 8 (índices 1, 4 e 7 no sistema (zero-based)
paginas_alvo = [200, 201, 202] # indices

for pagina, texto in texto_extraido.items():
   print(f"\n--- PÁGINA {pagina} ---")
   print(texto)

result = extrair_texto_pdf(pdf_path, paginas_alvo)   , gpu_enabled=False)

for pagina, texto in result.items():
   with open(f"pagina_{pagina}_texto.txt", "w", encoding="utf-8") as f:
       f.write(texto)
'''

### Funcs Testes #########################################################################################

def teste_examples_analyzer(pdf_paths: List[str], token_limit_for_summary: int = 100000): # Modificado para List[str]
    if not pdf_paths:
        print("Nenhum caminho de PDF fornecido para o teste.")
        return
    
    for pdf_path_item in pdf_paths:
        if not os.path.exists(pdf_path_item):
            print(f"Arquivo PDF de exemplo não encontrado: {pdf_path_item}")
            return # Interrompe se um arquivo não for encontrado

    # 2. Instanciar o analisador de documentos com a estratégia escolhida
    analyzer = PDFDocumentAnalyzer()

    # 3. Informar os arquivos que serão processados
    pdf_names_display = ", ".join([os.path.basename(p) for p in pdf_paths])
    print(f"Analisando o(s) documento(s) PDF: {pdf_names_display}...\n")
    
    try:
        # 4. Analisar o(s) documento(s) PDF em lote
        # O método analyze_pdf_document_batch processa todas as páginas de todos os arquivos.
        processed_data_batch = analyzer.analyze_pdf_documents(pdf_paths)
        
        if not processed_data_batch:
            print("Nenhum dado foi processado do(s) PDF(s).")
            return

        print(f"\n--- Dados Processados por Página (primeiras 5 páginas globais ou menos) ---")
        # Limita a exibição para não poluir o console em lotes grandes
        display_limit = 5 
        items_displayed_count = 0
        for global_page_key, data in processed_data_batch.items():
            if items_displayed_count >= display_limit:
                print("...")
                break
            
            file_idx = data['file_index']
            page_idx_in_file = data['page_index_in_file']
            original_pdf_path_for_item = data['original_pdf_path'] # Renomeado para evitar conflito de nome
            
            print(f"  Arquivo {file_idx + 1} ({os.path.basename(original_pdf_path_for_item)}), Página {page_idx_in_file + 1} (Chave Global: {global_page_key}):")
            print(f"    Texto (primeiros 50 chars): '{data['text_stored'][:50]}...'")
            print(f"    Inteligível: {data['inteligible']}")
            print(f"    Palavras Únicas: {data['number_words']}")
            print(f"    Tokens: {data['number_tokens']}") # model_name_for_tokens é usado internamente
            print(f"    Score TF-IDF: {data['tf_idf_score']:.4f}")
            print(f"    Páginas Semelhantes (chaves): {analyzer.format_global_keys_for_display(data['semelhantes'])}")
            items_displayed_count +=1
        
        # 5. Filtrar e classificar páginas (baseado nos dados combinados)
        print("\n--- Classificando Páginas (Resultado Combinado) ---")
        
        (relevant_indices, 
         unintelligible_indices, 
         count_selected, 
         count_discarded_similarity, 
         count_discarded_unintelligible) = analyzer.filter_and_classify_pages(processed_data_batch)
        
        total_pages_in_report = len(processed_data_batch)

        print(f"  Total de páginas globais analisadas (que tinham texto extraível): {total_pages_in_report}")
        print(f"  Páginas Selecionadas como Relevantes: {count_selected} (Chaves: {analyzer.format_global_keys_for_display(relevant_indices)})")
        print(f"  Páginas Descartadas por Ininteligibilidade: {count_discarded_unintelligible} (Chaves: {analyzer.format_global_keys_for_display(unintelligible_indices)})")
        print(f"  Páginas Descartadas por Similaridade (Redundância): {count_discarded_similarity}")

        if total_pages_in_report > 0:
            perc_selected = (count_selected / total_pages_in_report) * 100
            perc_discard_sim = (count_discarded_similarity / total_pages_in_report) * 100
            perc_discard_unint = (count_discarded_unintelligible / total_pages_in_report) * 100
            print(f"  Proporções: {perc_selected:.1f}% selecionadas, "
                  f"{perc_discard_unint:.1f}% descartadas (ininteligíveis), "
                  f"{perc_discard_sim:.1f}% descartadas (similares).")
            
        # 6. Agrupar textos relevantes respeitando o limite de tokens
        if relevant_indices:
            print(f"\n--- Agrupando Texto Relevante (limite de {token_limit_for_summary} tokens) ---")
            # model_name_for_tokens é usado internamente por group_texts_by_relevance_and_token_limit
            str_pages, aggregated_text, tokens_antes, tokens_depois = analyzer.group_texts_by_relevance_and_token_limit(
                processed_page_data=processed_data_batch,
                relevant_page_ordered_indices=relevant_indices, # Já são global_page_key
                token_limit=token_limit_for_summary
            )
            print(f"  Páginas consideradas para o texto agregado (chaves formatadas): {str_pages}\n")
            print(f"  Texto Agregado (primeiros 300 caracteres):\n'{aggregated_text[:300]}...'\n")
            print(f"  Tokens das páginas selecionadas (antes da supressão): {tokens_antes}\n")
            print(f"  Tokens do texto agregado final (após supressão): {tokens_depois}\n")
            if tokens_antes > tokens_depois:
                supressed_tokens = tokens_antes - tokens_depois
                percentage_supressed = (supressed_tokens / tokens_antes) * 100 if tokens_antes > 0 else 0
                print(f"  Tokens suprimidos: {supressed_tokens} ({percentage_supressed:.2f}% do total original das páginas selecionadas)")
        else:
            print("\nNenhuma página relevante encontrada para agregação.")
        
        # Não retorna mais processed_data, pois o teste é para exibição/verificação
    
    except FileNotFoundError as fnf_err: # Embora já verificado no início
        print(f"Erro: {fnf_err}")
    except RuntimeError as rt_err:
        print(f"Erro de execução: {rt_err}")
    except Exception as e:
        print(f"Ocorreu um erro inesperado durante a análise: {e}")
        import traceback
        traceback.print_exc()

def teste_get_processed_text():
    pdf_paths = [r'C:\Users\edson.eab\Downloads\PDFs-Testes\08500.013511_2025-29.pdf']
    analyzer = PDFDocumentAnalyzer()
    processed_page_data_combined = analyzer.analyze_pdf_documents(pdf_paths)
    classified_data = analyzer.filter_and_classify_pages(processed_page_data_combined)
    relevant_indices, *_ = classified_data
    aggregated_info = analyzer.group_texts_by_relevance_and_token_limit(processed_page_data_combined, relevant_indices, 180000)
    _, processed_text, *_ = aggregated_info
    return processed_text

def teste_filters_pdf(get_embeddings_from_api):
    # preprocess_text_advanced=False
    # mode_filter_similar='bigger_content'

    from src.settings import api_key_test
    processor = PDFDocumentAnalyzer()
        
    processed_files_metadata, all_indices_in_batch, all_texts_for_storage_dict, all_texts_for_analysis_list = processor.extract_texts_and_preprocess_files([r'C:\Users\edson.eab\Downloads\PDFs-Testes\08500.014141_2025-47.pdf'])

    ready_embeddings_openai, *_ = get_embeddings_from_api(all_texts_for_analysis_list, api_key=api_key_test)
    ready_embeddings_sentence = get_vectors(all_texts_for_analysis_list, model_embedding='all-MiniLM-L6-v2')  

    assert processed_files_metadata

    combined_processed_page_data, all_global_page_keys_ordered = processor.build_combined_page_data(processed_files_metadata, 
                                                                        all_indices_in_batch, all_texts_for_storage_dict)

    assert all_texts_for_storage_dict and all_texts_for_analysis_list

    tf_idf_scores_array_combined, tfidf_vectors_combined = get_tfidf_scores(all_texts_for_analysis_list)

    assert len(ready_embeddings_openai) == len(all_texts_for_analysis_list)
    assert len(ready_embeddings_sentence) == len(all_texts_for_analysis_list)
   
    dict_embeddings = {
        'embeddings_openai': ready_embeddings_openai,
        'embeddings_sentence': ready_embeddings_sentence,
        'tdfidf_vectors': None}

    results = []
    p=0
    for mode_filter in ['get_pages_among_similars_groups', 'get_pages_among_similars_graphs']: # 'get_pages_by_tfidf_initial', 'get_pages_among_similars_matrix'
        for embeddings_k in ['embeddings_openai', 'embeddings_sentence']: # 'tdfidf_vectors'
            embedding_vectors_combined = dict_embeddings[embeddings_k]
            parametros = {
                'mode_main_filter': mode_filter,
                'embedding_vectors_combined': embedding_vectors_combined,
                'similarity_threshold': 0.78 if embeddings_k == 'tdfidf_vectors' else (0.91 if embeddings_k == 'embeddings_openai' else 0.85)
            }
            p+=1
                    
            final_selected_ordered_indices, unintelligible_indices_set, discarded_by_similarity_count = processor.filter_and_classify_pages(combined_processed_page_data, 
                                        all_global_page_keys_ordered, parametros['embedding_vectors_combined'], tfidf_vectors_combined, tf_idf_scores_array_combined,
                                        mode_main_filter = parametros['mode_main_filter'], similarity_threshold=parametros['similarity_threshold'])
            print(f'''
            Processamento a partir do grupo de Parâmetros {p}: {embeddings_k} + {mode_filter}

            Páginas Relevantes consideradas: {len(final_selected_ordered_indices)}: \n\n{processor.format_global_keys_for_display(sorted(final_selected_ordered_indices))}

            Páginas Irrelevantes por Similaridade: {discarded_by_similarity_count}
            Páginas Descartadas (Ininteligíveis): {len(unintelligible_indices_set)} \n
            ''')
            print('==='*50)
            print('\n')
            
            results.append((f'{p}: {embeddings_k} + {mode_filter}', final_selected_ordered_indices))
    
    return results

    '''
    **Dados Resumidos (Páginas Relevantes Selecionadas de 727, 4 ininteligíveis):**

    | `mode_main_filter`                | `embeddings_openai` (limiar 0.87) | `embeddings_sentence` (limiar 0.87) | `tfidf_vectors` (limiar 0.80)  |
    | :-------------------------------- | :-------------------------------- | :---------------------------------- | :----------------------------- |
    | `get_pages_among_similars_matrix` | 66                                | 156                                 | 278                            |
    | `get_pages_among_similars_groups` | 186                               | 229                                 | 286                            |
    | `get_pages_among_similars_graphs` | **51**  -> 74                     | **125**    -> 104                   | **253**                        |
    | `get_pages_by_tfidf_initial`      | 66                                | 160                                 | 279                            |

    '''

def teste_analyze_page_differences(tupla_results):
    """
    Analisa uma lista de resultados de filtragem de páginas para encontrar as maiores diferenças.
    """
    import collections
    
    method_names, all_page_indices = [tp[0] for tp in tupla_results], [tp[1] for tp in  tupla_results]

    if len(method_names) != len(all_page_indices):
        raise ValueError("A lista de nomes de métodos e a lista de resultados devem ter o mesmo tamanho.")

    # Dicionário para rastrear quais métodos selecionaram cada página
    # Chave: page_index (int), Valor: lista de method_names (list[str])
    page_occurrences = collections.defaultdict(list)

    # Popula o dicionário
    for method_name, page_indices in zip(method_names, all_page_indices):
        for page_index in page_indices:
            page_occurrences[page_index].append(method_name)

    # Classifica as páginas com base na frequência
    total_methods = len(method_names)
    consensus_pages = []
    unique_pages = {}
    high_disagreement_pages = {} # Páginas que aparecem em 2 ou 3 grupos
    almost_consensus_pages = {}  # Páginas que aparecem em (total-2) ou (total-1) grupos

    sorted_pages = sorted(page_occurrences.keys())

    for page_index in sorted_pages:
        methods = page_occurrences[page_index]
        count = len(methods)
        

        if count == total_methods:
            consensus_pages.append(page_index)
        elif count == 1:
            unique_pages[page_index] = methods[0]
        elif 2 <= count <= 3: # Limiar para alta discordância
            high_disagreement_pages[page_index] = (count, methods)
        elif total_methods - 2 <= count < total_methods:
            # Identifica os métodos que *não* selecionaram a página
            missing_in = [name for name in method_names if name not in methods]
            almost_consensus_pages[page_index] = (count, missing_in)

    # Apresenta os resultados de forma clara
    print("Análise de Divergência entre os Métodos de Filtragem\n")
    print(f"Total de métodos analisados: {total_methods}")
    print("-" * 60)

    print(f"\n✅ PÁGINAS DE CONSENSO TOTAL ({len(consensus_pages)} páginas)")
    print("   (Selecionadas por todos os métodos)")
    print(f"   {consensus_pages}")
    print("-" * 60)

    print(f"\n❗️ PÁGINAS ÚNICAS ({len(unique_pages)} páginas)")
    print("   (Selecionadas por apenas 1 método - maior divergência)")
    for page, method in unique_pages.items():
        print(f"  - Pág {page}: Encontrada apenas por -> {method}")
    print("-" * 60)
    
    print(f"\n⚠️ PÁGINAS DE QUASE CONSENSO ({len(almost_consensus_pages)} páginas)")
    print("   (Selecionadas pela maioria, mas com exceções notáveis)")
    for page, (count, missing_methods) in almost_consensus_pages.items():
        print(f"  - Pág {page}: Encontrada por {count} métodos. Ausente em: {missing_methods}")
    print("-" * 60)

    print(f"\n❓ PÁGINAS DE ALTA DISCORDÂNCIA ({len(high_disagreement_pages)} páginas)")
    print("   (Selecionadas por apenas 2 ou 3 métodos)")
    for page, (count, methods) in high_disagreement_pages.items():
        # Para não poluir, podemos apenas listar a contagem
        print(f"  - Pág {page}: Selecionada por {count} métodos.")
    print("-" * 60)

from rich.console import Console
from rich.table import Table
import time # Para medição de tempo manual
import threading # Para execução paralela

def _worker_extract_strategy_performance(
    pdf_path: str,
    strategy_instance: PDFTextExtractorStrategy,
    results_list: list, # Lista para coletar resultados (compartilhada entre threads)
    lock: threading.Lock # Lock para acesso seguro à results_list
):
    """
    Função executada por cada thread para testar uma estratégia em um PDF.
    """
    pdf_name = os.path.basename(pdf_path)
    strategy_name = strategy_instance.__class__.__name__
    
    # Logger específico para a thread para melhor rastreamento, se necessário,
    # ou usar o logger global. Por simplicidade, usamos o logger global.
    # logger.info(f"Thread iniciada para: {pdf_name} com {strategy_name}")

    total_pages_str = "N/A"
    time_extraction_str = "N/A"
    total_chars_extracted_str = "N/A"
    error_obs_thread = None

    try:
        # 1. Obter número de páginas
        # Medição de tempo para get_total_pages pode ser menos crítica,
        # mas incluída para consistência se desejado.
        # _start_time_pages_thread = time.perf_counter()
        total_pages = strategy_instance.get_total_pages(pdf_path)
        # _time_pages_thread = time.perf_counter() - _start_time_pages_thread
        total_pages_str = str(total_pages)

        # 2. Extrair texto de todas as páginas e medir tempo
        start_time_extraction_thread = time.perf_counter()
        extracted_content_tuples = strategy_instance.extract_texts_from_pages(pdf_path, page_indices=None, check_inteligible=True)
        time_extraction_thread = time.perf_counter() - start_time_extraction_thread

        total_chars_extracted = sum(len(text) for _, text in extracted_content_tuples)
        
        time_extraction_str = f"{time_extraction_thread:.4f}"
        time_extraction_str_by_page = f"{time_extraction_thread / total_pages:.4f}"
        total_chars_extracted_str = str(total_chars_extracted)
        
        # Log dentro da thread (será intercalado no console)
        logger.info(f"  Resultado Thread '{strategy_name}' para '{pdf_name}': {time_extraction_thread:.4f}s, {total_pages_str} pgs, {total_chars_extracted_str} chars.")

    except NotImplementedError:
        error_obs_thread = "Não Implementada"
        logger.warning(f"  Thread '{strategy_name}' para '{pdf_name}': Não implementada.")
    except Exception as e:
        error_msg_thread = f"Erro: {type(e).__name__}"
        error_obs_thread = error_msg_thread
        logger.error(f"  ERRO Thread '{strategy_name}' para '{pdf_name}': {e}", exc_info=False) # exc_info=False para não poluir tanto o log de threads
    
    # Adiciona o resultado à lista compartilhada de forma thread-safe
    with lock:
        results_list.append({
            "PDF": pdf_name,
            "Strategy": strategy_name,
            "Pages": total_pages_str,
            "Extraction Time (s)": time_extraction_str,
            "Extraction Time/Page (s)": time_extraction_str_by_page,
            "Total Chars": total_chars_extracted_str,
            "Error/Obs": error_obs_thread,
            "_sort_key_pdf": pdf_name, # Para ordenação posterior
            "_sort_key_strategy": strategy_name # Para ordenação posterior
        })
    # logger.info(f"Thread finalizada para: {pdf_name} com {strategy_name}")

def test_extraction_strategies_performance(pdf_paths: List[str]):
    """
    Testa e compara o desempenho de diferentes estratégias de extração de texto
    em uma lista de arquivos PDF, usando threads para processar cada estratégia em paralelo por PDF.
    """
    if not pdf_paths:
        logger.warning("Nenhum caminho de PDF fornecido para o teste de desempenho de extração.")
        return

    valid_pdf_paths = []
    for pdf_path_item in pdf_paths:
        if not os.path.exists(pdf_path_item):
            logger.error(f"Arquivo PDF de teste não encontrado: {pdf_path_item}. Pulando este arquivo.")
        else:
            valid_pdf_paths.append(pdf_path_item)

    if not valid_pdf_paths:
        logger.error("Nenhum arquivo PDF válido encontrado para o teste de desempenho.")
        return

    strategies_to_test: List[PDFTextExtractorStrategy] = [
        FitzExtractor(),
        PdfPlumberExtractor(),
        PyPdfExtractor(),
    ]

    results_data_collected = [] # Lista para coletar resultados das threads
    threads_list = []
    results_collection_lock = threading.Lock() # Lock para proteger o acesso a results_data_collected

    logger.info(f"--- Iniciando Teste de Desempenho de Extração (com Threads) para {len(valid_pdf_paths)} PDF(s) ---")
    start_total_test_time = time.perf_counter()

    for pdf_path_current in valid_pdf_paths:
        pdf_name_current = os.path.basename(pdf_path_current)
        logger.info(f"\nDisparando threads de extração para PDF: {pdf_name_current}")

        for strategy_instance_current in strategies_to_test:
            thread = threading.Thread(
                target=_worker_extract_strategy_performance,
                args=(pdf_path_current, strategy_instance_current, results_data_collected, results_collection_lock)
            )
            threads_list.append(thread)
            thread.start()

    # Aguarda todas as threads terminarem
    logger.info(f"\nAguardando {len(threads_list)} threads de extração concluírem...")
    for thread_item in threads_list:
        thread_item.join()
    
    end_total_test_time = time.perf_counter()
    total_test_duration = end_total_test_time - start_total_test_time
    logger.info(f"Todas as threads concluídas. Tempo total do teste de desempenho: {total_test_duration:.2f}s")

    # Ordenar os resultados para uma apresentação mais consistente na tabela
    # (Opcional, mas bom se a ordem de conclusão das threads variar)
    results_data_sorted = sorted(results_data_collected, key=lambda x: (x["_sort_key_pdf"], x["_sort_key_strategy"]))

    # Imprimir tabela com Rich
    if not results_data_sorted:
        logger.info("\nNenhum resultado de desempenho para exibir na tabela.")
        return

    console = Console()
    table = Table(title=f"Comparativo de Desempenho (Threads) - {len(valid_pdf_paths)} PDFs",
                  show_header=True, header_style="bold magenta", show_lines=True)

    table.add_column("Arquivo PDF", style="cyan", min_width=20, overflow="fold")
    table.add_column("Estratégia", style="magenta", min_width=20)
    table.add_column("Páginas", justify="right", style="green")
    table.add_column("Tempo Extração Total (s)", justify="right", style="yellow")
    table.add_column("Tempo Extração p/Page (s)", justify="right", style="yellow")
    table.add_column("Total Caracteres", justify="right", style="blue")
    table.add_column("Observação/Erro", style="red", min_width=15, overflow="fold")

    for item in results_data_sorted:
        table.add_row(
            item["PDF"],
            item["Strategy"],
            item["Pages"],
            item["Extraction Time (s)"],
            item["Extraction Time/Page (s)"],
            item["Total Chars"],
            item["Error/Obs"] or ""
        )
    
    print("\n")
    console.print(table)
    logger.info(f"--- Teste de Desempenho de Extração (com Threads) Concluído ---")

r'''
# Lista de PDFs para o teste de desempenho

pdf_paths_for_perf_test = [r'C:\Users\edson.eab\Downloads\PDFs-Testes\08500.013511_2025-29.pdf',
r'C:\Users\edson.eab\Downloads\PDFs-Testes\08500.014072_2025-71.pdf',
r'C:\Users\edson.eab\Downloads\PDFs-Testes\08500.014141_2025-47.pdf']

pdf_paths_for_perf_test = [r'C:\Users\edson.eab\Downloads\PDFs-Testes\08500.014141_2025-47.pdf']

test_extraction_strategies_performance(pdf_paths_for_perf_test)


'''

### Funcs Testes extras:

def build_key_map_for_parts(processor: PDFDocumentAnalyzer, part_pdf_paths: List[str]) -> Tuple[Dict[str, str], List[str]]:
    """
    Constrói um mapa de chaves das partes para as chaves equivalentes do cenário de PDF único.
    Retorna o mapa e a lista ordenada de chaves globais das partes.
    """
    key_map_parts_to_single: Dict[str, str] = {}
    
    # Executa os passos iniciais para obter as chaves globais ordenadas das partes
    processed_files_metadata_p, indices_p, storage_p, _ = \
        processor.extract_texts_and_preprocess_files(part_pdf_paths)

    _, all_global_page_keys_ordered_p = \
        processor.build_combined_page_data(processed_files_metadata_p, indices_p, storage_p)

    # Cria o mapa: a chave da parte mapeia para uma chave como se fosse do PDF único (file_index 0)
    for i, part_key in enumerate(all_global_page_keys_ordered_p):
        # A chave equivalente no cenário de PDF único teria file_index 0 e page_index_in_file sequencial
        single_equivalent_key = f"file0_page{i}" 
        key_map_parts_to_single[part_key] = single_equivalent_key
        
    return key_map_parts_to_single, all_global_page_keys_ordered_p

def adjust_result_parts(
    result_parts_raw: Dict[str, Dict[str, Any]], 
    key_map_parts_to_single: Dict[str, str],
    original_pdf_path_single: str
) -> Dict[str, Dict[str, Any]]:
    """Ajusta o resultado das partes para ser comparável com o resultado do PDF único."""
    result_parts_adjusted: Dict[str, Dict[str, Any]] = {}

    for part_key, page_data_part in result_parts_raw.items():
        if part_key not in key_map_parts_to_single:
            logger.warning(f"Chave da parte '{part_key}' não encontrada no mapa de chaves. Pulando esta página.")
            continue

        single_key_equivalent = key_map_parts_to_single[part_key]
        
        adjusted_page_data = page_data_part.copy()
        adjusted_page_data['file_index'] = 0 # Corrigido para o cenário de PDF único
        adjusted_page_data['original_pdf_path'] = original_pdf_path_single # Corrigido
        
        # page_index_in_file é o índice da página DENTRO do arquivo original único
        # Derivado da single_key_equivalent (formato "0_X")
        try:
            page_index_str = single_key_equivalent.split('_page')[-1] 
            adjusted_page_data['page_index_in_file'] = int(page_index_str)
        except (IndexError, ValueError):
            logger.error(f"Não foi possível derivar page_index_in_file de '{single_key_equivalent}'.")
            # Pode ser necessário pular esta página ou atribuir um valor padrão.
            # Por agora, mantenha o antigo se falhar, mas logue o erro.

        # Ajustar chaves 'semelhantes'
        adjusted_semelhantes = []
        if 'semelhantes' in page_data_part and isinstance(page_data_part['semelhantes'], list):
            for sk_part in page_data_part['semelhantes']:
                if sk_part in key_map_parts_to_single:
                    adjusted_semelhantes.append(key_map_parts_to_single[sk_part])
                else:
                    logger.warning(f"Chave semelhante '{sk_part}' da parte não encontrada no mapa para '{part_key}'.")
        adjusted_page_data['semelhantes'] = sorted(adjusted_semelhantes) # Ordenar para comparação consistente

        result_parts_adjusted[single_key_equivalent] = adjusted_page_data
        
    return result_parts_adjusted

def compare_page_results(key: str, data_single: Dict[str, Any], data_part_adj: Dict[str, Any]) -> bool:
    """Compara os dados de uma única página, reportando diferenças."""
    import math
    is_equivalent = True
    logger.info(f"\n--- Comparando página com chave (equivalente single): {key} ---")

    fields_to_compare = [
        'text_stored', 'number_words', 'number_tokens', 
        'inteligible', 'file_index', 'page_index_in_file', 'original_pdf_path'
    ]
    float_fields = ['tf_idf_score']

    for field in fields_to_compare:
        val_single = data_single.get(field)
        val_part = data_part_adj.get(field)
        if val_single != val_part:
            logger.warning(f"  DIFERENÇA em '{field}':")
            logger.warning(f"    Single: {val_single}")
            logger.warning(f"    Partes: {val_part}")
            is_equivalent = False
        else:
            logger.info(f"  OK '{field}': {val_single}")

    for field in float_fields:
        val_single = data_single.get(field, 0.0)
        val_part = data_part_adj.get(field, 0.0)
        if not math.isclose(val_single, val_part, rel_tol=1e-4, abs_tol=1e-4): # Tolerância para floats
            logger.warning(f"  DIFERENÇA em '{field}':")
            logger.warning(f"    Single: {val_single}")
            logger.warning(f"    Partes: {val_part}")
            is_equivalent = False
        else:
            logger.info(f"  OK '{field}': {val_single}")
            
    # Comparar 'semelhantes' (como conjuntos, pois a ordem foi ajustada para sorted list)
    semelhantes_single = set(data_single.get('semelhantes', []))
    semelhantes_part = set(data_part_adj.get('semelhantes', []))
    if semelhantes_single != semelhantes_part:
        logger.warning(f"  DIFERENÇA em 'semelhantes':")
        logger.warning(f"    Single: {sorted(list(semelhantes_single))}")
        logger.warning(f"    Partes: {sorted(list(semelhantes_part))}")
        is_equivalent = False
    else:
        logger.info(f"  OK 'semelhantes': {sorted(list(semelhantes_single))}")
        
    return is_equivalent

def test_bacths_results():
    """Função principal do teste interativo."""
    original_pdf = r'C:\Users\edson.eab\Downloads\PDFs-Testes\08500.014072_2025-71.pdf'
    parts_pdfs = [r'C:\Users\edson.eab\Downloads\PDFs-Testes\01_08500.014072_2025-71.pdf',
                  r'C:\Users\edson.eab\Downloads\PDFs-Testes\11_08500.014072_2025-71.pdf']

    if not original_pdf or not parts_pdfs:
        logger.info("Inputs inválidos. Encerrando o teste.")
        return

    processor = PDFDocumentAnalyzer()

    # --- Cenário 1: PDF Único ---
    logger.info(f"\n=== Processando PDF ÚNICO: {original_pdf} ===")
    result_single_pdf = processor.analyze_pdf_documents([original_pdf])
    if not result_single_pdf:
        logger.error("Falha ao processar o PDF único. Não é possível continuar a comparação.")
        return

    # --- Cenário 2: PDFs Particionados ---
    logger.info(f"\n=== Processando PDFs PARTICIONADOS: {parts_pdfs} ===")
    result_parts_raw = processor.analyze_pdf_documents(parts_pdfs)
    if not result_parts_raw:
        logger.error("Falha ao processar os PDFs particionados. Não é possível continuar a comparação.")
        return

    # Construir o mapa de chaves para ajustar os resultados das partes
    key_map, _ = build_key_map_for_parts(processor, parts_pdfs)
    if not key_map:
         logger.error("Mapa de chaves não pôde ser construído. Verifique os logs de 'build_key_map_for_parts'.")
         return

    # Ajustar os resultados das partes para serem comparáveis
    result_parts_adjusted = adjust_result_parts(result_parts_raw, key_map, original_pdf)

    # --- Comparação ---
    logger.info("\n=== COMPARAÇÃO DOS RESULTADOS ===")
    
    # Verificar se o número de páginas processadas é o mesmo
    num_pages_single = len(result_single_pdf)
    num_pages_parts = len(result_parts_adjusted)

    logger.info(f"Número de páginas (após extração e combinação):")
    logger.info(f"  PDF Único: {num_pages_single}")
    logger.info(f"  PDFs Particionados (ajustado): {num_pages_parts}")

    if num_pages_single == 0 and num_pages_parts == 0:
        logger.info("Ambos os cenários resultaram em zero páginas processadas. Teste inconclusivo nesse aspecto, mas os fluxos rodaram.")
        return
        
    if num_pages_single != num_pages_parts:
        logger.error(f"DIFERENÇA CRÍTICA: Número de páginas processadas diverge! Single: {num_pages_single}, Partes: {num_pages_parts}")
        logger.error("Isso pode indicar problemas na extração de texto ou na lógica de combinação das partes.")
        logger.info("Chaves do PDF único:" + str(sorted(result_single_pdf.keys())))
        logger.info("Chaves dos PDFs Particionados (ajustado):" + str(sorted(result_parts_adjusted.keys())))
        # Não adianta prosseguir com a comparação página a página se o número de páginas difere muito
        # ou se as chaves não batem.
        #return # Descomente se quiser parar aqui em caso de divergência no número de páginas

    all_pages_equivalent = True
    
    # Comparar cada página
    # Usar as chaves do resultado do PDF único como referência, pois são o "padrão ouro"
    sorted_single_keys = sorted(result_single_pdf.keys())

    for single_key in sorted_single_keys:
        if single_key not in result_parts_adjusted:
            logger.error(f"Página com chave '{single_key}' (do PDF único) NÃO ENCONTRADA no resultado ajustado das partes.")
            all_pages_equivalent = False
            continue # Pula para a próxima chave do PDF único

        page_data_single = result_single_pdf[single_key]
        page_data_part_adj = result_parts_adjusted[single_key]

        if not compare_page_results(single_key, page_data_single, page_data_part_adj):
            all_pages_equivalent = False
            
    # Checar se há chaves no resultado ajustado das partes que não existem no resultado do PDF único
    # (Isso pode acontecer se a lógica de `build_key_map_for_parts` ou `adjust_result_parts` tiver problemas)
    for part_adj_key in result_parts_adjusted.keys():
        if part_adj_key not in result_single_pdf:
            logger.error(f"Chave '{part_adj_key}' (do resultado ajustado das partes) NÃO ENCONTRADA no resultado do PDF único.")
            all_pages_equivalent = False


    if all_pages_equivalent and num_pages_single == num_pages_parts and num_pages_single > 0 :
        logger.info("\n\nRESULTADO FINAL: SUCESSO! Os resultados do PDF único e dos PDFs particionados (após ajustes) são equivalentes.")
    else:
        logger.error("\n\nRESULTADO FINAL: FALHA! Foram encontradas divergências entre os resultados. Verifique os logs acima.")

