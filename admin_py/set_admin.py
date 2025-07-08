# admin_py/set_admin.py
import sys
import os
from typing import Optional

# Adiciona o diretório raiz ao path para encontrar 'src'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.services.firebase_manager import FbManagerAdminAuth, inicializar_firebase
from src.logger.logger import LoggerSetup

logger = LoggerSetup.get_logger(__name__)

def set_user_admin_status(email: str, is_admin: bool) -> bool:
    """
    Define ou remove o custom claim de 'admin' para um usuário.
    Esta é uma operação administrativa e deve ser chamada de um ambiente seguro.

    Args:
        email (str): O email do usuário a ser modificado.
        is_admin (bool): True para adicionar o claim, False para remover.

    Returns:
        bool: True se a operação foi bem-sucedida, False caso contrário.
    """
    try:
        # Garante que o Firebase esteja inicializado para esta operação
        inicializar_firebase()
        admin_auth_manager = FbManagerAdminAuth()
        success = admin_auth_manager.set_admin_claim(email, is_admin)

        if success:
            logger.info(f"Sucesso! Claim 'admin' para {email} definido como {is_admin}.")
        else:
            # A falha já é logada dentro de set_admin_claim
            logger.error(f"Falha ao definir o claim para {email}.")
        
        return success
    except Exception as e:
        logger.critical(f"ERRO CRÍTICO ao tentar definir status de admin para '{email}': {e}", exc_info=True)
        return False