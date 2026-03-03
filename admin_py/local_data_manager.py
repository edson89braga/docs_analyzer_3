# admin_py/local_data_manager.py
import os
import json
import logging
import re
from datetime import date, datetime, timezone
from typing import List, Dict, Any, Set, Tuple, Optional

from SOURCE.services.firebase_manager import (
    inicializar_firebase, FbManagerFirestore, FbManagerStorage, FbManagerAdminAuth
)

logger = logging.getLogger(__name__)

ADMIN_DATA_DIR = "admin_data"
ADMIN_LOGS_DIR = os.path.join(ADMIN_DATA_DIR, "logs")
ADMIN_METRICS_DIR = os.path.join(ADMIN_DATA_DIR, "metrics")

os.makedirs(ADMIN_LOGS_DIR, exist_ok=True)
os.makedirs(ADMIN_METRICS_DIR, exist_ok=True)

SYNC_METADATA_FILE = os.path.join(ADMIN_DATA_DIR, "sync_metadata.json")

def save_last_sync_timestamp():
    """Salva o timestamp da sincronização bem-sucedida em um arquivo local."""
    try:
        with open(SYNC_METADATA_FILE, 'w', encoding='utf-8') as f:
            json.dump({"last_sync_utc": datetime.now(timezone.utc).isoformat()}, f)
        logger.info(f"Timestamp da última sincronização salvo em {SYNC_METADATA_FILE}")
    except IOError as e:
        logger.error(f"Erro ao salvar o timestamp da sincronização: {e}")

def load_last_sync_timestamp() -> Optional[str]:
    """
    Carrega o timestamp da última sincronização do arquivo local.
    Retorna uma string formatada ou None.
    """
    if not os.path.exists(SYNC_METADATA_FILE):
        return None
    try:
        with open(SYNC_METADATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            ts_iso = data.get("last_sync_utc")
            if ts_iso:
                return datetime.fromisoformat(ts_iso).strftime('%d/%m/%Y às %H:%M:%S (UTC)')
    except (IOError, json.JSONDecodeError, KeyError) as e:
        logger.error(f"Erro ao carregar o timestamp da sincronização: {e}")
    return None

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

def get_user_id_to_name_map() -> Dict[str, str]:
    """Busca usuários do Firebase Auth e cria um mapa UID -> nome amigável."""
    user_map = {}
    try:
        inicializar_firebase()
        auth_manager = FbManagerAdminAuth()
        for user in auth_manager.list_users().iterate_all():
            if user.email:
                user_map[user.uid] = user.email.split('@')[0]
            else:
                user_map[user.uid] = user.uid # Fallback para o UID
    except Exception as e:
        logger.error(f"Erro ao popular mapa de usuários: {e}", exc_info=True)
    return user_map

def sync_cloud_data_to_local() -> Tuple[bool, str]:
    """
    Worker para baixar logs do Storage e métricas do Firestore.
    Otimizado para baixar apenas arquivos que ainda não existem localmente.
    Retorna um status e uma mensagem.
    """
    try:
        logger.info("Iniciando a sincronização de dados da nuvem...")
        inicializar_firebase()
        fs_manager = FbManagerFirestore()
        storage_manager = FbManagerStorage()
        auth_manager = FbManagerAdminAuth()
        
        # Sincronizar Logs do Storage
        from SOURCE.settings import CLOUD_LOGGER_FOLDER
        logger.info("Verificando logs no Firebase Storage...")
        all_logs_blobs = storage_manager.bucket.list_blobs(prefix=CLOUD_LOGGER_FOLDER)
        for blob in all_logs_blobs:
            if blob.name.endswith('/'):
                continue

            local_path = os.path.join(ADMIN_DATA_DIR, blob.name.replace('/', os.sep))
            
            if not os.path.exists(local_path):
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                logger.debug(f"Baixando log: {blob.name} para {local_path}")
                blob.download_to_filename(local_path)

        # Sincronizar Métricas do Firestore
        logger.info("Verificando métricas no Firestore...")
        all_user_ids = {user.uid for user in auth_manager.list_users().iterate_all()}
        for user_id in all_user_ids:
            metrics_collection_path = f'user_metrics/{user_id}/metrics'
            metrics_ref = fs_manager.db.collection(metrics_collection_path).stream()

            for metric_doc in metrics_ref:
                local_user_metric_dir = os.path.join(ADMIN_METRICS_DIR, user_id)
                os.makedirs(local_user_metric_dir, exist_ok=True)
                local_metric_path = os.path.join(local_user_metric_dir, f"{metric_doc.id}.json")
                
                if not os.path.exists(local_metric_path):
                    logger.debug(f"Baixando métrica para usuário '{user_id}': {metric_doc.id}")
                    try:
                        with open(local_metric_path, 'w', encoding='utf-8') as f:
                            json.dump(metric_doc.to_dict(), f, indent=2, ensure_ascii=False)
                    except Exception as write_err:
                        logger.error(f"Erro ao salvar arquivo de métrica local '{local_metric_path}': {write_err}")

        save_last_sync_timestamp()
        msg = "Sincronização de dados concluída!"
        logger.info(msg)
        return True, msg

    except Exception as e:
        msg = f"Erro durante a sincronização de dados: {e}"
        logger.error(msg, exc_info=True)
        return False, msg

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
    if selected_type.lower() in ["all", "todos", "log", "logs"]:
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
    if selected_type.lower() in ["all", "todos", "metric", "métricas"]:
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
