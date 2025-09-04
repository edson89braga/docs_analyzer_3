# admin_py/dashboard_plotter.py
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

PLOTLY_TEMPLATE = "plotly_dark" # ou "plotly", "ggplot2", etc.

def create_usage_chart(df: pd.DataFrame) -> go.Figure:
    """Cria o gráfico de linha para uso diário."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['date'], y=df['analysis_count'], mode='lines+markers', name='Análises Realizadas'))
    fig.add_trace(go.Scatter(x=df['date'], y=df['active_users'], mode='lines+markers', name='Usuários Ativos'))
    
    fig.update_layout(
        title="Uso Diário da Aplicação",
        xaxis_title="Data",
        yaxis_title="Contagem",
        legend_title="Métrica",
        template=PLOTLY_TEMPLATE,
        margin=dict(l=20, r=20, t=40, b=20),
        height=300
    )
    return fig

def create_costs_chart(df: pd.DataFrame) -> go.Figure:
    """Cria o gráfico de linha para custos diários."""
    fig = px.bar(df, x='date', y='total_cost', title="Custos Diários (USD)")
    
    fig.update_layout(
        xaxis_title="Data",
        yaxis_title="Custo (USD)",
        template=PLOTLY_TEMPLATE,
        margin=dict(l=20, r=20, t=40, b=20),
        height=300
    )
    fig.update_traces(marker_color='#FF9900')
    return fig

def create_cost_distribution_pie(data: dict) -> go.Figure:
    """Cria o gráfico de pizza para distribuição de custos."""
    labels = list(data.keys())
    values = list(data.values())
    
    fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.3)])
    fig.update_layout(
        title="Distribuição de Custos Totais",
        template=PLOTLY_TEMPLATE,
        margin=dict(l=20, r=20, t=40, b=20),
        height=300
    )
    return fig

def create_feedback_score_chart(data: dict) -> go.Figure:
    """Cria o gráfico de barras para o score de feedback."""
    labels = list(data.keys())
    values = list(data.values())
    
    fig = go.Figure(data=[go.Bar(x=labels, y=values, text=values, textposition='auto')])
    fig.update_layout(
        title="Score de Feedback da IA",
        xaxis_title="Avaliação do Usuário",
        yaxis_title="Total de Campos",
        template=PLOTLY_TEMPLATE,
        margin=dict(l=20, r=20, t=40, b=20),
        height=300
    )
    return fig
    
def create_top_edited_fields_chart(data: pd.Series) -> go.Figure:
    """Cria o gráfico de barras para os campos mais editados."""
    if data.empty:
        fig = go.Figure()
        fig.update_layout(
            title="Top 5 Campos Mais Corrigidos",
            template=PLOTLY_TEMPLATE,
            annotations=[dict(text="Nenhum dado de correção encontrado", showarrow=False)],
            height=300
        )
        return fig

    fig = px.bar(data, x=data.values, y=data.index, orientation='h', title="Top 5 Campos Mais Corrigidos")
    fig.update_layout(
        xaxis_title="Número de Correções",
        yaxis_title="Campo",
        template=PLOTLY_TEMPLATE,
        margin=dict(l=150, r=20, t=40, b=20),
        height=300
    )
    return fig

