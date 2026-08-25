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

import os, openai, httpx
from typing import Optional, Dict, Any, List, Tuple, Union
from openai import OpenAI, AuthenticationError, APIError, InternalServerError

# Imports do Projeto
from SOURCE.settings import (DEFAULT_LLM_PROVIDER, DEFAULT_LLM_MODEL, DEFAULT_TEMPERATURE, LLM_PF_MODEL_ID, LLM_PF_MAX_OUTPUT_TOKENS,
                            LLM_PF_MAX_OUTPUT_TOKENS_THINKING, LLM_PF_CONTEXT_WINDOW, LLM_PF_TOKEN_SAFETY_MARGIN)
from SOURCE.config.provider import is_local_mode
from SOURCE.utils import with_proxy
from SOURCE.core.prompts import (output_formats, review_function, normalizing_function, # prompts
                                formatted_initial_analysis, try_convert_to_pydantic_format, return_parse_prompt)

MODEL_FOR_COUNT_TOKENS = "gpt-4o"

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
    
    response_text = response_text if isinstance(response_text, str) else str(response_text)

    # Regex para remover o bloco <think>...</think>
    cleaned = re.sub(r"<think>.*?</think>\s*", "", response_text, flags=re.DOTALL)
    cleaned = cleaned.strip()  
    
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

# Timeout do /tokenize. A operação é local ao servidor e rápida (0,5s medidos para ~82k tokens);
# o valor é folgado apenas para absorver latência de rede.
LLM_PF_TOKENIZE_TIMEOUT = 20

# Teto de caracteres enviados ao /tokenize ao medir o desvio do tokenizer. Existe só para evitar um
# POST gigantesco em lotes atípicos — a proporção medida não melhora com amostras maiores.
LLM_PF_TOKENIZE_MAX_CHARS = 400_000

# Folga somada à contagem exata do /tokenize ao dimensionar max_tokens. Cobre pequenas diferenças
# entre o que é tokenizado aqui e o que o servidor monta na requisição real (tokens de controle do
# template, campos do response_format).
LLM_PF_EXACT_COUNT_BUFFER = 512


def get_llm_pf_base_url() -> str:
    """
    Retorna a URL base do endpoint llm_pf conforme o modo de execução.

    Returns:
        URL base, já com o sufixo '/v1'.

        Exemplo de retorno: 'http://llm.pf.gov.br:31893/v1'
    """
    return "http://llm.pf.gov.br:31893/v1" if is_local_mode() else "http://10.2.2.10:31893/v1"


def count_tokens_llm_pf(messages: Optional[List[Dict[str, str]]] = None, text: Optional[str] = None) -> Optional[int]:
    """
    Conta tokens com o tokenizer real do modelo, via endpoint `/tokenize` do vLLM.

    É a contagem exata: usa o tokenizer do modelo carregado no servidor, o mesmo que a API aplica ao
    validar (entrada + max_tokens) contra a janela de contexto. Passando `messages`, o chat template
    é aplicado e o total inclui os tokens de controle das tags de papel — que o tiktoken ignora.

    Existe porque o tiktoken (tokenizer da OpenAI) subestima gravemente o tokenizer do Qwen em texto
    jurídico em português: desvio medido de +21% a +30% (ver NOTES_llm_pf.md). A rota `/tokenize`
    fica fora do prefixo '/v1'.

    Falhas de rede não são propagadas: a contagem é um refinamento, e todos os chamadores têm
    fallback para a estimativa por tiktoken.

    Args:
        messages: Lista de dicts {"role": ..., "content": ...}; o chat template é aplicado.
        text: Texto puro, alternativa a `messages` (sem chat template).

    Returns:
        Número exato de tokens, ou None se o endpoint estiver indisponível ou responder fora do
        formato esperado.

        Exemplo de retorno: 94861

    Raises:
        ValueError: Se nem `messages` nem `text` forem fornecidos.
    """
    if messages is None and text is None:
        raise ValueError("count_tokens_llm_pf exige 'messages' ou 'text'.")

    payload: Dict[str, Any] = {"model": LLM_PF_MODEL_ID}
    if messages is not None:
        payload["messages"] = messages
    else:
        payload["prompt"] = text

    # A rota /tokenize é irmã de /v1, não filha: base_url termina em '/v1' e precisa ser removida.
    url = f"{get_llm_pf_base_url().rstrip('/').removesuffix('/v1')}/tokenize"

    try:
        # trust_env=False pelo mesmo motivo das chamadas de inferência: o proxy corporativo não
        # alcança a rede interna onde o endpoint está hospedado.
        with httpx.Client(trust_env=False, timeout=LLM_PF_TOKENIZE_TIMEOUT) as http_client:
            resp = http_client.post(url, json=payload)
            resp.raise_for_status()
            count = resp.json().get("count")
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning(
            "[TOKENIZE] Falha ao consultar %s (%s: %s). Usando estimativa por tiktoken.",
            url, type(exc).__name__, exc,
        )
        return None

    if not isinstance(count, int):
        logger.warning("[TOKENIZE] Resposta sem 'count' inteiro (%r). Usando estimativa por tiktoken.", count)
        return None

    return count


def measure_llm_pf_token_drift(sample_text: Union[str, List[str]]) -> Optional[float]:
    """
    Mede, para um documento específico, o quanto o tiktoken subestima o tokenizer real do Qwen.

    O desvio não é constante: depende do perfil do texto (português com CPFs, valores monetários e
    números de processo fragmenta pior no vocabulário da OpenAI). Medir por documento é mais fiel do
    que aplicar LLM_PF_TOKEN_SAFETY_MARGIN, um percentual fixo que a prática mostrou otimista.

    O resultado alimenta `compute_llm_pf_auto_token_limit`, convertendo a capacidade real da janela
    em unidades de tiktoken — que é como o `pdf_processor` conta as páginas ao truncar.

    Args:
        sample_text: Texto do documento, ou lista de textos de páginas (serão concatenados).

    Returns:
        Razão tokens_reais / tokens_tiktoken, nunca menor que 1.0, ou None se o `/tokenize` estiver
        indisponível ou a amostra for vazia.

        Exemplo de retorno: 1.305
    """
    if isinstance(sample_text, list):
        sample_text = "\n".join(t for t in sample_text if t)

    sample_text = sample_text[:LLM_PF_TOKENIZE_MAX_CHARS]
    if not sample_text.strip():
        logger.warning("[TOKENIZE] Amostra vazia; desvio do tokenizer não medido.")
        return None

    estimated = contar_tokens(sample_text, MODEL_FOR_COUNT_TOKENS)
    if estimated < 1:
        return None

    real = count_tokens_llm_pf(text=sample_text)
    if real is None:
        return None

    drift = max(1.0, real / estimated)
    logger.info(
        "[TOKENIZE] Desvio medido do tokenizer: %d tokens reais vs %d estimados (tiktoken) = %.3fx.",
        real, estimated, drift,
    )
    return drift


def scale_tokens_to_real(estimated_tokens: int, drift_ratio: Optional[float]) -> int:
    """
    Converte uma contagem em unidades de tiktoken para a contagem real do tokenizer do modelo.

    Usada nos totais exibidos no painel 'Dados do Processamento': o `pdf_processor` conta as páginas
    com tiktoken, mas o número que interessa ao usuário é o que o modelo enxerga — e é o que aparece
    nas métricas pós-análise, vindas do `usage` da API. Sem a conversão, o painel subestima os totais
    em ~25% e fica incoerente com essas métricas.

    Args:
        estimated_tokens: Contagem obtida via tiktoken.
        drift_ratio: Razão medida por measure_llm_pf_token_drift. Se None (provider diferente de
            llm_pf, ou `/tokenize` indisponível), a contagem é devolvida inalterada.

    Returns:
        Contagem convertida, ou a original quando não há razão de conversão.

        Exemplo de retorno: 87889  # para estimated_tokens=67353 e drift_ratio=1.305
    """
    if not drift_ratio:
        return estimated_tokens
    return round(estimated_tokens * drift_ratio)


def is_thinking_enabled(reasoning_effort: Optional[str]) -> bool:
    """
    Traduz o nível de reflexão escolhido no drawer de configurações para o flag `enable_thinking`
    do Qwen3.5 no endpoint llm_pf.

    Fonte única da decisão: a reserva de saída aplicada na truncagem de entrada
    (compute_llm_pf_auto_token_limit) precisa corresponder exatamente ao teto que a requisição vai
    pedir (compute_llm_pf_max_output_tokens); divergência entre as duas volta a produzir resposta
    truncada.

    Args:
        reasoning_effort: Valor do dropdown ('minimal', 'low', 'medium', 'high') ou None.

    Returns:
        True quando o raciocínio deve ser ativado na requisição.

        Exemplo de retorno: True  # para reasoning_effort='low'
    """
    return bool(reasoning_effort) and reasoning_effort.lower() != "minimal"


def compute_llm_pf_auto_token_limit(prompt_messages: List[Dict[str, str]], extra_reserve: int = 0,
                                    drift_ratio: Optional[float] = None,
                                    enable_thinking: bool = False) -> int:
    """
    Calcula o orçamento de tokens disponível para o texto de entrada (páginas do documento)
    no endpoint llm_pf, para uso quando o usuário deixa a truncagem manual desabilitada
    (campo 'Limite Tokens Input' vazio no drawer de configurações).

    A contagem usa tiktoken (MODEL_FOR_COUNT_TOKENS) como aproximação do tokenizer real do Qwen,
    porque o `pdf_processor` conta cada página assim ao truncar — medir as 200 páginas pelo
    `/tokenize` exigiria uma chamada de rede por página. A correção entra como fator de escala:
    `drift_ratio`, medido uma única vez sobre o texto do documento por `measure_llm_pf_token_drift`.
    Sem ele, cai-se em LLM_PF_TOKEN_SAFETY_MARGIN — percentual fixo que a prática mostrou otimista
    (desvio real de +21% a +30% contra os 10% configurados, ver NOTES_llm_pf.md).

    A reserva de saída é o próprio teto que a requisição vai pedir, e não uma constante de
    planejamento separada: pedir menos que o teto nominal produziria resposta truncada (content
    vazio, finish_reason='length'). Qual dos dois tetos reservar depende do modo de raciocínio
    (`enable_thinking`), porque o raciocínio do Qwen3.5 é longo e não limitável — reservar o teto
    sem raciocínio para um lote que será analisado no modo pensante deixa a resposta terminar antes
    do JSON. É o inverso da política anterior, que reservava sempre LLM_PF_MAX_OUTPUT_TOKENS e
    deixava o modo pensante depender da folga que sobrasse na janela.

    O modo é o que estiver selecionado na etapa 'Processar Conteúdo'. Se o usuário alterar o nível
    de reflexão depois, antes de 'Solicitar Análise', a reserva já não corresponde ao teto pedido:
    compute_llm_pf_max_output_tokens detecta a situação e emite o aviso correspondente.

    A conversão entre unidades entra como divisão pela razão de desvio, espelhando exatamente a
    inflação aplicada em compute_llm_pf_max_output_tokens. Descontar (1 - margem) do orçamento total,
    como se fazia antes, não é o inverso dessa inflação e deixava o teto de saída cair abaixo do
    nominal para prompts com overhead alto. Pelo mesmo motivo LLM_PF_EXACT_COUNT_BUFFER entra aqui:
    é a folga somada à contagem exata do input naquele cálculo, e sem descontá-la o teto de saída
    ficaria 512 tokens abaixo do nominal justamente nos lotes que enchem o orçamento.

    Fórmula:
        ratio           = drift_ratio ou (1 + LLM_PF_TOKEN_SAFETY_MARGIN)
        output_reserve  = LLM_PF_MAX_OUTPUT_TOKENS_THINKING se enable_thinking, senão
                          LLM_PF_MAX_OUTPUT_TOKENS
        input_total_max = (LLM_PF_CONTEXT_WINDOW - output_reserve - LLM_PF_EXACT_COUNT_BUFFER) / ratio
        budget          = input_total_max - tokens(prompt_messages) - extra_reserve

    O overhead do prompt é descontado em unidades de tiktoken, assumindo que ele sofre o mesmo desvio
    do corpo do documento — aproximação aceitável, já que o prompt é uma fração pequena do total.

    Args:
        prompt_messages: Lista de dicts {"role": ..., "content": ...} do prompt fixo já
            montado (sem o {input_text} substituído, ou com um placeholder curto no lugar).
        extra_reserve: Reserva adicional de tokens a descontar do orçamento (ex.: espaço
            reservado para o histórico de turnos futuros no chat). Padrão 0.
        drift_ratio: Razão tokens_reais/tokens_tiktoken medida para este documento (ver
            measure_llm_pf_token_drift). Se None, usa a margem fixa de segurança.
        enable_thinking: Se a análise deste lote será feita com o raciocínio ativado (ver
            is_thinking_enabled). Define qual teto de saída é reservado. Padrão False.

    Returns:
        Orçamento de tokens disponível para o texto de entrada, em unidades de tiktoken (mínimo 1).

        Exemplo de retorno: 68430
    """
    ratio = drift_ratio if drift_ratio else (1 + LLM_PF_TOKEN_SAFETY_MARGIN)
    output_reserve = LLM_PF_MAX_OUTPUT_TOKENS_THINKING if enable_thinking else LLM_PF_MAX_OUTPUT_TOKENS
    prompt_overhead = sum(contar_tokens(m.get("content", ""), MODEL_FOR_COUNT_TOKENS) for m in prompt_messages)
    input_total_max = int((LLM_PF_CONTEXT_WINDOW - output_reserve - LLM_PF_EXACT_COUNT_BUFFER) / ratio)
    budget = input_total_max - prompt_overhead - extra_reserve

    if budget < 1:
        logger.warning(
            "compute_llm_pf_auto_token_limit: orçamento calculado <= 0 "
            "(overhead_prompt=%d, extra_reserve=%d, input_total_max=%d). Forçando mínimo de 1.",
            prompt_overhead, extra_reserve, input_total_max,
        )
        budget = 1

    # O orçamento é expresso em tiktoken porque é a unidade em que o pdf_processor conta as páginas
    # ao truncar; o equivalente em tokens reais é o que aparece no painel 'Dados do Processamento'.
    logger.info(
        "[AUTO_TOKEN_LIMIT] overhead_prompt=%d, extra_reserve=%d, thinking=%s, output_reserve=%d, "
        "ratio=%.3f (%s), input_total_max=%d, budget_final=%d tiktoken (~%d tokens reais)",
        prompt_overhead, extra_reserve, enable_thinking, output_reserve, ratio,
        "medido" if drift_ratio else "margem fixa", input_total_max, budget,
        scale_tokens_to_real(budget, drift_ratio),
    )
    return budget

# Folga descontada ao recalcular o teto de saída na retentativa pós-erro 400. O servidor informa o
# input real como "at least N", ou seja, um piso — a folga cobre essa imprecisão declarada.
LLM_PF_RETRY_SAFETY_BUFFER = 512

# Timeout do client HTTP para chamadas llm_pf. Com thinking ativo o Qwen3.5 pode levar vários
# minutos para esgotar o orçamento de saída (LLM_PF_MAX_OUTPUT_TOKENS_THINKING=24_000): um timeout
# curto demais interrompe a conexão antes do servidor sequer devolver uma resposta (truncada ou
# não) — nesse caso o erro chega como APITimeoutError genérico, não como LLMTruncatedResponseError
# (que exige uma resposta HTTP real e observável; ver incidente de 24-25/ago/2026, reproduzido em
# ~9min: 3 tentativas de 180s cada). Sem thinking a saída é bem menor (LLM_PF_MAX_OUTPUT_TOKENS) e
# 180s é suficiente. Timeout é tratado como categoria própria (ver except (APIError,
# InternalServerError) em analyze_text_with_llm): não aciona a política de retry de
# LLMTruncatedResponseError, apenas o retry normal da SDK (LLM_PF_CLIENT_MAX_RETRIES).
LLM_PF_CLIENT_TIMEOUT_THINKING = 600
LLM_PF_CLIENT_TIMEOUT_DEFAULT = 300

# max_retries da SDK OpenAI para chamadas llm_pf — mesmo valor com ou sem thinking. Erros de timeout/
# conexão têm o retry normal e silencioso da própria SDK; a política de retry para truncamento real
# por loop de raciocínio (LLMTruncatedResponseError) é outra, tratada à parte em
# `_llm_analysis_thread_func` (thinking -> thinking -> sem thinking, com snackbar/log visíveis).
LLM_PF_CLIENT_MAX_RETRIES = 2

# Trechos que identificam um erro de contexto excedido nas mensagens do vLLM (endpoint PF) e da OpenAI.
_CONTEXT_LENGTH_ERROR_MARKERS = (
    "longer than the maximum model length",
    "maximum context length",
    "context_length_exceeded",
)

def is_context_length_error(api_err: Exception) -> bool:
    """
    Indica se uma exceção de API corresponde a estouro da janela de contexto do modelo.

    Args:
        api_err: Exceção capturada da chamada à API (APIError, InternalServerError etc.).

    Returns:
        True se a mensagem de erro indicar contexto excedido.
    """
    err_str = str(api_err).lower()
    return any(marker in err_str for marker in _CONTEXT_LENGTH_ERROR_MARKERS)

def parse_context_length_error(api_err: Exception) -> Optional[Tuple[int, int]]:
    """
    Extrai a contagem real de tokens de entrada e a janela de contexto de um erro de contexto excedido.

    Os números vêm do tokenizer real do modelo (não da aproximação por tiktoken), o que os torna a
    fonte confiável tanto para a mensagem exibida ao usuário quanto para recalcular o teto de saída
    numa retentativa. A extração é por padrão nomeado — buscar "os primeiros números da mensagem"
    capturaria o código HTTP ("Error code: 400") como se fosse contagem de tokens.

    Formatos cobertos:
        vLLM (antigo) : "The decoder prompt (length N) is longer than the maximum model length of M."
        vLLM (atual)  : "This model's maximum context length is M tokens. However, you requested X
                         output tokens and your prompt contains at least N input tokens..."
        OpenAI        : "This model's maximum context length is M tokens. However, your messages
                         resulted in N tokens."

    Args:
        api_err: Exceção capturada da chamada à API.

    Returns:
        Tupla (tokens_de_entrada_reais, janela_de_contexto) ou None se a mensagem não trouxer ambos.

        Exemplo de retorno: (89228, 131072)
    """
    err_str = str(api_err).lower()
    max_len_match = re.search(r"maximum (?:context length|model length)(?: is| of) (\d+)", err_str)
    input_len_match = (
        re.search(r"prompt contains at least (\d+) input tokens", err_str)
        or re.search(r"decoder prompt \(length (\d+)\)", err_str)
        or re.search(r"your messages resulted in (\d+) tokens", err_str)
        or re.search(r"parameter=input_tokens, value=(\d+)", err_str)
    )
    if not (max_len_match and input_len_match):
        return None
    return int(input_len_match.group(1)), int(max_len_match.group(1))

def compute_llm_pf_max_output_tokens(messages: List[Dict[str, str]], enable_thinking: bool = False) -> int:
    """
    Calcula o teto de tokens de saída (`max_tokens`) a pedir ao endpoint llm_pf.

    A API valida (tokens_de_entrada + max_tokens) contra a janela de contexto, então o teto nominal
    é limitado pelo espaço que sobra para as mensagens já montadas. A contagem de entrada vem do
    `/tokenize` do próprio endpoint (tokenizer real do modelo, chat template incluído), o que torna
    o cálculo exato; só se o endpoint estiver indisponível cai-se na estimativa por tiktoken inflada
    por LLM_PF_TOKEN_SAFETY_MARGIN, que subestima o tokenizer do Qwen (ver NOTES_llm_pf.md).

    O teto nominal depende do modo de raciocínio: com `enable_thinking=True` o modelo consome boa
    parte da saída raciocinando antes de emitir o JSON (raciocínio longo e não limitável no
    endpoint), então usa-se LLM_PF_MAX_OUTPUT_TOKENS_THINKING, maior. A truncagem automática de
    entrada reserva esse mesmo teto (ver compute_llm_pf_auto_token_limit), de modo que o `min`
    abaixo normalmente não corta nada. Chega-se ao corte em dois casos: 'Limite Tokens Input' fixado
    manualmente em valor alto demais, ou o nível de reflexão alterado depois de 'Processar Conteúdo'
    (a reserva foi dimensionada para o modo anterior). O aviso correspondente é emitido.

    Args:
        messages: Lista de dicts {"role": ..., "content": ...} já montada para o envio.
        enable_thinking: Se o modo de raciocínio do Qwen será enviado na requisição.

    Returns:
        Teto de tokens de saída a enviar em `max_tokens` (mínimo 1).

        Exemplo de retorno: 32000
    """
    nominal_max = LLM_PF_MAX_OUTPUT_TOKENS_THINKING if enable_thinking else LLM_PF_MAX_OUTPUT_TOKENS

    input_real = count_tokens_llm_pf(messages=messages)
    if input_real is not None:
        input_safe = input_real + LLM_PF_EXACT_COUNT_BUFFER
        fonte_contagem = "exata (/tokenize)"
    else:
        input_real = sum(contar_tokens(m.get("content", ""), MODEL_FOR_COUNT_TOKENS) for m in messages)
        input_safe = int(input_real * (1 + LLM_PF_TOKEN_SAFETY_MARGIN))
        fonte_contagem = "estimada (tiktoken + margem)"

    max_output = max(1, min(nominal_max, LLM_PF_CONTEXT_WINDOW - input_safe))

    logger.info(
        "[MAX_OUTPUT_TOKENS] input=%d (%s), input_com_folga=%d, thinking=%s, max_tokens=%d",
        input_real, fonte_contagem, input_safe, enable_thinking, max_output,
    )

    if max_output < nominal_max:
        # A truncagem automática reserva o teto do modo escolhido, então aqui só se chega fixando
        # 'Limite Tokens Input' manualmente em valor alto demais, ou alterando o nível de reflexão
        # depois de 'Processar Conteúdo' (a reserva ficou dimensionada para o modo anterior).
        logger.warning(
            "[MAX_OUTPUT_TOKENS] Teto de saída reduzido para %d (abaixo dos %d nominais): a entrada não "
            "deixou espaço suficiente. A resposta pode ser truncada — reprocesse o conteúdo com o nível "
            "de reflexão atual, ou reduza o 'Limite Tokens Input' nas configurações.",
            max_output, nominal_max,
        )

    return max_output

def _build_raw_fallback_text(raw_text: str | None, finish_reason: str | None) -> str:
    """
    Monta o texto exibido na UI quando a resposta da LLM não pôde ser convertida para o Pydantic.

    Preserva o conteúdo bruto (JSON malformado, JSON truncado ou raciocínio do modelo) para que o
    usuário ainda possa aproveitar o teor manualmente, prefixado por um aviso que explica o motivo.

    Args:
        raw_text: Texto bruto devolvido pela LLM (`content` ou `reasoning_content`); pode ser vazio.
        finish_reason: Motivo de término informado pela API ('stop', 'length', etc.).

    Returns:
        Texto pronto para exibição na UI.

        Exemplo de retorno:
        '[AVISO: Resposta não formatada corretamente pela IA — saída truncada por limite de tokens
        (finish_reason=length). Considere desativar o raciocínio ou reduzir o volume de páginas.]

        {"descricao_geral": "Requisição de instauração de Inquérito Poli'
    """
    if finish_reason == "length":
        aviso = ("[AVISO: Resposta não formatada corretamente pela IA — saída truncada por limite de tokens "
                 "(finish_reason=length). Considere desativar o raciocínio ou reduzir o volume de páginas.]")
    else:
        aviso = "[AVISO: Resposta não formatada corretamente pela IA]"

    if not raw_text:
        return f"{aviso}\n\n(A IA não retornou nenhum conteúdo aproveitável nesta requisição.)"

    return f"{aviso}\n\n{raw_text}"

def create_llm_pf_completion(client: OpenAI, **create_kwargs: Any) -> Any:
    """
    Executa `chat.completions.create` no endpoint llm_pf com autocorreção do teto de saída.

    A contagem de entrada calculada localmente é uma aproximação (tiktoken vs. tokenizer do Qwen);
    quando ela subestima o suficiente para que (entrada + max_tokens) ultrapasse a janela, a API
    devolve 400. Nesse caso o próprio erro informa a contagem real de entrada, usada aqui para
    recalcular `max_tokens` e repetir a chamada uma única vez — tornando a correção exata, sem
    depender da calibragem da margem de segurança.

    Args:
        client: Cliente OpenAI já configurado para o endpoint PF.
        **create_kwargs: Argumentos repassados a `chat.completions.create` (model, messages,
            max_tokens, etc.).

    Returns:
        O objeto ChatCompletion retornado pela API.

    Raises:
        APIError: Repropagado quando o erro não é de contexto excedido, quando a mensagem não traz
            as contagens necessárias, ou quando nem reduzir a saída resolveria (entrada sozinha
            maior que a janela).
    """
    try:
        return client.chat.completions.create(**create_kwargs)
    except (APIError, InternalServerError) as api_err:
        if not is_context_length_error(api_err):
            raise

        parsed = parse_context_length_error(api_err)
        if parsed is None:
            logger.warning("Erro de contexto excedido sem contagens legíveis na mensagem; sem retentativa.")
            raise

        real_input_tokens, context_window = parsed
        requested_max_tokens = create_kwargs.get("max_tokens") or 0
        adjusted_max_tokens = context_window - real_input_tokens - LLM_PF_RETRY_SAFETY_BUFFER

        if adjusted_max_tokens < 1 or adjusted_max_tokens >= requested_max_tokens:
            # Reduzir a saída não resolve: a entrada sozinha já não cabe na janela do modelo.
            logger.error(
                "Contexto excedido pela entrada (%d tokens reais, janela de %d); retentativa não aplicável.",
                real_input_tokens, context_window,
            )
            raise

        logger.warning(
            "Contexto excedido (entrada real=%d, janela=%d). Reduzindo max_tokens de %d para %d e repetindo.",
            real_input_tokens, context_window, requested_max_tokens, adjusted_max_tokens,
        )
        create_kwargs["max_tokens"] = adjusted_max_tokens
        return client.chat.completions.create(**create_kwargs)

client_openai = None

def _make_strict_schema(model: Any) -> Dict[str, Any]:
    """
    Gera o JSON schema de um modelo Pydantic garantindo que
    ``additionalProperties: false`` e ``required`` estejam presentes
    em TODOS os objetos do schema — raiz e quaisquer submodelos em ``$defs``.

    A OpenAI Responses API exige isso em cada nó do tipo ``object``,
    não apenas na raiz. Antes de ``PessoaEnvolvida`` ser introduzida o
    schema não tinha ``$defs``, então o bug era invisível.
    """
    schema = model.model_json_schema()
    for def_schema in schema.get("$defs", {}).values():
        if def_schema.get("type") == "object" and "properties" in def_schema:
            def_schema["required"] = list(def_schema["properties"].keys())
            def_schema["additionalProperties"] = False
    if "properties" in schema:
        schema["required"] = list(schema["properties"].keys())
    schema["additionalProperties"] = False
    return schema

def convert_pydantic_to_json_schema(formatted_initial_pydantic: Any) -> Dict[str, Any]:
    """
    Converte um modelo Pydantic para um esquema JSON compatível com a API OpenAI.

    Args:
        formatted_initial_pydantic (Any): Uma instância de um modelo Pydantic.

    Returns:
        Dict[str, Any]: Um dicionário representando o esquema JSON para a API OpenAI.
    """
    schema = _make_strict_schema(formatted_initial_pydantic)
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "formatted_initial_pydantic",
            "schema": schema,
            "strict": True,
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


class ContextLengthExceededError(Exception):
    """
    Levantada quando o prompt enviado à LLM excede o context window do modelo.
    Carrega uma mensagem já formatada para exibição direta na UI.
    """
    pass


class LLMTruncatedResponseError(Exception):
    """
    O LLM interrompeu a geração por atingir o limite de tokens de saída (finish_reason='length')
    antes de produzir conteúdo útil — endpoint llm_pf, com 'content' vazio e enable_thinking=True,
    tipicamente com o orçamento de raciocínio (thinking) esgotado.

    É sintoma de loop de raciocínio fechado, não de deliberação legítima só longa demais para o
    orçamento (diagnóstico de outro projeto que consome o mesmo endpoint, NOTES_LlmAnalysis.md §9.4:
    ampliar o teto de tokens não resolve — o loop só repete mais vezes). Deliberadamente distinta de
    um timeout de conexão (tratado à parte, com o retry normal da SDK — ver LLM_PF_CLIENT_MAX_RETRIES):
    aqui o servidor respondeu de fato, com uma resposta observável e truncada.

    Permite ao chamador (`_llm_analysis_thread_func` em nc_analyze_view.py) diferenciar este caso de
    uma falha de parsing/conteúdo genuína e reagir repetindo a chamada (mesmo teto de saída) antes de
    cair no fallback sem thinking.

    Attributes:
        reasoning_text: Texto de raciocínio bruto obtido até o corte, para eventual diagnóstico.
        token_usage_info: Uso de tokens da tentativa descartada — a chamada foi real e cobrada mesmo
            sem resposta aproveitável, e o chamador soma esse custo ao total reportado ao usuário.
    """
    def __init__(self, message: str, reasoning_text: Optional[str] = None,
                 token_usage_info: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.reasoning_text = reasoning_text
        self.token_usage_info = token_usage_info


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
        normalizing_and_review_response: bool = True,
        reasoning_effort: str = "low"
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
        reasoning_effort (str): Nível de reflexão vindo do drawer de configurações
                                 ('minimal', 'low', 'medium', 'high'). Usado apenas pelo
                                 provider 'llm_pf' (Qwen3.5): o modo thinking fica ativo
                                 sempre que o valor for diferente de 'minimal', já que o
                                 modelo não distingue níveis intermediários de raciocínio.

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
    # Definido aqui (não só dentro do branch 'llm_pf') para estar sempre disponível nos 'except'
    # abaixo, inclusive quando o provider não é 'llm_pf' ou a exceção ocorre antes do branch rodar.
    enable_thinking = False

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

                # Converter a classe Pydantic para JSON schema (strict, inclui $defs)
                json_schema = _make_strict_schema(output_formats[prompt_name])
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
                    final_response = try_convert_to_pydantic_format(final_response_text_clean, output_formats[prompt_name])
                    if not isinstance(final_response, output_formats[prompt_name]):
                        raise ValueError("Falha na conversão para Pydantic após coerção.")                    
                except Exception as e:
                    logger.error(f"Erro ao processar JSON do OpenAI: {e}")
                    # raise
                    # Fallback: Retorna o texto bruto se o JSON falhar
                    logger.warning("Retornando resposta bruta devido a falha no parsing JSON.")
                    final_response = f"[AVISO: Resposta não formatada corretamente pela IA]\n\n{final_response_text}"         
                
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
            # enable_thinking precisa ser conhecido ANTES de instanciar o client: define o timeout da
            # conexão HTTP (ver LLM_PF_CLIENT_TIMEOUT_* acima — 180s não é suficiente quando o Qwen
            # raciocina). max_retries da SDK é o mesmo em ambos os casos (LLM_PF_CLIENT_MAX_RETRIES).
            enable_thinking = is_thinking_enabled(reasoning_effort)
            client_timeout = LLM_PF_CLIENT_TIMEOUT_THINKING if enable_thinking else LLM_PF_CLIENT_TIMEOUT_DEFAULT

            if is_local_mode():
                # Configurações para o endpoint interno da PF
                # trust_env=False evita que HTTP_PROXY/HTTPS_PROXY do SO desviem a chamada para o
                # proxy corporativo, que não alcança a rede interna onde o endpoint está hospedado.
                base_url = "http://llm.pf.gov.br:31893/v1"
                api_key_pf = "EMPTY"
                model_pf = LLM_PF_MODEL_ID
                # Instancia o cliente OpenAI com base_url customizada
                client_pf = OpenAI(
                    api_key=api_key_pf,
                    base_url=base_url,
                    timeout=client_timeout,
                    max_retries=LLM_PF_CLIENT_MAX_RETRIES,
                    http_client=httpx.Client(trust_env=False)
                )
            else:
                custom_http_client = httpx.Client(trust_env=False)
                base_url = "http://10.2.2.10:31893/v1"
                api_key_pf = "EMPTY"
                model_pf = LLM_PF_MODEL_ID

                client_pf = OpenAI(
                    api_key=api_key_pf,
                    base_url=base_url,
                    timeout=client_timeout,
                    max_retries=LLM_PF_CLIENT_MAX_RETRIES,
                    http_client=custom_http_client
                )

            if prompt_name == "PROMPT_UNICO_for_INITIAL_ANALYSIS":
                prompt_list_dicts = prompts[prompt_name]
                messages = []
                for msg_dict in prompt_list_dicts:
                    modified_msg_dict = {key: value.replace("{input_text}", processed_text) for key, value in msg_dict.items()}
                    messages.append(modified_msg_dict)

                # Converter a classe Pydantic para JSON schema (strict, inclui $defs)
                json_schema = _make_strict_schema(output_formats[prompt_name])

                response_format = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": output_formats[prompt_name].__name__,
                        "schema": json_schema,
                        "strict": True
                    }
                }

                # Qwen3.5 não suporta mais o soft switch '/no_think' no texto (confirmado em teste
                # manual no endpoint); o controle correto é 'enable_thinking' via chat_template_kwargs.
                # (enable_thinking já foi calculado acima, antes de instanciar o client_pf)
                logger.info(
                    f"Usando {model_pf} com modo de raciocínio {'ativado' if enable_thinking else 'desativado'} "
                    f"(enable_thinking={enable_thinking}, timeout={client_timeout}s, max_retries={LLM_PF_CLIENT_MAX_RETRIES})."
                )

                # Chamada para chat completions (max_tokens limitado ao espaço restante da janela;
                # em caso de 400 por contexto, a chamada se reajusta e repete uma vez)
                logger.info('[DEBUG]: Requisitando à API do endpoint PF...')
                response = create_llm_pf_completion(
                    client_pf,
                    model=model_pf,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=compute_llm_pf_max_output_tokens(messages, enable_thinking),
                    response_format=response_format,
                    extra_body={"chat_template_kwargs": {"enable_thinking": enable_thinking}}
                )
                logger.info('[DEBUG]: Requisição concluída.')

                # Uso de tokens é extraído logo após a resposta, antes de qualquer possibilidade de
                # 'raise' abaixo: precisa estar disponível mesmo quando a tentativa for descartada por
                # truncamento no raciocínio (LLMTruncatedResponseError) — a chamada foi real e cobrada,
                # e o chamador soma esse custo ao total reportado ao usuário mesmo em retry.
                usage = response.usage
                if usage:
                    token_usage_info = {
                        "input_tokens": usage.prompt_tokens if hasattr(usage, 'prompt_tokens') else 0,
                        "cached_tokens": 0,  # Endpoint PF pode não suportar cache
                        "output_tokens": usage.completion_tokens if hasattr(usage, 'completion_tokens') else 0,
                        "reasoning_tokens": 0,
                        "total_tokens": usage.total_tokens if hasattr(usage, 'total_tokens') else 0,
                        "successful_requests": 1,
                        "total_cost_usd": 0.0,  # Custos não aplicáveis ou calcular se houver config
                    }
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

                # Extrair o conteúdo da resposta
                choice = response.choices[0]
                finish_reason = choice.finish_reason
                final_response_text = choice.message.content

                if not final_response_text:
                    # Com enable_thinking=True o Qwen pode consumir todo o orçamento de saída no
                    # raciocínio: 'content' volta vazio. O endpoint (vLLM) nomeia esse campo
                    # 'reasoning'; 'reasoning_content' é o nome adotado por outros provedores
                    # compatíveis com a API OpenAI e fica como alternativa.
                    reasoning_text = (getattr(choice.message, "reasoning", None)
                                      or getattr(choice.message, "reasoning_content", None))

                    if finish_reason == "length" and enable_thinking:
                        # Sintoma do loop de raciocínio fechado (ver docstring de
                        # LLMTruncatedResponseError) — repassa ao chamador para aplicar a política de
                        # retry (thinking -> thinking -> sem thinking), em vez de devolver o
                        # raciocínio cru como se fosse a resposta.
                        _tokens_saida = token_usage_info.get("output_tokens", 0)
                        logger.warning(
                            "Endpoint PF truncou durante o raciocínio (finish_reason=%s, content vazio, "
                            "%d caracteres de raciocínio, %d tokens de saída consumidos). Repassando ao "
                            "chamador para retry.",
                            finish_reason, len(reasoning_text or ""), _tokens_saida,
                        )
                        raise LLMTruncatedResponseError(
                            f"LLM interrompeu a geração por limite de tokens (finish_reason={finish_reason}) "
                            f"antes de produzir conteúdo útil. Orçamento de saída usado: {_tokens_saida} tokens.",
                            reasoning_text, token_usage_info
                        )

                    # Demais casos (thinking desligado, ou finish_reason != 'length'): aproveitar o
                    # raciocínio como texto bruto é melhor do que devolver nada ao usuário.
                    final_response_text = reasoning_text
                    logger.warning(
                        "Endpoint PF devolveu 'content' vazio (finish_reason=%s); usando o raciocínio "
                        "como texto bruto (%d caracteres).",
                        finish_reason, len(final_response_text or "")
                    )

                _truncated_response_preview = (final_response_text or "")[:500]
                if final_response_text and len(final_response_text) > 500:
                    _truncated_response_preview += "... [truncado]"
                logger.debug(f"[DEBUG]: final_response_text obtido: \n{_truncated_response_preview}\n")

                try:
                    final_response_text_clean = extract_and_clean_json(final_response_text)
                    final_response = try_convert_to_pydantic_format(final_response_text_clean, output_formats[prompt_name])
                    if not isinstance(final_response, output_formats[prompt_name]):
                        raise ValueError("Falha na conversão para Pydantic após coerção.")
                except Exception as e:
                    logger.error(f"Erro ao processar JSON do endpoint PF: {e}", exc_info=True)
                    # raise
                    # Fallback: Retorna o texto bruto se o JSON falhar
                    logger.warning("Retornando resposta bruta devido a falha no parsing JSON.")
                    final_response = _build_raw_fallback_text(final_response_text, finish_reason)

                # token_usage_info já foi extraído logo após a resposta (ver acima) — precisa estar
                # disponível mesmo se LLMTruncatedResponseError for levantada antes deste ponto.

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
    except (APIError, InternalServerError) as api_err:
        logger.error(f"Erro da API {provider}: {api_err}. Pode ser um problema temporário ou de input.", exc_info=True)
        # Detecta context length exceeded — mensagem vinda do vLLM/OpenAI
        # Exemplos conhecidos:
        #   vLLM/llm_pf : "The decoder prompt (length N) is longer than the maximum model length of M."
        #   OpenAI API   : "This model's maximum context length is M tokens. However, your messages resulted in N tokens."
        if is_context_length_error(api_err):
            parsed = parse_context_length_error(api_err)
            if parsed:
                prompt_len, max_len = parsed
                detail = (f"Documento filtrado com {prompt_len:,} tokens excede o limite de "
                          f"{max_len:,} tokens do modelo selecionado.")
            else:
                detail = "O documento filtrado excede o limite de tokens do modelo selecionado."
            raise ContextLengthExceededError(detail) from api_err

        # Timeout de conexão (APITimeoutError, subclasse de APIError) é deliberadamente mantido
        # específico e à parte de LLMTruncatedResponseError: aqui o servidor não chegou a responder
        # (a SDK já retentou sozinha até LLM_PF_CLIENT_MAX_RETRIES vezes, com o mesmo timeout, antes
        # de levantar), então não há resposta truncada observável para diagnosticar como loop de
        # raciocínio — é engolido abaixo pelo 'except Exception' genérico, como os demais APIError
        # sem padrão reconhecido.
    except LLMTruncatedResponseError:
        # Repropaga sem log adicional (já logada no ponto de origem, acima): o chamador decide a
        # política de retry (thinking -> thinking -> sem thinking); aqui seria engolida pelo
        # 'except Exception' genérico abaixo, que não repropaga.
        raise
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
 
    from SOURCE.core.pdf_processor import PDFDocumentAnalyzer
    analyzer = PDFDocumentAnalyzer()
    # Extrai o texto de todas as páginas
    combined_processed_page_data, all_global_page_keys_ordered, \
    tfidf_vectors_combined, tf_idf_scores_array_combined = analyzer.analyze_pdf_documents([pdf_path])

    final_selected_ordered_indices, _, _ = analyzer.filter_and_classify_pages(
        combined_processed_page_data, all_global_page_keys_ordered,
        tfidf_vectors_combined=tfidf_vectors_combined, tf_idf_scores_array_combined=tf_idf_scores_array_combined)
    
    _, full_text, _, final_aggregated_tokens = analyzer.group_texts_by_relevance_and_token_limit(combined_processed_page_data, final_selected_ordered_indices, 180000)

    logger.info(f"Total tokens from accumulated text: {final_aggregated_tokens}")
    logger.info(f"Texto extraído de {len(final_selected_ordered_indices)} páginas e concatenado.")
    
    return full_text

def get_prompt_template():
    import json
    from SOURCE.core.prompts import get_prompts_for_initial_analysis
    from SOURCE.settings import ASSETS_DIR

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
logger.debug(f"Carregado AI_ORCHESTRATOR em {execution_time:.4f}s")
