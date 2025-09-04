# admin_py/dashboard_analyzer.py
import pandas as pd
import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from admin_py.local_data_manager import ADMIN_METRICS_DIR, get_available_users

logger = logging.getLogger(__name__)

def load_all_metrics_to_dataframe() -> Optional[pd.DataFrame]:
    """
    Carrega todos os arquivos de métricas JSON do diretório local para um DataFrame pandas.
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
    
    # Padroniza e converte a coluna de timestamp
    df['timestamp'] = pd.to_datetime(df['timestamp_event'], errors='coerce')
    df = df.dropna(subset=['timestamp']) # Remove linhas sem timestamp válido
    df['date'] = df['timestamp'].dt.date
    
    return df

def calculate_kpis(df: pd.DataFrame, user_id_to_name_map: Dict[str, str], days: int) -> Dict[str, Any]:
    """Calcula os KPIs principais a partir do DataFrame de métricas."""
    if df is None or df.empty:
        return {"total_users": 0, "total_analyses": 0, "total_feedbacks": 0, "total_cost_usd": 0.0, "avg_cost_per_analysis": 0.0}

    # Adiciona o filtro de período no início da função
    cutoff_date = (datetime.now() - timedelta(days=days)).date()
    df_period = df[df['date'] >= cutoff_date]

    analyses_df = df_period[df_period['event_type'] == 'pdf_analysis_completed']
    feedbacks_df = df_period[df_period['event_type'] == 'llm_feedback']

    total_users = len(get_available_users(user_id_to_name_map))
    total_analyses = len(analyses_df)
    total_feedbacks = len(feedbacks_df)
    
    total_cost_embeddings = analyses_df['processing_metadata_calculated_embedding_cost_usd'].sum()
    total_cost_llm = analyses_df['llm_analysis_metadata_total_cost_usd'].sum()
    total_cost_usd = total_cost_embeddings + total_cost_llm
    
    avg_cost_per_analysis = (total_cost_usd / total_analyses) if total_analyses > 0 else 0.0

    return {
        "total_users": total_users,
        "total_analyses": total_analyses,
        "total_feedbacks": total_feedbacks,
        "total_cost_usd": total_cost_usd,
        "avg_cost_per_analysis": avg_cost_per_analysis
    }

def prepare_usage_data(df: pd.DataFrame, days: int) -> pd.DataFrame:
    """Prepara os dados de uso diário (análises e usuários ativos)."""
    if df is None or df.empty:
        return pd.DataFrame(columns=['date', 'analysis_count', 'active_users'])

    cutoff_date = (datetime.now() - timedelta(days=days)).date()
    df_filtered = df[df['date'] >= cutoff_date]
    
    analyses_df = df_filtered[df_filtered['event_type'] == 'pdf_analysis_completed']
    
    daily_analyses = analyses_df.groupby('date').size().rename('analysis_count')
    daily_active_users = df_filtered.groupby('date')['user_id'].nunique().rename('active_users')
    
    usage_df = pd.concat([daily_analyses, daily_active_users], axis=1).fillna(0).astype(int).reset_index()
    usage_df = usage_df.sort_values('date')
    
    # Garante que todos os dias no período estejam presentes
    all_days = pd.date_range(start=cutoff_date, end=datetime.now().date(), freq='D').date
    usage_df = usage_df.set_index('date').reindex(all_days, fill_value=0).reset_index().rename(columns={'index': 'date'})
    
    return usage_df

def prepare_cost_data(df: pd.DataFrame, days: int) -> pd.DataFrame:
    """Prepara os dados de custo diário."""
    if df is None or df.empty:
        return pd.DataFrame(columns=['date', 'total_cost'])

    cutoff_date = (datetime.now() - timedelta(days=days)).date()
    analyses_df = df[(df['event_type'] == 'pdf_analysis_completed') & (df['date'] >= cutoff_date)].copy()
    
    analyses_df['total_cost'] = analyses_df['processing_metadata_calculated_embedding_cost_usd'].fillna(0) + \
                                analyses_df['llm_analysis_metadata_total_cost_usd'].fillna(0)

    daily_costs = analyses_df.groupby('date')['total_cost'].sum().reset_index()
    
    # Garante que todos os dias no período estejam presentes
    all_days = pd.date_range(start=cutoff_date, end=datetime.now().date(), freq='D').date
    daily_costs = daily_costs.set_index('date').reindex(all_days, fill_value=0).reset_index().rename(columns={'index': 'date'})

    return daily_costs

def prepare_cost_distribution_data(df: pd.DataFrame, days: int) -> Dict[str, float]:
    """Prepara os dados para o gráfico de pizza de distribuição de custos."""
    if df is None or df.empty:
        return {"Embeddings": 0, "Análise LLM": 0}
        
    cutoff_date = (datetime.now() - timedelta(days=days)).date()
    analyses_df = df[(df['event_type'] == 'pdf_analysis_completed') & (df['date'] >= cutoff_date)]
    total_cost_embeddings = analyses_df['processing_metadata_calculated_embedding_cost_usd'].sum()
    total_cost_llm = analyses_df['llm_analysis_metadata_total_cost_usd'].sum()
    
    return {"Embeddings": total_cost_embeddings, "Análise LLM": total_cost_llm}

def prepare_feedback_quality_data(df: pd.DataFrame, days: int) -> Dict[str, int]:
    """Prepara os dados para o gráfico de barras de score de feedback."""
    if df is None or df.empty:
        return {"Corretos (IA)": 0, "Corrigidos (Usuário)": 0}

    cutoff_date = (datetime.now() - timedelta(days=days)).date()
    feedbacks_df = df[(df['event_type'] == 'llm_feedback') & (df['date'] >= cutoff_date)].copy()
    if feedbacks_df.empty:
        return {"Corretos (IA)": 0, "Corrigidos (Usuário)": 0}

    feedback_fields = feedbacks_df.explode('details_feedback_fields')
    
    # Normaliza a coluna explodida
    normalized_fields = pd.json_normalize(feedback_fields['details_feedback_fields'])
    
    correct_count = normalized_fields['llm_acertou'].sum()
    corrected_count = (normalized_fields['llm_acertou'] == False).sum()
    
    return {"Corretos (IA)": int(correct_count), "Corrigidos (Usuário)": int(corrected_count)}
    
def prepare_top_edited_fields_data(df: pd.DataFrame, days: int, top_n: int = 5) -> pd.Series:
    """Prepara os dados dos campos mais editados."""
    if df is None or df.empty:
        return pd.Series(dtype=int)

    cutoff_date = (datetime.now() - timedelta(days=days)).date()
    feedbacks_df = df[(df['event_type'] == 'llm_feedback') & (df['date'] >= cutoff_date)].copy()
    if feedbacks_df.empty:
        return pd.Series(dtype=int)
    
    feedback_fields = feedbacks_df.explode('details_feedback_fields')
    normalized_fields = pd.json_normalize(feedback_fields['details_feedback_fields'])
        
    corrected_fields = normalized_fields[normalized_fields['llm_acertou'] == False]
    
    if corrected_fields.empty:
        return pd.Series(dtype=int)
        
    top_edited = corrected_fields['label_campo'].value_counts().nlargest(top_n)
    return top_edited

def prepare_user_activity_table(df: pd.DataFrame, user_id_to_name_map: Dict[str, str], days: int) -> pd.DataFrame:
    """Prepara uma tabela com o resumo da atividade por usuário."""
    if df is None or df.empty:
        return pd.DataFrame()

    # Adiciona o filtro de período no início da função
    cutoff_date = (datetime.now() - timedelta(days=days)).date()
    df_period = df[df['date'] >= cutoff_date]

    analyses_df = df_period[df_period['event_type'] == 'pdf_analysis_completed'].copy()
    feedbacks_df = df_period[df_period['event_type'] == 'llm_feedback'].copy()

    user_analyses = analyses_df.groupby('user_id').size().rename('Análises')
    user_feedbacks = feedbacks_df.groupby('user_id').size().rename('Feedbacks')
    
    analyses_df['total_cost'] = analyses_df['processing_metadata_calculated_embedding_cost_usd'].fillna(0) + \
                                analyses_df['llm_analysis_metadata_total_cost_usd'].fillna(0)
    user_costs = analyses_df.groupby('user_id')['total_cost'].sum().rename('Custo (USD)')

    # Usa todos os eventos para encontrar a última atividade
    last_activity = df_period.groupby('user_id')['timestamp'].max().rename('Última Atividade')

    # Combina todas as séries em um DataFrame
    user_table = pd.concat([user_analyses, user_feedbacks, user_costs, last_activity], axis=1).fillna(0)
    user_table['Nome'] = user_table.index.map(user_id_to_name_map).fillna('Usuário Desconhecido')

    # Filtra usuários que não estão mais no mapa de usuários (ex: deletados)
    user_table = user_table[user_table['Nome'] != 'Usuário Desconhecido']

    # Reordena e formata as colunas
    user_table = user_table[['Nome', 'Análises', 'Feedbacks', 'Custo (USD)', 'Última Atividade']].reset_index(drop=True)
    user_table['Análises'] = user_table['Análises'].astype(int)
    user_table['Feedbacks'] = user_table['Feedbacks'].astype(int)
    user_table = user_table.sort_values(by='Análises', ascending=False)

    return user_table

