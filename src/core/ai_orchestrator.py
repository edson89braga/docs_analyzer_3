# src/core/ai_orchestrator.py
"""
Módulo responsável por orquestrar a interação com os modelos de linguagem (LLMs)
usando LangChain.
"""
import os
from time import perf_counter
from typing import Optional, Dict, Any, List, Tuple
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
from src.core.prompts import prompts, output_formats, review_function, normalizing_function, formatted_initial_analysis, try_convert_to_pydantic_format, merge_parts_into_model

# Configuração do Logger
# (Assume que LoggerSetup já foi inicializado em run.py)
from src.logger.logger import LoggerSetup
logger = LoggerSetup.get_logger(__name__)

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
    # Corrigido erro de digitação: "cost_per_million" em vez de "coust_per_million"
    cost_per_million = embedding_config.get("coust_per_million")

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
                cost_input = (input_tokens / 1_000_000) * model_config.get("input_coust_million", 0.0)
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
    return len(codificador.encode(texto))
    
def criar_batches(textos, limite_tokens, model_name):
    batches = []
    batch_atual = []
    tokens_batch = 0

    for texto in textos:
        tokens_texto = contar_tokens(texto, model_name)
        if tokens_texto > limite_tokens:
            continue  # Ignora textos que excedem o limite individual
        if batch_atual and (tokens_batch + tokens_texto > limite_tokens):
            batches.append(batch_atual)
            batch_atual = []
            tokens_batch = 0
        
        batch_atual.append(texto)
        tokens_batch += tokens_texto

    if batch_atual:
        batches.append(batch_atual)

    return batches

client_openai = None

@timing_decorator()
def get_embeddings_from_api(pages_texts: List[str], model_embedding: str, api_key: str = None, loaded_embeddings_providers: List[dict] = None) -> Tuple:
    global client_openai
    if model_embedding == 'text-embedding-3-small':
        logger.info('[DEBUG]: Modelo embeddings: text-embedding-3-small')
        try:
            os.environ["OPENAI_API_KEY"] = api_key
            if not client_openai:
                client_openai = OpenAI()
            
            limite_tokens = 300_000
            batches = criar_batches(pages_texts, limite_tokens, model_embedding)

            embeddings, total_tokens = [], 0
            for batch in batches:
                response = client_openai.embeddings.create(
                    model=model_embedding,
                    input=batch,
                )
                embeddings.extend([item.embedding for item in response.data])
                total_tokens += (response.usage.total_tokens)
            
            cost_usd = 0
            if loaded_embeddings_providers:
                cost_usd = calc_costs_embedding_process(total_tokens, model_embedding, loaded_embeddings_providers)

        finally:
            os.environ["OPENAI_API_KEY"] = ""
    else:
        raise ValueError(f"Modelo embeddings '{model_embedding}' desconhecido.")
    
    return embeddings, total_tokens, cost_usd

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
    
    # 2. Obter o Prompt (formato de mensagens de chat)
    # Ex: [{"role": "system", "content": "Você é um assistente."}, 
    # {"role": "user", "content": "Analise: {input_text}"}]
    
    start_time = perf_counter()

    # 3. Configurar e Executar a Cadeia LangChain
    llm = None
    #chain_result: Optional[Dict[str, Any]] = None
    final_response: Optional[str] = None
    token_usage_info: Optional[Dict[str, Any]] = None

    # Define a chave API no ambiente TEMPORARIAMENTE para o LangChain usar
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
                    text_format = output_formats[prompt_name] # formatted_initial_analysis
                    #text={
                    #    "format": {
                    #        "type": "json_schema",
                    #        "name": "FormatAnaliseInicial",
                    #        "strict": False,
                    #        "schema": FormatAnaliseInicial.model_json_schema()
                    #    }
                    #},
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
                dados_segmentados = []
                main_tokens_count = 0
                for msg_dict in prompts[prompt_name]:
                    if "{input_text}" in msg_dict["content"]:
                        relevant_part = msg_dict["content"].replace("{input_text}", processed_text)
                        main_tokens_count = contar_tokens(relevant_part, MODEL_FOR_COUNT_TOKENS)
                        logger.info(f"Total_tokens contabilizado na parte principal: {main_tokens_count}")
                        break
                if not main_tokens_count:
                    logger.warning("Placeholder [input_text] não encontrado ou não contabilizado na apuração do cache mínimo previsto!")

                for prompt_group, output_format in zip(prompts[prompt_name], output_formats):
                    
                    modified_prompt_list = []
                    for msg_dict in prompt_group:
                        modified_msg_dict = {key: value.replace("{input_text}", processed_text) for key, value in msg_dict.items()}
                        modified_prompt_list.append(modified_msg_dict)

                    response = client_openai.responses.parse(
                        model=model_name,
                        input=modified_prompt_list, 
                        temperature=temperature,
                        text_format = output_format 
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
                        }   
                    dados_segmentados.append((final_response, token_usage_info))  
                
                token_usage_info = {
                    "input_tokens":  0,
                    "cached_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens":  0,
                } 
                all_finals_responses = []
                for dados, output_format in zip(dados_segmentados, output_formats):
                    final_response, tokens_info = dados
                    
                    if not isinstance(final_response, output_format):
                        final_response = try_convert_to_pydantic_format(final_response, output_format)
                        all_finals_responses.append(final_response)
                    
                    token_usage_info["input_tokens"]  += tokens_info["input_tokens"]
                    token_usage_info["cached_tokens"] += tokens_info["cached_tokens"]
                    token_usage_info["output_tokens"] += tokens_info["output_tokens"]
                    token_usage_info["total_tokens"]  += tokens_info["total_tokens"]
                
                # Unificar output_formats:
                final_response = merge_parts_into_model(parts=all_finals_responses, target_model=formatted_initial_analysis)
                print(f"\n[DEBUG] final_response by merge: {final_response}")

                # Analisar proporção de cached_tokens em prompts:
                tokens_minimo_in_cache = main_tokens_count * (len(dados_segmentados)-1) # O prompt inicial não aproveita cache
                if tokens_minimo_in_cache:
                    if token_usage_info["cached_tokens"] >= tokens_minimo_in_cache:
                        logger.info(f"A apuração do cache mínimo previsto foi atingida: {token_usage_info['cached_tokens']} >= {tokens_minimo_in_cache}")
                    else:
                        logger.warning(f"O cache mínimo previsto NÃO foi registrado! {token_usage_info['cached_tokens']} < {tokens_minimo_in_cache}")
                else: # fallback para tentar confirmar uma proporção mínima
                    if not token_usage_info["cached_tokens"]:
                        logger.warning("Não houve aproveitamento de cache!")
                    else:
                        aproveitamento = round(token_usage_info["cached_tokens"]/token_usage_info["input_tokens"] , 2)
                        logger.info(f"Proporção de aproveitamento de cache: {aproveitamento}")
                
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


# --- (Opcional) Exemplo de uso (somente para teste direto do módulo) ---
if __name__ == '__main__':
    print("Executando teste local do ai_orchestrator (requer configuração manual e credenciais)")

    # Para testar, você precisaria:
    # 1. Simular um objeto 'page' com 'session' contendo token/id válidos.
    # 2. Ter uma chave API válida salva no Firestore e a chave Fernet no Keyring.
    # 3. Fornecer um texto de exemplo.

    # Exemplo (NÃO FUNCIONAL SEM SETUP COMPLETO):
    # class MockPage:
    #     def __init__(self):
    #         self.session = {
    #             "auth_id_token": "SEU_TOKEN_ID_AQUI",
    #             "auth_user_id": "SEU_USER_ID_AQUI"
    #         }
    #     def get(self, key): return self.session.get(key)
    #     def contains_key(self, key): return key in self.session
    #     def set(self, key, value): self.session[key] = value
    #     def remove(self, key): self.session.pop(key, None)

    # mock_page = MockPage()
    # sample_text = "Este é um documento de exemplo sobre Python e Flet..."

    # try:
    #     # Certifique-se que o Firebase Admin está inicializado se for rodar fora do Flet
    #     from src.services.firebase_manager import inicializar_firebase
    #     inicializar_firebase() # Pode precisar de tratamento de erro

    #     analysis_result = analyze_text_with_llm(mock_page, sample_text)

    #     if analysis_result:
    #         print("\n--- Resultado da Análise ---")
    #         print(analysis_result)
    #     else:
    #         print("\n--- Análise falhou ---")

    # except Exception as main_e:
    #      print(f"Erro ao executar teste principal: {main_e}")
    pass


'''
Testes interativos:

from src.settings import api_key_test
from src.core.ai_orchestrator import *

os.environ["OPENAI_API_KEY"] = api_key_test

client_openai = OpenAI()

=====================================================

response = client_openai.chat.completions.create(
    model="gpt-4.1-nano",
    messages=[
        {"role": "user", "content": "Diga-me em que você pode me ajudar."},
    ],
    response_format = response_format, # json_schema
)

final_response = response.choices[0].message.content

token_usage_info = response.usage

=====================================================

from pydantic import BaseModel 
class FormatTeste(BaseModel):
    resposta: str

response = client_openai.responses.create(
    model="gpt-4.1-nano",
    input=[{"role": "user", "content": "Diga-me em que você pode me ajudar."}],
    text={
        "format": {
            "type": "json_schema",
            "name": "FormatTeste",
            "strict": False,
            "schema": FormatTeste.model_json_schema()
        }
    }
)

response = client_openai.responses.parse(
    model="gpt-4.1-nano",
    input=[{"role": "user", "content": "Diga-me em que você pode me ajudar."}],
    text_format = FormatTeste          # parse também aceita pydantic direto
)

final_response = response.output_text
token_usage_info = response.usage

================================================================================================

from src.settings import api_key_test
from src.core.ai_orchestrator import *

provider= "openai"
model_name= "gpt-4.1-nano"
temperature= 0.2

llm = ChatOpenAI(
    model_name=model_name,
    temperature=temperature,
    openai_api_key=api_key_test 
)

template_simples = "Qual é a capital de {assunto}?"
prompt = PromptTemplate(input_variables=["assunto"], template=template_simples)

chain = LLMChain(llm=llm, prompt=prompt)

chain_result = chain.invoke({"assunto": "Afeganistão"})

with get_openai_callback() as cb:
    chain_result = chain.invoke({"assunto": "Afeganistão"})
    # token_usage_info = cb
    token_usage_info = {
        "input_tokens": cb.prompt_tokens,
        "input_tokens_cached": cb.prompt_tokens_cached,
        "output_tokens": cb.completion_tokens,
        "total_tokens": cb.total_tokens,
        "successful_requests": cb.successful_requests,
        "total_cost_usd": cb.total_cost
    }
    logger.info(f"Uso de tokens (OpenAI): {token_usage_info}")

chain_result.get("text")


=================================================================================================

client = client_openai

assistant = client.beta.assistants.create(
    model="gpt-4.1-nano",
    name = "Assistant NC Analytics", 
    instructions = "Você é um analista técnico especializado em triagem documental e análise preliminar de peças oficiais. Sua principal função é processar documentos recebidos por canais institucionais, extrair informações estruturadas relevantes, classificar os dados conforme listas de referência e elaborar resumos objetivos sobre o conteúdo analisado. "
                    "Atua com base em normas administrativas, jurídicas e operacionais, com foco em precisão, rastreabilidade e fundamentação."
)

new_thread = client.beta.threads.create()

for msg in lista_de_mensagens:
    client.beta.threads.messages.create(
        thread_id=new_thread.id,
        role=msg["role"],
        content=msg["content"]
    )

run = client.beta.threads.runs.create(
  assistant_id=assistant.id,
  thread_id=new_thread.id,
  model="gpt-4.1-nano",
    response_format={
        "type": "json_schema",
        "json_schema": {  
            "name": "FormatTeste",
            "strict": False,
            "schema": FormatTeste.model_json_schema()  # Schema válido
        }
    }
)
------------------------------------------------
run = client.beta.threads.create_and_run(
    assistant_id=assistant.id,
    thread={
        "messages": [
        {"role": "user", "content": "Diga-me em que você pode me ajudar."}
        ]
    },
    model="gpt-4.1-nano",
    response_format={
        "type": "json_schema",
        "json_schema": {  
            "name": "FormatTeste",
            "strict": False,
            "schema": FormatTeste.model_json_schema()  # Schema válido
        }
    }
)

messages = client.beta.threads.messages.list(thread_id=run.thread_id)
resposta = messages.data[0].content[0].text.value

run = client.beta.threads.runs.retrieve(
  thread_id=run.thread_id,
  run_id=run.id
)
tokens = run.usage
tokens = run.usage.prompt_tokens
tokens = run.usage.completion_tokens
tokens = run.usage.total_tokens
tokens = run.usage.prompt_token_details['cached_tokens']


.input_tokens_details.cached_tokens
runs = client.beta.threads.runs.list(run.thread_id)

'''