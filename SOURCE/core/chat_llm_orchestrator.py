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

from SOURCE.utils import with_proxy
from SOURCE.core.ai_orchestrator import calc_costs_llm_analysis
from SOURCE.settings import DEFAULT_LLM_PROVIDER, DEFAULT_LLM_MODEL, DEFAULT_TEMPERATURE

class ChatLLMOrchestrator:
    """
    Orquestra a conversa entre o usuário e o LLM, com base no contexto de um documento.
    """
    def __init__(self, provider: str = "openai"):
        """
        Inicializa o orquestrador de chat.
        
        Args:
            provider: O provedor LLM a ser usado (ex: "openai" ou "llm_pf").
        """
        self.provider = provider
        self.client: Optional[openai.OpenAI] = None

    def _initialize_client(self, api_key: str):
        """Inicializa o cliente OpenAI ou compatível se necessário."""
        if self.provider == "openai":
            if self.client is None or self.client.api_key != api_key:
                if not api_key:
                    msg_error = "A chave da API da OpenAI deve ser fornecida."
                    logger.error(msg_error)
                    raise ValueError(msg_error)
                
                logger.debug("Inicializando ou atualizando cliente OpenAI para o chat.")
                self.client = openai.OpenAI(api_key=api_key)
        elif self.provider == "llm_pf":
            # Para llm_pf, usar base_url customizada e api_key fixa
            base_url = "http://llm.pf.gov.br:31893/v1"
            api_key_pf = "EMPTY"
            if self.client is None or self.client.base_url != base_url:
                logger.debug("Inicializando cliente para endpoint llm_pf.")
                self.client = openai.OpenAI(
                    api_key=api_key_pf,
                    base_url=base_url
                )
        else:
            raise ValueError(f"Provedor '{self.provider}' não suportado.")

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
        previous_response_id: str,
        instructions: str,
        document_context: str,
        history: List[Dict[str, str]],
        user_question: str,
        loaded_llm_providers: List[Dict[str, Any]],
        temperature: float = 1.0,
        reasoning_mode: str = None,
        verbosity_level: str = None,
        provider: str = "openai"
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Gera uma resposta do LLM via streaming usando a API apropriada.

        Args:
            api_key: A chave da API (para OpenAI) ou ignorada (para llm_pf).
            model_name: O nome do modelo a ser usado (ex: "gpt-4o-mini" ou "Qwen3-8B-AWQ").
            temperature: A temperatura para a geração da resposta.
            instructions: As instruções de sistema para o modelo.
            document_context: O texto completo do documento a ser analisado.
            history: O histórico da conversa atual.
            user_question: A nova pergunta do usuário.
            provider: O provedor LLM ("openai" ou "llm_pf").

        Yields:
            Dict[str, Any]: Dicionários contendo o status e os dados.
        """
        self._initialize_client(api_key)
        
        if not self.client:
            yield {"type": "error", "content": "Cliente não inicializado."}
            return
        
        start_time = time.perf_counter()

        # Lógica específica para llm_pf usando Chat Completions API
        if provider == "llm_pf":
            model_name = "Qwen3-8B-AWQ"  # Modelo fixo para llm_pf
            # Anexar /no_think à pergunta do usuário
            user_question_with_no_think = user_question + " /no_think"
            messages = self._build_input_items(document_context, history, user_question_with_no_think, instructions=instructions)
            
            try:
                response = self.client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=32000,
                    stream=False  # Desabilita streaming
                )
                
                # Processa resposta não-streaming (response é um objeto, não um iterador)
                full_response_content = ""
                if hasattr(response, 'choices') and response.choices:
                    for choice in response.choices:
                        if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                            content = choice.message.content
                            if content:
                                full_response_content += content
                                yield {"type": "chunk", "content": content}
                elif hasattr(response, 'content'):
                    # Fallback direto para propriedade content se choices não estiver disponível
                    full_response_content = response.content
                    full_response_content = full_response_content.replace("<think>", "").replace("</think>", "").strip("\n")
                    if full_response_content:
                        yield {"type": "chunk", "content": full_response_content}
                else:
                    logger.warning("[DEBUG] Resposta do llm_pf não contém choices ou content esperados.")
                
                logger.info(f"[DEBUG] Resposta completa do llm_pf:\n{full_response_content}\n")  # Log da resposta completa (início)

                final_usage_data = response.usage

                if final_usage_data:
                    token_usage_info = {
                        "input_tokens":  final_usage_data.prompt_tokens or 0,
                        "cached_tokens": 0, 
                        "output_tokens": final_usage_data.completion_tokens or 0,
                        "reasoning_tokens": 0, 
                        "total_tokens":  final_usage_data.total_tokens or 0,
                    }
                    token_usage_info["total_cost_usd"] = 0
                    token_usage_info["previous_response_id"] = None

                    total_time = round(time.perf_counter() - start_time, 2)       
                    logger.info(f"Resposta do chat recebida. Model: {model_name}; Tempo de resposta: {total_time}s; Métricas: {token_usage_info}")
                    yield {"type": "final_metrics", "data": token_usage_info}
                else:
                    logger.warning("Não foi possível obter métricas de uso da resposta do chat.")
                    yield {"type": "final_metrics", "data": {}}
                
            except Exception as e:
                logger.error(f"Erro no provider llm_pf: {e}", exc_info=True)
                yield {"type": "error", "content": f"Erro no endpoint llm_pf: {e}"}
            return
        
        # Lógica para OpenAI (Responses API)
        logger.info(f'[DEBUG CACHE] Previous_response_id: {previous_response_id}')

        if not previous_response_id:
            input_items = self._build_input_items(document_context, history, user_question, instructions=instructions)
        else:
            # Com ativação do Previous_response_id e do Store, o input itens deve ser apenas a nova pergunta do usuário
            input_items = [{"role": "user", "content": user_question}]

        full_response_content = ""
        final_usage_data = {}
        
        # Monta kwargs para a Requests API sem enviar parâmetros top-level inválidos
        data_to_openai_api = {
            "model": model_name,
            # "instructions": instructions_with_context, 
            # -> Movido para input_message (role: system) a fim de otimizar o cache ao descontinuar o uso do field instruction da api
            "input": input_items,
            "previous_response_id": previous_response_id,
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
                    previous_response_id = response.id
                    logger.info(f'[DEBUG CACHE] New_response_id: {response.id}')
                else:
                    logger.info('[DEBUG CACHE] Resposta não contém "id" para previous_response_id.')

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
                token_usage_info["previous_response_id"] = previous_response_id
                                
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


