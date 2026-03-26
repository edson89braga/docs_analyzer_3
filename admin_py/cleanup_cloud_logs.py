# admin_py/cleanup_cloud_logs.py
import os
import sys
from datetime import datetime, timedelta, timezone

# Adiciona o diretório raiz ao path para encontrar 'src'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from SOURCE.services.firebase_manager import FbManagerStorage, FbManagerAdminAuth, inicializar_firebase
from SOURCE.logger.logger import LoggerSetup

logger = LoggerSetup.get_logger(__name__)

def get_cloud_log_stats(days_to_keep: int=30) -> dict:
    """
    Busca estatísticas sobre os arquivos de log no Firebase Storage.

    Args:
        days_to_keep: Número de dias para considerar um arquivo como "antigo".

    Returns:
        Um dicionário com 'total_count' e 'old_count', ou um dicionário de erro.
    """
    logger.info(f"Buscando estatísticas de logs na nuvem (retenção: {days_to_keep} dias)...")
    try:
        inicializar_firebase()
        storage_manager = FbManagerStorage()
    except Exception as e:
        msg = f"FALHA CRÍTICA: Não foi possível inicializar o Firebase Admin SDK: {e}"
        logger.critical(msg)
        return {"error": msg}

    total_count = 0
    old_count = 0
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)

    try:
        from SOURCE.settings import CLOUD_LOGGER_FOLDER
        def count_blobs(prefix: str):
            nonlocal total_count, old_count
            blobs_iterator = storage_manager.bucket.list_blobs(prefix=prefix)
            for blob in blobs_iterator:
                if blob.name.endswith('/'): continue
                total_count += 1
                if blob.updated and blob.updated < cutoff_date:
                    old_count += 1

        # Legacy logs e Novos logs
        count_blobs(CLOUD_LOGGER_FOLDER)
        auth_manager = FbManagerAdminAuth()
        for user in auth_manager.list_users().iterate_all():
            count_blobs(f"users/{user.uid}/logs/")
        
        logger.info(f"Estatísticas de logs obtidas: {total_count} arquivos no total, {old_count} arquivos antigos.")
        return {"total_count": total_count, "old_count": old_count}
    except Exception as e:
        msg = f"Erro ao buscar estatísticas de logs na nuvem: {e}"
        logger.error(msg, exc_info=True)
        return {"error": msg}

def run_cloud_log_cleanup(days_to_keep: int, dry_run: bool = False) -> bool:
    """
    Executa a limpeza de logs antigos no Firebase Storage.
    
    Args:
        days_to_keep: Número de dias de logs a serem mantidos.
        dry_run: Se True, apenas lista os arquivos que seriam deletados.

    Returns:
        True se a operação foi bem-sucedida, False caso contrário.
    """
    logger.info("=" * 60)
    logger.info(f"INICIANDO LIMPEZA DE LOGS NA NUVEM - {datetime.now()}")
    logger.info(f"Modo: {'DRY RUN (simulação)' if dry_run else 'EXECUÇÃO REAL'}")
    logger.info(f"Período de retenção: {days_to_keep} dias")
    logger.info("=" * 60)

    try:
        inicializar_firebase()
        storage_manager = FbManagerStorage()
        logger.info("Conexão com Firebase Storage (Admin SDK) estabelecida.")
    except Exception as e:
        logger.critical(f"FALHA CRÍTICA: Não foi possível inicializar o Firebase Admin SDK: {e}")
        return False

    try:
        auth_manager = FbManagerAdminAuth()
        extra_prefixes = [f"users/{user.uid}/logs/" for user in auth_manager.list_users().iterate_all()]
    except Exception as e:
        logger.warning(f"Não foi possível obter usuários para limpar novos logs: {e}")
        extra_prefixes = None

    try:
        # Chama a função de limpeza do LoggerSetup
        LoggerSetup.cleanup_cloud_logs(
            storage_manager=storage_manager,
            days_to_keep=days_to_keep,
            dry_run=dry_run,
            extra_prefixes=extra_prefixes
        )
        logger.info("Script de limpeza de logs finalizado com sucesso.")
        return True
    except Exception as e:
        logger.error(f"Ocorreu um erro inesperado durante a execução da limpeza: {e}", exc_info=True)
        return False

        