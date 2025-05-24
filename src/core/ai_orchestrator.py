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
from src.services.firebase_client import FirebaseClientFirestore # Para buscar chave criptografada
from src.services import credentials_manager # Para descriptografar a chave
from src.settings import DEFAULT_LLM_PROVIDER, DEFAULT_LLM_MODEL, DEFAULT_TEMPERATURE
from src.core import prompts # Módulo que criamos para os prompts
import flet as ft # Para obter contexto do usuário da página

# Configuração do Logger
# (Assume que LoggerSetup já foi inicializado em run.py)
from src.logger.logger import LoggerSetup
logger = LoggerSetup.get_logger(__name__)

from src.core.prompts import FormatAnaliseInicial
# Converta o modelo em um esquema JSON:
schema = FormatAnaliseInicial.model_json_schema()
# Adicione a propriedade 'strict' ao esquema:
response_format = {
    "type": "json_schema",
    "json_schema": {
        "name": "FormatAnaliseInicial",
        "schema": schema,
        "strict": False
    }
}

def get_api_key_in_firestore(user_token, user_id, provider):
    firestore_client = FirebaseClientFirestore() # Instancia o cliente Firestore
    # O nome do serviço no Firestore precisa corresponder ao que foi salvo na Task 1.3
    # Assumindo que foi salvo como "openai_api_key" para o provedor "openai"
    
    service_name_firestore = f"{provider}" # Ou uma lógica de mapeamento mais robusta
    logger.debug(f"Buscando chave API criptografada para serviço: {service_name_firestore}")
    encrypted_key_bytes = firestore_client.get_user_api_key_client(
        user_token, user_id, service_name_firestore
    )

    if not encrypted_key_bytes:
        logger.error(f"Chave API criptografada para '{service_name_firestore}' não encontrada no Firestore para o usuário {user_id}.")
        # A UI deve informar o usuário para configurar a chave.
        return None

    logger.debug("Descriptografando chave API...")
    decrypted_api_key = credentials_manager.decrypt(encrypted_key_bytes)

    if not decrypted_api_key:
        logger.error(f"Falha ao descriptografar a chave API para '{service_name_firestore}' do usuário {user_id}.")
        # Pode indicar chave de criptografia local ausente ou corrompida.
        return None

    logger.info(f"Chave API para o provedor '{provider}' obtida e descriptografada com sucesso.")
    return decrypted_api_key

client_openai = None

# --- Função Principal de Análise ---

def analyze_text_with_llm(
        page: ft.Page,
        prompt_name: str,
        processed_text: str,
        provider: str = DEFAULT_LLM_PROVIDER,
        model_name: Optional[str] = DEFAULT_LLM_MODEL,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
    """
    Envia texto processado para um LLM através do LangChain para análise,
    usando ChatPromptTemplate para prompts estruturados com roles.

    Args:
        page (ft.Page): A instância da página Flet para acesso ao contexto do usuário (token, ID).
        processed_text (str): O texto extraído e pré-processado do PDF.
        provider (str): O provedor LLM a ser usado (atualmente suporta 'openai').
        model_name (Optional[str]): O modelo específico a ser usado (ex: 'gpt-4o').
                                     Se None, usa o padrão para o provedor.
        temperature (float): Parâmetro de temperatura para a geração do LLM.
        prompt_name (str): O nome do prompt a ser recuperado do módulo `prompts`.
                           Espera-se que retorne uma lista de tuplas (role, content_template).

    Returns:
        tuple[Optional[str], Optional[Dict[str, Any]]]:
            A resposta do LLM em caso de sucesso e informações de uso de token,
            ou (None, None) em caso de erro.
    """
    global client_openai

    logger.info(f"Iniciando análise de texto com LLM. Provider: {provider}, Prompt: {prompt_name}")

    decrypted_api_key: Optional[str] = None # Gera a chave de sessão esperada (deve corresponder à lógica em LLMConfigCard)
    service_name_firestore = f"{provider}" # Ou uma lógica de mapeamento mais robusta
    session_key_for_decrypted_api_key = f"decrypted_api_key_{service_name_firestore}"

    # 0. Tenta obter da sessão (cache)
    if page.session.contains_key(session_key_for_decrypted_api_key):
        decrypted_api_key = page.session.get(session_key_for_decrypted_api_key)
        if decrypted_api_key: # Verifica se não é None ou string vazia, se isso for um estado válido
            logger.info(f"Chave API descriptografada para '{provider}' obtida da sessão.")
        else: # Chave na sessão mas é None/vazia, indica que não está configurada
            logger.warning(f"Chave API para '{provider}' está na sessão como vazia/None. Considerada não configurada.")
            # A UI deveria ter impedido a chamada ou o usuário precisa configurar.
            # Ou, se uma chave vazia na sessão significa "sem chave", então o comportamento está correto.
            # Vamos assumir que se está na sessão e não é uma string "válida", é porque não tem.
            # Se uma chave pode ser explicitamente None na sessão para indicar "não configurado",
            # a lógica abaixo de buscar no Firestore não seria acionada desnecessariamente.
            # Para este caso, se está na sessão e é None/vazia, não prosseguimos.
            if decrypted_api_key is None: # Se foi explicitamente setada como None
                logger.error(f"Chave API para '{provider}' explicitamente definida como None na sessão. O usuário precisa configurar.")
                return None, None # Ou mostrar mensagem para configurar

    # 1. Obter Contexto do Usuário e Chave API
    if not decrypted_api_key: # Se ainda não temos uma chave válida            
        logger.info(f"Chave API para '{provider}' não encontrada na sessão ou inválida. Tentando carregar do Firestore.")

        user_token = page.session.get("auth_id_token")
        user_id = page.session.get("auth_user_id")

        if not user_token or not user_id:
            logger.error("Contexto do usuário (token/ID) não encontrado na sessão Flet. Abortando análise.")
            # Idealmente, a UI já deveria ter garantido isso, mas é uma salvaguarda.
            # A UI deve lidar com a ausência de resposta.
            return None, None
                    
        try:
            decrypted_api_key = get_api_key_in_firestore(user_token, user_id, provider)
            if not decrypted_api_key:
                return None, None
            page.session.set(f"decrypted_api_key_{service_name_firestore}", decrypted_api_key)
        except Exception as e:
            logger.error(f"Erro ao obter/descriptografar chave API para '{provider}': {e}", exc_info=True)
            return None, None

    # Se após todas as tentativas, decrypted_api_key ainda for None ou vazia
    if not decrypted_api_key:
        logger.error(f"Chave API para o provedor '{provider}' não está configurada ou não pôde ser obtida.")
        # A UI deve informar o usuário para configurar a chave.
        return None, None
    
    # 2. Obter o Prompt (formato de mensagens de chat)
    # Ex: [{"role": "system", "content": "Você é um assistente."}, 
    # {"role": "user", "content": "Analise: {input_text}"}]
    prompt_dicts: Optional[List[Dict[str, str]]] = prompts.get_prompt(prompt_name)
    if not prompt_dicts or not isinstance(prompt_dicts, list):
        logger.error(f"Prompt '{prompt_name}' não encontrado ou não está no formato de lista de dicionários esperado.")
        return None, None
    if not all(isinstance(d, dict) and "role" in d and "content" in d for d in prompt_dicts):
        logger.error(f"Prompt '{prompt_name}' não contém os dicionários esperados com chaves 'role' e 'content'.")
        return None, None
    
    start_time = perf_counter()

    # 3. Configurar e Executar a Cadeia LangChain
    llm = None
    #chain_result: Optional[Dict[str, Any]] = None
    final_response: Optional[str] = None
    token_usage_info: Optional[Dict[str, Any]] = None

    # Define a chave API no ambiente TEMPORARIAMENTE para o LangChain usar
    try:
        if provider == "openai":
            # Replace placeholder {1} with {2} in all messages
            modified_prompt_dicts = []
            for msg_dict in prompt_dicts:
                modified_msg_dict = {key: value.replace("{input_text}", processed_text) for key, value in msg_dict.items()}
                modified_prompt_dicts.append(modified_msg_dict)
            prompt_dicts = modified_prompt_dicts

            try:
                os.environ["OPENAI_API_KEY"] = decrypted_api_key
                # Chamada à API de ChatCompletion
                if not client_openai:
                    client_openai = OpenAI()
                response = client_openai.responses.parse(
                    model=model_name,
                    input=prompt_dicts,
                    temperature=temperature,
                    text={
                        "format": {
                            "type": "json_schema",
                            "name": "FormatAnaliseInicial",
                            "strict": False,
                            "schema": FormatAnaliseInicial.model_json_schema()
                        }
                    },
                )
            finally:
                os.environ["OPENAI_API_KEY"] = ""

            final_response = response.output_text

            # Obter informações sobre o uso de tokens
            cb = response.usage # callback
            token_usage_info = {
                    "input_tokens": cb.input_tokens,
                    "cached_tokens": cb.input_tokens_details.cached_tokens,
                    "output_tokens": cb.output_tokens,
                    "total_tokens": cb.total_tokens,
                    "successful_requests": 1,
                    "total_cost_usd": 0 # TODO 
                }
        elif provider == "lang_chain_openai":
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
                openai_api_key=decrypted_api_key # Passa a chave aqui  
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
                    "input_tokens": cb.prompt_tokens,
                    "cached_tokens": cb.prompt_tokens_cached,
                    "output_tokens": cb.completion_tokens,
                    "total_tokens": cb.total_tokens,
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
        # A UI deve notificar o usuário sobre a chave inválida.
    except APIError as api_err:
        logger.error(f"Erro da API {provider}: {api_err}. Pode ser um problema temporário ou de input.", exc_info=True)
        # Pode ser útil retornar a mensagem de erro para a UI.
    except Exception as e:
        logger.error(f"Erro inesperado durante a execução da cadeia LangChain ({provider}): {e}", exc_info=True)

    end_time = perf_counter()

    return final_response, token_usage_info, end_time - start_time

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

response = client_openai.responses.parse(
    model="gpt-4.1-nano",
    input=[
        {"role": "user", "content": "Diga-me em que você pode me ajudar."},
    ],
    text={
        "format": {
            "type": "json_schema",
            "name": "FormatAnaliseInicial",
            "strict": False,
            "schema": FormatAnaliseInicial.model_json_schema()
        }
    }
)
#text_format = FormatAnaliseInicial # pydantic

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


'''