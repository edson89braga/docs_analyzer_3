''' TODO: Criar pytestes para este módulo. '''

from rich import print
from sympy import limit
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


### pdf_extraction_strategies:
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional
import pdfplumber
# Para o PyPdfExtractor (exemplo de flexibilidade)
# import pypdf

class PDFTextExtractorStrategy(ABC):
    """Interface abstrata para estratégias de extração de texto de PDFs."""

    @abstractmethod
    def get_total_pages(self, pdf_path: str) -> int:
        """Retorna o número total de páginas do PDF."""
        pass

    @abstractmethod
    def extract_texts_from_pages(self, pdf_path: str, page_indices: Optional[List[int]] = None) -> List[Tuple[int, str]]:
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
    def extract_texts_from_pages(self, pdf_path: str, page_indices: Optional[List[int]] = None) -> List[Tuple[int, str]]:
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
            return content_by_page
        except Exception as e:
            # Idealmente, o logger viria daqui ou seria injetado.
            # Por simplicidade, relançamos a exceção para ser tratada pelo chamador.
            # logger.error(f"Erro ao extrair textos do PDF {os.path.basename(pdf_path)} com PdfPlumber: {str(e)}")
            raise RuntimeError(f"PdfPlumber extraction error for {pdf_path}: {e}")

class PyPdfExtractor(PDFTextExtractorStrategy):
    """Estratégia de extração de texto usando pypdf (Exemplo de flexibilidade)."""

    def get_total_pages(self, pdf_path: str) -> int:
        try:
            # from pypdf import PdfReader # Mova o import para o topo se usar frequentemente
            # reader = PdfReader(pdf_path)
            # return len(reader.pages)
            raise NotImplementedError("PyPdfExtractor.get_total_pages não implementado neste exemplo.")
        except Exception as e:
            raise RuntimeError(f"PyPdf extraction error (get_total_pages) for {pdf_path}: {e}")

    def extract_texts_from_pages(self, pdf_path: str, page_indices: Optional[List[int]] = None) -> List[Tuple[int, str]]:
        # content_by_page = []
        # try:
        #     from pypdf import PdfReader # Mova o import para o topo se usar frequentemente
        #     reader = PdfReader(pdf_path)
        #     total_pages_in_pdf = len(reader.pages)

        #     if page_indices is None:
        #         indices_to_process = list(range(total_pages_in_pdf))
        #     else:
        #         indices_to_process = [idx for idx in page_indices if 0 <= idx < total_pages_in_pdf]
            
        #     for p_idx in indices_to_process:
        #         page_pdf = reader.pages[p_idx]
        #         text = page_pdf.extract_text() or ""
        #         content_by_page.append((p_idx, text))
        #     return content_by_page
        # except Exception as e:
        #     raise RuntimeError(f"PyPdf extraction error for {pdf_path}: {e}")
        raise NotImplementedError("PyPdfExtractor.extract_texts_from_pages não implementado neste exemplo. Descomente e instale pypdf para usar.")


### text_processing_utils:
import re
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException
# Supondo que src.utils.count_tokens existe
from src.utils import count_tokens as util_count_tokens

model_name_for_tokens: str = "gpt-3.5-turbo" # Adicionado para consistência com count_tokens e reduce_text

def preprocess_text_basic(text: str) -> str:
    """
    Realiza pré-processamento básico: remove espaços extras e converte para minúsculas.
    """
    text = re.sub(r'\s+', ' ', text)
    return text.lower()

def preprocess_text_advanced(text: str) -> str:
    """
    Realiza pré-processamento avançado: remove caracteres especiais e pontuação,
    exceto os necessários para datas/horários, após o pré-processamento básico.
    """
    text = preprocess_text_basic(text)
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
        logger.debug(f"Texto considerado ininteligível devido à alta proporção de (cid:N) (>{cid_threshold*100}%).") # Adicione logger se disponível
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


### text_analysis_utils:
import numpy as np
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
def analyze_text_similarity(pages_texts: List[str], model_name: str = 'all-MiniLM-L6-v2') -> np.ndarray:
    """
    Analisa similaridades entre textos (páginas) usando embeddings de sentenças.
    Retorna uma matriz de similaridade.
    """
    model = get_sentence_transformer_model(model_name)
    embeddings = sk_normalize(model.encode(pages_texts))
    similarity_matrix = cosine_similarity(embeddings)
    return similarity_matrix

@timing_decorator()
def calculate_text_relevance_tfidf(pages_texts: List[str], language: str = 'portuguese') -> np.ndarray:
    """
    Calcula a relevância de cada texto (página) usando TF-IDF.
    Retorna um array com os scores TF-IDF para cada texto.
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
    tf_idf_scores = tf_idf_matrix.sum(axis=1).A1  # .A1 converte para array 1D
    return tf_idf_scores

def get_similar_items_indices(item_index: int, similarity_matrix: np.ndarray, threshold: float = 0.87) -> List[int]:
    """
    Identifica itens semelhantes a um item específico com base na matriz de similaridade.
    """
    if not (0 <= item_index < similarity_matrix.shape[0]):
        return [] # Índice fora dos limites
        
    similar_indices = []
    for j in range(similarity_matrix.shape[0]):
        if item_index == j:
            continue
        if similarity_matrix[item_index, j] > threshold:
            similar_indices.append(j)
    return similar_indices


### pdf_document_analyzer:
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

class PDFDocumentAnalyzer:
    """
    Classe principal para processamento e análise de documentos PDF.
    Orquestra a extração de texto, pré-processamento, análise e classificação de páginas.
    """
    def __init__(self, extractor_strategy: PDFTextExtractorStrategy = PdfPlumberExtractor()):
        self.extractor = extractor_strategy

    def get_pdf_page_count(self, pdf_path: str) -> int:
        """Obtém o número total de páginas de um arquivo PDF usando a estratégia configurada."""
        return self.extractor.get_total_pages(pdf_path)

    def extract_texts_and_preprocess(self, pdf_path: str, page_indices: Optional[List[int]] = None):
        """
        Processa um PDF, extrai texto de cada página e realiza análises.

        Args:
            pdf_path (str): Caminho do arquivo PDF.
            page_indices (Optional[List[int]]): Índices das páginas a serem processadas (base 0).
                                                 Se None, todas as páginas são processadas.

        Returns:
            Dict[int, Dict[str, Any]]: Dicionário com dados de cada página processada,
                                       incluindo texto, contagem de palavras/tokens,
                                       inteligibilidade, score TF-IDF e páginas semelhantes.
        """
        if not os.path.exists(pdf_path):
            logger.error(f"PDF não encontrado: {pdf_path}")
            raise FileNotFoundError(f"PDF não encontrado: {pdf_path}")

        logger.info(f'Processando PDF {os.path.basename(pdf_path)}')

        try:
            # 1. Extrair texto das páginas
            # O método extract_texts_from_pages já lida com page_indices=None para todas as páginas
            extracted_pages_content = self.extractor.extract_texts_from_pages(pdf_path, page_indices)
            
            if not extracted_pages_content:
                logger.warning(f"Nenhum texto extraído do PDF {os.path.basename(pdf_path)} para os índices fornecidos.")
                return {}

            # Mapear os textos extraídos para facilitar o acesso e manter os índices originais
            # Mesmo que page_indices seja fornecido, a lista retornada pode ser menor
            # se alguns índices estiverem fora do intervalo ou não tiverem conteúdo.
            # Vamos usar os índices retornados por extract_texts_from_pages como a fonte da verdade.

            actual_indices = [idx for idx, _ in extracted_pages_content]
            
            # 2. Pré-processar textos
            # Texto para armazenamento e exibição (preprocessamento básico)
            texts_for_storage = {idx: preprocess_text_basic(text) for idx, text in extracted_pages_content}
            # Texto para análises mais profundas (preprocessamento avançado)
            texts_for_analysis = [preprocess_text_advanced(text) for _, text in extracted_pages_content]

            return actual_indices, texts_for_storage, texts_for_analysis

        except Exception as e:
            logger.error(f"Erro ao processar PDF {os.path.basename(pdf_path)}: {str(e)}")
            raise

    def analyze_similarity_and_relevance(self, pdf_path, actual_indices, texts_for_storage, texts_for_analysis) -> Dict[int, Dict[str, Any]]:
        """
        Continuação da função extract_texts_and_preprocess.
        """
        try:
            # 3. Realizar análises de similaridade e relevância
            # É importante que texts_for_analysis corresponda à ordem dos actual_indices
            # se formos mapear os resultados de volta para os índices originais.
            similarity_matrix = analyze_text_similarity(texts_for_analysis)
            tf_idf_scores_array = calculate_text_relevance_tfidf(texts_for_analysis)

            # Mapear scores TF-IDF de volta aos índices originais das páginas
            tf_idf_scores = {actual_indices[i]: tf_idf_scores_array[i] for i in range(len(actual_indices))}
            
            # 4. Montar dicionário de dados por página
            processed_page_data: Dict[int, Dict[str, Any]] = {}
            for i, original_page_index in enumerate(actual_indices):
                text_stored = texts_for_storage[original_page_index]
                
                is_intelligible = is_text_intelligible(text_stored) # Usa o texto com pré-processamento básico
                if not is_intelligible:
                    try:
                        lang = detect(text_stored)
                        logger.warning(f'[red]Página original {original_page_index+1} considerada ininteligível ({lang}) / Qtde caracteres: {len(text_stored)}')
                    except LangDetectException:
                        logger.warning(f'[red]Página original {original_page_index+1} considerada ininteligível (não detectado) / Qtde caracteres: {len(text_stored)}')


                # `get_similar_items_indices` espera um índice relativo à matriz de similaridade,
                # que é `i` neste loop, pois `texts_for_analysis` foi usado para criar a matriz.
                # Os índices retornados por `get_similar_items_indices` também são relativos.
                # Precisamos mapeá-los de volta para os `actual_indices`.
                relative_similar_indices = get_similar_items_indices(i, similarity_matrix)
                absolute_similar_indices = [actual_indices[sim_idx] for sim_idx in relative_similar_indices]

                processed_page_data[original_page_index] = {
                    'texto': text_stored,
                    'number_words': count_unique_words(text_stored),
                    'number_tokens': count_tokens(text_stored, model_name=model_name_for_tokens), # Usando a função de utils
                    'inteligible': is_intelligible,
                    'tf_idf_score': round(tf_idf_scores.get(original_page_index, 0.0), 4),
                    'semelhantes': absolute_similar_indices # Lista de índices de páginas originais
                }
            
            return processed_page_data

        except Exception as e:
            logger.error(f"Erro ao processar PDF {os.path.basename(pdf_path)}: {str(e)}")
            raise

    @timing_decorator()
    def analyze_pdf_document(self, pdf_path: str, page_indices: Optional[List[int]] = None) -> Dict[int, Dict[str, Any]]:
        
        actual_indices, texts_for_storage, texts_for_analysis = self.extract_texts_and_preprocess(pdf_path, page_indices)
        processed_page_data = self.analyze_similarity_and_relevance(pdf_path, actual_indices, texts_for_storage, texts_for_analysis)

        return processed_page_data

    @timing_decorator()
    def filter_and_classify_pages(
        self, 
        processed_page_data: Dict[int, Dict[str, Any]]
    ) -> Tuple[List[int], List[int], int, int, int]: # <--- MODIFICADO: Novo tipo de retorno
        """
        Filtra e classifica páginas com base em sua relevância (TF-IDF) e similaridade.
        Remove páginas ininteligíveis e redundantes (mantendo a mais relevante do grupo).

        Args:
            processed_page_data (Dict[int, Dict[str, Any]]): Dados processados das páginas.

        Returns:
            Tuple[List[int], List[int], int, int, int]: Tupla contendo:
                - Lista de índices das páginas relevantes (ordenadas por TF-IDF descendente).
                - Lista de índices das páginas consideradas ininteligíveis.
                - Contagem de páginas selecionadas como relevantes.
                - Contagem de páginas descartadas por similaridade (redundância).
                - Contagem de páginas descartadas por serem ininteligíveis.
        """
        if not processed_page_data:
            return [], [], 0, 0, 0 # Retornar zeros para as contagens

        processed_indices = set()
        unintelligible_indices_set = set() # Renomeado para clareza, pois é um set
        relevant_indices_candidates = set()
        # NOVO: Contador para páginas descartadas por similaridade
        discarded_by_similarity_count = 0
        
        page_indices_available = sorted(processed_page_data.keys())
        total_pages_processed_initially = len(page_indices_available) # Total de páginas que entraram no método

        # Primeira varredura para identificar todas as páginas ininteligíveis
        for page_idx in page_indices_available:
            if not processed_page_data[page_idx]['inteligible']:
                unintelligible_indices_set.add(page_idx)
                processed_indices.add(page_idx)
        
        # Contagem de páginas descartadas por ininteligibilidade já é o tamanho de unintelligible_indices_set
        discarded_by_unintelligibility_count = len(unintelligible_indices_set)

        # Agora, processe as demais páginas para relevância e similaridade
        for page_idx in page_indices_available:
            if page_idx in processed_indices: # Se ininteligível ou já processada em um grupo
                continue

            data = processed_page_data[page_idx]
            current_group_indices_from_data = {page_idx}.union(
                idx for idx in data.get('semelhantes', [])
                if idx in processed_page_data
            )
            
            group_to_evaluate = [
                idx for idx in current_group_indices_from_data
                if idx not in processed_indices 
            ]

            if not group_to_evaluate:
                if page_idx not in processed_indices:
                    relevant_indices_candidates.add(page_idx)
                    processed_indices.add(page_idx)
                continue
            
            if len(group_to_evaluate) == 1:
                most_relevant_in_group = group_to_evaluate[0]
                # Nenhuma página descartada por similaridade neste caso (só há uma no grupo a avaliar)
            else:
                most_relevant_in_group = max(
                    group_to_evaluate,
                    key=lambda p_idx_key: processed_page_data[p_idx_key]['number_words']
                )
                logger.info(f'Do grupo de páginas semelhantes (considerando apenas inteligíveis e não processadas) '
                            f'{[p + 1 for p in sorted(list(group_to_evaluate))]}, '
                            f'a página {most_relevant_in_group + 1} foi selecionada.')
                
                # NOVO: Contabilizar páginas descartadas por similaridade
                for group_member_idx in group_to_evaluate:
                    if group_member_idx != most_relevant_in_group:
                        discarded_by_similarity_count += 1
            
            relevant_indices_candidates.add(most_relevant_in_group)
            
            if most_relevant_in_group in processed_page_data:
                 processed_page_data[most_relevant_in_group]['tf_idf_score'] *= 2
            
            processed_indices.update(group_to_evaluate)

        final_relevant_indices_list = list(relevant_indices_candidates) # Renomeado para clareza
        final_relevant_indices_list.sort(
            key=lambda p_idx: processed_page_data[p_idx]['tf_idf_score'],
            reverse=True
        )
        
        selected_relevant_count = len(final_relevant_indices_list)
        
        # Verificação de consistência (opcional, para debug):
        # A soma das selecionadas, descartadas por similaridade e descartadas por ininteligibilidade
        # deveria ser igual ao total de páginas processadas inicialmente.
        if total_pages_processed_initially != (selected_relevant_count + discarded_by_similarity_count + discarded_by_unintelligibility_count):
            logger.warning("Contagem de páginas inconsistente em filter_and_classify_pages!")
            logger.warning(f"Total Inicial: {total_pages_processed_initially}, Selecionadas: {selected_relevant_count}, "
                           f"Descartadas Simil.: {discarded_by_similarity_count}, Descartadas Inint.: {discarded_by_unintelligibility_count}")

        return (
            final_relevant_indices_list, 
            sorted(list(unintelligible_indices_set)), 
            selected_relevant_count, 
            discarded_by_similarity_count, 
            discarded_by_unintelligibility_count
        )

    @timing_decorator()
    def group_texts_by_relevance_and_token_limit(
        self,
        processed_page_data: Dict[int, Dict[str, Any]],
        relevant_page_indices: List[int], # Já ordenados por relevância
        token_limit: int,
    ) -> Tuple[str, str, int, int]: # <--- MODIFICADO: Adicionado retorno para contagens de tokens
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
                - String formatada dos intervalos de páginas consideradas.
                - Texto acumulado das páginas selecionadas (e possivelmente truncadas).
                - Total de tokens das páginas selecionadas ANTES de qualquer truncamento.
                - Total de tokens do texto acumulado FINAL (após truncamento, se houver).
        """
        current_total_tokens_final = 0 # Renomeado para clareza, este será o total final
        # NOVO: Variável para rastrear tokens totais das páginas selecionadas antes do truncamento
        total_tokens_before_truncation = 0
        considered_page_indices_for_output = []

        texts_for_concatenation = {}

        limit_reached = False
        for page_idx in relevant_page_indices:
            if page_idx not in processed_page_data:
                logger.warning(f"Índice de página relevante {page_idx+1} não encontrado nos dados processados. Ignorando.")
                continue

            page_text = processed_page_data[page_idx]['texto']
            # Usar a função count_tokens que agora aceita model_name
            page_tokens = count_tokens(page_text, model_name=model_name_for_tokens)

            # NOVO: Adicionar tokens desta página ao total antes do truncamento
            # Isso acontece independentemente de a página ser totalmente incluída, parcialmente ou não.
            # Estamos interessados no total das páginas que *tentamos* incluir.
            if page_idx not in considered_page_indices_for_output:
                 total_tokens_before_truncation += page_tokens

            if limit_reached:
                continue

            if current_total_tokens_final + page_tokens <= token_limit:
                texts_for_concatenation[page_idx] = page_text
                current_total_tokens_final += page_tokens
                if page_idx not in considered_page_indices_for_output:
                    considered_page_indices_for_output.append(page_idx)
            else:
                remaining_token_budget = token_limit - current_total_tokens_final
                if remaining_token_budget > 0:
                    # Usar a função reduce_text_to_limit que agora aceita model_name
                    partial_text = reduce_text_to_limit(page_text, remaining_token_budget, model_name=model_name_for_tokens)
                    texts_for_concatenation[page_idx] = partial_text
                    # Recalcular tokens do texto parcial para precisão
                    current_total_tokens_final += count_tokens(partial_text, model_name=model_name_for_tokens)
                    if page_idx not in considered_page_indices_for_output:
                        considered_page_indices_for_output.append(page_idx)
                    logger.info(f'Texto da página {page_idx + 1} reduzido para caber no limite de tokens.')
                    limit_reached = True

        sorted_indices_for_concatenation = sorted(texts_for_concatenation.keys())
        
        accumulated_text_parts = [texts_for_concatenation[idx] for idx in sorted_indices_for_concatenation]
        accumulated_text = " ".join(accumulated_text_parts).strip()
        
        # RECALCULAR tokens finais do texto agregado para máxima precisão,
        # pois o join(" ") pode adicionar/remover tokens.
        final_aggregated_tokens = count_tokens(accumulated_text, model_name=model_name_for_tokens)

        str_pages_considered = get_string_intervalos(sorted(considered_page_indices_for_output), incrementa_1=True)

        # MODIFICADO: Retornar as duas contagens de tokens
        return str_pages_considered, accumulated_text, total_tokens_before_truncation, final_aggregated_tokens


### --- Teste-Exemplo de uso --------------------------------------------------------------

def test_example(pdf_path: str, token_limit_for_summary: int = 100000, page_indices_to_process: Optional[List[int]] = None):
    if not os.path.exists(pdf_path):
        print(f"Arquivo PDF de exemplo não encontrado: {pdf_path}")
        return

    # 2. Instanciar o analisador de documentos com a estratégia escolhida
    analyzer = PDFDocumentAnalyzer()

    # 3. Obter o número total de páginas (opcional, apenas para informação)
    try:
        total_pages = analyzer.get_pdf_page_count(pdf_path)
        print(f"O PDF '{os.path.basename(pdf_path)}' possui {total_pages} páginas.\n")
    except Exception as e:
        print(f"Erro ao obter contagem de páginas: {e}")
        return

    # 4. Analisar o documento PDF (todas as páginas ou um subconjunto)
    # Para analisar páginas específicas, ex: page_indices = [0, 2, 4]
    # Para analisar todas as páginas: page_indices = None
    print(f"Analisando o documento PDF: {pdf_path}...")
    try:
        # page_indices_to_process = [i for i in range(min(5, total_pages))] # Ex: primeiras 5 páginas
        
        processed_data = analyzer.analyze_pdf_document(pdf_path, page_indices=page_indices_to_process)
        
        if not processed_data:
            print("Nenhum dado foi processado.")
            return

        print(f"\n--- Dados Processados por Página (primeiras 3 páginas ou menos) ---")
        for i, (page_idx, data) in enumerate(processed_data.items()):
            if i >= 3 and page_indices_to_process is None : # Limita a exibição para não poluir
                print("...")
                break
            print(f"  Página {page_idx + 1}:")
            print(f"    Texto (primeiros 50 chars): '{data['texto'][:50]}...'")
            print(f"    Inteligível: {data['inteligible']}")
            print(f"    Palavras Únicas: {data['number_words']}")
            print(f"    Tokens: {data['number_tokens']}")
            print(f"    Score TF-IDF: {data['tf_idf_score']:.4f}")
            print(f"    Páginas Semelhantes (índices): {[s_idx + 1 for s_idx in data['semelhantes']]}")
        
        # 5. Filtrar e classificar páginas
        print("\n--- Classificando Páginas ---")
        
        (relevant_indices, 
         unintelligible_indices, 
         count_selected, 
         count_discarded_similarity, 
         count_discarded_unintelligible) = analyzer.filter_and_classify_pages(processed_data)
        
        total_pages_in_report = len(processed_data) # Total de páginas que o processed_data continha

        print(f"  Total de páginas analisadas (que tinham texto extraível): {total_pages_in_report}")
        print(f"  Páginas Selecionadas como Relevantes: {count_selected} (Índices: {[idx + 1 for idx in relevant_indices]})")
        print(f"  Páginas Descartadas por Ininteligibilidade: {count_discarded_unintelligible} (Índices: {[idx + 1 for idx in unintelligible_indices]})")
        print(f"  Páginas Descartadas por Similaridade (Redundância): {count_discarded_similarity}")

        # Opcional: Calcular proporções
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
            str_pages, aggregated_text, tokens_antes, tokens_depois = analyzer.group_texts_by_relevance_and_token_limit(
                processed_page_data=processed_data,
                relevant_page_indices=relevant_indices,
                token_limit=token_limit_for_summary
            )
            print(f"  Páginas consideradas para o texto agregado: {str_pages}\n")
            print(f"  Texto Agregado (primeiros 300 caracteres):\n'{aggregated_text[:300]}...'\n")
            print(f"  Tokens das páginas selecionadas (antes da supressão): {tokens_antes}\n")
            print(f"  Tokens do texto agregado final (após supressão): {tokens_depois}\n")
            if tokens_antes > tokens_depois:
                supressed_tokens = tokens_antes - tokens_depois
                percentage_supressed = (supressed_tokens / tokens_antes) * 100 if tokens_antes > 0 else 0
                print(f"  Tokens suprimidos: {supressed_tokens} ({percentage_supressed:.2f}% do total original das páginas selecionadas)")
        else:
            print("\nNenhuma página relevante encontrada para agregação.")
        
        return processed_data
    
    except FileNotFoundError as fnf_err:
        print(f"Erro: {fnf_err}")
    except RuntimeError as rt_err: # Captura erros de extração, por exemplo
        print(f"Erro de execução: {rt_err}")
    except Exception as e:
        print(f"Ocorreu um erro inesperado durante a análise: {e}")
        import traceback
        traceback.print_exc()

r'''

pdf_path = r'C:\Users\edson.eab\Downloads\PDFs-Testes\08500.013511_2025-29.pdf'
pdf_path = r'C:\Users\edson.eab\Downloads\PDFs-Testes\08500.014072_2025-71.pdf'
pdf_path = r'C:\Users\edson.eab\Downloads\PDFs-Testes\08500.014141_2025-47.pdf'
token_limit_for_summary = 100000
processed_data = test_example(pdf_path)

'''