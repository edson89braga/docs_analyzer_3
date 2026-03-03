# src/core/ai_orchestrator.py
"""
Módulo responsável por orquestrar a interação com os modelos de linguagem (LLMs)
usando LangChain.
"""
# Configuração do Logger
import datetime
import logging
logger = logging.getLogger(__name__)

from time import perf_counter
start_time = perf_counter()
logger.debug(f"{start_time:.4f}s - Iniciando ai_orchestrator.py")

import os
from typing import Optional, Dict, Any, List, Tuple, Union
from openai import OpenAI, AuthenticationError, APIError # Para tratamento específico de erros OpenAI

# Imports do Projeto
from src.settings import DEFAULT_LLM_PROVIDER, DEFAULT_LLM_MODEL, DEFAULT_TEMPERATURE

from src.utils import with_proxy
from src.core.prompts import (output_formats, review_function, normalizing_function, # prompts
                                formatted_initial_analysis, try_convert_to_pydantic_format, return_parse_prompt)

MODEL_FOR_COUNT_TOKENS = "gpt-4o"

def calc_costs_embedding_process(tokens_count, embedding_model_id, loaded_embeddings_providers) -> Optional[float]:
    """
    Calcula o custo do processo de embedding com base nos tokens e no modelo utilizado.

    Args:
        Contagem de tokens (int).
        ID do modelo de embedding (str) usado.
        loaded_embeddings_providers:Lista de dicionários, onde cada dicionário
                                    contém informações de configuração do modelo
                                    de embedding, incluindo 'name' (str) e cost_per_million' (float/int).
                                    Ou None se a lista de custos não estiver disponível.

    Returns:
        O custo calculado em USD como float, ou None se o cálculo não puder ser realizado
        devido a dados ausentes, inválidos ou configuração não encontrada.
    """
    #tokens_and_model_id_session = self.page.session.get(KEY_SESSION_TOKENS_EMBEDDINGS)
    #model_embeddings_list_session = self.page.session.get(KEY_SESSION_MODEL_EMBEDDINGS_LIST)
    
    if not tokens_count or not embedding_model_id:
        logger.debug("Dados de tokens e/ou ID do modelo não fornecidos para cálculo de custo de embedding.")
        return None
    
    if not loaded_embeddings_providers:
        logger.debug("Custos de modelos de embedding não fornecidos.")
        return None

    if not isinstance(tokens_count, int) or tokens_count < 0:
        logger.warning(
            f"Contagem de tokens inválida fornecida: {tokens_count}. "
            "Deve ser um inteiro não negativo." )
        return None

    if not embedding_model_id or not isinstance(embedding_model_id, str):
        logger.warning(
            f"ID do modelo de embedding inválido ou ausente: '{embedding_model_id}'. "
            "Deve ser uma string não vazia." )
        return None

    # Busca a configuração do modelo de embedding (case-insensitive para o nome do modelo)
    embedding_config = next(
        (
            emb for emb in loaded_embeddings_providers
            if emb.get("name", "").lower() == embedding_model_id.lower()
        ),
        None
    )

    if not embedding_config:
        logger.warning(
            f"Configuração de custo não encontrada para o modelo de embedding: '{embedding_model_id}'."
        )
        return None

    # Obtenção e validação do custo por milhão de tokens
    cost_per_million = embedding_config.get("cost_per_million")

    if cost_per_million is None:
        logger.warning(
            f"Atributo 'cost_per_million' não definido ou é None para o modelo "
            f"'{embedding_model_id}' na lista de configurações de custo."
        )
        return None
    
    if not isinstance(cost_per_million, (int, float)) or cost_per_million < 0:
        logger.warning(
            f"Valor de 'cost_per_million' inválido ({cost_per_million}) para o modelo "
            f"'{embedding_model_id}'. Deve ser um valor numérico não negativo."
        )
        return None

    # Se não houver tokens, o custo é zero.
    if tokens_count == 0:
        logger.debug(
            f"Nenhum token processado para o modelo '{embedding_model_id}'. "
            "Custo de embedding: U$ 0.00"
        )
        return 0.0

    # Cálculo do custo
    calculated_embedding_cost_usd = (tokens_count / 1_000_000) * cost_per_million

    logger.info(
        f"Custo de embeddings calculado: {tokens_count} tokens para o modelo "
        f"'{embedding_model_id}' -> U$ {calculated_embedding_cost_usd:.6f}"
    )
    return calculated_embedding_cost_usd

def calc_costs_llm_analysis(input_tokens, cached_tokens, output_tokens, provider_used_raw, model_used_raw, loaded_llm_providers):
    """
    Calcula o custo estimado da análise LLM com base nos tokens e na configuração do modelo.

    Args:
        input_tokens (int): Número de tokens de entrada.
        cached_tokens (int): Número de tokens em cache.
        output_tokens (int): Número de tokens de saída.
        provider_used_raw (str): Nome do provedor LLM utilizado.
        model_used_raw (str): Nome do modelo LLM utilizado.
        loaded_llm_providers (List[Dict]): Lista de configurações dos provedores LLM carregados.

    Returns:
        float: O custo calculado em USD como float, ou 0.0 se o cálculo não puder ser realizado.
    """
    calculated_cost_usd = 0.0

    #loaded_llm_providers = self.page.session.get(KEY_SESSION_LOADED_LLM_PROVIDERS)
    if loaded_llm_providers and provider_used_raw and model_used_raw:
        provider_config = next((
            p for p in loaded_llm_providers
            if p.get("system_name", "").lower() == provider_used_raw # Compara com system_name
        ), None)
        
        if provider_config:
            model_config = next((
                m for m in provider_config.get("models", [])
                if m.get('id', "").lower() == model_used_raw
            ), None)
            
            if model_config:
                cost_input = ((input_tokens-cached_tokens) / 1_000_000) * model_config.get("input_coust_million", 0.0)
                cost_cache = (cached_tokens / 1_000_000) * model_config.get("cache_coust_million", 0.0)
                cost_output = (output_tokens / 1_000_000) * model_config.get("output_coust_million", 0.0)
                calculated_cost_usd = cost_input + cost_cache + cost_output
                logger.info(f"Custo calculado: Input=${cost_input:.6f}, Cache=${cost_cache:.6f}, Output=${cost_output:.6f} -> Total=${calculated_cost_usd:.6f}")
            else:
                logger.warning(f"Configuração do modelo '{model_used_raw}' não encontrada para o provedor '{provider_used_raw}' para cálculo de custo.")
        else:
            logger.warning(f"Configuração do provedor '{provider_used_raw}' não encontrada para cálculo de custo.")
    else:
        logger.warning("Dados insuficientes (provedores carregados, provedor/modelo usado) para calcular o custo.")
    
    #metadata_to_display["total_cost_usd"] = calculated_cost_usd 
    return calculated_cost_usd

import json
import re
import tiktoken

def extract_and_clean_json(response_text: str) -> str:
    """
    Extrai e limpa JSON de uma resposta, removendo delimitadores de markdown,
    espaços em branco extras e tratando erros de formatação comuns.

    Args:
        response_text (str): Texto bruto da resposta que pode conter JSON.

    Returns:
        str: JSON limpo pronto para parsing.

    Raises:
        ValueError: Se nenhum JSON válido puder ser extraído.
    """
    if not response_text:
        raise ValueError("Texto de resposta vazio fornecido.")

    # Remove tags de thinking (< think > e < /think >)
    cleaned = response_text.replace("<think>", "").replace("</think>", "").strip()
    
    # Tenta remover delimitadores de markdown (```json ... ```, ``` ... ```)
    # Padrão 1: ```json ... ``` ou ```json ... ```
    markdown_pattern = r'```(?:json)?\s*(.*?)\s*```'
    match = re.search(markdown_pattern, cleaned, re.DOTALL)
    if match:
        cleaned = match.group(1).strip()
        logger.debug("JSON extraído de delimitadores markdown.")
    
    # Tenta remover whitespace extra no início/fim
    cleaned = cleaned.strip()
    
    # Tenta fazer um parse básico para validar
    try:
        json.loads(cleaned)
        logger.debug("JSON validado com sucesso após limpeza.")
        return cleaned
    except json.JSONDecodeError as e:
        logger.debug(f"Erro ao parsear JSON após limpeza inicial: {e}")
    
    # Fallback: tenta encontrar um objeto JSON dentro do texto
    # Procura por { no início e } no final
    brace_start = cleaned.find('{')
    brace_end = cleaned.rfind('}')
    
    if brace_start != -1 and brace_end != -1 and brace_start < brace_end:
        potential_json = cleaned[brace_start:brace_end + 1]
        try:
            json.loads(potential_json)
            logger.debug("JSON extraído procurando por chaves { }.")
            return potential_json
        except json.JSONDecodeError as e:
            logger.debug(f"Erro ao parsear JSON extraído por chaves: {e}")
    
    # Fallback: tenta encontrar um array JSON
    bracket_start = cleaned.find('[')
    bracket_end = cleaned.rfind(']')
    
    if bracket_start != -1 and bracket_end != -1 and bracket_start < bracket_end:
        potential_json = cleaned[bracket_start:bracket_end + 1]
        try:
            json.loads(potential_json)
            logger.debug("JSON array extraído procurando por colchetes [ ].")
            return potential_json
        except json.JSONDecodeError as e:
            logger.debug(f"Erro ao parsear JSON array extraído por colchetes: {e}")
    
    # Se tudo falhar, loga o texto para debug e lança erro
    logger.error(f"Não foi possível extrair JSON válido. Texto recebido:\n{cleaned[:500]}")
    raise ValueError(
        f"Não foi possível extrair JSON válido da resposta. "
        f"Primeiro caractere: '{cleaned[0] if cleaned else 'VAZIO'}'."
    )

def contar_tokens(texto: Union[str, Any], model_name: str) -> int:
    """
    Conta o número de tokens em um texto usando o codificador tiktoken.

    Args:
        texto (Union[str, Any]): O texto a ser tokenizado. Será convertido para string se não for.
        model_name (str): O nome do modelo para o qual o codificador tiktoken será obtido.

    Returns:
        int: O número de tokens no texto.
    """
    codificador = tiktoken.encoding_for_model(model_name)
    texto = str(texto) if not isinstance(texto, str) else texto
    return len(codificador.encode(texto))
    
def criar_batches(
    textos_com_indices: List[Tuple[int, str]],
    limite_tokens_por_texto: int,
    limite_tokens_por_batch: int,
    model_name: str
) -> List[Tuple[List[str], List[int]]]:
    """
    Cria batches de textos a partir de uma lista de (índice_original, texto),
    respeitando os limites de tokens por texto individual e por batch.

    Args:
        textos_com_indices: Lista de tuplas (índice_original, texto_da_pagina).
        limite_tokens_por_texto: Máximo de tokens permitido para um único texto.
        limite_tokens_por_batch: Máximo total de tokens permitido para um batch de textos.
        model_name: Nome do modelo de embedding para contagem de tokens.

    Returns:
        Lista de tuplas, onde cada tupla contém:
        (lista_de_textos_para_o_batch, lista_de_indices_originais_correspondentes).
    """
    batches_com_info_original = []
    batch_atual_textos = []
    batch_atual_indices_originais = []
    tokens_acumulados_no_batch_atual = 0

    for original_idx, texto_pagina in textos_com_indices:
        tokens_texto_pagina = contar_tokens(texto_pagina, model_name)

        if tokens_texto_pagina > limite_tokens_por_texto:
            logger.warning(
                f"Texto original no índice {original_idx} com {tokens_texto_pagina} tokens "
                f"excede o limite de {limite_tokens_por_texto} tokens por texto e será ignorado."
            )
            continue  # Pula este texto

        # Se o batch atual não estiver vazio E adicionar o novo texto estouraria o limite do batch
        if batch_atual_textos and \
           (tokens_acumulados_no_batch_atual + tokens_texto_pagina > limite_tokens_por_batch):
            # Fecha o batch atual e o adiciona à lista de batches
            batches_com_info_original.append((batch_atual_textos, batch_atual_indices_originais))
            # Reseta para um novo batch
            batch_atual_textos = []
            batch_atual_indices_originais = []
            tokens_acumulados_no_batch_atual = 0
        
        # Adiciona o texto atual (que é válido) ao batch atual
        batch_atual_textos.append(texto_pagina)
        batch_atual_indices_originais.append(original_idx)
        tokens_acumulados_no_batch_atual += tokens_texto_pagina

    # Adiciona o último batch se ele contiver algum texto
    if batch_atual_textos:
        batches_com_info_original.append((batch_atual_textos, batch_atual_indices_originais))

    logger.debug("Procedido: criar_batches")
    return batches_com_info_original

client_openai = None

@with_proxy()
def get_embeddings_from_api(
    pages_texts: List[str],
    model_embedding: str = 'text-embedding-3-small',
    api_key: Optional[str] = None, # Alterado para Optional[str]
    loaded_embeddings_providers: Optional[List[Dict[str, Any]]] = None # Alterado para Optional
) -> Tuple[List[Union[List[float], None]], int, float]:
    """
    Obtém embeddings para uma lista de textos usando a API da OpenAI,
    respeitando os limites de tokens e gerenciando batches.

    Args:
        pages_texts: Lista de strings, onde cada string é o texto de uma página.
        model_embedding: Nome do modelo de embedding da OpenAI a ser usado.
        api_key: Chave da API da OpenAI (opcional, pode ser pega do ambiente).
        loaded_embeddings_providers: Informações sobre provedores (para cálculo de custo, opcional).

    Returns:
        Uma tupla contendo:
        - Lista de embeddings: Mesmo tamanho de `pages_texts`. Cada item é um vetor (lista de floats)
          ou None se o embedding não pôde ser gerado para aquela página.
        - total_tokens_api: Número total de tokens processados pela API.
        - cost_usd: Custo estimado em USD do processamento.
    """
    global client_openai

    if not pages_texts:
        logger.debug("get_embeddings_from_api: Recebeu uma lista de textos vazia. Retornando resultados vazios.")
        return [], 0, 0

    if not isinstance(pages_texts, list) or not isinstance(pages_texts[0], str):
        logger.warning(f"Erro de tipo em get_embeddings_from_api. Esperado List[str], mas recebeu {type(pages_texts)} com tipos interno {type(pages_texts[0])}.")
        
    if model_embedding != 'text-embedding-3-small': # Atualmente, focando neste modelo
        raise ValueError(f"Modelo de embedding '{model_embedding}' não é 'text-embedding-3-small' e não é suportado por esta implementação focada.")

    logger.info(f"Solicitando embeddings da API para o modelo: {model_embedding}")

    # Limites da API OpenAI (conforme regras fornecidas)
    LIMITE_TOKENS_POR_TEXTO_API = 8191
    # LIMITE_TOKENS_POR_BATCH_API = 300_000 # Limite "hard" da API
    # Usar o recomendado com margem para evitar problemas com a contagem da API
    LIMITE_TOKENS_POR_BATCH_RECOMENDADO = 250_000
    # Adicional: text-embedding-3-small e -large podem aceitar um array de até 2048 strings.
    # Nossa função criar_batches não limita o número de strings, apenas o total de tokens.
    # Para robustez extra, poderíamos adicionar um limite de strings por batch, mas o token é o principal.

    # Associa cada texto ao seu índice original para rastreamento
    textos_com_indices_originais = list(enumerate(pages_texts))

    # Cria os batches de textos válidos, já desconsiderando os que excedem o limite individual
    batches_para_api = criar_batches(
        textos_com_indices_originais,
        LIMITE_TOKENS_POR_TEXTO_API,
        LIMITE_TOKENS_POR_BATCH_RECOMENDADO,
        model_embedding
    )

    # Inicializa a lista final de embeddings com Nones
    # Terá o mesmo tamanho da lista `pages_texts` original.
    lista_final_embeddings_ordenada: List[Union[List[float], None]] = [None] * len(pages_texts)
    total_tokens_api = 0
    cost_usd = 0.0

    if not batches_para_api:
        logger.warning(
            "Nenhum batch foi criado para a API. Isso pode ocorrer se a lista de "
            "textos de entrada estiver vazia ou se todos os textos excederem o "
            "limite individual de tokens."
        )
        return lista_final_embeddings_ordenada, total_tokens_api, cost_usd

    try:
        # Configura o cliente OpenAI se ainda não estiver configurado ou se uma nova chave for fornecida
        # Esta lógica assume que se `api_key` é fornecido, ele deve ser usado,
        # caso contrário, o cliente (se já existir) ou um novo cliente usará a chave do ambiente.
        current_api_key_in_env = os.environ.get("OPENAI_API_KEY")
        key_to_use = api_key if api_key else current_api_key_in_env

        if not key_to_use:
            raise ValueError("Chave API da OpenAI não fornecida nem configurada no ambiente.")

        # Reinstanciar o cliente se a chave mudou ou se não existe
        if client_openai is None or (api_key and client_openai.api_key != api_key) :
            logger.debug("Instanciando ou reinstanciando o cliente OpenAI com a chave fornecida/ambiente.")
            client_openai = OpenAI(api_key=key_to_use, timeout=180, max_retries=2)
        
        for batch_de_textos, batch_de_indices_originais in batches_para_api:
            if not batch_de_textos: # Segurança, não deve acontecer se criar_batches for correta
                continue

            # Para text-embedding-3-small, a dimensão padrão é 1536.
            # Se você quisesse um número menor de dimensões (e o modelo suportar), passaria `dimensions=`
            response = client_openai.embeddings.create(
                model=model_embedding,
                input=batch_de_textos
                # dimensions=256 # Exemplo se quisesse embeddings menores e o modelo suportasse
            )

            # A API retorna os embeddings na mesma ordem dos textos enviados no input do batch.
            # response.data[j].embedding corresponde a batch_de_textos[j]
            # response.data[j].index é o índice DENTRO DO BATCH (0 a N-1 do batch)
            for i, embedding_obj in enumerate(response.data):
                indice_original_da_pagina = batch_de_indices_originais[i]
                lista_final_embeddings_ordenada[indice_original_da_pagina] = embedding_obj.embedding
            
            total_tokens_api += response.usage.total_tokens
        
        if loaded_embeddings_providers:
            cost_usd = calc_costs_embedding_process(total_tokens_api, model_embedding, loaded_embeddings_providers)

    except Exception as e:
        logger.error(f"Erro ao obter embeddings da API OpenAI: {e}", exc_info=True)
        # Em caso de erro, a lista_final_embeddings_ordenada pode estar parcialmente preenchida.
        # O chamador pode decidir como lidar com isso.
        # Re-lançar a exceção é geralmente uma boa prática.
        raise

    num_embeddings_gerados = sum(1 for emb in lista_final_embeddings_ordenada if emb is not None)
    logger.info(
        f"Embeddings obtidos para {num_embeddings_gerados} de {len(pages_texts)} páginas. "
        f"Total de tokens API: {total_tokens_api}. Custo estimado: ${cost_usd:.5f}"
    )
    assert num_embeddings_gerados == len(pages_texts)

    return lista_final_embeddings_ordenada, total_tokens_api, cost_usd

def convert_pydantic_to_json_schema(formatted_initial_pydantic: Any) -> Dict[str, Any]:
    """
    Converte um modelo Pydantic para um esquema JSON compatível com a API OpenAI.

    Args:
        formatted_initial_pydantic (Any): Uma instância de um modelo Pydantic.

    Returns:
        Dict[str, Any]: Um dicionário representando o esquema JSON para a API OpenAI.
    """
    schema = formatted_initial_pydantic.model_json_schema()
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "formatted_initial_pydantic",
            "schema": schema,
            "strict": False
        }
    }
    return response_format

def _get_prompt_to_cache(prompts, key_prompt: str, placeholder_str: str, input_processed_text: str) -> Tuple[List[Dict[str, str]], int]:
    """
    Prepara um prompt para cache, substituindo um placeholder e contando os tokens.

    Args:
        key_prompt (str): Chave para recuperar o prompt do dicionário `prompts`.
        placeholder_str (str): O placeholder a ser substituído no prompt.
        input_processed_text (str): O texto que substituirá o placeholder.

    Returns:
        Tuple[List[Dict[str, str]], int]: Uma tupla contendo:
            - A lista de dicionários do prompt modificado.
            - A contagem de tokens do prompt principal.
    """
    prompt_inicial_para_cache = prompts[key_prompt]
    prompt_inicial_para_cache = [{key: value.replace(placeholder_str, input_processed_text) for key, value in msg_dict.items()} for msg_dict in prompt_inicial_para_cache]
    main_tokens_count = contar_tokens(prompt_inicial_para_cache, MODEL_FOR_COUNT_TOKENS)
    if main_tokens_count:
        logger.info(f"Total_tokens contabilizado na parte principal: {main_tokens_count}")
    else:
        logger.warning("Placeholder [input_text] não encontrado ou não contabilizado na apuração do cache mínimo previsto!")
    return prompt_inicial_para_cache, main_tokens_count

def _get_final_response(dados_segmentados: List[Any], output_format: Any) -> Any:
    """
    Extrai a resposta final de uma lista de dados segmentados e tenta convertê-la
    para o formato de saída especificado, se necessário.

    Args:
        dados_segmentados (List[Any]): Uma lista de objetos de resposta segmentados.
        output_format (Any): O formato de saída esperado (e.g., um modelo Pydantic).

    Returns:
        Any: A resposta final, possivelmente convertida para o formato especificado.
    """
    final_response = dados_segmentados[-1].output_text
    if not isinstance(final_response, output_format):
        final_response = try_convert_to_pydantic_format(final_response, output_format)
    logger.debug("Procedido: _get_final_response -> try_convert_to_pydantic_format")
    return final_response
                
def _get_token_usage_info(dados_segmentados: List[Any], waited_cached_tokens: int = 0) -> Dict[str, Any]:
    """
    Calcula e retorna informações de uso de tokens a partir de dados segmentados.
    Também loga informações sobre o aproveitamento de cache.

    Args:
        dados_segmentados (List[Any]): Uma lista de objetos de resposta segmentados,
                                       cada um contendo informações de uso de tokens.
        waited_cached_tokens (int): O número de tokens em cache esperados para verificação.

    Returns:
        Dict[str, Any]: Um dicionário contendo o total de input_tokens, cached_tokens,
                        output_tokens e total_tokens.
    """
    token_usage_info = {
        "input_tokens":  0,
        "cached_tokens": 0,
        "output_tokens": 0,
        "reasoning_tokens": 0,
        "total_tokens":  0,
    }
    
    for response in dados_segmentados:
        cb = response.usage # callback
        tokens_info = {
            "input_tokens":  cb.input_tokens,
            "cached_tokens": cb.input_tokens_details.cached_tokens,
            "output_tokens": cb.output_tokens,
            "reasoning_tokens": cb.output_tokens_details.reasoning_tokens,
            "total_tokens":  cb.total_tokens,
        }
        token_usage_info["input_tokens"]  += tokens_info["input_tokens"]
        token_usage_info["cached_tokens"] += tokens_info["cached_tokens"]
        token_usage_info["output_tokens"] += tokens_info["output_tokens"]
        token_usage_info["reasoning_tokens"] += tokens_info["reasoning_tokens"]
        token_usage_info["total_tokens"]  += tokens_info["total_tokens"]

    # Analisar proporção de cached_tokens em prompts:
    if waited_cached_tokens:
        if token_usage_info["cached_tokens"] >= (waited_cached_tokens*0.96):
            logger.info(f"A apuração do cache mínimo previsto foi atingida: {token_usage_info['cached_tokens']} >= {waited_cached_tokens}")
        else:
            logger.warning(f"O cache mínimo previsto NÃO foi registrado! {token_usage_info['cached_tokens']} < {waited_cached_tokens}")
    else: # fallback para tentar confirmar uma proporção mínima
        if not token_usage_info["cached_tokens"]:
            logger.warning("Não houve aproveitamento de cache!")
        else:
            aproveitamento = round(token_usage_info["cached_tokens"]/token_usage_info["input_tokens"] , 2)
            logger.info(f"Proporção de aproveitamento de cache: {aproveitamento}")
    
    logger.debug("Procedido: _get_token_usage_info")
    return token_usage_info

# --- Função Principal de Análise ---
@with_proxy()
def analyze_text_with_llm(
        prompt_name: str,
        prompts: Dict[str, List],
        processed_text: str,
        provider: str = DEFAULT_LLM_PROVIDER,
        model_name: Optional[str] = DEFAULT_LLM_MODEL,
        temperature: float = DEFAULT_TEMPERATURE,
        api_key: str = None,
        loaded_llm_providers: Dict = {},
        normalizing_and_review_response: bool = True
    ) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
    """
    Envia texto processado para um LLM através do LangChain para análise,
    usando ChatPromptTemplate para prompts estruturados com roles.

    Args:
        processed_text (str): O texto extraído e pré-processado do PDF.
        provider (str): O provedor LLM a ser usado (atualmente suporta 'openai').
        model_name (Optional[str]): O modelo específico a ser usado (ex: 'gpt-4o').
                                     Se None, usa o padrão para o provedor.
        temperature (float): Parâmetro de temperatura para a geração do LLM.
        prompt_name (str): O nome do prompt a ser recuperado do módulo `prompts`.
                           Espera-se que retorne uma lista de tuplas (role, content_template).

    Returns:
        Tuple[Optional[Any], Optional[Dict[str, Any]]]: Uma tupla contendo:
            - final_response: A resposta final do LLM, formatada conforme `output_formats`.
            - token_usage_info: Um dicionário com informações detalhadas sobre o uso de tokens e custo.
    """
    global client_openai

    logger.info(f"Iniciando análise de texto com LLM. Provider: {provider}, Model: {model_name}; Prompt: {prompt_name}")
       
    start_time = perf_counter()

    llm = None
    #chain_result: Optional[Dict[str, Any]] = None
    final_response: Optional[str] = None
    token_usage_info: Optional[Dict[str, Any]] = None

    try:
        if provider == "openai":
            os.environ["OPENAI_API_KEY"] = api_key
            
            # Reinstancia o cliente se ele não existir ou se a chave API mudou.
            if client_openai is None or client_openai.api_key != api_key:
                logger.info(f"Instanciando ou atualizando cliente OpenAI com a nova chave API para o provedor '{provider}'.")
                client_openai = OpenAI(api_key=api_key, timeout=180, max_retries=2)
            
            # Chamada à API de ChatCompletion
            if not client_openai:
                client_openai = OpenAI(timeout=180, max_retries=2)
            
            if prompt_name == "PROMPT_UNICO_for_INITIAL_ANALYSIS":
                prompt_list_dicts = prompts[prompt_name]
                modified_prompt_list = []
                for msg_dict in prompt_list_dicts:
                    modified_msg_dict = {key: value.replace("{input_text}", processed_text) for key, value in msg_dict.items()}
                    modified_prompt_list.append(modified_msg_dict)

                # Converter a classe Pydantic para JSON schema
                json_schema = output_formats[prompt_name].model_json_schema()
                json_schema = output_formats[prompt_name].model_json_schema()
                json_schema["required"] = list(json_schema["properties"].keys())
                json_schema["additionalProperties"] = False
                data_to_api = {
                    "model": model_name,
                    "input": modified_prompt_list, # Lista única
                    "text": {
                        "format": {
                            "type": "json_schema",
                            "name": output_formats[prompt_name].__name__,  
                            "schema": json_schema,
                            "strict": True
                        }
                    }                 
                    # "text_format": output_formats[prompt_name]
                }
                if model_name.startswith("gpt-4"):
                    data_to_api.update({"temperature": temperature})

                logger.info('[DEBUG]: Requisitando à API da Openai...')
                # response = client_openai.responses.parse(**data_to_api)

                response = client_openai.responses.create(**data_to_api)
                
                logger.info('[DEBUG]: Requisição concluída.')
                
                final_response_text = response.output_text
                try:
                    final_response_text_clean = extract_and_clean_json(final_response_text)
                    final_response = output_formats[prompt_name].model_validate_json(final_response_text_clean)
                except (ValueError, json.JSONDecodeError) as e:
                    logger.error(f"Erro ao processar JSON do OpenAI: {e}")
                    raise
                
                # Obter informações sobre o uso de tokens
                cb = response.usage # callback
                token_usage_info = {
                        "input_tokens":  cb.input_tokens,
                        "cached_tokens": cb.input_tokens_details.cached_tokens,
                        "output_tokens": cb.output_tokens,
                        "reasoning_tokens": cb.output_tokens_details.reasoning_tokens,
                        "total_tokens":  cb.total_tokens,
                        "successful_requests": 1,
                    }
                token_usage_info["total_cost_usd"] = calc_costs_llm_analysis(token_usage_info["input_tokens"], token_usage_info["cached_tokens"], token_usage_info["output_tokens"], 
                                                                             provider, model_name, loaded_llm_providers)
            elif prompt_name == "PROMPTS_SEGMENTADOS_for_INITIAL_ANALYSIS":
                # prompt_inicial_para_cache, main_tokens_count = _get_prompt_to_cache(prompts, "prompt_inicial_para_cache", "{input_text}", processed_text)
                raise ValueError("Modo 'Prompt segmentado' não implementado.")                

        elif provider == "lang_chain_openai":
            raise ValueError("Provedor LangChain OpenAI não implementado.")

        elif provider == "llm_pf":
            # Configurações para o endpoint interno da PF
            base_url = "http://llm.pf.gov.br:31893/v1"
            api_key_pf = "EMPTY"
            model_pf = "Qwen3-8B-AWQ"  # Modelo fixo para este endpoint
            
            # Instancia o cliente OpenAI com base_url customizada
            client_pf = OpenAI(
                api_key=api_key_pf,
                base_url=base_url,
                timeout=180,
                max_retries=2
            )
            
            if prompt_name == "PROMPT_UNICO_for_INITIAL_ANALYSIS":
                prompt_list_dicts = prompts[prompt_name]
                # Anexar /no_think ao processed_text para llm_pf
                processed_text_with_no_think = processed_text + " /no_think"
                messages = []
                for msg_dict in prompt_list_dicts:
                    modified_msg_dict = {key: value.replace("{input_text}", processed_text_with_no_think) for key, value in msg_dict.items()}
                    messages.append(modified_msg_dict)

                # Converter a classe Pydantic para JSON schema
                json_schema = output_formats[prompt_name].model_json_schema()
                json_schema["required"] = list(json_schema["properties"].keys())
                json_schema["additionalProperties"] = False
                
                response_format = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": output_formats[prompt_name].__name__,
                        "schema": json_schema,
                        "strict": True
                    }
                }
                
                # Chamada para chat completions
                logger.info('[DEBUG]: Requisitando à API do endpoint PF...')
                response = client_pf.chat.completions.create(
                    model=model_pf,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=32000,  # Ajustar conforme necessário
                    response_format=response_format
                )
                logger.info('[DEBUG]: Requisição concluída.')
                
                # Extrair o conteúdo da resposta
                final_response_text = response.choices[0].message.content

                logger.info(f"[DEBUG]: final_response_text obtido: \n{final_response_text}\n")
                
                try:
                    final_response_text_clean = extract_and_clean_json(final_response_text)
                    final_response = output_formats[prompt_name].model_validate_json(final_response_text_clean)
                except (ValueError, json.JSONDecodeError) as e:
                    logger.error(f"Erro ao processar JSON do endpoint PF: {e}", exc_info=True)
                    raise
                
                # Obter informações sobre o uso de tokens (se disponível)
                usage = response.usage
                if usage:
                    token_usage_info = {
                        "input_tokens": usage.prompt_tokens if hasattr(usage, 'prompt_tokens') else 0,
                        "cached_tokens": 0,  # Endpoint PF pode não suportar cache
                        "output_tokens": usage.completion_tokens if hasattr(usage, 'completion_tokens') else 0,
                        "reasoning_tokens": 0,
                        "total_tokens": usage.total_tokens if hasattr(usage, 'total_tokens') else 0,
                        "successful_requests": 1,
                    }
                    token_usage_info["total_cost_usd"] = 0.0  # Custos não aplicáveis ou calcular se houver config
                else:
                    token_usage_info = {
                        "input_tokens": 0,
                        "cached_tokens": 0,
                        "output_tokens": 0,
                        "reasoning_tokens": 0,
                        "total_tokens": 0,
                        "successful_requests": 1,
                        "total_cost_usd": 0.0
                    }
                    
            elif prompt_name == "PROMPTS_SEGMENTADOS_for_INITIAL_ANALYSIS":
                raise ValueError("Modo 'Prompt segmentado' não implementado para provider 'llm_pf'.")
            
        # --- Adicionar blocos `elif provider == "azure":` etc. aqui no futuro ---
            
        # --- Adicionar blocos `elif provider == "azure":` etc. aqui no futuro ---
        # elif provider == "azure":
        #    env_var_name = "AZURE_OPENAI_API_KEY"
        #    #os.environ[env_var_name] = decrypted_api_key
        #    # Configurar endpoint, deployment_name etc.
        #    # llm = AzureChatOpenAI(...)
        #    # ... (resto da configuração da cadeia) ...
        #    logger.warning("Provedor Azure não implementado.")
        #    return None # Por enquanto

        else:
            logger.error(f"Provedor LLM '{provider}' não suportado.")
            return None, None

    except AuthenticationError as auth_err:
        logger.error(f"Erro de Autenticação com a API {provider}: {auth_err}. Verifique a chave API.", exc_info=True)
        # A GUI deve notificar o usuário sobre a chave inválida.
    except APIError as api_err:
        logger.error(f"Erro da API {provider}: {api_err}. Pode ser um problema temporário ou de input.", exc_info=True)
        # Pode ser útil retornar a mensagem de erro para a UI.
    except Exception as e:
        logger.error(f"Erro inesperado durante a execução de Analyze_text_with_LLM ({provider}): {e}", exc_info=True)
    
    finally:
        os.environ["OPENAI_API_KEY"] = ""

    #pr-int('\n\n', f'final_response: {type(final_response)}\n', final_response, '\n\n')

    if normalizing_and_review_response:
        # Normalizações e revisões devem ser feitas aqui
        final_response = normalizing_function(final_response)
        
        final_response = review_function(final_response)

    logger.info(f"Token_usage_info: {token_usage_info}")

    processing_time = perf_counter() - start_time
    return final_response, token_usage_info, processing_time

### ================================================================================================
# FUNÇÕES UTILITÁRIAS:

def get_text_from_pdf(pdf_path: str) -> Optional[str]:
    if not os.path.exists(pdf_path):
        logger.error(f"Arquivo PDF não encontrado em: {pdf_path}")
        return None
 
    from src.core.pdf_processor import PDFDocumentAnalyzer
    analyzer = PDFDocumentAnalyzer()
    # Extrai o texto de todas as páginas
    combined_processed_page_data, all_global_page_keys_ordered, \
    embedding_vectors_combined, tfidf_vectors_combined, tf_idf_scores_array_combined = analyzer.analyze_pdf_documents([pdf_path])
    
    final_selected_ordered_indices, _, _ = analyzer.filter_and_classify_pages(
        combined_processed_page_data, all_global_page_keys_ordered,embedding_vectors_combined, tfidf_vectors_combined, tf_idf_scores_array_combined)
    
    _, full_text, _, final_aggregated_tokens = analyzer.group_texts_by_relevance_and_token_limit(combined_processed_page_data, final_selected_ordered_indices, 180000)

    logger.info(f"Total tokens from accumulated text: {final_aggregated_tokens}")
    logger.info(f"Texto extraído de {len(final_selected_ordered_indices)} páginas e concatenado.")
    
    return full_text

def get_prompt_template():
    import json
    from src.core.prompts import get_prompts_for_initial_analysis
    from src.settings import ASSETS_DIR

    prompts_path = os.path.join(ASSETS_DIR, 'dict_prompts.json')
    if not os.path.exists(prompts_path):
        logger.error(f"Arquivo de prompts não encontrado em: {prompts_path}")
        return None

    with open(prompts_path, 'r', encoding='utf-8') as f:
        loaded_components = json.load(f)

    # Constrói os pipelines de prompts usando a lógica existente
    final_prompts, _ = get_prompts_for_initial_analysis(
        loaded_components["ALL_lists"],
        loaded_components["ALL_prompts"]
    )

    prompt_unico_structure = final_prompts.get('PROMPT_UNICO_for_INITIAL_ANALYSIS')
    if not prompt_unico_structure:
        logger.error("A estrutura 'PROMPT_UNICO_for_INITIAL_ANALYSIS' não foi encontrada nos prompts construídos.")
        return None
    
    logger.info("Estrutura de prompt carregada e construída com sucesso.")
    return final_prompts

def generate_full_prompt_from_pdf(pdf_path: str) -> Optional[str]:
    """
    Gera um arquivo de texto (.txt) contendo o prompt completo que seria enviado à IA,
    a partir de um único arquivo PDF e do template de prompt "PROMPT_UNICO".

    Este método realiza as seguintes etapas:
    1. Extrai o conteúdo de texto completo de todas as páginas do PDF fornecido.
    2. Carrega a estrutura de prompts a partir do arquivo JSON local ('dict_prompts.json').
    3. Constrói o pipeline de "PROMPT_UNICO_for_INITIAL_ANALYSIS".
    4. Mescla o texto do PDF no placeholder {input_text} do prompt.
    5. Salva o resultado final em um arquivo .txt legível.

    Args:
        pdf_path (str): O caminho para o arquivo PDF de entrada.
        output_dir (str): O diretório onde o arquivo .txt de saída será salvo.

    Returns:
        Optional[str]: O caminho para o arquivo .txt gerado em caso de sucesso,
                       ou None se ocorrer um erro.
    """
    # from run import load_to_utils
    # load_to_utils()
    # from src.core.pdf_processor import *
    # from src.core.ai_orchestrator import *
    # 
    # pdf_path = input("Digite o caminho do PDF para composição do prompt_mesclado: ")
    # generate_full_prompt_from_pdf(pdf_path) 
    import json
    from pathlib import Path
    logger.info(f"Iniciando geração de prompt completo para o arquivo: {pdf_path}")

    # --- 1. Extrair e Processar o Conteúdo do PDF ---
    try:
        full_text = get_text_from_pdf(pdf_path)
        assert full_text

    except Exception as e:
        logger.error(f"Erro ao processar o PDF '{pdf_path}': {e}", exc_info=True)
        return None

    # --- 2. Carregar e Construir o Prompt Estruturado ---
    try:
        final_prompts = get_prompt_template()
        assert final_prompts

    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        logger.error(f"Erro ao carregar ou construir os prompts: {e}", exc_info=True)
        return None

    # --- 3. Mesclar Conteúdo do PDF no Prompt e Formatar Saída ---
    final_prompt_content_str = ""
    placeholder = "{input_text}"

    prompt_unico_structure = final_prompts.get('PROMPT_UNICO_for_INITIAL_ANALYSIS')
    for i, prompt_part in enumerate(prompt_unico_structure):
        role = prompt_part.get("role", "unknown_role").upper()
        content = prompt_part.get("content", "")

        # Substitui o placeholder pelo texto completo do PDF
        if placeholder in content:
            content = content.replace(placeholder, full_text)

        final_prompt_content_str += f"--- PARTE {i+1}: ROLE = {role} ---\n\n"
        final_prompt_content_str += content
        final_prompt_content_str += "\n\n"
    
    # --- 4. Salvar o Prompt Completo em Arquivo .txt ---
    output_dir = os.getcwd()
    try:
        # Cria o diretório de saída se não existir
        os.makedirs(output_dir, exist_ok=True)

        # Gera um nome de arquivo de saída baseado no nome do PDF
        pdf_filename_stem = Path(pdf_path).stem
        output_filename = f"{pdf_filename_stem}_full_prompt.txt"
        output_path = os.path.join(output_dir, output_filename)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_prompt_content_str)

        logger.info(f"Prompt completo salvo com sucesso em: {output_path}")
        return output_path

    except IOError as e:
        logger.error(f"Erro de I/O ao salvar o arquivo de prompt: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Erro inesperado ao salvar o arquivo de prompt: {e}", exc_info=True)
        return None

api_key = '...'
def get_response_llm_from_pdf(pdf_path):
    from pathlib import Path

    aggregated_text = get_text_from_pdf(pdf_path)
    loaded_prompts = get_prompt_template()
    
    final_response, token_usage_info, processing_time_llm = analyze_text_with_llm("PROMPT_UNICO_for_INITIAL_ANALYSIS", loaded_prompts, aggregated_text,
                                                                                                        api_key=api_key, normalizing_and_review_response=False)
    logger.info(f"Uso de Tokens da LLM: {token_usage_info}")
    logger.info(f"Tempo de processamento da LLM: {processing_time_llm:.4f}s")

    # Salvar a resposta final em um arquivo .txt local
    output_dir = os.getcwd()
    try:
        pdf_filename_stem = Path(pdf_path).stem 
        output_filename = f"{pdf_filename_stem}_final_response.txt"
        output_path = os.path.join(output_dir, output_filename)
        with open(output_path, 'w', encoding='utf-8') as f: f.write(final_response)
        print(f"Resposta final salva com sucesso em: {output_path}")
    except IOError as e:
        print(f"Erro de I/O ao salvar o arquivo de resposta: {e}", exc_info=True)

### ================================================================================================

execution_time = perf_counter() - start_time
logger.info(f"[DEBUG] Carregado AI_ORCHESTRATOR em {execution_time:.4f}s")
