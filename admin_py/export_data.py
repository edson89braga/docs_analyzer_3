# admin_py/export_data.py
import os
import json
import logging
import re
import pandas as pd
from datetime import date, datetime
from typing import List, Dict, Any

from admin_py.local_data_manager import ADMIN_LOGS_DIR, ADMIN_METRICS_DIR

logger = logging.getLogger(__name__)

def _parse_log_line(line: str) -> Dict[str, Any]:
    """Extrai o nível de log de uma linha de log formatada."""
    match = re.search(r"\| (INFO|WARNING|ERROR|CRITICAL)\s*\|", line)
    return {"nível (log)": match.group(1)} if match else {}

def _parse_pdf_analysis_metric(metric_data: Dict) -> Dict[str, Any]:
    """Extrai e achata os dados de uma métrica de 'pdf_analysis_completed'."""
    row = {}
    proc_meta = metric_data.get("processing_metadata", {})
    llm_meta = metric_data.get("llm_analysis_metadata", {})
    
    row["tipo_metric"] = "pdf_analysis_completed"
    row["filenames_uploaded"] = ", ".join(metric_data.get("filenames_uploaded", []))
    
    # Flatten processing_metadata
    for key, value in proc_meta.items():
        row[f"proc_{key}"] = value
        
    # Flatten llm_analysis_metadata
    for key, value in llm_meta.items():
        row[f"llm_{key}"] = value
        
    return row

def _parse_llm_feedback_metric(metric_data: Dict) -> Dict[str, Any]:
    """Extrai e resume os dados de uma métrica de 'llm_feedback'."""
    row = {}
    details = metric_data.get("details", {})
    feedback_fields = details.get("feedback_fields", [])
    
    acertos = sum(1 for field in feedback_fields if field.get("llm_acertou") is True)
    erros = sum(1 for field in feedback_fields if field.get("llm_acertou") is False)
    campos_errados = [field.get("label_campo") for field in feedback_fields if field.get("llm_acertou") is False]

    row["tipo_metric"] = "llm_feedback"
    row["analysis_timestamp_ref"] = details.get("analysis_timestamp_ref")
    row["acertos_feedback"] = acertos
    row["erros_feedback"] = erros
    row["campos_com_erro"] = ", ".join(campos_errados) if campos_errados else "N/A"
    
    return row

def process_filtered_data_for_export(selected_user: str, selected_level: str, selected_date: date, selected_type: str, user_id_to_name_map: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Processa arquivos locais filtrados e extrai dados estruturados para exportação.
    """
    processed_data = []
    
    # Processa Logs
    if selected_type in ["ALL", "log"]:
        date_path_segment = selected_date.strftime('%Y/%m/%d').replace('/', os.sep)
        log_dir_for_date = os.path.join(ADMIN_LOGS_DIR, date_path_segment)
        if os.path.isdir(log_dir_for_date):
            for filename in os.listdir(log_dir_for_date):
                user_id_match = re.search(r'_([a-zA-Z0-9]+)\.log$', filename)
                user_id = user_id_match.group(1) if user_id_match else None
                if user_id and (selected_user == "ALL" or selected_user == user_id):
                    filepath = os.path.join(log_dir_for_date, filename)
                    user_name = user_id_to_name_map.get(user_id, user_id)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            for line in f:
                                log_level_data = _parse_log_line(line)
                                if selected_level == "ALL" or log_level_data.get("nível (log)") == selected_level:
                                    row = {
                                        "usuário": user_name, "tipo": "log", "data_dia": selected_date.strftime('%Y-%m-%d'),
                                        "conteúdo": line.strip()
                                    }
                                    row.update(log_level_data)
                                    processed_data.append(row)
                    except Exception as e:
                        logger.warning(f"Erro ao processar log para exportação '{filepath}': {e}")

    # Processa Métricas
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
                                ts_str = metric_data.get('timestamp_event') or metric_data.get('feedback_submission_timestamp')
                                if ts_str and datetime.fromisoformat(ts_str).date() == selected_date:
                                    row = {"usuário": user_name, "tipo": "metric", "data_dia": selected_date.strftime('%Y-%m-%d')}
                                    event_type = metric_data.get("event_type")
                                    if event_type == "pdf_analysis_completed":
                                        row.update(_parse_pdf_analysis_metric(metric_data))
                                    elif event_type == "llm_feedback":
                                        row.update(_parse_llm_feedback_metric(metric_data))
                                    processed_data.append(row)
                        except Exception as e:
                            logger.warning(f"Erro ao processar métrica para exportação '{filepath}': {e}")

    return processed_data

def export_data_to_excel(data: List[Dict[str, Any]], save_path: str) -> bool:
    """
    Converte uma lista de dicionários para um arquivo Excel.
    """
    if not data:
        logger.warning("Nenhum dado para exportar.")
        return False
    try:
        df = pd.DataFrame(data)
        df.to_excel(save_path, index=False, engine='openpyxl')
        logger.info(f"Dados exportados com sucesso para: {save_path}")
        return True
    except Exception as e:
        logger.error(f"Falha ao exportar para Excel: {e}", exc_info=True)
        return False