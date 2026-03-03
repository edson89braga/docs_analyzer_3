# FILE: admin_py/user_verification.py

import logging
from firebase_admin import auth as firebase_auth
from src.services.firebase_manager import inicializar_firebase

logger = logging.getLogger(__name__)

def generate_verification_link(email: str) -> tuple[bool, str]:
    """
    Gera um link de verificação de e-mail para um usuário específico.

    Args:
        email (str): O e-mail do usuário para o qual o link será gerado.

    Returns:
        tuple[bool, str]: Uma tupla contendo um booleano de sucesso e o link (em caso de sucesso)
                          ou uma mensagem de erro (em caso de falha).
    """
    try:
        inicializar_firebase()  # Garante que o SDK Admin esteja inicializado
        link = firebase_auth.generate_email_verification_link(email)
        logger.info(f"Link de verificação gerado com sucesso para {email}.")
        return True, link
    except firebase_auth.UserNotFoundError:
        msg = f"Usuário com e-mail '{email}' não encontrado no Firebase Authentication."
        logger.error(msg)
        return False, msg
    except Exception as e:
        msg = f"Erro inesperado ao gerar link para '{email}': {e}"
        logger.error(msg, exc_info=True)
        return False, msg