# admin_py/dashboard_analyzer.py
"""
Carregamento e agregação das métricas para o painel administrativo.

Convenção deste módulo: **as funções de agregação recebem o DataFrame já filtrado**. O recorte
por período, usuário, modelo e provedor é aplicado uma única vez, no `run_admin_streamlit.py`,
via `apply_filters`. Antes, cada função refazia internamente o corte de período enquanto o
filtro de usuário era aplicado por fora — o que tornava impossível garantir que dois gráficos
lado a lado estivessem olhando para o mesmo recorte.
"""

import pandas as pd
import os
import json
import logging
from typing import Any, Dict, Iterable, List, Optional
from datetime import date, datetime, timedelta

from admin_py.local_data_manager import ADMIN_METRICS_DIR

logger = logging.getLogger(__name__)

# Eventos contabilizados como "requisição" ao LLM. A análise de PDF e a mensagem de chat são
# ambas uma chamada ao modelo e consomem tokens; separá-las na contagem escondia todo o
# consumo do chat, que até então nem era sincronizado pelo painel.
REQUEST_EVENT_TYPES = ("pdf_analysis_completed", "chat_request_completed")

EVENT_TYPE_LABELS = {
    "pdf_analysis_completed": "Análise de PDF",
    "chat_request_completed": "Chat",
    "llm_feedback": "Feedback",
}

# Granularidades disponíveis para o eixo temporal, mapeadas para regras de resample do pandas.
GRANULARITY_RULES = {"Dia": "D", "Semana": "W-MON", "Mês": "MS"}

# Colunas numéricas de custo. Podem não existir em recortes antigos/novos; sempre acessadas
# por `_col`, que devolve uma série de zeros quando a coluna está ausente.
COL_COST_LLM = "llm_analysis_metadata_total_cost_usd"
COL_COST_EMBED = "processing_metadata_calculated_embedding_cost_usd"
COL_INPUT_TOKENS = "llm_analysis_metadata_input_tokens"
COL_OUTPUT_TOKENS = "llm_analysis_metadata_output_tokens"
COL_CACHED_TOKENS = "llm_analysis_metadata_cached_tokens"
COL_MODEL = "llm_analysis_metadata_llm_model_used"
COL_PROVIDER = "llm_analysis_metadata_llm_provider_used"
COL_PAGES = "processing_metadata_total_pages_processed"
COL_LLM_TIME = "llm_analysis_metadata_processing_time"


def _col(df: pd.DataFrame, name: str, default: float = 0.0) -> pd.Series:
    """
    Devolve uma coluna numérica do DataFrame, ou uma série constante se ela não existir.

    Os documentos de métrica evoluíram entre versões do aplicativo: campos como o custo de
    embeddings aparecem em apenas 2 dos 824 registros históricos. Sem esta guarda, qualquer
    recorte que não contenha nenhum documento com o campo levantaria KeyError.

    Args:
        df: DataFrame de métricas.
        name: Nome da coluna desejada.
        default: Valor usado quando a coluna não existe ou é nula.

    Returns:
        Série numérica alinhada ao índice de `df`.
    """
    if name not in df.columns:
        return pd.Series(default, index=df.index, dtype="float64")
    return pd.to_numeric(df[name], errors="coerce").fillna(default)


def _parse_duration(value: object) -> Optional[float]:
    """
    Converte uma duração no formato "MMm:SSs" para segundos.

    Args:
        value: String de duração gravada pela aplicação (ex.: "01m:05s").

    Returns:
        Total de segundos, ou None se o valor não for interpretável.

        Exemplo: "01m:05s" -> 65.0
    """
    if not isinstance(value, str) or "m:" not in value:
        return None
    try:
        minutos, segundos = value.split("m:")
        return int(minutos) * 60 + int(segundos.rstrip("s"))
    except (ValueError, AttributeError):
        return None


def load_all_metrics_to_dataframe() -> Optional[pd.DataFrame]:
    """
    Carrega todos os arquivos de métricas JSON do diretório local para um DataFrame pandas.

    Returns:
        DataFrame com uma linha por evento de métrica e as colunas aninhadas achatadas com
        separador '_' (ex.: `llm_analysis_metadata_total_cost_usd`), acrescido de 'user_id',
        'timestamp' e 'date'. None se não houver métricas.
    """
    all_metrics_data = []
    if not os.path.isdir(ADMIN_METRICS_DIR):
        logger.warning(f"Diretório de métricas '{ADMIN_METRICS_DIR}' não encontrado.")
        return None

    for user_id in os.listdir(ADMIN_METRICS_DIR):
        user_dir = os.path.join(ADMIN_METRICS_DIR, user_id)
        if not os.path.isdir(user_dir):
            continue
        for filename in os.listdir(user_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(user_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        metric = json.load(f)
                        metric['user_id'] = user_id
                        all_metrics_data.append(metric)
                except (json.JSONDecodeError, IOError) as e:
                    logger.error(f"Erro ao carregar ou decodificar a métrica '{filepath}': {e}")

    if not all_metrics_data:
        logger.info("Nenhuma métrica encontrada para análise.")
        return None

    df = pd.json_normalize(all_metrics_data, sep='_')

    # Padroniza e converte a coluna de timestamp.
    # format='ISO8601' é obrigatório: sem ele, o pandas infere um único formato a partir do
    # primeiro registro e converte para NaT todos os que não casarem. Como praticamente todos
    # os timestamps gravados têm microssegundos, um registro cujo isoformat() os omita (o que
    # ocorre quando os microssegundos são exatamente zero) seria descartado em silêncio.
    total_bruto = len(df)
    df['timestamp'] = pd.to_datetime(df['timestamp_event'], errors='coerce', format='ISO8601')
    df = df.dropna(subset=['timestamp'])  # Remove linhas sem timestamp válido
    df['date'] = df['timestamp'].dt.date

    descartados = total_bruto - len(df)
    if descartados:
        logger.warning(f"{descartados} evento(s) descartado(s) por timestamp inválido.")

    logger.info(f"Métricas carregadas: {len(df)} eventos de {df['user_id'].nunique()} usuários.")
    return df


def attach_user_names(df: pd.DataFrame, user_id_to_name_map: Dict[str, str]) -> pd.DataFrame:
    """
    Acrescenta a coluna 'user_name' ao DataFrame de métricas.

    As métricas são gravadas por UID; o nome amigável vem do Firebase Auth. Resolver isso uma
    única vez após o carregamento evita que cada agregação precise carregar o mapa.

    Args:
        df: DataFrame de métricas recém-carregado.
        user_id_to_name_map: Mapa UID -> nome amigável.

    Returns:
        O mesmo DataFrame com a coluna 'user_name'. UIDs sem correspondência (ex.: usuários
        removidos do Auth) mantêm o próprio UID como rótulo, para que sua atividade continue
        visível em vez de desaparecer silenciosamente do painel.
    """
    if df is None or df.empty:
        return df
    df = df.copy()
    df['user_name'] = df['user_id'].map(user_id_to_name_map).fillna(df['user_id'])
    return df


def get_date_bounds(df: pd.DataFrame) -> tuple[date, date]:
    """
    Retorna a primeira e a última data presentes nos dados.

    Usado para inicializar o seletor de intervalo com o alcance real dos dados, em vez de um
    período fixo que pode cair inteiramente num intervalo sem uso.

    Args:
        df: DataFrame de métricas.

    Returns:
        Tupla (data_inicial, data_final). Se não houver dados, ambas são a data de hoje.
    """
    hoje = datetime.now().date()
    if df is None or df.empty or 'date' not in df.columns:
        return hoje, hoje
    return df['date'].min(), df['date'].max()


def apply_filters(
    df: pd.DataFrame,
    data_inicial: date,
    data_final: date,
    user_ids: Optional[Iterable[str]] = None,
    modelos: Optional[Iterable[str]] = None,
    provedores: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    """
    Aplica o recorte global do painel: período, usuários, modelos e provedores.

    Ponto único de filtragem — todas as funções de agregação assumem que o DataFrame recebido
    já passou por aqui.

    Args:
        df: DataFrame completo de métricas.
        data_inicial: Primeiro dia do intervalo (inclusive).
        data_final: Último dia do intervalo (inclusive).
        user_ids: UIDs a manter. None ou vazio mantém todos.
        modelos: Modelos LLM a manter. None ou vazio mantém todos.
        provedores: Provedores a manter. None ou vazio mantém todos.

    Returns:
        DataFrame filtrado (cópia).
    """
    if df is None or df.empty:
        return pd.DataFrame()

    filtered = df[(df['date'] >= data_inicial) & (df['date'] <= data_final)].copy()

    if user_ids:
        filtered = filtered[filtered['user_id'].isin(list(user_ids))]
    if modelos and COL_MODEL in filtered.columns:
        # Eventos de feedback não têm modelo próprio; mantê-los evita que o filtro de modelo
        # esvazie a aba de feedback, cuja atribuição de modelo vem do join com a análise.
        filtered = filtered[filtered[COL_MODEL].isin(list(modelos)) | filtered[COL_MODEL].isna()]
    if provedores and COL_PROVIDER in filtered.columns:
        filtered = filtered[filtered[COL_PROVIDER].isin(list(provedores)) | filtered[COL_PROVIDER].isna()]

    return filtered


def get_filter_options(df: pd.DataFrame) -> Dict[str, List[str]]:
    """
    Lista os valores disponíveis para os filtros de modelo e provedor.

    Args:
        df: DataFrame completo de métricas.

    Returns:
        Dicionário com as listas ordenadas.

        Exemplo de retorno:
        {
            "modelos": ["GPT-4.1-MINI", "GPT-5-NANO", "QWEN3.5-35B-A3B-FP8"],
            "provedores": ["LLM_PF", "OPENAI"]
        }
    """
    if df is None or df.empty:
        return {"modelos": [], "provedores": []}
    modelos = sorted(df[COL_MODEL].dropna().unique()) if COL_MODEL in df.columns else []
    provedores = sorted(df[COL_PROVIDER].dropna().unique()) if COL_PROVIDER in df.columns else []
    return {"modelos": list(modelos), "provedores": list(provedores)}


def get_requests(df: pd.DataFrame) -> pd.DataFrame:
    """
    Recorta apenas os eventos contabilizados como requisição ao LLM.

    Args:
        df: DataFrame já filtrado.

    Returns:
        Subconjunto com os eventos de REQUEST_EVENT_TYPES.
    """
    if df is None or df.empty or 'event_type' not in df.columns:
        return pd.DataFrame()
    return df[df['event_type'].isin(REQUEST_EVENT_TYPES)]


def has_cost_data(df: pd.DataFrame) -> bool:
    """
    Informa se o recorte contém algum custo maior que zero.

    O painel usa este teste para exibir os indicadores e gráficos de custo apenas quando eles
    têm conteúdo: o uso atual é majoritariamente do provedor interno (LLM_PF), cujo custo é
    sempre zero — manter os painéis de custo visíveis nesse cenário ocupa espaço nobre com
    valores fixos em "$0.00".

    Args:
        df: DataFrame já filtrado.

    Returns:
        True se houver custo registrado no recorte.
    """
    if df is None or df.empty:
        return False
    requests = get_requests(df)
    if requests.empty:
        return False
    return bool((_col(requests, COL_COST_LLM) + _col(requests, COL_COST_EMBED)).sum() > 0)


def calculate_kpis(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calcula os indicadores da aba de uso, respeitando integralmente o recorte recebido.

    Args:
        df: DataFrame já filtrado por `apply_filters`.

    Returns:
        Dicionário de indicadores.

        Exemplo de retorno:
        {
            "total_requests": 824,
            "total_analyses": 780,
            "total_chats": 44,
            "active_users": 27,
            "total_documents": 812,
            "total_pages": 9430,
            "input_tokens": 10248311,
            "output_tokens": 812043,
            "avg_response_seconds": 42.7,
            "total_cost_usd": 12.4451,
            "avg_cost_per_request": 0.0151
        }
    """
    empty = {"total_requests": 0, "total_analyses": 0, "total_chats": 0, "active_users": 0,
             "total_documents": 0, "total_pages": 0, "input_tokens": 0, "output_tokens": 0,
             "avg_response_seconds": 0.0, "total_cost_usd": 0.0, "avg_cost_per_request": 0.0}
    if df is None or df.empty:
        return empty

    requests = get_requests(df)
    if requests.empty:
        empty["active_users"] = int(df['user_id'].nunique())
        return empty

    total_requests = len(requests)
    analyses = requests[requests['event_type'] == 'pdf_analysis_completed']

    total_documents = 0
    if 'filenames_uploaded' in analyses.columns:
        total_documents = int(
            analyses['filenames_uploaded'].apply(lambda x: len(x) if isinstance(x, list) else 0).sum()
        )

    total_cost = float((_col(requests, COL_COST_LLM) + _col(requests, COL_COST_EMBED)).sum())

    duracoes = requests[COL_LLM_TIME].map(_parse_duration).dropna() if COL_LLM_TIME in requests.columns else pd.Series(dtype=float)

    return {
        "total_requests": total_requests,
        "total_analyses": len(analyses),
        "total_chats": int((requests['event_type'] == 'chat_request_completed').sum()),
        # Usuários ativos no recorte — não o total cadastrado. O indicador anterior contava
        # diretórios locais e não reagia a nenhum filtro.
        "active_users": int(requests['user_id'].nunique()),
        "total_documents": total_documents,
        "total_pages": int(_col(analyses, COL_PAGES).sum()),
        "input_tokens": int(_col(requests, COL_INPUT_TOKENS).sum()),
        "output_tokens": int(_col(requests, COL_OUTPUT_TOKENS).sum()),
        "avg_response_seconds": float(duracoes.mean()) if not duracoes.empty else 0.0,
        "total_cost_usd": total_cost,
        "avg_cost_per_request": (total_cost / total_requests) if total_requests else 0.0,
    }


def _resample_period(series_df: pd.DataFrame, granularidade: str) -> pd.DataFrame:
    """
    Adiciona a coluna 'periodo' truncada conforme a granularidade escolhida.

    Args:
        series_df: DataFrame com a coluna 'timestamp'.
        granularidade: Uma das chaves de GRANULARITY_RULES ("Dia", "Semana", "Mês").

    Returns:
        Cópia do DataFrame com a coluna 'periodo' (datetime).
    """
    rule = GRANULARITY_RULES.get(granularidade, "D")
    out = series_df.copy()
    out['periodo'] = out['timestamp'].dt.to_period(
        {"D": "D", "W-MON": "W", "MS": "M"}[rule]
    ).dt.start_time
    return out


def prepare_requests_by_period_and_user(
    df: pd.DataFrame, granularidade: str = "Dia", top_n_users: int = 12
) -> pd.DataFrame:
    """
    Prepara a série de requisições por período, discriminada por usuário.

    É a base do gráfico principal da aba de uso: barras empilhadas que respondem "quantas
    requisições" e "de quem" na mesma figura.

    Args:
        df: DataFrame já filtrado.
        granularidade: "Dia", "Semana" ou "Mês".
        top_n_users: Usuários exibidos individualmente; os demais são somados em "Outros",
            para que a legenda permaneça legível com dezenas de usuários.

    Returns:
        DataFrame com as colunas 'periodo', 'user_name' e 'requisicoes'.
    """
    requests = get_requests(df)
    if requests.empty:
        return pd.DataFrame(columns=['periodo', 'user_name', 'requisicoes'])

    base = _resample_period(requests, granularidade)

    top_users = base['user_name'].value_counts().nlargest(top_n_users).index
    base['user_name'] = base['user_name'].where(base['user_name'].isin(top_users), 'Outros')

    grouped = base.groupby(['periodo', 'user_name']).size().rename('requisicoes').reset_index()
    return grouped.sort_values('periodo')


def prepare_events_by_period_and_user(
    df: pd.DataFrame, event_type: str, granularidade: str = "Dia", top_n_users: int = 12
) -> pd.DataFrame:
    """
    Versão genérica de `prepare_requests_by_period_and_user` para um tipo de evento específico.

    Usada pela aba de feedback, que precisa da mesma leitura (por período e por usuário)
    aplicada aos eventos 'llm_feedback'.

    Args:
        df: DataFrame já filtrado.
        event_type: Valor de 'event_type' a isolar.
        granularidade: "Dia", "Semana" ou "Mês".
        top_n_users: Usuários exibidos individualmente antes do agrupamento em "Outros".

    Returns:
        DataFrame com as colunas 'periodo', 'user_name' e 'eventos'.
    """
    if df is None or df.empty or 'event_type' not in df.columns:
        return pd.DataFrame(columns=['periodo', 'user_name', 'eventos'])

    subset = df[df['event_type'] == event_type]
    if subset.empty:
        return pd.DataFrame(columns=['periodo', 'user_name', 'eventos'])

    base = _resample_period(subset, granularidade)
    top_users = base['user_name'].value_counts().nlargest(top_n_users).index
    base['user_name'] = base['user_name'].where(base['user_name'].isin(top_users), 'Outros')

    grouped = base.groupby(['periodo', 'user_name']).size().rename('eventos').reset_index()
    return grouped.sort_values('periodo')


def prepare_user_period_heatmap(df: pd.DataFrame, granularidade: str = "Dia") -> pd.DataFrame:
    """
    Monta a matriz usuário x período de requisições, para o mapa de calor de adoção.

    Args:
        df: DataFrame já filtrado.
        granularidade: "Dia", "Semana" ou "Mês".

    Returns:
        DataFrame pivotado — índice = usuário (ordenado por volume total), colunas = período,
        valores = número de requisições.
    """
    requests = get_requests(df)
    if requests.empty:
        return pd.DataFrame()

    base = _resample_period(requests, granularidade)
    pivot = base.pivot_table(
        index='user_name', columns='periodo', values='event_type', aggfunc='size', fill_value=0
    )
    return pivot.loc[pivot.sum(axis=1).sort_values(ascending=False).index]


def prepare_token_usage_by_period(df: pd.DataFrame, granularidade: str = "Dia") -> pd.DataFrame:
    """
    Prepara o consumo de tokens de entrada e saída por período.

    Substitui os gráficos de custo quando o recorte não tem custo: com o provedor interno,
    o volume de tokens é a métrica de capacidade relevante.

    Args:
        df: DataFrame já filtrado.
        granularidade: "Dia", "Semana" ou "Mês".

    Returns:
        DataFrame com 'periodo', 'input_tokens', 'cached_tokens' e 'output_tokens'.
    """
    requests = get_requests(df)
    if requests.empty:
        return pd.DataFrame(columns=['periodo', 'input_tokens', 'cached_tokens', 'output_tokens'])

    base = _resample_period(requests, granularidade)
    base['input_tokens'] = _col(base, COL_INPUT_TOKENS)
    base['cached_tokens'] = _col(base, COL_CACHED_TOKENS)
    base['output_tokens'] = _col(base, COL_OUTPUT_TOKENS)

    return (
        base.groupby('periodo')[['input_tokens', 'cached_tokens', 'output_tokens']]
        .sum().reset_index().sort_values('periodo')
    )


def prepare_cost_data(df: pd.DataFrame, granularidade: str = "Dia") -> pd.DataFrame:
    """
    Prepara o custo total por período.

    Args:
        df: DataFrame já filtrado.
        granularidade: "Dia", "Semana" ou "Mês".

    Returns:
        DataFrame com as colunas 'periodo' e 'total_cost'.
    """
    requests = get_requests(df)
    if requests.empty:
        return pd.DataFrame(columns=['periodo', 'total_cost'])

    base = _resample_period(requests, granularidade)
    base['total_cost'] = _col(base, COL_COST_LLM) + _col(base, COL_COST_EMBED)

    return base.groupby('periodo')['total_cost'].sum().reset_index().sort_values('periodo')


def prepare_cost_by_model(df: pd.DataFrame) -> pd.DataFrame:
    """
    Distribui o custo total por modelo LLM.

    Substitui a pizza "Embeddings x Análise LLM": o custo de embeddings está presente em
    apenas 2 dos 824 registros históricos, o que tornava aquela divisão sempre 100%/0%.
    A quebra por modelo responde a pergunta útil — onde o gasto está concentrado.

    Args:
        df: DataFrame já filtrado.

    Returns:
        DataFrame com 'modelo', 'custo' e 'requisicoes', ordenado por custo decrescente.
    """
    requests = get_requests(df)
    if requests.empty or COL_MODEL not in requests.columns:
        return pd.DataFrame(columns=['modelo', 'custo', 'requisicoes'])

    base = requests.copy()
    base['custo'] = _col(base, COL_COST_LLM) + _col(base, COL_COST_EMBED)
    base['modelo'] = base[COL_MODEL].fillna('N/D')

    grouped = base.groupby('modelo').agg(
        custo=('custo', 'sum'), requisicoes=('custo', 'size')
    ).reset_index()
    return grouped[grouped['custo'] > 0].sort_values('custo', ascending=False)


def prepare_model_usage(df: pd.DataFrame) -> pd.DataFrame:
    """
    Resume o uso por modelo: volume, tokens e tempo médio de resposta.

    Args:
        df: DataFrame já filtrado.

    Returns:
        DataFrame com 'Modelo', 'Provedor', 'Requisições', 'Tokens Entrada', 'Tokens Saída',
        'Tempo Médio (s)' e 'Custo (USD)', ordenado por volume decrescente.
    """
    colunas = ['Modelo', 'Provedor', 'Requisições', 'Tokens Entrada', 'Tokens Saída',
               'Tempo Médio (s)', 'Custo (USD)']
    requests = get_requests(df)
    if requests.empty or COL_MODEL not in requests.columns:
        return pd.DataFrame(columns=colunas)

    base = requests.copy()
    base['Modelo'] = base[COL_MODEL].fillna('N/D')
    base['Provedor'] = base[COL_PROVIDER].fillna('N/D') if COL_PROVIDER in base.columns else 'N/D'
    base['_in'] = _col(base, COL_INPUT_TOKENS)
    base['_out'] = _col(base, COL_OUTPUT_TOKENS)
    base['_cost'] = _col(base, COL_COST_LLM) + _col(base, COL_COST_EMBED)
    base['_secs'] = base[COL_LLM_TIME].map(_parse_duration) if COL_LLM_TIME in base.columns else None

    grouped = base.groupby(['Modelo', 'Provedor']).agg(
        **{
            'Requisições': ('_in', 'size'),
            'Tokens Entrada': ('_in', 'sum'),
            'Tokens Saída': ('_out', 'sum'),
            'Tempo Médio (s)': ('_secs', 'mean'),
            'Custo (USD)': ('_cost', 'sum'),
        }
    ).reset_index()

    return grouped[colunas].sort_values('Requisições', ascending=False)


def prepare_user_activity_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepara a tabela de atividade por usuário, respeitando o recorte recebido.

    Args:
        df: DataFrame já filtrado.

    Returns:
        DataFrame ordenado por número de requisições.

        Exemplo de retorno:
            Usuário | Requisições | Análises | Chat | Feedbacks | Documentos | Páginas |
            Tokens Entrada | Tokens Saída | Custo (USD) | Última Atividade
    """
    colunas = ['Usuário', 'Requisições', 'Análises', 'Chat', 'Feedbacks', 'Documentos',
               'Páginas', 'Tokens Entrada', 'Tokens Saída', 'Custo (USD)', 'Última Atividade']
    if df is None or df.empty:
        return pd.DataFrame(columns=colunas)

    requests = get_requests(df)
    base = df.copy()
    base['_in'] = _col(base, COL_INPUT_TOKENS)
    base['_out'] = _col(base, COL_OUTPUT_TOKENS)
    base['_cost'] = _col(base, COL_COST_LLM) + _col(base, COL_COST_EMBED)
    base['_pages'] = _col(base, COL_PAGES)
    base['_is_request'] = base['event_type'].isin(REQUEST_EVENT_TYPES)
    base['_is_analysis'] = base['event_type'] == 'pdf_analysis_completed'
    base['_is_chat'] = base['event_type'] == 'chat_request_completed'
    base['_is_feedback'] = base['event_type'] == 'llm_feedback'
    if 'filenames_uploaded' in base.columns:
        base['_docs'] = base['filenames_uploaded'].apply(lambda x: len(x) if isinstance(x, list) else 0)
    else:
        base['_docs'] = 0

    grouped = base.groupby('user_name').agg(
        **{
            'Requisições': ('_is_request', 'sum'),
            'Análises': ('_is_analysis', 'sum'),
            'Chat': ('_is_chat', 'sum'),
            'Feedbacks': ('_is_feedback', 'sum'),
            'Documentos': ('_docs', 'sum'),
            'Páginas': ('_pages', 'sum'),
            'Tokens Entrada': ('_in', 'sum'),
            'Tokens Saída': ('_out', 'sum'),
            'Custo (USD)': ('_cost', 'sum'),
            'Última Atividade': ('timestamp', 'max'),
        }
    ).reset_index().rename(columns={'user_name': 'Usuário'})

    inteiros = ['Requisições', 'Análises', 'Chat', 'Feedbacks', 'Documentos', 'Páginas',
                'Tokens Entrada', 'Tokens Saída']
    grouped[inteiros] = grouped[inteiros].astype(int)

    return grouped[colunas].sort_values('Requisições', ascending=False)
