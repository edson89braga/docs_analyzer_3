DEBUG_MODE = False

from rich import print
from src.utils import timing_decorator

### nltk_initializer:
import nltk
import warnings

def initialize_nltk_data():
    """
    Verifica e baixa os recursos NLTK necessários ('punkt', 'stopwords')
    se eles ainda não estiverem presentes.
    """
    resources = ["punkt", "stopwords"]
    for resource in resources:
        try:
            if resource == "punkt":
                nltk.data.find(f'tokenizers/{resource}')
            elif resource == "stopwords":
                nltk.data.find(f'corpora/{resource}')
        except nltk.downloader.DownloadError:
            nltk.download(resource, quiet=True)
        except Exception as e:
            # Captura outras exceções, como problemas de rede durante a busca
            warnings.warn(f"Could not verify NLTK resource {resource} due to: {e}. Download will be attempted.")
            try:
                nltk.download(resource, quiet=True)
            except Exception as download_exc:
                warnings.warn(f"Failed to download NLTK resource {resource}: {download_exc}")

# Executa a inicialização quando este módulo é importado
initialize_nltk_data()

### pdf_extraction_strategies: #########################################################################################
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional, Union, Set

import pdfplumber
from PyPDF2 import PdfReader
import fitz

class PDFTextExtractorStrategy(ABC):
    """Interface abstrata para estratégias de extração de texto de PDFs."""

    @abstractmethod
    def get_total_pages(self, pdf_path: str) -> int:
        """Retorna o número total de páginas do PDF."""
        pass

    @abstractmethod
    def extract_texts_from_pages(self, pdf_path: str, page_indices: Optional[List[int]] = None, check_inteligible: bool = False) -> List[Tuple[int, str]]:
        """
        Extrai textos de páginas específicas de um PDF.

        Args:
            pdf_path (str): Caminho do arquivo PDF.
            page_indices (Optional[List[int]]): Índices das páginas a serem extraídas (base 0).
                                                 Se None, todas as páginas são processadas.

        Returns:
            List[Tuple[int, str]]: Lista de tuplas, onde cada tupla contém o índice da página (base 0) e seu texto.
        """
        pass

class PdfPlumberExtractor(PDFTextExtractorStrategy):
    """Estratégia de extração de texto usando pdfplumber."""

    def get_total_pages(self, pdf_path: str) -> int:
        with pdfplumber.open(pdf_path) as pdf:
            return len(pdf.pages)

    @timing_decorator()
    def extract_texts_from_pages(self, pdf_path: str, page_indices: Optional[List[int]] = None, check_inteligible: bool = False) -> List[Tuple[int, str]]:
        content_by_page = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                total_pages_in_pdf = len(pdf.pages)
                
                if page_indices is None:
                    # Processa todas as páginas se page_indices não for fornecido
                    indices_to_process = list(range(total_pages_in_pdf))
                else:
                    # Filtra índices para garantir que estão dentro dos limites do PDF
                    indices_to_process = [idx for idx in page_indices if 0 <= idx < total_pages_in_pdf]

                for p_idx in indices_to_process:
                    page_pdf = pdf.pages[p_idx]
                    text = page_pdf.extract_text() or ""  # Garante que o texto não seja None
                    content_by_page.append((p_idx, text))
            
            if check_inteligible:
                print_text_intelligibility(content_by_page)

            return content_by_page
        except Exception as e:
            # Idealmente, o logger viria daqui ou seria injetado.
            # Por simplicidade, relançamos a exceção para ser tratada pelo chamador.
            # logger.error(f"Erro ao extrair textos do PDF {os.path.basename(pdf_path)} com PdfPlumber: {str(e)}")
            raise RuntimeError(f"PdfPlumber extraction error for {pdf_path}: {e}")

class PyPdfExtractor(PDFTextExtractorStrategy):
    """Estratégia de extração de texto usando pypdf """

    def get_total_pages(self, pdf_path: str) -> int:
        try:
            reader = PdfReader(pdf_path)
            return len(reader.pages)
            #raise NotImplementedError("PyPdfExtractor.get_total_pages não implementado neste exemplo.")
        except Exception as e:
            raise RuntimeError(f"PyPdf extraction error (get_total_pages) for {pdf_path}: {e}")

    def extract_texts_from_pages(self, pdf_path: str, page_indices: Optional[List[int]] = None, check_inteligible: bool = False) -> List[Tuple[int, str]]:
        content_by_page = []
        try:
            reader = PdfReader(pdf_path)
            total_pages_in_pdf = len(reader.pages)
            if page_indices is None:
                indices_to_process = list(range(total_pages_in_pdf))
            else:
                indices_to_process = [idx for idx in page_indices if 0 <= idx < total_pages_in_pdf]
          
            for p_idx in indices_to_process:
                page_pdf = reader.pages[p_idx]
                text = page_pdf.extract_text() or ""
                content_by_page.append((p_idx, text))
            
            if check_inteligible:
                print_text_intelligibility(content_by_page)
                
            return content_by_page
        except Exception as e:
            raise RuntimeError(f"PyPdf extraction error for {pdf_path}: {e}")
        #raise NotImplementedError("PyPdfExtractor.extract_texts_from_pages não implementado neste exemplo. Descomente e instale pypdf para usar.")

class FitzExtractor(PDFTextExtractorStrategy):
    """Estratégia de extração de texto usando Docling"""

    def get_total_pages(self, pdf_path: str) -> int:
        try:
            doc = fitz.open(pdf_path)
            return len(doc)
        except Exception as e:
            raise RuntimeError(f"PyPdf extraction error (get_total_pages) for {pdf_path}: {e}")

    def extract_texts_from_pages(self, pdf_path: str, page_indices: Optional[List[int]] = None, check_inteligible: bool = False) -> List[Tuple[int, str]]:
        content_by_page = []
        try:
            doc = fitz.open(pdf_path)
            total_pages_in_pdf = len(doc)
            if page_indices is None:
                indices_to_process = list(range(total_pages_in_pdf))
            else:
                indices_to_process = [idx for idx in page_indices if 0 <= idx < total_pages_in_pdf]
          
            for p_idx in indices_to_process:
                text = doc[p_idx].get_text() or ""
                content_by_page.append((p_idx, text))

            if check_inteligible:
                print_text_intelligibility(content_by_page)

            return content_by_page
        except Exception as e:
            raise RuntimeError(f"PyPdf extraction error for {pdf_path}: {e}")
        
### text_processing_utils: #########################################################################################
import re
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException
# Supondo que src.utils.count_tokens existe
from src.utils import count_tokens as util_count_tokens

model_name_for_tokens: str = "gpt-3.5-turbo" # Adicionado para consistência com count_tokens e reduce_text

def function_preprocess_text_basic(text: str, clean_spaces=True, lowercase=False) -> str:
    """
    Realiza pré-processamento básico: remove espaços extras e converte para minúsculas.
    Resultado usado para as funções count_tokens, count_words, e is_text_intelligible.
    """
    if clean_spaces:
        text = re.sub(r'\s+', ' ', text)
    if lowercase:
        text = text.lower()
    return text

def function_preprocess_text_advanced(text: str) -> str:
    """
    Realiza pré-processamento avançado: remove caracteres especiais e pontuação,
    exceto os necessários para datas/horários, após o pré-processamento básico.

    Resultado usado apenas para as funções analyze_text_similarity e calculate_text_relevance_tfidf.
    """
    text = function_preprocess_text_basic(text)
    text = re.sub(r'[^\w\sÀ-ÿ.,!?;:()\'\"-]', '', text)
    return text

def count_unique_words(text: str) -> int:
    """Conta o número de palavras únicas em um texto."""
    return len(set(text.split()))

allowed_langs = ['pt', 'it', 'gl', 'es', 'fr']

def is_text_intelligible(text: str, cid_threshold: float = 0.7) -> bool:
    """
    Verifica se o texto é inteligível em um conjunto de idiomas,
    considerando também a alta ocorrência de padrões (cid:N).

    Args:
        text (str): Texto a ser analisado.
        allowed_langs (Optional[List[str]]): Idiomas permitidos. Padrão: ['pt', 'it', 'gl', 'es', 'fr'].
        cid_threshold (float): Proporção máxima de '(cid:N)' permitida para o texto ser considerado
                               potencialmente inteligível antes da detecção de idioma.
                               Ex: 0.7 significa que se mais de 70% do texto for (cid:N) ou similar,
                               é considerado ininteligível.

    Returns:
        bool: True se o texto for considerado inteligível, False caso contrário.
    """
    cleaned_text = text.strip()
    if not cleaned_text:
        return False

    # Contar ocorrências de "(cid:"  Character Identifier
    # Usamos uma expressão regular mais simples para contar as ocorrências de "(cid:..."
    cid_occurrences = len(re.findall(r'\(cid:\d+\)', cleaned_text)) # \d+ para um ou mais dígitos

    # Se não houver (cid:N), o comprimento de cada é 0.
    # Se houver, estimar o comprimento ocupado por eles.
    # Cada "(cid:N)" tem pelo menos 6 caracteres: ( c i d : N )
    # Se N tem 1 dígito, 6 chars. Se 2 dígitos, 7 chars.
    # Vamos usar uma média ou um mínimo, por exemplo, 6 caracteres por ocorrência.
    estimated_cid_chars_length = cid_occurrences * 6 # Uma estimativa conservadora

    if len(cleaned_text) > 0 and estimated_cid_chars_length / len(cleaned_text) > cid_threshold:
        #logger.debug(f"Texto considerado ininteligível devido à alta proporção de (cid:N) (>{cid_threshold*100}%).") # Adicione logger se disponível
        return False

    try:
        # Remover os (cid:N) antes de passar para langdetect pode ajudar
        text_for_langdetect = re.sub(r'\(cid:\d+\)', '', cleaned_text).strip()
        if not text_for_langdetect: # Se sobrou nada após remover (cid:N)
            return False
            
        lang = detect(text_for_langdetect)
        # logger.debug(f"Idioma detectado para o texto (sem cids): '{lang}'") # Adicione logger
        return lang in allowed_langs if lang else False
    except LangDetectException:
        # logger.debug("LangDetectException, texto considerado ininteligível.") # Adicione logger
        return False

def count_tokens(text: str, model_name: str) -> int:
    """Wrapper para a função de contagem de tokens utilitária."""
    return util_count_tokens(text, model_name=model_name)

### text_analysis_utils: #########################################################################################
from numpy import array as np_array
from numpy import ndarray as np_ndarray
from numpy import any as np_any

from nltk.corpus import stopwords
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import normalize as sk_normalize
from sklearn.feature_extraction.text import TfidfVectorizer

# Cache para o modelo SentenceTransformer para evitar recarregamentos
_sentence_model = None

def get_sentence_transformer_model(model_name: str = 'all-MiniLM-L6-v2'):
    global _sentence_model
    if _sentence_model is None:
        _sentence_model = SentenceTransformer(model_name)
    return _sentence_model

@timing_decorator()
def get_vectors(pages_texts, model_embedding: str = 'all-MiniLM-L6-v2'):
    print('\n', f'[DEBUG]: Modelo embeddings: {model_embedding}', '\n')
    model = get_sentence_transformer_model(model_embedding)
    vectors_combined = model.encode(pages_texts)

    if not isinstance(vectors_combined, np_ndarray):
        vectors_combined = np_array(vectors_combined)
    
    # Verifica se o array não está vazio
    if vectors_combined.size == 0:
        logger.warning(f"Array 'ready_embeddings' fornecido está vazio para o modelo '{model_embedding}'. Retornando matriz de similaridade vazia.")
        return np_array([])

    assert len(vectors_combined) == len(pages_texts), f"Quantidade de vetores ({len(vectors_combined)}) difere da quantidade de textos ({len(pages_texts)})."
    return vectors_combined

def get_similarity_matrix(vectors_combined, normalizer: bool = True):
    if normalizer: # vetores provenientes do tfidf são arrays de 1D e não podem ser normalizados
        vectors_combined = sk_normalize(vectors_combined)
    similarity_matrix = cosine_similarity(vectors_combined)
    return similarity_matrix

@timing_decorator()
def get_tfidf_scores(pages_texts: List[str], language: str = 'portuguese') -> np_array:
    """
    Calcula a relevância de cada texto (página) usando TF-IDF.
    Retorna um array com os scores TF-IDF para cada texto, e os vetores.
    """
    # Garante que stopwords para o idioma especificado estejam disponíveis
    try:
        current_stopwords = list(set(stopwords.words(language)))
    except OSError: # Pode ocorrer se o corpus 'stopwords' para o idioma não existir
        warnings.warn(f"Stopwords para '{language}' não encontradas. Tentando baixar...")
        try:
            nltk.download('stopwords', quiet=True)
            current_stopwords = list(set(stopwords.words(language)))
        except Exception as e:
            warnings.warn(f"Falha ao baixar stopwords para '{language}': {e}. Usando lista vazia de stopwords.")
            current_stopwords = []
            
    vectorizer = TfidfVectorizer(stop_words=current_stopwords)
    tf_idf_matrix = vectorizer.fit_transform(pages_texts)
    
    tf_idf_scores = np_array(tf_idf_matrix.sum(axis=1)).flatten()  # converte para array 1D
    
    return tf_idf_scores, tf_idf_matrix

def get_similar_items_indices(item_index: int, similarity_matrix: np_array, similarity_threshold: float = 0.87, exclude_idx=[]) -> List[int]:
    """
    Identifica itens semelhantes a um item específico com base na matriz de similaridade.
    """
    if not (0 <= item_index < similarity_matrix.shape[0]):
        return [] # Índice fora dos limites
        
    similar_indices = []
    for j in range(similarity_matrix.shape[0]):
        if j==item_index or j in exclude_idx:
            continue
        if similarity_matrix[item_index, j] > similarity_threshold:
            similar_indices.append(j)
    return similar_indices

from scipy.sparse import vstack
from scipy.sparse.base import spmatrix

def check_if_has_similar_items(
    current_page_vector: Union[np_ndarray, spmatrix], # Ou seu tipo np_array
    selected_matrix: Union[np_ndarray, spmatrix],     # Ou seu tipo np_array
    similarity_threshold: float = 0.87
) -> bool:
    """
    Verifica se current_page_vector é similar a algum vetor na selected_matrix.
    current_page_vector deve ser 2D (1, N_features).
    selected_matrix deve ser 2D (K_selecionados, N_features).
    """
    # Validações (importantes se esta função for mais genérica):
    if not hasattr(selected_matrix, 'shape') or selected_matrix.shape[0] == 0:
        # Se selected_matrix estiver vazia (nenhuma página selecionada ainda), não há similaridade.
        # No seu fluxo atual, isso é coberto por `if not relevant_indices_candidates:`,
        # então selected_matrix nunca deveria estar vazia quando esta função é chamada.
        return False
    if current_page_vector.ndim == 1: # Garante que o vetor atual seja 2D
        current_page_vector = current_page_vector.reshape(1, -1)


    similarities = cosine_similarity(current_page_vector, selected_matrix)
    if np_any(similarities >= similarity_threshold):
        return True
    return False

### pdf_document_analyzer: #########################################################################################
import os
from typing import Dict, Any
# Importando as funções e classes dos "módulos" acima
# from .pdf_extraction_strategies import PDFTextExtractorStrategy, PdfPlumberExtractor (se fossem arquivos separados)
# from .text_processing_utils import ( (se fossem arquivos separados)
#     preprocess_text_basic, preprocess_text_advanced,
#     count_unique_words, is_text_intelligible, count_tokens
# )
# from .text_analysis_utils import ( (se fossem arquivos separados)
#     analyze_text_similarity, calculate_text_relevance_tfidf,
#     get_similar_items_indices
# )
# Supondo que as funções de src.utils existem
from src.utils import timing_decorator, reduce_text_to_limit, get_string_intervalos
# Supondo que src.logger.logger existe
from src.logger.logger import LoggerSetup
logger = LoggerSetup.get_logger(__name__)

# Importa o inicializador do NLTK para garantir que os dados sejam baixados
# import src.core.nltk_initializer (se fosse arquivo separado)

def print_text_intelligibility(texts_normalized: list[tuple[int, str]]):
    print('\n')
    for p_idx, text in texts_normalized:
        is_intelligible = is_text_intelligible(text) 
        if not is_intelligible:
            try:
                lang = detect(text)
                logger.warning(f'[red]Página original {p_idx+1} considerada ininteligível ({lang}) / Qtde caracteres: {len(text)}')
            except LangDetectException:
                logger.warning(f'[red]Página original {p_idx+1} considerada ininteligível (não detectado) / Qtde caracteres: {len(text)}')
    print('\n')

import networkx as nx

class PDFDocumentAnalyzer:
    """
    Classe principal para processamento e análise de documentos PDF.
    Orquestra a extração de texto, pré-processamento, análise e classificação de páginas.
    """
    def __init__(self, extractor_strategy: PDFTextExtractorStrategy = FitzExtractor()):
        self.extractor = extractor_strategy

    def get_pdf_page_count(self, pdf_path: str) -> int:
        """Obtém o número total de páginas de um arquivo PDF usando a estratégia configurada."""
        return self.extractor.get_total_pages(pdf_path)

    def _generate_global_page_key(self, file_index: int, page_index_in_file: int) -> str:
        """Gera uma chave única global para uma página. Ex: 'file0_page15'"""
        return f"file{file_index}_page{page_index_in_file}"

    def format_global_keys_for_display(self, global_keys: Union[List[str], Set[str]]) -> str:
        """
        Converte uma lista de global_page_key em uma string formatada para display.
        Exemplo: ["file0_page0", "file0_page1", "file0_page2", "file1_page0", "file1_page1"] => "Arq1 Pág1-3, Arq2 Pág1-2"
        
        Args:
            global_keys (Union[List[str], Set[str]]): Lista ou conjunto de global_page_key (str)
        
        Returns:
            str: String formatada para display
        """
        if not global_keys: 
            return "Nenhuma"

        parsed_pages = []
        for key in global_keys:
            match = re.match(r"file(\d+)_page(\d+)", key)
            if match:
                file_num = int(match.group(1)) + 1 # Para ser 1-based
                page_num = int(match.group(2)) + 1 # Para ser 1-based
                parsed_pages.append({'file': file_num, 'page': page_num, 'original_key': key})
        
        if not parsed_pages: 
            return ", ".join(global_keys) # Fallback

        # Ordena primeiro por arquivo, depois por página
        parsed_pages.sort(key=lambda x: (x['file'], x['page']))
        
        output_parts = []
        current_file = -1
        current_interval_start = -1
        
        for p_info in parsed_pages:
            if p_info['file'] != current_file: # Mudou de arquivo
                if current_interval_start != -1: # Fecha intervalo anterior
                    if current_page_in_interval == current_interval_start:
                        output_parts.append(f"Arq{current_file} Pág{current_interval_start}")
                    else:
                        output_parts.append(f"Arq{current_file} Pág{current_interval_start}-{current_page_in_interval}")
                current_file = p_info['file']
                current_interval_start = p_info['page']
                current_page_in_interval = p_info['page']
            elif p_info['page'] == current_page_in_interval + 1: # Continua intervalo
                current_page_in_interval = p_info['page']
            else: # Quebrou intervalo no mesmo arquivo
                if current_interval_start != -1:
                    if current_page_in_interval == current_interval_start:
                        output_parts.append(f"Arq{current_file} Pág{current_interval_start}")
                    else:
                        output_parts.append(f"Arq{current_file} Pág{current_interval_start}-{current_page_in_interval}")
                current_interval_start = p_info['page']
                current_page_in_interval = p_info['page']
        
        # Fecha o último intervalo
        if current_interval_start != -1:
            if current_page_in_interval == current_interval_start:
                output_parts.append(f"Arq{current_file} Pág{current_interval_start}")
            else:
                output_parts.append(f"Arq{current_file} Pág{current_interval_start}-{current_page_in_interval}")
        
        if output_parts:
            if all(part.startswith('Arq1 ') for part in output_parts): 
                output_parts = [part.replace('Arq1 ', '') for part in output_parts]

        #assert len(output_parts) == len(global_keys), f"Quantidade de partes formatadas diferente da quantidade de global_keys: \n\n{output_parts}\n\n{global_keys}\n)"
        return ", ".join(output_parts) if output_parts else "Nenhuma"

    ### ======================================================================================

    @timing_decorator()
    def extract_texts_and_preprocess_files(self, pdf_paths_ordered: List[str], clean_spaces=True, lowercase=False
                                           ) -> Tuple[List[Tuple[int, str]], List[List[int]], List[Dict[int, str]], List[str]]:
        """
        Extrai textos de um lote de PDFs ordenados e os pré-processa.
        Retorna uma tupla contendo metadados dos arquivos processados, listas de índices de páginas,
        textos pré-processados para armazenamento e textos pré-processados para análise.
        Retorna uma tupla: (processed_files_metadata, all_indices_in_batch, 
                            all_texts_for_storage_combined)
        """
        if not pdf_paths_ordered:
            logger.warning("Nenhum caminho de PDF fornecido para análise em lote.")
            return [], [], [], [], 0

        processed_files_metadata: List[Tuple[int, str]] = [] # ARMAZENA (original_file_idx, pdf_path)
        all_indices_in_batch: List[List[int]] = []
        all_texts_for_storage_dict: List[Dict[int, str]] = []
        all_texts_for_analysis_list: List[str] = []

        for file_idx, pdf_path in enumerate(pdf_paths_ordered):
            if not os.path.exists(pdf_path):
                logger.error(f"PDF não encontrado no lote: {pdf_path} (Índice {file_idx}). Pulando.")
                continue
            
            logger.info(f"Processando arquivo {file_idx + 1}/{len(pdf_paths_ordered)}: {os.path.basename(pdf_path)}")

            try:
                extracted_pages_content_single_file = self.extractor.extract_texts_from_pages(pdf_path, None)
                if not extracted_pages_content_single_file:
                    logger.warning(f"Nenhum texto extraído de {os.path.basename(pdf_path)}.")
                    continue

                actual_indices_in_file = [idx for idx, _ in extracted_pages_content_single_file]
                texts_for_storage_single_file = {idx: function_preprocess_text_basic(text, clean_spaces, lowercase) for idx, text in extracted_pages_content_single_file}
                texts_for_analysis_single_file = [function_preprocess_text_basic(text, clean_spaces, lowercase) for _, text in extracted_pages_content_single_file]

                processed_files_metadata.append((file_idx, pdf_path)) 
                all_indices_in_batch.append(actual_indices_in_file)
                all_texts_for_storage_dict.append(texts_for_storage_single_file)
                all_texts_for_analysis_list.extend(texts_for_analysis_single_file)
                
            except Exception as e:
                logger.error(f"Erro ao processar (extração/pré-proc) arquivo {os.path.basename(pdf_path)}: {e}", exc_info=True)
                continue 

        if not all_texts_for_analysis_list:
            logger.warning("Nenhum texto para análise combinado de todos os arquivos.")
        else:
            logger.info(f"Extração e pré-processamento em lote concluídos. Total de páginas com texto para análise: {len(all_texts_for_analysis_list)}")
        
        return processed_files_metadata, all_indices_in_batch, all_texts_for_storage_dict, all_texts_for_analysis_list

    def build_combined_page_data(self, 
                                 processed_files_metadata: List[Tuple[int, str]], 
                                 all_indices_in_batch: List[List[int]],
                                 all_texts_for_storage_dict: List[Dict[int, str]]
                                 ) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:

        combined_processed_page_data: Dict[str, Dict[str, Any]] = {}
        all_global_page_keys_ordered: List[str] = [] 
        
        for processed_list_idx, (file_idx, pdf_path) in enumerate(processed_files_metadata):

            actual_indices_in_file = all_indices_in_batch[processed_list_idx]
            texts_for_storage_single_file = all_texts_for_storage_dict[processed_list_idx]

            for page_idx_in_file in actual_indices_in_file:
                text_stored = texts_for_storage_single_file[page_idx_in_file]
            
                global_page_key = self._generate_global_page_key(file_idx, page_idx_in_file)
                all_global_page_keys_ordered.append(global_page_key)

                combined_processed_page_data[global_page_key] = {
                    'text_stored': text_stored,
                    'number_words': count_unique_words(text_stored),
                    'number_tokens': count_tokens(text_stored, model_name=model_name_for_tokens),
                    'inteligible': is_text_intelligible(text_stored),
                    'tf_idf_score': 0.0, 
                    'vector': None,
                    'semelhantes': [],
                    'file_index': file_idx, 
                    'page_index_in_file': page_idx_in_file,
                    'original_pdf_path': pdf_path
                }

        return combined_processed_page_data, all_global_page_keys_ordered

    @timing_decorator()
    def get_similarity_and_tfidf_score_docs(self, all_texts_for_analysis_list: List[str], 
                                            model_embedding: str = 'all-MiniLM-L6-v2', ready_embeddings: np_array = None, preprocess_text_advanced: bool = False, 
                                            ) -> Dict[str, Dict[str, Any]]:
        assert model_embedding in ['all-MiniLM-L6-v2', 'tfidf_vectorizer'], "Modelo de embeddings inválido. Deve ser 'all-MiniLM-L6-v2' ou 'tfidf_vectorizer'."
        
        if preprocess_text_advanced:
            all_texts_for_analysis_list = [function_preprocess_text_advanced(text) for text in all_texts_for_analysis_list]
        
        # --- 2. Análise de Similaridade e TF-IDF (COMBINADA para todos os arquivos) ---
        logger.info(f"Realizando análise de similaridade e TF-IDF para {len(all_texts_for_analysis_list)} páginas combinadas.")
        try:
            #similarity_matrix_combined = analyze_text_similarity(all_texts_for_storage_combined, model_embedding=model_embedding, ready_embeddings=ready_embeddings)
            #tf_idf_scores_array_combined = calculate_text_relevance_tfidf(all_texts_for_storage_combined)
            
            if ready_embeddings is not None:
                assert len(ready_embeddings) == len(all_texts_for_analysis_list)
                embedding_vectors_combined = ready_embeddings
            elif model_embedding == 'all-MiniLM-L6-v2':
                embedding_vectors_combined = get_vectors(all_texts_for_analysis_list, model_embedding=model_embedding)
            else: # 'tfidf_vectorizer'
                # Deve ser None para não causar erro no método filter_and_classify_pages ao comandar get_similarity_matrix
                embedding_vectors_combined = None 

            tf_idf_scores_array_combined, tfidf_vectors_combined = get_tfidf_scores(all_texts_for_analysis_list)
            
        except Exception as e:
            logger.error(f"Erro durante análise combinada de similaridade/TF-IDF: {e}", exc_info=True)
            raise
            # Pode optar por continuar sem esses dados ou retornar erro.
            # Por ora, os scores/semelhantes podem ficar zerados/vazios.

        logger.info(f"Análise em lote concluída. Total de páginas processadas globalmente: {len(all_texts_for_analysis_list)}")
        return embedding_vectors_combined, tfidf_vectors_combined, tf_idf_scores_array_combined

    @timing_decorator()
    def analyze_pdf_documents(self, pdf_paths_ordered: List[str],
                              clean_spaces=True, lowercase=False,
                              model_embedding: str = 'all-MiniLM-L6-v2', ready_embeddings: np_array = None, preprocess_text_advanced: bool = False) -> Dict[str, Dict[str, Any]]:

        processed_files_metadata, all_indices_in_batch, all_texts_for_storage_dict, all_texts_for_analysis_list = self.extract_texts_and_preprocess_files(
                                                                                                                        pdf_paths_ordered, clean_spaces, lowercase)
        if not processed_files_metadata:
            logger.warning("Nenhum arquivo PDF produziu dados na fase de extração.")
            return {}
    
        combined_processed_page_data, all_global_page_keys_ordered = self.build_combined_page_data(processed_files_metadata, 
                                                                            all_indices_in_batch, all_texts_for_storage_dict)

        if not all_texts_for_storage_dict or not all_texts_for_analysis_list:
            logger.warning("Nenhum texto para análise combinado de todos os arquivos. Pulando análise de similaridade e relevância.")
            return combined_processed_page_data
        
        embedding_vectors_combined, tfidf_vectors_combined, tf_idf_scores_array_combined = self.get_similarity_and_tfidf_score_docs(
                                                                    all_texts_for_analysis_list, model_embedding, ready_embeddings, preprocess_text_advanced)

        return combined_processed_page_data, all_global_page_keys_ordered, embedding_vectors_combined, tfidf_vectors_combined, tf_idf_scores_array_combined
   
    ### ======================================================================================

    @timing_decorator()
    def filter_and_classify_pages(
        self, 
        combined_processed_page_data: Dict[str, Dict[str, Any]],
        all_global_page_keys_ordered: List[str], 
        embedding_vectors_combined: Optional[np_ndarray] = None,
        tfidf_vectors_combined: Optional[np_ndarray] = None,
        tf_idf_scores_array_combined: Optional[np_ndarray] = None, 
        mode_main_filter: str = 'get_pages_among_similars_graphs', # 'get_pages_by_tfidf_initial', 'get_pages_among_similars_matrix', get_pages_among_similars_groups
        mode_filter_similar: str = 'bigger_content', # 'higher_initial_score'
        similarity_threshold: float = 0.87
        
    ) -> Tuple[List[str], List[str], int, int, int]: # Retorna listas de global_page_key (str)
        """
        Filtra e classifica páginas com base em sua relevância (TF-IDF) e similaridade.
        Remove páginas ininteligíveis e redundantes (mantendo a mais relevante do grupo).
        """
        if not combined_processed_page_data:
            return [], {}, 0 # Retornar zeros para as contagens
        elif len(combined_processed_page_data)==1:
            return [next(iter(combined_processed_page_data))], {}, 0  # Only one page, return it

        for i, global_page_key in enumerate(all_global_page_keys_ordered):
            assert global_page_key in combined_processed_page_data

        total_pages = len(combined_processed_page_data) # Total de páginas que entraram no método

        processed_indices = set()
        relevant_indices_candidates = set()
        discarded_by_similarity_count = 0
                
        unintelligible_indices_set = set() # Renomeado para clareza, pois é um set
        # Primeira varredura para identificar todas as páginas ininteligíveis
        for current_page_index in combined_processed_page_data:
            if not combined_processed_page_data[current_page_index]['inteligible']:
                unintelligible_indices_set.add(current_page_index)
                processed_indices.add(current_page_index)
        discarded_by_unintelligibility_count = len(unintelligible_indices_set)

        page_indices_available = sorted(combined_processed_page_data.keys())

        if len(page_indices_available) -len(unintelligible_indices_set) < 2:
            return list(set(page_indices_available) - unintelligible_indices_set), unintelligible_indices_set, 0

        if mode_main_filter != 'get_pages_by_tfidf_initial':
            similarity_matrix_combined = get_similarity_matrix(embedding_vectors_combined) if embedding_vectors_combined is not None else get_similarity_matrix(tfidf_vectors_combined)

        # Agora, processe as demais páginas para relevância e similaridade
        if mode_main_filter == 'get_pages_by_tfidf_initial':
            assert not (isinstance(embedding_vectors_combined, list) and len(embedding_vectors_combined) == 0)

            # Mapear scores TF-IDF e similaridade de volta aos dados das páginas globais
            for i, global_page_key in enumerate(all_global_page_keys_ordered):
                combined_processed_page_data[global_page_key]['tf_idf_score'] = round(tf_idf_scores_array_combined[i], 4)
                combined_processed_page_data[global_page_key]['vector'] = tfidf_vectors_combined[i] if embedding_vectors_combined is None else embedding_vectors_combined[i]

            page_indices_available = sorted(combined_processed_page_data.keys(),
                                            key=lambda p_idx: combined_processed_page_data[p_idx]['tf_idf_score'],
                                            reverse=True)
            
            selected_page_vectors = [] # Lista de vetores tfidf das páginas já selecionadas

            for current_page_index in page_indices_available:
                if current_page_index in processed_indices: # Se ininteligível 
                    continue
                
                current_page_vector = combined_processed_page_data[current_page_index]['vector']
                current_page_vector = current_page_vector if embedding_vectors_combined is None else np_array(current_page_vector)
                
                if not relevant_indices_candidates: # Se é a primeira página (a mais relevante), seleciona.
                    relevant_indices_candidates.add(current_page_index)
                    selected_page_vectors.append(current_page_vector)
                    continue
                
                # Vetores TF-IDF esparsos (já devem ser 1xN cada) Ou np.array de uma lista de vetores 1D ou (1,N) resulta em matriz 2D
                selected_matrix = vstack(selected_page_vectors) if embedding_vectors_combined is None else np_array(selected_page_vectors) 
                if selected_matrix.ndim == 1: selected_matrix = selected_matrix.reshape(1,-1)  # Se só havia um vetor antes e ele foi achatado para 1D
                is_redundant = check_if_has_similar_items(current_page_vector, selected_matrix, similarity_threshold=similarity_threshold)
                
                if not is_redundant:
                    relevant_indices_candidates.add(current_page_index)
                    selected_page_vectors.append(current_page_vector)
                else:
                    discarded_by_similarity_count += 1

        elif mode_main_filter == 'get_pages_among_similars_matrix':
            # Mapear scores TF-IDF e similaridade de volta aos dados das páginas globais
            for i, global_page_key in enumerate(all_global_page_keys_ordered):             
                relative_similar_indices = get_similar_items_indices(i, similarity_matrix_combined, similarity_threshold=similarity_threshold)
                # Converte índices relativos (da lista combinada) para chaves de página globais
                absolute_similar_global_keys = [all_global_page_keys_ordered[sim_idx] for sim_idx in relative_similar_indices]
                combined_processed_page_data[global_page_key]['semelhantes'] = absolute_similar_global_keys

        elif mode_main_filter == 'get_pages_among_similars_groups':
            # Agrupa páginas semelhantes iterativamente. Cada grupo contém uma página 'principal' e suas semelhantes.
            # pages_assigned_to_group rastreia todos os índices relativos que já pertencem a algum grupo.
            pages_assigned_to_group = set() 
            # Mapear scores TF-IDF e similaridade de volta aos dados das páginas globais
            for i, global_page_key in enumerate(all_global_page_keys_ordered):
                if i in pages_assigned_to_group:
                    if 'semelhantes' not in combined_processed_page_data[global_page_key]:
                        combined_processed_page_data[global_page_key]['semelhantes'] = []
                    continue
                
                pages_assigned_to_group.add(i)

                # Encontra vizinhos diretos de 'i'
                # Não precisa de exclude_idx aqui, pois vamos filtrar depois; e estava a criar muitos grupos pequenos.
                relative_similar_indices = get_similar_items_indices(i, similarity_matrix_combined, similarity_threshold=similarity_threshold)

                current_group_similar_global_keys = []
                for sim_idx in relative_similar_indices:
                    if sim_idx not in pages_assigned_to_group:
                        # Este vizinho ainda não foi agrupado, então ele entra no grupo de 'i'
                        pages_assigned_to_group.add(sim_idx)
                        current_group_similar_global_keys.append(all_global_page_keys_ordered[sim_idx])
                
                combined_processed_page_data[global_page_key]['semelhantes'] = current_group_similar_global_keys

        elif mode_main_filter == 'get_pages_among_similars_graphs':
            #  Agrupa páginas semelhantes usando um grafo de similaridade e componentes conectados.
            pages_assigned_to_group = set() # Evitar auto-loops e duplicatas de arestas
            # Construir o grafo
            graph = nx.Graph()
            # Mapear scores TF-IDF e similaridade de volta aos dados das páginas globais
            for i, global_page_key in enumerate(all_global_page_keys_ordered):      
                graph.add_node(i) # Adiciona cada página como um nó
                pages_assigned_to_group.add(i)
                relative_similar_indices = get_similar_items_indices(i, similarity_matrix_combined, exclude_idx=pages_assigned_to_group, similarity_threshold=similarity_threshold)
                for sim_idx in relative_similar_indices:
                    graph.add_edge(i, sim_idx)
                pages_assigned_to_group.update(relative_similar_indices)

            # Encontrar componentes conectados:
            connected_components_groups = list(nx.connected_components(graph))
            # Converter para lista de listas (nx retorna conjuntos):
            connected_components_groups = [list(group) for group in connected_components_groups]

            # Crie um mapeamento de índice de página (relativo) para seu componente (lista de índices relativos)
            page_idx_to_component_map = {}
            for component in connected_components_groups:
                for page_relative_idx in component:
                    page_idx_to_component_map[page_relative_idx] = component

            for i, global_page_key in enumerate(all_global_page_keys_ordered):
                if i in page_idx_to_component_map:
                    current_component = page_idx_to_component_map[i]
                    # Semelhantes são todos os outros no mesmo componente
                    similar_relative_indices = [idx for idx in current_component if idx != i]
                    combined_processed_page_data[global_page_key]['semelhantes'] = [all_global_page_keys_ordered[sim_idx] for sim_idx in similar_relative_indices]
                else: # Página não está em nenhum componente (pode acontecer se for única)
                    combined_processed_page_data[global_page_key]['semelhantes'] = []

        else:
            msg_error = f"Modo de filtro principal desconhecido: {mode_main_filter}"
            logger.error(msg_error)
            raise ValueError(msg_error)

        if mode_main_filter != 'get_pages_by_tfidf_initial':

            for current_page_index in page_indices_available:
                if current_page_index in processed_indices: # Se ininteligível ou já processada em um grupo
                    continue

                data = combined_processed_page_data[current_page_index]
                current_group_indices_from_data = {current_page_index}.union(
                    idx for idx in data.get('semelhantes', [])
                    if idx in combined_processed_page_data
                )
                
                group_to_evaluate = [
                    idx for idx in current_group_indices_from_data
                    if idx not in processed_indices 
                ]

                if not group_to_evaluate:
                    if current_page_index not in processed_indices:
                        relevant_indices_candidates.add(current_page_index)
                        processed_indices.add(current_page_index)
                    continue
                
                if len(group_to_evaluate) == 1:
                    most_relevant_in_group = group_to_evaluate[0]
                    # Nenhuma página descartada por similaridade neste caso (só há uma no grupo a avaliar)
                else:
                    if mode_filter_similar == 'bigger_content':
                        most_relevant_in_group = max(
                            group_to_evaluate,
                            key=lambda p_idx_key: combined_processed_page_data[p_idx_key]['number_words'] )
                    elif mode_filter_similar == 'higher_initial_score':
                        for i, global_page_key in enumerate(all_global_page_keys_ordered):
                            assert global_page_key in combined_processed_page_data
                            combined_processed_page_data[global_page_key]['tf_idf_score'] = round(tf_idf_scores_array_combined[i], 4)

                        most_relevant_in_group = max(
                            group_to_evaluate,
                            key=lambda p_idx_key: combined_processed_page_data[p_idx_key]['tf_idf_score'] )
                    else:
                        msg_error = f"Modo de filtro de similaridade desconhecido: {mode_filter_similar}"
                        logger.error(msg_error)
                        raise ValueError(msg_error)
                    
                    if DEBUG_MODE:
                        print(f'Do grupo de páginas semelhantes (considerando apenas inteligíveis e não processadas) '
                                    f'{[p for p in sorted(list(group_to_evaluate))]}, '
                                    f'o índice-página {most_relevant_in_group} foi selecionado.')
                    
                    # Contabilizar páginas descartadas por similaridade
                    for group_member_idx in group_to_evaluate:
                        if group_member_idx != most_relevant_in_group:
                            discarded_by_similarity_count += 1
                
                relevant_indices_candidates.add(most_relevant_in_group)
                
                # Atualiza com o grupo original, não o filtrado group_to_evaluate
                processed_indices.update(current_group_indices_from_data)

        # --- PASSO 3: Recálculo de TF-IDF no Conjunto Não Redundante ---
        if not relevant_indices_candidates:
            logger.warning("Nenhuma página selecionada após a primeira filtragem.")
            return [], {}, 0 

        logger.info(f"Páginas-índices após 1ª filtragem ({len(relevant_indices_candidates)} de {total_pages}).")

        texts_for_recalculation = [combined_processed_page_data[i]['text_stored'] for i in relevant_indices_candidates]
        final_relevance_scores, _ = get_tfidf_scores(texts_for_recalculation)

        final_pages_data  = []
        for i, original_page_idx in enumerate(relevant_indices_candidates):
            final_pages_data .append({
                "original_index": original_page_idx,
                "recalculated_relevance": final_relevance_scores[i]
            })
        
        # Ordenar pelo score de relevância recalculado (decrescente)
        sorted_final_pages_data = sorted(final_pages_data, key=lambda x: x["recalculated_relevance"], reverse=True)

        final_selected_ordered_indices = [page_data["original_index"] for page_data in sorted_final_pages_data]
        
        selected_relevant_count = len(final_selected_ordered_indices)      

        # Verificação de consistência (opcional, para debug):
        # A soma das selecionadas, descartadas por similaridade e descartadas por ininteligibilidade
        # deveria ser igual ao total de páginas processadas inicialmente.
        if total_pages != (selected_relevant_count + discarded_by_similarity_count + discarded_by_unintelligibility_count):
            logger.warning("Contagem de páginas inconsistente em filter_and_classify_pages!")
            logger.warning(f"Total Inicial: {total_pages}, Selecionadas: {selected_relevant_count}, "
                           f"Descartadas Simil.: {discarded_by_similarity_count}, Descartadas Inint.: {discarded_by_unintelligibility_count}")
        #print('\n')
        #logger.info(f"[DEBUG] Índices relevantes após filtro: \n{sorted(final_selected_ordered_indices)}\n")
        
        return (
            final_selected_ordered_indices, # ordenado pelo score tfidf recalculado
            unintelligible_indices_set,
            discarded_by_similarity_count
        )

    @timing_decorator()
    def group_texts_by_relevance_and_token_limit(
        self,
        processed_page_data: Dict[str, Dict[str, Any]], # Chave é global_page_key (str)
        relevant_page_ordered_indices: List[str], # Lista de global_page_key (str)
        token_limit: int,
    ) -> Tuple[str, str, int, int]: 
        """
        Agrupa textos de páginas relevantes, respeitando um limite de tokens.
        Os textos são concatenados na ordem original das páginas,
        mas a seleção das páginas é baseada na lista `relevant_page_indices`.

        Args:
            processed_page_data (Dict[int, Dict[str, Any]]): Dados processados das páginas.
            relevant_page_indices (List[int]): Lista de índices de páginas relevantes,
                                               já ordenadas por prioridade.
            token_limit (int): Limite máximo de tokens para o texto acumulado.
            model_name_for_tokens (str, optional): Nome do modelo para contagem de tokens,
                                                   passado para count_tokens e reduce_text_to_limit.
                                                   Default é "gpt-3.5-turbo".

        Returns:
            Tuple[str, str, int, int]: Tupla contendo:
                - intervalos de páginas consideradas.
                - Texto acumulado das páginas selecionadas (e possivelmente truncadas).
                - Total de tokens das páginas selecionadas ANTES de qualquer truncamento.
                - Total de tokens do texto acumulado FINAL (após truncamento, se houver).
        """
        current_total_tokens_final = 0 # Total final
        total_tokens_before_truncation = 0 # Variável para rastrear tokens totais das páginas selecionadas antes do truncamento
        texts_for_concatenation = {}

        assert len(relevant_page_ordered_indices) == len(set(relevant_page_ordered_indices))

        limit_reached = False
        for page_idx in relevant_page_ordered_indices:
            if page_idx not in processed_page_data:
                #logger.warning(f"Índice de página relevante {page_idx+1} não encontrado nos dados processados. Ignorando.")
                logger.warning(f"Chave de página relevante '{page_idx}' não encontrada...")
                continue

            page_text = processed_page_data[page_idx]['text_stored']
            
            page_tokens = count_tokens(page_text, model_name=model_name_for_tokens)

            # Adicionar tokens desta página ao total antes do truncamento
            # Isso acontece independentemente de a página ser totalmente incluída, parcialmente ou não.
            # Estamos interessados no total das páginas que *tentamos* incluir.
            total_tokens_before_truncation += page_tokens

            if limit_reached:
                continue

            if current_total_tokens_final + page_tokens <= token_limit:
                texts_for_concatenation[page_idx] = page_text
                current_total_tokens_final += page_tokens
            else:
                remaining_token_budget = token_limit - current_total_tokens_final
                if remaining_token_budget > 0:
                    
                    # Usar a função reduce_text_to_limit 
                    partial_text = reduce_text_to_limit(page_text, remaining_token_budget, model_name=model_name_for_tokens)
                    texts_for_concatenation[page_idx] = partial_text
                    
                    # Recalcular tokens do texto parcial para precisão
                    current_total_tokens_final += count_tokens(partial_text, model_name=model_name_for_tokens)
                    
                    logger.info(f'Texto da página {page_idx} reduzido para caber no limite de tokens.')
                    limit_reached = True

        def get_sortable_page_key(global_key: str) -> Tuple[int, int]:
            # Função para extrair (file_idx, page_idx_in_file) para ordenação
            # formato exato de _generate_global_page_key: exemplo: "file0_page10"
            parts = global_key.replace("file", "").replace("page", "").split('_')
            return int(parts[0]), int(parts[1])

        keys_of_included_texts = list(texts_for_concatenation.keys())
        logically_sorted_keys = sorted(keys_of_included_texts, key=get_sortable_page_key)
        #str_pages_considered = self.format_global_keys_for_display(logically_sorted_keys)      

        accumulated_text_parts = [texts_for_concatenation[key] for key in logically_sorted_keys]
        accumulated_text = " ".join(accumulated_text_parts).strip()

        # Recalcula tokens finais do texto agregado para máxima precisão, pois o join(" ") pode adicionar/remover tokens.
        final_aggregated_tokens = count_tokens(accumulated_text, model_name=model_name_for_tokens)

        print("\n")
        if set(relevant_page_ordered_indices) == set(keys_of_included_texts):
            logger.info("[DEBUG] Índices relevantes integra os mesmos índices do texto final agregado.\n")
        else:
            logger.info(f"[DEBUG] Índices relevantes NÃO integra os mesmos índices do texto final agregado.\n {set(keys_of_included_texts)-set(relevant_page_ordered_indices)}\n")

        return keys_of_included_texts, accumulated_text, total_tokens_before_truncation, final_aggregated_tokens


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

