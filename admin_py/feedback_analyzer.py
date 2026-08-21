# admin_py/feedback_analyzer.py
"""
Normalização e análise dos eventos de feedback ('llm_feedback').

O evento de feedback é aninhado: cada documento carrega uma lista `details.feedback_fields`
com uma entrada por campo avaliado (19 campos por submissão, tipicamente). Analisar esse
formato diretamente é inviável — todo gráfico precisaria repetir o mesmo `explode` +
`json_normalize`.

Este módulo converte tudo em uma tabela "longa": **uma linha por (submissão, campo)**, já
enriquecida com o usuário, a data e — via join com a análise que originou o feedback — o
modelo e o provedor usados. Essa tabela é a base única da visão gerencial, da visão de
detalhe e da matriz de confusão.
"""

import logging
from typing import Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Colunas da tabela longa de feedback, na ordem de exibição.
FEEDBACK_LONG_COLUMNS = [
    "timestamp", "date", "user_id", "user_name", "arquivo", "campo", "nome_campo",
    "tipo_campo", "acertou", "valor_llm", "valor_corrigido", "similaridade",
    "modelo", "provedor", "reanalise", "doc_id",
]

# Tipos de campo cujos valores original/corrigido são persistidos pelo aplicativo.
# Espelha FEEDBACK_VALUE_SAFE_FIELD_TYPES em SOURCE/services/firebase_client.py: os demais
# tipos transcrevem trechos do documento analisado e têm os valores descartados na origem.
VALUE_BEARING_FIELD_TYPES = ("dropdown", "radio_button", "checkbox", "textfield_valor")


def _extract_filename(batch_name: object) -> str:
    """
    Extrai um nome de arquivo legível a partir do rótulo do lote de análise.

    Args:
        batch_name: Valor de `details.related_batch_name`, no formato
            "Arquivo selecionado: <nome>.pdf" ou "Arquivos selecionados: <nome> e Outros N".

    Returns:
        str: O nome do arquivo, ou "N/A" quando ausente.

        Exemplo:
            "Arquivo selecionado: 08500.013511_2025-29.pdf" -> "08500.013511_2025-29.pdf"
    """
    if not isinstance(batch_name, str) or not batch_name or batch_name == "N/A":
        return "N/A"
    for prefix in ("Arquivo selecionado: ", "Arquivos selecionados: "):
        if batch_name.startswith(prefix):
            return batch_name[len(prefix):]
    return batch_name


def _as_text(value: object) -> Optional[str]:
    """
    Normaliza um valor de campo para texto, preservando a ausência como None.

    Os valores gravados são heterogêneos: os dropdowns trazem strings e 'valor_apuracao' traz
    float. Uma coluna pandas com essa mistura é do tipo 'object' e o Arrow — usado pelo
    Streamlit para serializar tabelas — rejeita a conversão, derrubando a renderização com
    "Expected bytes, got a 'float' object". Uniformizar aqui mantém a tabela exibível e as
    comparações de confusão consistentes.

    Args:
        value: Valor bruto vindo do documento de feedback.

    Returns:
        O valor como string, ou None se ausente.

        Exemplo: 1000.0 -> "1000.0"; None -> None; "DELEFIN" -> "DELEFIN"
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return str(value)


def build_feedback_long_table(
    df: pd.DataFrame,
    user_id_to_name_map: Optional[Dict[str, str]] = None,
) -> pd.DataFrame:
    """
    Constrói a tabela longa de feedback: uma linha por campo avaliado.

    Explode `details.feedback_fields` e faz o join com o evento de análise correspondente
    (`details.analysis_timestamp_ref` = `llm_analysis_metadata.event_timestamp_iso`, dentro do
    mesmo usuário), para atribuir modelo e provedor a cada campo avaliado.

    Args:
        df: DataFrame completo de métricas, como retornado por
            `dashboard_analyzer.load_all_metrics_to_dataframe`.
        user_id_to_name_map: Mapa UID -> nome amigável. Quando ausente, exibe o próprio UID.

    Returns:
        DataFrame com as colunas de FEEDBACK_LONG_COLUMNS. Vazio se não houver feedbacks.

        Exemplo de uma linha:
        {
            "timestamp": Timestamp("2025-06-30 12:01:59"),
            "date": date(2025, 6, 30),
            "user_id": "lbIETcibo6TOIU1IUNtmLzvAjzy2",
            "user_name": "joao.silva",
            "arquivo": "08500.013511_2025-29.pdf",
            "campo": "Área de Atribuição",
            "nome_campo": "area_atribuicao",
            "tipo_campo": "dropdown",
            "acertou": False,
            "valor_llm": "DELEFIN",
            "valor_corrigido": "DELEPAT",
            "similaridade": None,
            "modelo": "GPT-4.1-MINI",
            "provedor": "OPENAI",
            "reanalise": False,
            "doc_id": "20250630120159271_llm_feedback_b8b854",
        }
    """
    empty = pd.DataFrame(columns=FEEDBACK_LONG_COLUMNS)
    if df is None or df.empty or "event_type" not in df.columns:
        return empty

    feedbacks = df[df["event_type"] == "llm_feedback"].copy()
    if feedbacks.empty or "details_feedback_fields" not in feedbacks.columns:
        return empty

    user_id_to_name_map = user_id_to_name_map or {}

    # Mapa (user_id, timestamp_da_analise) -> (modelo, provedor), para atribuir cada feedback
    # à configuração que o gerou. O casamento cobre ~99% dos registros históricos.
    analysis_lookup: Dict[tuple, tuple] = {}
    analyses = df[df["event_type"] == "pdf_analysis_completed"]
    ref_col = "llm_analysis_metadata_event_timestamp_iso"
    if not analyses.empty and ref_col in analyses.columns:
        for row in analyses.itertuples(index=False):
            ref = getattr(row, ref_col, None)
            if not isinstance(ref, str):
                continue
            analysis_lookup[(row.user_id, ref)] = (
                getattr(row, "llm_analysis_metadata_llm_model_used", None),
                getattr(row, "llm_analysis_metadata_llm_provider_used", None),
            )

    records = []
    for row in feedbacks.itertuples(index=False):
        fields = getattr(row, "details_feedback_fields", None)
        if not isinstance(fields, list):
            continue

        ref = getattr(row, "details_analysis_timestamp_ref", None)
        modelo, provedor = analysis_lookup.get((row.user_id, ref), (None, None))
        arquivo = _extract_filename(getattr(row, "details_related_batch_name", None))
        user_name = user_id_to_name_map.get(row.user_id, row.user_id)
        reanalise = bool(pd.notna(getattr(row, "reanalysis_occurrence", None))) if hasattr(row, "reanalysis_occurrence") else False
        doc_id = getattr(row, "client_doc_id", None)

        for field in fields:
            if not isinstance(field, dict):
                continue
            records.append({
                "timestamp": row.timestamp,
                "date": row.date,
                "user_id": row.user_id,
                "user_name": user_name,
                "arquivo": arquivo,
                "campo": field.get("label_campo") or field.get("nome_campo"),
                "nome_campo": field.get("nome_campo"),
                "tipo_campo": field.get("tipo_campo"),
                "acertou": bool(field.get("llm_acertou", True)),
                "valor_llm": _as_text(field.get("valor_original_llm")),
                "valor_corrigido": _as_text(field.get("valor_atual_ui")),
                "similaridade": field.get("similaridade_pos_edicao"),
                "modelo": modelo,
                "provedor": provedor,
                "reanalise": reanalise,
                "doc_id": doc_id,
            })

    if not records:
        return empty

    long_df = pd.DataFrame(records, columns=FEEDBACK_LONG_COLUMNS)
    logger.info(f"Tabela longa de feedback construída: {len(long_df)} campos avaliados.")
    return long_df


def calculate_feedback_kpis(long_df: pd.DataFrame, total_analyses: int) -> Dict[str, float]:
    """
    Calcula os indicadores da visão gerencial de feedback.

    Args:
        long_df: Tabela longa de feedback (já filtrada pelo período/usuário desejado).
        total_analyses: Total de análises no mesmo recorte, para a taxa de retorno.

    Returns:
        Dicionário com os indicadores.

        Exemplo de retorno:
        {
            "total_feedbacks": 141,
            "total_campos": 2675,
            "taxa_acerto": 0.9065,
            "taxa_retorno": 0.1711,
            "total_reanalises": 14
        }
    """
    if long_df is None or long_df.empty:
        return {"total_feedbacks": 0, "total_campos": 0, "taxa_acerto": 0.0,
                "taxa_retorno": 0.0, "total_reanalises": 0}

    total_feedbacks = long_df["doc_id"].nunique()
    total_campos = len(long_df)
    taxa_acerto = long_df["acertou"].mean() if total_campos else 0.0
    taxa_retorno = (total_feedbacks / total_analyses) if total_analyses else 0.0
    total_reanalises = long_df[long_df["reanalise"]]["doc_id"].nunique()

    return {
        "total_feedbacks": int(total_feedbacks),
        "total_campos": int(total_campos),
        "taxa_acerto": float(taxa_acerto),
        "taxa_retorno": float(taxa_retorno),
        "total_reanalises": int(total_reanalises),
    }


def prepare_accuracy_by_period(long_df: pd.DataFrame, granularidade: str = "Dia") -> pd.DataFrame:
    """
    Agrega acertos e correções por período, para o gráfico de composição temporal.

    Args:
        long_df: Tabela longa de feedback.
        granularidade: "Dia", "Semana" ou "Mês" — mesmas opções do filtro global.

    Returns:
        DataFrame com 'periodo', 'acertos', 'erros' e 'taxa_acerto'.
    """
    colunas = ["periodo", "acertos", "erros", "taxa_acerto"]
    if long_df is None or long_df.empty:
        return pd.DataFrame(columns=colunas)

    freq = {"Dia": "D", "Semana": "W", "Mês": "M"}.get(granularidade, "D")
    base = long_df.copy()
    base["periodo"] = base["timestamp"].dt.to_period(freq).dt.start_time

    grouped = base.groupby("periodo").agg(
        total=("acertou", "size"),
        acertos=("acertou", "sum"),
    ).reset_index()
    grouped["erros"] = grouped["total"] - grouped["acertos"]
    grouped["taxa_acerto"] = grouped["acertos"] / grouped["total"]

    return grouped[colunas].sort_values("periodo")


def prepare_accuracy_by_field(long_df: pd.DataFrame, min_amostras: int = 1) -> pd.DataFrame:
    """
    Calcula a taxa de acerto por campo, normalizada pelo número de avaliações.

    Substitui a contagem absoluta de "campos mais corrigidos": um campo com 34 correções em
    141 avaliações (24% de erro) e outro com 34 em 40 (85%) são problemas de magnitudes
    diferentes, indistinguíveis na contagem bruta.

    Args:
        long_df: Tabela longa de feedback.
        min_amostras: Descarta campos com menos avaliações que este limite.

    Returns:
        DataFrame ordenado por taxa de acerto crescente (piores primeiro).

        Exemplo de retorno:
            campo                  | avaliacoes | erros | taxa_acerto
            "Área de Atribuição"   | 141        | 34    | 0.7589
            "Tipo Documento Origem"| 141        | 34    | 0.7589
    """
    if long_df is None or long_df.empty:
        return pd.DataFrame(columns=["campo", "avaliacoes", "erros", "taxa_acerto"])

    grouped = long_df.groupby("campo").agg(
        avaliacoes=("acertou", "size"),
        acertos=("acertou", "sum"),
    ).reset_index()
    grouped = grouped[grouped["avaliacoes"] >= min_amostras]
    grouped["erros"] = grouped["avaliacoes"] - grouped["acertos"]
    grouped["taxa_acerto"] = grouped["acertos"] / grouped["avaliacoes"]

    return grouped[["campo", "avaliacoes", "erros", "taxa_acerto"]].sort_values("taxa_acerto")


def prepare_accuracy_by_field_and_model(long_df: pd.DataFrame, min_amostras: int = 5) -> pd.DataFrame:
    """
    Cruza taxa de acerto por campo e por modelo, para o heatmap comparativo.

    Args:
        long_df: Tabela longa de feedback.
        min_amostras: Número mínimo de avaliações para a célula (campo, modelo) ser exibida.
            Evita que uma combinação com 1 avaliação apareça como 0% ou 100%.

    Returns:
        DataFrame pivotado — índice = campo, colunas = modelo, valores = taxa de acerto
        (NaN nas células abaixo do mínimo de amostras).
    """
    if long_df is None or long_df.empty or long_df["modelo"].isna().all():
        return pd.DataFrame()

    base = long_df.dropna(subset=["modelo"])
    if base.empty:
        return pd.DataFrame()

    grouped = base.groupby(["campo", "modelo"]).agg(
        avaliacoes=("acertou", "size"),
        taxa_acerto=("acertou", "mean"),
    ).reset_index()
    grouped.loc[grouped["avaliacoes"] < min_amostras, "taxa_acerto"] = pd.NA

    return grouped.pivot(index="campo", columns="modelo", values="taxa_acerto")


def prepare_submission_table(long_df: pd.DataFrame) -> pd.DataFrame:
    """
    Agrega a tabela longa em uma linha por submissão de feedback (visão mestre).

    Args:
        long_df: Tabela longa de feedback.

    Returns:
        DataFrame ordenado do mais recente para o mais antigo.

        Exemplo de retorno:
            Data/Hora | Usuário | Arquivo | Modelo | Campos | Corrigidos | Taxa de Acerto | Reanálise
    """
    colunas = ["Data/Hora", "Usuário", "Arquivo", "Modelo", "Campos", "Corrigidos",
               "Taxa de Acerto", "Reanálise", "doc_id"]
    if long_df is None or long_df.empty:
        return pd.DataFrame(columns=colunas)

    grouped = long_df.groupby("doc_id").agg(
        **{
            "Data/Hora": ("timestamp", "first"),
            "Usuário": ("user_name", "first"),
            "Arquivo": ("arquivo", "first"),
            "Modelo": ("modelo", "first"),
            "Campos": ("acertou", "size"),
            "Acertos": ("acertou", "sum"),
            "Reanálise": ("reanalise", "first"),
        }
    ).reset_index()

    grouped["Corrigidos"] = grouped["Campos"] - grouped["Acertos"]
    grouped["Taxa de Acerto"] = grouped["Acertos"] / grouped["Campos"]
    grouped["Modelo"] = grouped["Modelo"].fillna("N/D")

    return grouped[colunas].sort_values("Data/Hora", ascending=False)


def build_confusion_matrix(long_df: pd.DataFrame, nome_campo: str) -> pd.DataFrame:
    """
    Monta a matriz de confusão de um campo de valor único: resposta da IA x correção do usuário.

    Só produz resultado para campos cujos valores são persistidos (ver
    VALUE_BEARING_FIELD_TYPES); para campos de texto livre os valores são descartados na
    origem por conterem conteúdo do documento analisado.

    Args:
        long_df: Tabela longa de feedback.
        nome_campo: Nome interno do campo (ex.: "area_atribuicao").

    Returns:
        DataFrame pivotado — índice = valor respondido pela IA, colunas = valor corrigido pelo
        usuário, valores = contagem de ocorrências. Vazio quando não há dados de valor.

        A diagonal representa os acertos; as células fora dela são as confusões recorrentes
        que servem de insumo para ajuste de prompt e das listas de opções.
    """
    if long_df is None or long_df.empty:
        return pd.DataFrame()

    subset = long_df[
        (long_df["nome_campo"] == nome_campo)
        & long_df["valor_llm"].notna()
        & long_df["valor_corrigido"].notna()
    ].copy()

    if subset.empty:
        return pd.DataFrame()

    return pd.crosstab(subset["valor_llm"], subset["valor_corrigido"])


def prepare_top_confusions(long_df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    """
    Lista os erros recorrentes de classificação: o que a IA respondeu x o que o usuário corrigiu.

    É a leitura acionável da matriz de confusão. A matriz completa de um campo como
    'area_atribuicao' tem ~19x17 células quase todas zeradas; esta lista extrai apenas as
    células fora da diagonal com ocorrência real, ordenadas por frequência, e cruza todos os
    campos de uma vez.

    Args:
        long_df: Tabela longa de feedback.
        top_n: Número máximo de confusões retornadas.

    Returns:
        DataFrame ordenado por frequência decrescente.

        Exemplo de retorno:
            Campo                 | Resposta da IA        | Corrigido para  | Ocorrências
            "Área de Atribuição"  | "DELEFIN"             | "DELEPAT"       | 4
            "Tipo Documento Origem"| "Ofício"             | "Relatório"     | 3
    """
    colunas = ["Campo", "Resposta da IA", "Corrigido para", "Ocorrências"]
    if long_df is None or long_df.empty:
        return pd.DataFrame(columns=colunas)

    erros = long_df[
        (~long_df["acertou"])
        & long_df["valor_llm"].notna()
        & long_df["valor_corrigido"].notna()
    ].copy()

    if erros.empty:
        return pd.DataFrame(columns=colunas)

    grouped = (
        erros.groupby(["campo", "valor_llm", "valor_corrigido"])
        .size()
        .rename("Ocorrências")
        .reset_index()
        .sort_values("Ocorrências", ascending=False)
        .head(top_n)
    )
    grouped.columns = colunas
    return grouped


def get_fields_with_values(long_df: pd.DataFrame) -> pd.DataFrame:
    """
    Lista os campos que possuem valores registrados, aptos à matriz de confusão.

    Args:
        long_df: Tabela longa de feedback.

    Returns:
        DataFrame com 'nome_campo', 'campo' (rótulo) e 'com_valor' (nº de avaliações com
        valor registrado), ordenado do mais frequente para o menos.
    """
    if long_df is None or long_df.empty:
        return pd.DataFrame(columns=["nome_campo", "campo", "com_valor"])

    com_valor = long_df[long_df["valor_llm"].notna() & long_df["valor_corrigido"].notna()]
    if com_valor.empty:
        return pd.DataFrame(columns=["nome_campo", "campo", "com_valor"])

    return (
        com_valor.groupby(["nome_campo", "campo"])
        .size()
        .rename("com_valor")
        .reset_index()
        .sort_values("com_valor", ascending=False)
    )
