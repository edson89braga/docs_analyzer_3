# cleanup_cloud_logs.py
import os
import sys
import argparse
from datetime import datetime

# Adiciona o diretório 'src' ao path para importar módulos do projeto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from src.services.firebase_manager import FbManagerStorage
from src.logger.logger import LoggerSetup

def run_cloud_log_cleanup(days_to_keep: int, dry_run: bool = False):
    """
    Executa a limpeza de logs antigos no Firebase Storage.
    
    Args:
        days_to_keep: Número de dias de logs a serem mantidos.
        dry_run: Se True, apenas lista os arquivos que seriam deletados, sem executar a deleção.
    """
    # Inicializa um logger simples para o script, sem handlers de nuvem ou customizados
    LoggerSetup.initialize(routine_name="cloud_cleanup_script", dev_mode=True)
    logger = LoggerSetup.get_logger(__name__)
    
    logger.info("=" * 60)
    logger.info(f"INICIANDO SCRIPT DE LIMPEZA DE LOGS NA NUVEM - {datetime.now()}")
    logger.info(f"Modo: {'DRY RUN (simulação)' if dry_run else 'EXECUÇÃO REAL'}")
    logger.info(f"Período de retenção: {days_to_keep} dias")
    logger.info("=" * 60)

    try:
        storage_manager = FbManagerStorage()
        logger.info("Conexão com Firebase Storage (Admin SDK) estabelecida.")
    except Exception as e:
        logger.error(f"FALHA CRÍTICA: Não foi possível inicializar o Firebase Admin SDK: {e}")
        logger.error("Verifique se as credenciais de serviço (credentials_manager) estão configuradas corretamente neste ambiente.")
        return

    # Acessa o método de classe diretamente, passando a instância do manager
    # Vamos adaptar a função para aceitar o modo dry_run
    try:
        # Reutilizamos o método _cleanup_old_cloud_logs, mas agora ele precisa ser acessível
        # ou sua lógica duplicada. É melhor torná-lo público e adaptá-lo.
        # Vamos criar um wrapper público em LoggerSetup para isso.
        
        # Chamando a função de limpeza (que precisará ser adaptada para dry-run)
        LoggerSetup.cleanup_cloud_logs(
            storage_manager=storage_manager,
            days_to_keep=days_to_keep,
            dry_run=dry_run
        )
        
    except Exception as e:
        logger.error(f"Ocorreu um erro inesperado durante a execução da limpeza: {e}", exc_info=True)
    
    logger.info("=" * 60)
    logger.info("Script de limpeza de logs finalizado.")
    logger.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Script para limpar logs antigos do Firebase Storage."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Número de dias de logs a serem mantidos. Logs mais antigos serão removidos. Padrão: 30."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Executa o script em modo de simulação, apenas listando os arquivos que seriam removidos, sem de fato removê-los."
    )
    
    args = parser.parse_args()
    
    run_cloud_log_cleanup(days_to_keep=args.days, dry_run=args.dry_run)


'''
Para simular (ver o que seria apagado):
>>> python cleanup_cloud_logs.py --dry-run

Para limpar logs com mais de 15 dias:
>>> python cleanup_cloud_logs.py --days 15

'''