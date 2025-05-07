# src/core/pdf_processor.py:

import nltk, pdfplumber, re, os

from nltk.corpus import stopwords
from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import normalize
from sklearn.feature_extraction.text import TfidfVectorizer

from src.utils import timing_decorator, count_tokens, reduce_text_to_limit, get_string_intervalos

from src.logger.logger import LoggerSetup
logger = LoggerSetup.get_logger(__name__)

# Baixar corpora de nltk para legibilidade
# A NLTK usa o módulo nltk.data para gerenciar os corpora, e ele verifica se o corpus já está baixado antes de tentar baixá-lo novamente.
nltk.download('punkt', quiet=True)          # punkt: um tokenizador de sentenças
nltk.download('punkt_tab', quiet=True)      # punkt_tab: um tokenizador para dados tabulares
nltk.download('stopwords', quiet=True)      # stopwords: uma lista de palavras comuns para ignorar no processamento de texto (ex.: "o", "e", etc.)

class PDFProcessor:
    """Classe principal para processamento de PDFs."""
    
    def __init__(self):
        ...
    
    def get_len_pages(self, path_pdf):
        """
        Obtém o número total de páginas de um arquivo PDF.
        
        :param path_pdf: Caminho do arquivo PDF
        :return: Número total de páginas
        """
        with pdfplumber.open(path_pdf) as pdf:
            number_pages = len(pdf.pages)
        return number_pages

    @timing_decorator()
    def extract_texts_from_pdf(self, pdf_path, indice_paginas=None):
        """
        Extrai textos de um PDF, considerando apenas páginas especificadas por indice_paginas.

        Args:
            pdf_path (str): Caminho do arquivo PDF.
            indice_paginas (Optional[List[int]]): Índices das páginas a serem extraídas. Se None, todas as páginas serão processadas.

        Returns:
            List[Tuple[int, str]]: Uma lista com os índices das páginas e seus respectivos textos.
        """
        total_pages = self.get_len_pages(pdf_path)
        if not indice_paginas:
            indice_paginas = list(range(total_pages))
        try:
            conteudo_paginas = []
            with pdfplumber.open(pdf_path) as pdf:
                for p in range(total_pages):
                    if p not in indice_paginas:
                        continue
                    page_pdf = pdf.pages[p]
                    texto = page_pdf.extract_text() or ""  # Garantir que parte não seja None
                    conteudo_paginas.append((p, texto))
                    # text += page_text + "\f"  # Form feed para separar páginas
            return conteudo_paginas
        except Exception as e:
            logger.error(f"Erro ao extrair textos do PDF {os.basename(pdf_path)}: {str(e)}")
            raise
           
class TextAnalyzer:
    """Classe para análise de texto."""

    def __init__(self, processor: PDFProcessor):
        self.pdf_processor = processor

    # Métodos sobre texto puro:.......................................

    def preprocess_1(self, text):
        """
        Realiza pré-processamento básico do texto, removendo espaços extras e convertendo para minúsculas.
        
        :param text: Texto a ser processado
        :return: Texto processado
        """
        # Remove espaços em branco extras e caracteres especiais
        text = re.sub(r'\s+', ' ', text)
        return text.lower()

    def preprocess_2(self, text):        
        """
        Realiza pré-processamento intermediário do texto, removendo caracteres especiais e pontuação,
        exceto os que forem necessários para a formatação de datas e horários.
        
        :param text: Texto a ser processado
        :return: Texto processado

        """
        # Realiza pré-processamento do texto mantendo caracteres acentuados e pontuações comuns.
        text = self.preprocess_1(text)
        text = re.sub(r'[^\w\sÀ-ÿ.,!?;:()\'\"-]', '', text)  
        return text
    
    def count_unique_words(self, text):
        """
        Conta o número de palavras únicas em um texto.
        
        :param text: Texto a ser analisado
        :return: Número de palavras únicas
        """
        return len(set(text.split()))

    def is_intelligible(self, text):
        # Filtra páginas sem conteúdo inteligível em Português
        """
        Filtra páginas sem conteúdo inteligível em Português (ou outros idiomas que se assemelhem a português).
        
        :param text: Texto a ser analisado
        :return: True se o texto for considerado inteligível, False caso contrário
        """
        try:
            result = len(text) > 0 and detect(text) in ['pt', 'it', 'gl', 'es', 'fr']            
            return result 
        except LangDetectException:
            return False

    # Métodos sobre grupos de textos (páginas):........................

    @timing_decorator()
    def analyze_similarities(self, pages_text):
        """
        Analisa similaridades entre páginas de um PDF.
        
        Recebe um array de strings com o texto de cada página e retorna uma matriz de similaridade.
        A similaridade é calculada com base em embeddings de sentenças, que são normalizados.
        A matriz de similaridade é uma matriz simétrica em que a linha i e coluna j representa a similaridade
        entre as páginas i e j.
        
        :param pages_text: Array de strings com o texto de cada página
        :return: Matriz de similaridade entre as páginas
        """
        model = SentenceTransformer('all-MiniLM-L6-v2')  # Se precisar de m,ais precisão, tentar o modelo ('all-mpnet-base-v2')
        # Calcular e normalizar embeddings para cada página:
        embeddings = normalize(model.encode(pages_text))
        # Cálculo de similaridade para detectar redundância:
        similarity_matrix = cosine_similarity(embeddings)
        return similarity_matrix

    @timing_decorator()
    def calc_pages_relevance(self, pages_text):
        """Análise de Frequência de Palavras com TF-IDF
        
        Nesta função, utilizamos o método de Term Frequency-Inverse Document Frequency (TF-IDF) 
        para calcular a importância de cada palavra em um documento (ou página de um PDF).
        
        A ideia é que as palavras mais comuns em um documento são menos importantes do que as palavras
        mais raras, pois elas são mais representativas do conteúdo do documento.
        
        Por isso, utilizamos o vetorizador TfidfVectorizer para:
        1. Transformar cada página em um vetor de palavras únicas
        2. Calcular a frequência de cada palavra em cada página
        3. Calcular a frequência inversa do documento (IDF) para cada palavra
        4. Calcular a pontuação TF-IDF para cada palavra em cada página
        
        A pontuação TF-IDF é calculada como o produto da frequência de uma palavra em uma página
        e a sua frequência inversa do documento. Isso significa que as palavras mais comuns em um
        documento terão uma pontuação TF-IDF mais baixa, enquanto as palavras mais raras terão uma
        pontuação TF-IDF mais alta.
        
        Por fim, retornamos um array com as pontuações TF-IDF para cada página.
        
        :param pages_text: Array de strings com o texto de cada página
        :return: Array de pontuações TF-IDF para cada página

        Em outras palavras:

        O TF-IDF é um método usado para identificar quais palavras são mais importantes em um texto. Ele funciona assim:

        TF (Frequência do termo): Conta quantas vezes uma palavra aparece em uma página.
        IDF (Frequência inversa do documento): Dá menos importância às palavras muito comuns e mais importância às palavras raras.
        TF-IDF: Multiplica os dois valores acima. Assim, palavras que aparecem muito em um documento, mas pouco em outros, recebem pontuação alta.
        Isso ajuda a destacar palavras que realmente representam o conteúdo do texto, ignorando palavras genéricas como "e", "de", "o".
        """
        stop_words = list(set(stopwords.words('portuguese')))
        vectorizer = TfidfVectorizer(stop_words=stop_words)
        tf_idf_matrix = vectorizer.fit_transform(pages_text)
        tf_idf_scores = tf_idf_matrix.sum(axis=1).A1 
        return tf_idf_scores

    # Métodos comparativos:............................................

    def return_similar_pages(self, indice_a_comparar:int, similarity_matrix, limiar=0.87):
        """
        Identifica páginas semelhantes com base em uma matriz de similaridade.
        
        :param indice_a_comparar: Índice da página base para comparação
        :param similarity_matrix: Matriz de similaridade entre as páginas
        :param limiar: Limiar de similaridade para considerar páginas semelhantes (padrão: 0.87)
        :return: Lista de índices das páginas semelhantes
        """
        # Objetivo: Filtrar páginas redundantes (considerando limiar de similaridade > 0.87)
        # TODO: obter tamanho do grupo a partir da similarity_matrix, dispensando o argumento tamanho_do_grupo
        tamanho_do_grupo = similarity_matrix.shape[0]
        semelhantes = []
        i = indice_a_comparar
        for j in range(tamanho_do_grupo):
            if i == j: 
                continue
            if similarity_matrix[i][j] > limiar:
                semelhantes.append(j)
        return semelhantes

    # Métodos principais da classe:....................................

    @timing_decorator()
    def extract_and_analyze_pdf(self, pdf_path, indice_paginas=None):
        """
        Processa um PDF, extrai texto de cada página e calcula similaridade entre as páginas.
        
        :param pdf_path: Caminho do arquivo PDF
        :param indice_paginas: Índices das páginas a serem processadas
        :return: Dicionário com dados de cada página, incluindo texto, tamanho, relevância e similaridade
        """
        try:
            if not os.path.exists(pdf_path):
                raise FileNotFoundError(f"PDF não encontrado: {pdf_path}")
            logger.info(f'Processando PDF {os.path.basename(pdf_path)}')

            # Extrai texto de cada página do PDF
            tp_pages_text = self.pdf_processor.extract_texts_from_pdf(pdf_path, indice_paginas=indice_paginas)
            tp_pages_text = [(ind, self.preprocess_1(texto)) for ind, texto in tp_pages_text] 
            
            # Processa o texto de cada página
            pages_text = [self.preprocess_2(texto) for _, texto in tp_pages_text] 
            similarity_matrix = self.analyze_similarities(pages_text)
            tf_idf_scores = self.calc_pages_relevance(pages_text)

            dict_dados_pages = {}        
            for ind, text in tp_pages_text:
                inteligível = self.is_intelligible(text)
                if not inteligível:
                    logger.warning(f'[red]Página {ind+1} considerada ininteligível ({detect(text)}) / Qtde caracteres: {len(text)}')
                dict_dados_pages[ind] = {
                    'texto':    text, 
                    'number_words': self.count_unique_words(text), 
                    'number_tokens':count_tokens(text), 
                    'inteligível':  inteligível, 
                    'tf_idf_score': round(tf_idf_scores[ind], 4), 
                    'semelhantes':  self.return_similar_pages(ind, similarity_matrix) 
                    }
            
            # indices_pgs_relevantes, ininteligiveis = filter_and_classify_pages(dict_dados_pages)
            return dict_dados_pages 
        except Exception as e:
            logger.error(f"Erro ao processar PDF: {str(e)}")
            raise
    
    def filter_and_classify_pages(self, dict_dados_pages):
        """
        Ordena as páginas mais importantes de um PDF com base em sua relevância e similaridade.
        
        :param dict_dados_pages: Dicionário com dados de cada página (texto, tamanho, relevância e similaridade)
        :return: Tupla com (índices das páginas mais relevantes, índices das páginas consideradas ininteligíveis)
        """
        # Conjuntos para acompanhar as páginas processadas e irrelevantes
        processadas     = set()
        ininteligiveis  = set()
        irrelevantes    = set()
        mais_relevantes = set()  # Usar set para evitar duplicados
        
        # Processar cada página
        for i, dados in dict_dados_pages.items():
            if i in processadas:
                continue
            
            # Se a página não é inteligível, adiciona ao conjunto de ininteligíveis
            if not dados['inteligível']:
                ininteligiveis.add(i)
                irrelevantes.add(i)  # Páginas não inteligíveis são irrelevantes
            # Se a página tem semelhantes, selecionar a com maior tamanho
            elif dados['semelhantes']:
                # Conjunto de páginas semelhantes
                grupo_semlh = [p for p in (dados['semelhantes'] + [i]) if p not in processadas]
                # Selecionar a página com maior tamanho
                maior_pagina = max(grupo_semlh, key=lambda p: dict_dados_pages[p]['number_words'])
                mais_relevantes.add(maior_pagina)
                logger.info(f'Selecionada página {maior_pagina+1} do grupo de semelhantes {[p+1 for p in grupo_semlh]}.')
                # Potencializa o score por haver repetição da página no contexto:
                dict_dados_pages[maior_pagina]['tf_idf_score'] = dict_dados_pages[maior_pagina]['tf_idf_score'] *2 
                processadas.update(grupo_semlh)
                irrelevantes.update(set(grupo_semlh) - {maior_pagina})  # Restantes são irrelevantes
            # Se a página não tem semelhantes, adiciona ao conjunto de mais relevantes
            else:
                mais_relevantes.add(i)  # Páginas inteligíveis sem semelhantes são relevantes
                
            processadas.add(i)
        
        # Ordenar as páginas mais relevantes
        mais_relevantes = [(p, dict_dados_pages[p]['tf_idf_score']) for p in mais_relevantes]
        mais_relevantes = sorted(mais_relevantes, key=lambda x: x[1], reverse=True)
        mais_relevantes = [it[0] for it in mais_relevantes]
        
        # print_dict_as_table(dict_dados_pages, ['inteligível', 'number_words', 'tf_idf_score', 'semelhança_geral', 'semelhantes'], sort_key='tf_idf_score')
        return mais_relevantes, list(ininteligiveis)

    def text_groupby_relevance_and_token_limit(self, dict_dados_pages, indices_pgs_relevantes, limite_token):
        """
        Agrupa textos de páginas relevantes respeitando um limite de tokens.
        
        :param dict_pgs_relevantes: Dicionário com textos das páginas relevantes
        :param indices_pgs_relevantes: Lista de índices das páginas relevantes
        :param limite_token: Limite máximo de tokens permitido
        
        :return: Tupla com (string de páginas consideradas, texto acumulado)
        """
        dict_pgs_relevantes = {k: v['texto'] for k, v in dict_dados_pages.items() if k in indices_pgs_relevantes}
        total_tokens = 0
        indices_considerado = []
        for page in indices_pgs_relevantes:
            texto = dict_pgs_relevantes.get(page, "")
            indices_considerado.append(page)
            len_texto = count_tokens(texto)
        
            # Verifica se o texto do grupo cabe no limite
            if total_tokens + len_texto <= limite_token:
                total_tokens += len_texto
            else:
                # Completa o restante do limite com parte do texto, se houver espaço
                dict_pgs_relevantes[page] = reduce_text_to_limit(texto, limite_token-total_tokens) # texto_parcial
                print(f'Texto reduzido na página {page+1}.')
                break  # Sai do loop ao atingir o limite

        str_paginas_consideradas = get_string_intervalos(indices_considerado, incrementa_1=True)

        texto_acumulado = ""
        for ind in sorted(indices_considerado):
            texto_acumulado += f" {dict_pgs_relevantes[ind]}"

        return str_paginas_consideradas, texto_acumulado

'''
def process_pdf(pdf_path, indice_paginas=None):
    print(f'Processando PDF {os.path.basename(pdf_path)}')
    start_time = time()

    tp_pages_text = extract_texts_from_pdf(pdf_path, indice_paginas=indice_paginas)
    tp_pages_text = [(ind, preprocess_text_1(texto)) for ind, texto in tp_pages_text] 

    dict_dados_pages = {}
    if not indice_paginas:
        pages_text = [preprocess_text_2(texto) for _, texto in tp_pages_text] 
        similarity_matrix = analise_similaridade(pages_text)
        tf_idf_scores = analise_frequencia_palavras(pages_text)
        
        for ind, text in tp_pages_text:
            semelhantes = return_similar_pages(len(pages_text), ind, similarity_matrix)
            inteligível = is_intelligible(text, ind=ind)
            dict_dados_pages[ind] = {'texto':text, 
                                'inteligível': inteligível, 
                                'tamanho': count_unique_words(text), 
                                'tf_idf_score': round(tf_idf_scores[ind], 4), 
                                'semelhantes': semelhantes }

        indices_pgs_relevantes, ininteligiveis = ordenar_paginas_relevantes(dict_dados_pages)
        dict_pgs_relevantes = {k: v['texto'] for k, v in dict_dados_pages.items() if k in indices_pgs_relevantes}
    else:
        for ind, text in tp_pages_text:
            dict_dados_pages[ind] = text

        indices_pgs_relevantes = indice_paginas
        dict_pgs_relevantes = dict_dados_pages
        ininteligiveis = []

    end_time = time()  # Marca o tempo de término
    tempo_de_processamento = f"Tempo de processamento do arquivo: {end_time - start_time:.2f}s"
    return dict_pgs_relevantes, indices_pgs_relevantes, ininteligiveis, tempo_de_processamento

def agrupar_textos_por_prioridade(dict_pgs_relevantes, indices_pgs_relevantes, limite_token, modelo_ia):
    total_tokens = 0
    indices_considerado = []
    for page in indices_pgs_relevantes:
        texto = dict_pgs_relevantes.get(page, "")
        indices_considerado.append(page)
        len_texto = count_tokens(modelo_ia, texto)
    
        # Verifica se o texto do grupo cabe no limite
        if total_tokens + len_texto <= limite_token:
            total_tokens += len_texto
        else:
            # Completa o restante do limite com parte do texto, se houver espaço
            dict_pgs_relevantes[page] = reduzir_texto_para_limite(texto, limite_token-total_tokens, modelo_ia) # texto_parcial
            print(f'Texto reduzido na página {page+1}.')
            break  # Sai do loop ao atingir o limite

    str_paginas_consideradas = get_string_intervalos(indices_considerado, incrementa_1=True)

    texto_acumulado = ""
    for ind in sorted(indices_considerado):
        texto_acumulado += f" {dict_pgs_relevantes[ind]}"

    return str_paginas_consideradas, texto_acumulado

'''