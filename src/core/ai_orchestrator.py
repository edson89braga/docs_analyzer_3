# src/core/ai_orchestrator.py
"""
Módulo responsável por orquestrar a interação com os modelos de linguagem (LLMs)
usando LangChain.
"""

from time import perf_counter
start_time = perf_counter()
print(f"{start_time:.4f}s - Iniciando ai_orchestrator.py")

import os
from typing import Optional, Dict, Any, List, Tuple, Union
from openai import OpenAI, AuthenticationError, APIError # Para tratamento específico de erros OpenAI

# LangChain Imports
from langchain_openai import ChatOpenAI
#from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain # Não será mais usado diretamente com PromptTemplate simples
from langchain_core.prompts import ChatPromptTemplate # Alterado de PromptTemplate
from langchain_core.output_parsers import StrOutputParser # Para LCEL
from langchain_community.callbacks.manager import get_openai_callback

# Imports do Projeto
from src.settings import DEFAULT_LLM_PROVIDER, DEFAULT_LLM_MODEL, DEFAULT_TEMPERATURE

from src.utils import timing_decorator
from src.core.prompts import (prompts, output_formats, review_function, normalizing_function,
                                formatted_initial_analysis, try_convert_to_pydantic_format, return_parse_prompt)

# Configuração do Logger
import logging
logger = logging.getLogger(__name__)

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
        logger.info("Dados de tokens e/ou ID do modelo não fornecidos para cálculo de custo de embedding.")
        return None
    
    if not loaded_embeddings_providers:
        logger.info("Custos de modelos de embedding não fornecidos.")
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
        logger.info(
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
    Returns:
        O custo calculado em USD como float, ou 0.0 se o cálculo não puder ser realizado.
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

import tiktoken

def contar_tokens(texto, model_name):
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

    return batches_com_info_original

client_openai = None

@timing_decorator()
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
        logger.info("get_embeddings_from_api: Recebeu uma lista de textos vazia. Retornando resultados vazios.")
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
             logger.info("Instanciando ou reinstanciando o cliente OpenAI com a chave fornecida/ambiente.")
             client_openai = OpenAI(api_key=key_to_use) # Usa a chave efetiva
        
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

def convert_pydantic_to_json_schema(formatted_initial_pydantic):
    #Conversão para modelo em esquema JSON, se necessário:
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

def _get_prompt_to_cache(key_prompt, placeholder_str, input_processed_text):
    prompt_inicial_para_cache = prompts[key_prompt]
    prompt_inicial_para_cache = [{key: value.replace(placeholder_str, input_processed_text) for key, value in msg_dict.items()} for msg_dict in prompt_inicial_para_cache]
    main_tokens_count = contar_tokens(prompt_inicial_para_cache, MODEL_FOR_COUNT_TOKENS)
    if main_tokens_count:
        logger.info(f"Total_tokens contabilizado na parte principal: {main_tokens_count}")
    else:
        logger.warning("Placeholder [input_text] não encontrado ou não contabilizado na apuração do cache mínimo previsto!")
    return prompt_inicial_para_cache, main_tokens_count

def _get_final_response(dados_segmentados, output_format):
    # print(f"\n[DEBUG] Response: {response}")
    # for response in dados_segmentados:
    #    final_response = response.output_text
    final_response = dados_segmentados[-1].output_text
    if not isinstance(final_response, output_format):
        final_response = try_convert_to_pydantic_format(final_response, output_format)
    return final_response
                
def _get_token_usage_info(dados_segmentados, waited_cached_tokens=0):
    # Obter informações sobre o uso de tokens
    token_usage_info = {
        "input_tokens":  0,
        "cached_tokens": 0,
        "output_tokens": 0,
        "total_tokens":  0,
    } 
    
    for response in dados_segmentados:
        cb = response.usage # callback
        tokens_info = {
            "input_tokens":  cb.input_tokens,
            "cached_tokens": cb.input_tokens_details.cached_tokens,
            "output_tokens": cb.output_tokens,
            "total_tokens":  cb.total_tokens,
        }
        token_usage_info["input_tokens"]  += tokens_info["input_tokens"]
        token_usage_info["cached_tokens"] += tokens_info["cached_tokens"]
        token_usage_info["output_tokens"] += tokens_info["output_tokens"]
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

    return token_usage_info

# --- Função Principal de Análise ---
@timing_decorator()
def analyze_text_with_llm(
        prompt_name: str,
        processed_text: str,
        provider: str = DEFAULT_LLM_PROVIDER,
        model_name: Optional[str] = DEFAULT_LLM_MODEL,
        temperature: float = DEFAULT_TEMPERATURE,
        api_key: str = None,
        loaded_llm_providers: Dict = {},
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
        (final_response: formatted_initial_analysis, 
        token_usage_info:Dict[str, Any],
        processing_time: float)
    """
    global client_openai

    logger.info(f"Iniciando análise de texto com LLM. Provider: {provider}, Prompt: {prompt_name}")
       
    start_time = perf_counter()

    llm = None
    #chain_result: Optional[Dict[str, Any]] = None
    final_response: Optional[str] = None
    token_usage_info: Optional[Dict[str, Any]] = None

    try:
        if provider == "openai":
            os.environ["OPENAI_API_KEY"] = api_key
            # Chamada à API de ChatCompletion
            if not client_openai:
                client_openai = OpenAI()
            if prompt_name == "PROMPT_UNICO_for_INITIAL_ANALYSIS":
                logger.info(f"Prompt_name recebido: {prompt_name}")
                prompt_list_dicts = prompts[prompt_name]
                modified_prompt_list = []
                for msg_dict in prompt_list_dicts:
                    modified_msg_dict = {key: value.replace("{input_text}", processed_text) for key, value in msg_dict.items()}
                    modified_prompt_list.append(modified_msg_dict)

                response = client_openai.responses.parse(
                    model=model_name,
                    input=modified_prompt_list, # Lista única
                    temperature=temperature,
                    text_format = output_formats[prompt_name]
                )
                #print(f"\n[DEBUG] Response: {response}")
                final_response = response.output_text

                # Obter informações sobre o uso de tokens
                cb = response.usage # callback
                token_usage_info = {
                        "input_tokens":  cb.input_tokens,
                        "cached_tokens": cb.input_tokens_details.cached_tokens,
                        "output_tokens": cb.output_tokens,
                        "total_tokens":  cb.total_tokens,
                        "successful_requests": 1,
                    }
                token_usage_info["total_cost_usd"] = calc_costs_llm_analysis(token_usage_info["input_tokens"], token_usage_info["cached_tokens"], token_usage_info["output_tokens"], 
                                                                             provider, model_name, loaded_llm_providers)
            elif prompt_name == "PROMPTS_SEGMENTADOS_for_INITIAL_ANALYSIS":
                logger.info(f"Prompt_name recebido: {prompt_name}")

                prompt_inicial_para_cache, main_tokens_count = _get_prompt_to_cache("prompt_inicial_para_cache", "{input_text}", processed_text)

                dados_segmentados = []
                for prompt_group in prompts[prompt_name]:
                    
                    response = client_openai.responses.create(
                        model=model_name,
                        input=prompt_inicial_para_cache+prompt_group, 
                        temperature=temperature,
                        user="Assistant_NC_Analytics" 
                    )
                    dados_segmentados.append(response)
                    print(f"[DEBUG] Final response for segment: {response.output_text}")
                    print(f"[DEBUG] Token usage info for segment: {response.usage}\n\n")
                
                parser_prompt_final = return_parse_prompt([response.output_text for response in dados_segmentados])
                
                response = client_openai.responses.parse(
                    model=model_name,
                    input=parser_prompt_final, 
                    temperature=temperature,
                    text_format=formatted_initial_analysis
                )
                dados_segmentados.append(response)
                
                print(f"[DEBUG] Final response for segment: {response.output_text}")
                print(f"[DEBUG] Token usage info for segment: {response.usage}\n\n")
                
                final_response = _get_final_response(dados_segmentados, formatted_initial_analysis)
                
                waited_cached_tokens=main_tokens_count*(len(dados_segmentados)-2) # O prompt inicial e final não aproveita cache
                token_usage_info = _get_token_usage_info(dados_segmentados, waited_cached_tokens)

                token_usage_info["total_cost_usd"] = calc_costs_llm_analysis(token_usage_info["input_tokens"], token_usage_info["cached_tokens"], token_usage_info["output_tokens"], 
                                                                    provider, model_name, loaded_llm_providers)
                # "successful_requests": 1,

        elif provider == "lang_chain_openai":
            prompt_dicts = prompts[prompt_name]
            try:
                prompt_messages_for_template: List[Tuple[str, str]] = []
                for msg_dict in prompt_dicts:
                    prompt_messages_for_template.append((msg_dict["role"], msg_dict["content"]))
                chat_prompt_template = ChatPromptTemplate.from_messages(prompt_dicts)
            except Exception as e:
                logger.error(f"Erro ao criar ChatPromptTemplate a partir das mensagens do prompt '{prompt_name}': {e}", exc_info=True)
                return None, None

            logger.info(f"Configurando LangChain com OpenAI. Modelo: {model_name}, Temp: {temperature}")

            llm = ChatOpenAI(
                model_name=model_name,
                temperature=temperature,
                openai_api_key=api_key # Passa a chave aqui  
            )
            
            #prompt_template = PromptTemplate(input_variables=["input_text"], template=prompt_string)
            #chain = LLMChain(llm=llm, prompt=prompt_template)
            
            # Construindo a cadeia com LCEL
            chain = chat_prompt_template | llm | StrOutputParser()

            # Usar o callback do OpenAI para capturar o uso de tokens
            # A variável no dicionário de entrada DEVE corresponder a 'input_variables' do PromptTemplate
            with get_openai_callback() as cb:
                final_response = chain.invoke({"input_text": processed_text})
                token_usage_info = {
                    "input_tokens":  cb.prompt_tokens,
                    "cached_tokens": cb.prompt_tokens_cached,
                    "output_tokens": cb.completion_tokens,
                    "total_tokens":  cb.total_tokens,
                    "successful_requests": cb.successful_requests,
                    "total_cost_usd": cb.total_cost
                }
                print('\n')
                logger.info(f"Uso de tokens (OpenAI): {token_usage_info}")
            
            # Processar o resultado da cadeia
            if final_response is not None:
                # A chave do resultado no dicionário é geralmente 'text' para LLMChain
                final_response = final_response.get("text") if isinstance(final_response, dict) else final_response
                if final_response:
                    logger.info("Análise LLM concluída com sucesso.")
                else:
                    logger.error(f"Cadeia LangChain executada, mas a resposta não contém a chave 'text' esperada. Resultado: {final_response}")
            else:
                logger.error(f"Resultado inesperado da cadeia LangChain: {final_response}")
            
        # --- Adicionar blocos `elif provider == "azure":` etc. aqui no futuro ---
        # elif provider == "azure":
        #    env_var_name = "AZURE_OPENAI_API_KEY"
        #    #os.environ[env_var_name] = decrypted_api_key
        #    # Configurar endpoint, deployment_name etc.
        #    # llm = AzureChatOpenAI(...)
        #    # ... (resto da configuração da cadeia) ...
        #    logger.warning("Provedor Azure ainda não implementado.")
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
        logger.error(f"Erro inesperado durante a execução da cadeia LangChain ({provider}): {e}", exc_info=True)
    
    finally:
        os.environ["OPENAI_API_KEY"] = ""

    print('\n\n', f'final_response: {type(final_response)}\n', final_response, '\n\n')

    # Normalizações e revisões devem ser feitas aqui
    final_response = normalizing_function(final_response)
    
    final_response = review_function(final_response)

    logger.info(f"Token_usage_info: {token_usage_info}")

    processing_time = perf_counter() - start_time
    return final_response, token_usage_info, processing_time


execution_time = perf_counter() - start_time
print(f"Carregado AI_ORCHESTRATOR em {execution_time:.4f}s")
