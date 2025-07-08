# admin_py/local_data_manager.py
import os
import json
import logging
import re
from datetime import date, datetime
from typing import List, Dict, Any, Set, Tuple

logger = logging.getLogger(__name__)

ADMIN_DATA_DIR = "admin_data"
ADMIN_LOGS_DIR = os.path.join(ADMIN_DATA_DIR, "logs")
ADMIN_METRICS_DIR = os.path.join(ADMIN_DATA_DIR, "metrics")

os.makedirs(ADMIN_LOGS_DIR, exist_ok=True)
os.makedirs(ADMIN_METRICS_DIR, exist_ok=True)

def get_available_users(user_id_to_name_map: Dict[str, str]) -> List[Tuple[str, str]]:
    """
    Busca os IDs de usuário que possuem dados locais e retorna uma lista de
    tuplas com (nome_amigavel, user_id).

    Args:
        user_id_to_name_map: Dicionário que mapeia UID para nome de usuário.

    Returns:
        Uma lista ordenada de tuplas (nome_amigavel, user_id).
    """
    local_user_ids: Set[str] = set()
    try:
        if os.path.exists(ADMIN_LOGS_DIR):
            local_user_ids.update(os.listdir(ADMIN_LOGS_DIR))
        if os.path.exists(ADMIN_METRICS_DIR):
            local_user_ids.update(os.listdir(ADMIN_METRICS_DIR))
    except OSError as e:
        logger.error(f"Erro ao listar diretórios de usuários locais: {e}")
    
    # Monta a lista de retorno apenas com os usuários que têm dados locais
    users_with_names = []
    for user_id in sorted(list(local_user_ids)):
        display_name = user_id_to_name_map.get(user_id, user_id) # Usa o ID como fallback
        users_with_names.append((display_name, user_id))
        
    return sorted(users_with_names, key=lambda x: x[0]) # Ordena pelo nome amigável

def get_filtered_logs(selected_user: str, selected_level: str, selected_date: date, selected_type: str, user_id_to_name_map: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Lê e filtra os arquivos de log e métricas locais com base nos filtros selecionados.

    Args:
        selected_user: O ID do usuário para filtrar, ou "ALL" para todos.
        selected_level: O nível de log para filtrar (ex: 'INFO'), ou "ALL".
        selected_date: A data para filtrar as entradas.
        selected_type: O tipo de entrada para filtrar ('log', 'metric'), ou "ALL".
        user_id_to_name_map: Dicionário que mapeia UID para nome de usuário.

    Returns:
        Uma lista de dicionários, onde cada dicionário representa uma entrada formatada.
    """
    filtered_entries: List[Dict[str, Any]] = []
    
    # 1. Filtra Logs
    if selected_type in ["ALL", "log"]:
        date_path_segment = selected_date.strftime('%Y/%m/%d').replace('/', os.sep)
        log_dir_for_date = os.path.join(ADMIN_LOGS_DIR, date_path_segment)
        
        if os.path.isdir(log_dir_for_date):
            for filename in os.listdir(log_dir_for_date):
                user_id_match = re.search(r'_([a-zA-Z0-9]+)\.log$', filename)
                user_id_from_file = user_id_match.group(1) if user_id_match else None
                
                user_matches = (selected_user == "ALL" or selected_user == user_id_from_file)
                
                if filename.endswith(".log") and user_matches and user_id_from_file:
                    filepath = os.path.join(log_dir_for_date, filename)
                    user_name = user_id_to_name_map.get(user_id_from_file, user_id_from_file)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            for line in f:
                                if selected_level == "ALL" or f"| {selected_level}" in line:
                                    filtered_entries.append({
                                        "type": "log", "user_name": user_name, "content": line.strip()
                                    })
                    except Exception as e:
                        logger.warning(f"Erro ao ler arquivo de log '{filepath}': {e}")

    # 2. Filtra Métricas
    if selected_type in ["ALL", "metric"]:
        users_to_scan = list(user_id_to_name_map.keys()) if selected_user == "ALL" else [selected_user]
        
        for user_id in users_to_scan:
            user_metric_dir = os.path.join(ADMIN_METRICS_DIR, user_id)
            user_name = user_id_to_name_map.get(user_id, user_id)
            if os.path.isdir(user_metric_dir):
                for filename in os.listdir(user_metric_dir):
                    if filename.endswith(".json"):
                        filepath = os.path.join(user_metric_dir, filename)
                        try:
                            with open(filepath, 'r', encoding='utf-8') as f:
                                metric_data = json.load(f)
                                timestamp_str = metric_data.get('timestamp_event') or metric_data.get('feedback_submission_timestamp')
                                if timestamp_str:
                                    event_date = datetime.fromisoformat(timestamp_str).date()
                                    if event_date == selected_date:
                                        pretty_json = json.dumps(metric_data, indent=2, ensure_ascii=False)
                                        summary = f"Métrica: {metric_data.get('event_type', 'N/A')} em {timestamp_str}"
                                        
                                        filtered_entries.append({
                                            "type": "metric", "user_name": user_name, "content": f"{summary}\n{'-'*60}\n{pretty_json}"
                                        })
                        except Exception as e:
                            logger.warning(f"Erro ao processar arquivo de métrica '{filepath}': {e}")
                            
    filtered_entries.sort(key=lambda x: x.get('content', ''))
    return filtered_entries
