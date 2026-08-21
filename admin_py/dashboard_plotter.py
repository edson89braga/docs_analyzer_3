# admin_py/dashboard_plotter.py
"""
Construção das figuras Plotly do painel administrativo.

Este módulo só desenha: recebe DataFrames já agregados por `dashboard_analyzer` ou
`feedback_analyzer` e devolve figuras. Nenhuma regra de recorte ou cálculo mora aqui.
"""

from typing import Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

PLOTLY_TEMPLATE = "plotly_dark"

# Altura padrão dos gráficos em linha. Gráficos de leitura vertical (rankings, mapas de calor)
# calculam a própria altura em função do número de categorias.
DEFAULT_HEIGHT = 340

_BASE_LAYOUT = dict(
    template=PLOTLY_TEMPLATE,
    margin=dict(l=20, r=20, t=50, b=20),
)


def _empty_figure(title: str, mensagem: str = "Sem dados no período selecionado") -> go.Figure:
    """
    Cria uma figura vazia com uma mensagem centralizada.

    Mantém o layout do painel estável quando um recorte não tem dados, em vez de exibir um
    eixo vazio sem explicação.

    Args:
        title: Título do gráfico.
        mensagem: Texto exibido no centro da área do gráfico.

    Returns:
        Figura Plotly sem séries.
    """
    fig = go.Figure()
    fig.update_layout(
        title=title,
        annotations=[dict(text=mensagem, showarrow=False, font=dict(size=13, color="gray"))],
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        height=DEFAULT_HEIGHT,
        **_BASE_LAYOUT,
    )
    return fig


def create_requests_by_user_chart(
    df: pd.DataFrame, granularidade: str = "Dia", value_col: str = "requisicoes",
    title: str = "Requisições por período e usuário", yaxis_title: str = "Requisições",
) -> go.Figure:
    """
    Gráfico principal de uso: barras empilhadas de volume por período, segmentadas por usuário.

    Responde "quanto" e "de quem" na mesma figura — antes só havia uma linha agregada, sem
    qualquer discriminação por usuário nos gráficos.

    Args:
        df: DataFrame com as colunas 'periodo', 'user_name' e a coluna de valor.
        granularidade: Rótulo do eixo X ("Dia", "Semana" ou "Mês").
        value_col: Nome da coluna de valor a plotar.
        title: Título do gráfico.
        yaxis_title: Rótulo do eixo Y.

    Returns:
        Figura de barras empilhadas.
    """
    if df is None or df.empty:
        return _empty_figure(title)

    fig = px.bar(
        df, x='periodo', y=value_col, color='user_name',
        labels={'periodo': granularidade, value_col: yaxis_title, 'user_name': 'Usuário'},
        title=title,
    )
    fig.update_layout(
        barmode='stack',
        xaxis_title=granularidade,
        yaxis_title=yaxis_title,
        legend_title="Usuário",
        height=DEFAULT_HEIGHT,
        **_BASE_LAYOUT,
    )
    return fig


def create_user_period_heatmap(
    pivot: pd.DataFrame, granularidade: str = "Dia",
    title: str = "Intensidade de uso por usuário",
) -> go.Figure:
    """
    Mapa de calor usuário x período.

    Torna visível o padrão de adoção — quem usa continuamente, quem testou uma vez e parou,
    quem entrou recentemente —, leitura que uma série agregada não permite.

    Args:
        pivot: Matriz com índice = usuário, colunas = período, valores = requisições.
        granularidade: Rótulo do eixo X.
        title: Título do gráfico.

    Returns:
        Figura de mapa de calor.
    """
    if pivot is None or pivot.empty:
        return _empty_figure(title)

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=pivot.columns,
        y=pivot.index,
        colorscale="Viridis",
        hovertemplate="<b>%{y}</b><br>%{x|%d/%m/%Y}<br>%{z} requisições<extra></extra>",
        colorbar=dict(title="Reqs"),
    ))
    fig.update_layout(
        title=title,
        xaxis_title=granularidade,
        yaxis_title="Usuário",
        height=max(DEFAULT_HEIGHT, 60 + 26 * len(pivot.index)),
        **_BASE_LAYOUT,
    )
    return fig


def create_token_usage_chart(df: pd.DataFrame, granularidade: str = "Dia") -> go.Figure:
    """
    Consumo de tokens de entrada e saída por período.

    Args:
        df: DataFrame com 'periodo', 'input_tokens', 'cached_tokens' e 'output_tokens'.
        granularidade: Rótulo do eixo X.

    Returns:
        Figura de barras agrupadas.
    """
    title = "Consumo de tokens"
    if df is None or df.empty:
        return _empty_figure(title)

    fig = go.Figure()
    fig.add_trace(go.Bar(x=df['periodo'], y=df['input_tokens'], name='Entrada'))
    fig.add_trace(go.Bar(x=df['periodo'], y=df['output_tokens'], name='Saída'))
    if 'cached_tokens' in df.columns and df['cached_tokens'].sum() > 0:
        fig.add_trace(go.Bar(x=df['periodo'], y=df['cached_tokens'], name='Cacheados'))

    fig.update_layout(
        title=title,
        barmode='group',
        xaxis_title=granularidade,
        yaxis_title="Tokens",
        height=DEFAULT_HEIGHT,
        **_BASE_LAYOUT,
    )
    return fig


def create_costs_chart(df: pd.DataFrame, granularidade: str = "Dia") -> go.Figure:
    """
    Custo total por período.

    Args:
        df: DataFrame com as colunas 'periodo' e 'total_cost'.
        granularidade: Rótulo do eixo X.

    Returns:
        Figura de barras.
    """
    title = "Custo por período (USD)"
    if df is None or df.empty:
        return _empty_figure(title)

    fig = px.bar(df, x='periodo', y='total_cost', title=title)
    fig.update_traces(marker_color='#FF9900', hovertemplate="%{x|%d/%m/%Y}<br>$%{y:.4f}<extra></extra>")
    fig.update_layout(
        xaxis_title=granularidade,
        yaxis_title="Custo (USD)",
        height=DEFAULT_HEIGHT,
        **_BASE_LAYOUT,
    )
    return fig


def create_cost_by_model_chart(df: pd.DataFrame) -> go.Figure:
    """
    Distribuição do custo por modelo LLM.

    Args:
        df: DataFrame com as colunas 'modelo' e 'custo'.

    Returns:
        Figura de rosca.
    """
    title = "Custo por modelo"
    if df is None or df.empty:
        return _empty_figure(title, "Nenhum custo registrado no período")

    fig = go.Figure(data=[go.Pie(labels=df['modelo'], values=df['custo'], hole=.4)])
    fig.update_traces(hovertemplate="<b>%{label}</b><br>$%{value:.4f} (%{percent})<extra></extra>")
    fig.update_layout(title=title, height=DEFAULT_HEIGHT, **_BASE_LAYOUT)
    return fig


def create_accuracy_by_field_chart(df: pd.DataFrame, top_n: int = 20) -> go.Figure:
    """
    Taxa de acerto por campo, do pior para o melhor.

    Substitui o gráfico de contagem absoluta de campos corrigidos: a taxa normaliza pelo
    número de avaliações, tornando comparáveis campos com volumes distintos de feedback.

    Args:
        df: DataFrame de `feedback_analyzer.prepare_accuracy_by_field`.
        top_n: Número máximo de campos exibidos (os de pior desempenho).

    Returns:
        Figura de barras horizontais, com o número de avaliações no hover.
    """
    title = "Taxa de acerto por campo"
    if df is None or df.empty:
        return _empty_figure(title, "Nenhum feedback no período selecionado")

    data = df.head(top_n).iloc[::-1]  # pior no topo após a inversão do eixo horizontal

    fig = go.Figure(go.Bar(
        x=data['taxa_acerto'],
        y=data['campo'],
        orientation='h',
        marker=dict(
            color=data['taxa_acerto'],
            colorscale=[[0, "#D62728"], [0.5, "#FF9900"], [1, "#2CA02C"]],
            cmin=0, cmax=1,
        ),
        text=[f"{v:.0%}" for v in data['taxa_acerto']],
        textposition='outside',
        customdata=data[['avaliacoes', 'erros']].values,
        hovertemplate=("<b>%{y}</b><br>Acerto: %{x:.1%}<br>"
                       "Avaliações: %{customdata[0]}<br>Correções: %{customdata[1]}<extra></extra>"),
    ))
    fig.update_layout(
        title=title,
        xaxis_title="Taxa de acerto",
        xaxis=dict(tickformat=".0%", range=[0, 1.12]),
        yaxis_title=None,
        height=max(DEFAULT_HEIGHT, 60 + 26 * len(data)),
        margin=dict(l=220, r=20, t=50, b=20),
        template=PLOTLY_TEMPLATE,
    )
    return fig


def create_accuracy_heatmap(pivot: pd.DataFrame) -> go.Figure:
    """
    Mapa de calor da taxa de acerto por campo e modelo.

    Viabilizado pelo cruzamento entre o feedback e a análise que o originou. Responde onde
    cada modelo é mais fraco — leitura necessária desde a migração para o provedor interno.

    Args:
        pivot: Matriz de `feedback_analyzer.prepare_accuracy_by_field_and_model`.

    Returns:
        Figura de mapa de calor. Células com amostragem insuficiente ficam em branco.
    """
    title = "Taxa de acerto por campo e modelo"
    if pivot is None or pivot.empty:
        return _empty_figure(title, "Amostragem insuficiente para comparar modelos")

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values.astype(float),
        x=pivot.columns,
        y=pivot.index,
        colorscale=[[0, "#D62728"], [0.5, "#FF9900"], [1, "#2CA02C"]],
        zmin=0, zmax=1,
        texttemplate="%{z:.0%}",
        hovertemplate="<b>%{y}</b><br>%{x}<br>Acerto: %{z:.1%}<extra></extra>",
        colorbar=dict(title="Acerto", tickformat=".0%"),
        hoverongaps=False,
    ))
    fig.update_layout(
        title=title,
        xaxis_title="Modelo",
        yaxis_title=None,
        height=max(DEFAULT_HEIGHT, 80 + 26 * len(pivot.index)),
        margin=dict(l=220, r=20, t=50, b=20),
        template=PLOTLY_TEMPLATE,
    )
    return fig


def create_feedback_score_chart(df: pd.DataFrame) -> go.Figure:
    """
    Composição de acertos e correções por período.

    Args:
        df: DataFrame com 'periodo', 'acertos' e 'erros'.

    Returns:
        Figura de barras empilhadas.
    """
    title = "Acertos e correções por período"
    if df is None or df.empty:
        return _empty_figure(title, "Nenhum feedback no período selecionado")

    fig = go.Figure()
    fig.add_trace(go.Bar(x=df['periodo'], y=df['acertos'], name='Corretos (IA)', marker_color='#2CA02C'))
    fig.add_trace(go.Bar(x=df['periodo'], y=df['erros'], name='Corrigidos (usuário)', marker_color='#D62728'))
    fig.update_layout(
        title=title,
        barmode='stack',
        xaxis_title="Período",
        yaxis_title="Campos avaliados",
        height=DEFAULT_HEIGHT,
        **_BASE_LAYOUT,
    )
    return fig


def create_confusion_heatmap(matrix: pd.DataFrame, campo: str) -> go.Figure:
    """
    Matriz de confusão de um campo: resposta da IA x correção do usuário.

    A diagonal representa os acertos; as células fora dela são as confusões que servem de
    insumo direto para ajuste de prompt e das listas de opções.

    Args:
        matrix: Matriz de `feedback_analyzer.build_confusion_matrix`.
        campo: Rótulo do campo, usado no título.

    Returns:
        Figura de mapa de calor quadrado.
    """
    title = f"Matriz de confusão — {campo}"
    if matrix is None or matrix.empty:
        return _empty_figure(title, "Sem valores registrados para este campo")

    def _truncate(rotulos: pd.Index, limite: int = 34) -> list[str]:
        return [r if len(str(r)) <= limite else f"{str(r)[:limite - 1]}…" for r in rotulos]

    fig = go.Figure(data=go.Heatmap(
        z=matrix.values,
        x=_truncate(matrix.columns),
        y=_truncate(matrix.index),
        colorscale="Blues",
        texttemplate="%{z}",
        hovertemplate="IA: %{y}<br>Corrigido: %{x}<br>%{z} ocorrência(s)<extra></extra>",
        showscale=False,
    ))
    fig.update_layout(
        title=title,
        xaxis_title="Corrigido pelo usuário",
        yaxis_title="Resposta da IA",
        height=max(DEFAULT_HEIGHT, 120 + 26 * len(matrix.index)),
        margin=dict(l=260, r=20, t=50, b=140),
        template=PLOTLY_TEMPLATE,
    )
    return fig
