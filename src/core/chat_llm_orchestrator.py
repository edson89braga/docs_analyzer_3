# src/core/chat_llm_orchestrator.py
"""
Módulo de orquestração para o chat interativo com documentos.

Responsável por gerenciar a conversa com a Responses API da OpenAI, construindo
o payload de entrada, gerenciando o streaming de eventos e calculando métricas de uso.
"""

import logging
logger = logging.getLogger(__name__)

import time
from typing import List, Dict, Any, Optional, Generator, Tuple

import openai
from openai import AuthenticationError, APIError

from src.utils import with_proxy
from src.core.ai_orchestrator import calc_costs_llm_analysis
from src.settings import DEFAULT_LLM_PROVIDER, DEFAULT_LLM_MODEL, DEFAULT_TEMPERATURE


def find_prefix_match_len(str1: str, str2: str) -> int:
    """Encontra o comprimento do prefixo comum mais longo entre duas strings."""
    min_len = min(len(str1), len(str2))
    for i in range(min_len):
        if str1[i] != str2[i]:
            return i
    return min_len

class ChatLLMOrchestrator:
    """
    Orquestra a conversa entre o usuário e o LLM, com base no contexto de um documento.
    """
    def __init__(self):
        """
        Inicializa o orquestrador de chat.
        """
        self.client: Optional[openai.OpenAI] = None
        self.previous_response_id = None

        self.last_request_debug_info = {
            # "prompt_cache_key": None,
            # "instructions_str": "",
            "input_str": ""
        }        

    def _initialize_client(self, api_key: str):
        """Inicializa o cliente OpenAI se necessário."""
        if self.client is None or self.client.api_key != api_key:
            if not api_key:
                msg_error = "A chave da API da OpenAI deve ser fornecida."
                logger.error(msg_error)
                raise ValueError(msg_error)
            
            logger.debug("Inicializando ou atualizando cliente OpenAI para o chat.")
            self.client = openai.OpenAI(api_key=api_key)

    def _build_input_items(
        self,
        document_context: str,
        history: List[Dict[str, str]],
        user_question: str,
        instructions: str = None
    ) -> List[Dict[str, str]]:
        """
        Constrói a lista de itens de entrada para a Responses API.
        """
        input_items = []

        if instructions is not None:
            input_items.append({
                "role": "system",
                "content": instructions
            })

        # Adiciona o contexto do documento e a confirmação inicial. 
        input_items.append({
            "role": "user",
            "content": f"Considere o conteúdo transcrito abaixo como contexto para as perguntas que farei a seguir:\n\n"
                       f"--- INÍCIO DO CONTEÚDO TRANSCRITO ---\n"
                       f"{document_context}\n"
                       f"--- FIM DO CONTEÚDO TRANSCRITO ---"
        })
        input_items.append({
            "role": "assistant",
            "content": "Entendido. Estou pronto para responder perguntas sobre o documento fornecido."
        })

        # Adiciona o histórico da conversa
        input_items.extend(history)
        
        # Adiciona a nova pergunta do usuário
        input_items.append({"role": "user", "content": user_question})

        return input_items

    @with_proxy()
    def generate_response(
        self,
        api_key: str,
        model_name: str,
        instructions: str,
        document_context: str,
        history: List[Dict[str, str]],
        user_question: str,
        loaded_llm_providers: List[Dict[str, Any]],
        temperature: float = 1.0,
        reasoning_mode: str = None,
        verbosity_level: str = None
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Gera uma resposta do LLM via streaming usando a Responses API.

        Args:
            api_key: A chave da API da OpenAI.
            model_name: O nome do modelo a ser usado (ex: "gpt-4o-mini").
            temperature: A temperatura para a geração da resposta.
            instructions: As instruções de sistema para o modelo.
            document_context: O texto completo do documento a ser analisado.
            history: O histórico da conversa atual.
            user_question: A nova pergunta do usuário.

        Yields:
            Dict[str, Any]: Dicionários contendo o status e os dados.
        """
        self._initialize_client(api_key)
        
        if not self.client:
            yield {"type": "error", "content": "Cliente OpenAI não inicializado."}
            return

        # Monta o prompt de instruções com o contexto estático
        # instructions_with_context = (
        #     "--- INÍCIO DE CONTEÚDO DE DOCUMENTO(S) PARA ANÁLISE ---\n"
        #     f"{document_context}\n"
        #     "--- FIM DO CONTEÚDO DO DOCUMENTO ---\n\n"
        #     f"{instructions}\n\n"
        #     "Com base no documento fornecido e nas instruções acima, responda às perguntas e interações a seguir."
        # )

        # Gera uma chave de cache estável baseada no conteúdo do documento.
        # Isso ajuda a OpenAI a rotear requisições sobre o mesmo documento para o mesmo cache. 
        # [Esta estratégia não funcionou]
        # cache_key_hash = hashlib.sha256(document_context.encode('utf-8')).hexdigest()
        # prompt_cache_key = f"doc_sha256_{cache_key_hash}"

        if not self.previous_response_id:
            input_items = self._build_input_items(document_context, history, user_question, instructions=instructions)
        else:
            # Com ativação do Previous_response_id e do Store, o input itens deve ser apenas a nova pergunta do usuário
            input_items = [{"role": "user", "content": user_question}]

        # --- DEBUG: Comparação de Prefixo ---            
        # Análise mais profunda comparando o conteúdo real
        # instructions_str = instructions_with_context
        input_str = str(input_items)
        
        if self.last_request_debug_info["input_str"]:
            # instr_match_len = find_prefix_match_len(self.last_request_debug_info["instructions_str"], instructions_str)
            input_match_len = find_prefix_match_len(self.last_request_debug_info["input_str"], input_str)

            # logger.info(f"[CACHE CHECK] Comprimento do prefixo correspondente em 'instructions': {instr_match_len} de {len(instructions_str)} caracteres.")
            logger.info(f"[CACHE CHECK] Comprimento do prefixo correspondente em 'input': {input_match_len} de {len(input_str)} caracteres.")
        else:
            logger.info("[CACHE CHECK] Primeira requisição - sem comparação disponível.")

        # Armazena as informações desta requisição para a próxima comparação
        # self.last_request_debug_info["prompt_cache_key"] = prompt_cache_key
        # self.last_request_debug_info["instructions_str"] = instructions_str 
        self.last_request_debug_info["input_str"] = input_str
        # --- FIM DEBUG ---

        full_response_content = ""
        final_usage_data = {}
        
        # Monta kwargs para a Requests API sem enviar parâmetros top-level inválidos
        data_to_openai_api = {
            "model": model_name,
            # "instructions": instructions_with_context, 
            # -> Movido para input_message (role: system) a fim de tentar ativar o cache ao descontinuar o uso do field instruction da api
            "input": input_items,
            "previous_response_id": self.previous_response_id,
            "truncation": "auto", 
            "temperature": temperature if model_name.startswith("gpt-4") else None,
            "stream": False,
            # Stream desabilitado propositalmente devido restrição da conta OpenAI que exige uma autenticação extra para uso de stream nos modelos gpt-5;
            # Poderia deixar habilitado o stream para uso com modelos gpt-4, mas parece que o excesso de atualizações em chunks prejudicou a GUI flet;
            "store": True 
            # Store obrigatório True se usar previous_response_id
            # "store": False # Padrão é True. Se False, não armazena resposta do modelo para recuperação posterior; Prejudicaria o cache?
        }
        try: 
            # Para modelos da família 'gpt-5' (ou outros que suportem), passe parâmetros
            # em estruturas aceitas pelo SDK/Responses API, em vez de 'reasoning_effort'/'verbosity'
            if model_name.startswith("gpt-5"):
                if reasoning_mode:
                    # parâmetro aninhado conforme SDK/Docs: reasoning: { "effort": "minimal" | "low" | ... }
                    data_to_openai_api["reasoning"] = {"effort": reasoning_mode}
                if verbosity_level:
                    # parâmetro aninhado para controlar verbosity/text: { "verbosity": "low" | "medium" | "high" }
                    data_to_openai_api["text"] = {"verbosity": verbosity_level}
                
            # Remove valores None (evita passar chaves com valor None)
            request_kwargs = {k: v for k, v in data_to_openai_api.items() if v is not None}
            
            request_kwargs_str = f"Model: {request_kwargs['model']}; stream: {request_kwargs['stream']};" 
            if 'reasoning' in request_kwargs:
                request_kwargs_str += f" Reasoning: {request_kwargs['reasoning']}; Text: {request_kwargs['text']};"
            # request_kwargs_str += f"\nInstructions: {request_kwargs['instructions'][:160]} \nInput items count: {len(input_items)}"
            msgs = [f"{item['content'][:100]}..." for item in request_kwargs['input']]
            msgs = "\n".join(msgs)
            request_kwargs_str += f"\n{msgs}"

            logger.info(f"[DEBUG] Enviando request para OpenAI com kwargs: \n{request_kwargs_str}") # TODO: suprimir esse log

            start_time = time.perf_counter()
            try:
                response = self.client.responses.create(**request_kwargs)

            except TypeError as te:
                # Detecta erro de parâmetro inesperado e tenta sem os campos novos
                msg = str(te)
                if any(x in msg for x in ("reasoning", "reasoning_effort", "verbosity", "text")):
                    logger.warning(
                        "Client não aceita os kwargs 'reasoning'/'text' — tentando novamente sem eles. "
                        f"Erro original: {msg}"
                    )
                    fallback_kwargs = {k: v for k, v in request_kwargs.items() if k not in ("reasoning", "text")}
                    response = self.client.responses.create(**fallback_kwargs)
                else:
                    raise

            # Se o request foi com stream=True, processa eventos como antes
            if request_kwargs.get("stream"):
                for event in response:
                    if event.type == "response.output_text.delta" and getattr(event, "delta", None):
                        content_chunk = event.delta
                        full_response_content += content_chunk
                        yield {"type": "chunk", "content": content_chunk}

                    if event.type == "response.completed":
                        if hasattr(event, "response") and event.response.usage:
                            final_usage_data = event.response.usage.model_dump()
                        break
            
            else:
                # Resposta completa em uma única chamada
                # 1) preferência: propriedade helper output_text (quando disponível)
                if hasattr(response, "output_text") and response.output_text:
                    full_response_content = response.output_text
                    yield {"type": "chunk", "content": full_response_content}
                else:
                    # 2) fallback: iterar por response.output e extrair textos
                    if hasattr(response, "output") and response.output:
                        for out in response.output:
                            # cada item pode expor .content (lista) ou .text — cobrimos ambos
                            if getattr(out, "content", None):
                                for c in out.content:
                                    text = getattr(c, "text", None) or (c.get("text") if isinstance(c, dict) else None)
                                    if text:
                                        full_response_content += text
                                        yield {"type": "chunk", "content": text}
                            elif getattr(out, "text", None):
                                full_response_content += out.text
                                yield {"type": "chunk", "content": out.text}

                # coleta métricas de uso se existirem
                if getattr(response, "usage", None):
                    final_usage_data = response.usage.model_dump()

                if getattr(response, "id", None):
                    self.previous_response_id = response.id
                    logger.info(f'[DEBUG] previous_response_id: {response.id}')
                else:
                    logger.info('[DEBUG] Resposta não contém "id" para previous_response_id.')

            total_time = round(time.perf_counter() - start_time, 2)

            # Finalização com métricas
            if final_usage_data:
                token_usage_info = {
                    "input_tokens":  final_usage_data.get("input_tokens", 0),
                    "cached_tokens": final_usage_data["input_tokens_details"]["cached_tokens"], 
                    "output_tokens": final_usage_data.get("output_tokens", 0),
                    "reasoning_tokens": final_usage_data["output_tokens_details"]["reasoning_tokens"], 
                    "total_tokens":  final_usage_data.get("total_tokens", 0),
                }

                cost_usd = calc_costs_llm_analysis(
                    token_usage_info["input_tokens"],
                    token_usage_info["cached_tokens"],
                    token_usage_info["output_tokens"],
                    "openai", # Hardcoded por enquanto, pois a lógica é específica
                    model_name,
                    loaded_llm_providers
                )
                token_usage_info["total_cost_usd"] = cost_usd
                
                logger.info(f"Resposta do chat recebida. Model: {model_name}; Tempo de resposta: {total_time}s; Métricas: {token_usage_info}")
                yield {"type": "final_metrics", "data": token_usage_info}
            else:
                logger.warning("Não foi possível obter métricas de uso da resposta do chat.")
                yield {"type": "final_metrics", "data": {}}

        except AuthenticationError as auth_err:
            logger.error(f"Erro de Autenticação com a API de Chat: {auth_err}", exc_info=True)
            yield {"type": "error", "content": f"Erro de Autenticação: Verifique sua chave API. ({auth_err.body.get('message', '')})"}
        except APIError as api_err:
            logger.error(f"Erro da API de Chat: {api_err}", exc_info=True)
            yield {"type": "error", "content": f"Erro da API provedora: {api_err.message}"}
        except Exception as e:
            logger.error(f"Erro inesperado durante a geração da resposta do chat: {e}", exc_info=True)
            yield {"type": "error", "content": f"Ocorreu um erro inesperado ao se comunicar com a IA: {e}"}

