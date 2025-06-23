# src/utils/config_manager.py
import logging
logger = logging.getLogger(__name__)

from time import perf_counter
start_time = perf_counter()
logger.debug(f"{start_time:.4f}s - Iniciando config_manager.py")

import atexit
import keyring
import logging
from typing import Dict, Any, Optional

from src.settings import (APP_NAME, PROXY_URL_DEFAULT, PROXY_PORT_DEFAULT, PROXY_KEYRING_SERVICE, K_PROXY_ENABLED, K_PROXY_PASSWORD_SAVED, 
                          K_PROXY_IP_URL, K_PROXY_PORT, K_PROXY_USERNAME, K_PROXY_PASSWORD)

''' Se essa backend migrar para nuvem, avaliar como funcionará a sistemática do Save_proxy_settings se necessário'''

# --- Funções de Gerenciamento de Configuração ---

def get_proxy_settings() -> Optional[Dict[str, Any]]:
    """
    Recupera as configurações de proxy (EXCETO SENHA) salvas no Keyring.

    Returns:
        Optional[Dict[str, Any]]: Dicionário com 'enabled', 'ip', 'port', 'username',
                                  ou {'enabled': False} se não configurado/erro.
    """
    logger.debug(f"Buscando config proxy (sem senha) do Keyring (Service: {PROXY_KEYRING_SERVICE})")
    config_start = {K_PROXY_ENABLED: False, 
              K_PROXY_PASSWORD_SAVED: False, 
              K_PROXY_IP_URL: PROXY_URL_DEFAULT, 
              K_PROXY_PORT: PROXY_PORT_DEFAULT, 
              K_PROXY_USERNAME: None}
    config = config_start.copy()

    try:
        enabled_str = keyring.get_password(PROXY_KEYRING_SERVICE, K_PROXY_ENABLED)
        config[K_PROXY_ENABLED] = enabled_str is not None and enabled_str.lower() in ('true', '1')

        pwd_saved_str = keyring.get_password(PROXY_KEYRING_SERVICE, K_PROXY_PASSWORD_SAVED)
        config[K_PROXY_PASSWORD_SAVED] = pwd_saved_str is not None and pwd_saved_str.lower() in ('true', '1')

        logger.debug(f"Proxy settings: Enabled={config[K_PROXY_ENABLED]}")

        config[K_PROXY_IP_URL] = keyring.get_password(PROXY_KEYRING_SERVICE, K_PROXY_IP_URL) or PROXY_URL_DEFAULT
        config[K_PROXY_PORT] = keyring.get_password(PROXY_KEYRING_SERVICE, K_PROXY_PORT) or PROXY_PORT_DEFAULT
        config[K_PROXY_USERNAME] = keyring.get_password(PROXY_KEYRING_SERVICE, K_PROXY_USERNAME)            
        
        if enabled_str and enabled_str.lower() in ('true', '1'):
            logger.info(f"Proxy details loaded: IP={config.get(K_PROXY_IP_URL)}, Port={config.get(K_PROXY_PORT)}, User={config.get(K_PROXY_USERNAME)}")
            
        return config

    except Exception as e:
        logger.error(f"Erro ao buscar configuração de proxy do Keyring: {e}", exc_info=True)
        # Retorna um estado seguro (desabilitado) em caso de erro na leitura
        return config_start

def delete_proxy_settings() -> None:
    """
    Deleta as configurações de proxy (username e password) do Keyring.
    """
    logger.info(f"Deletando configs proxy do Keyring (Service: {PROXY_KEYRING_SERVICE})")
    try:
        keyring.delete_password(PROXY_KEYRING_SERVICE, K_PROXY_USERNAME)
    except keyring.errors.PasswordDeleteError:
        logger.debug("Username não existia para deletar.")
    try:
        keyring.delete_password(PROXY_KEYRING_SERVICE, K_PROXY_PASSWORD)
    except keyring.errors.PasswordDeleteError:
        logger.debug("Senha não existia para deletar.")
    
def save_proxy_settings(config: Dict[str, Any]) -> bool:
    """
    Salva as configurações de proxy no Keyring. Salva/Deleta a senha separadamente.

    Args:
        config (Dict[str, Any]): Dicionário da UI. Espera chaves 'enabled'(bool),
            'ip'(str), 'port'(str), 'username'(Optional[str]), 'password'(Optional[str]).

    Returns:
        bool: True se sucesso, False caso contrário.
    """
    logger.info(f"Salvando config proxy no Keyring (Service: {PROXY_KEYRING_SERVICE})")
    try:
        # Salva enabled, ip, port, username (como antes)
        enabled_str = "true" if config.get(K_PROXY_ENABLED, False) else "false"
        passwd_saved_str = "true" if config.get(K_PROXY_PASSWORD_SAVED, False) else "false"

        keyring.set_password(PROXY_KEYRING_SERVICE, K_PROXY_ENABLED, enabled_str)
        keyring.set_password(PROXY_KEYRING_SERVICE, K_PROXY_PASSWORD_SAVED, passwd_saved_str)

        keyring.set_password(PROXY_KEYRING_SERVICE, K_PROXY_IP_URL, config.get(K_PROXY_IP_URL, PROXY_URL_DEFAULT))
        keyring.set_password(PROXY_KEYRING_SERVICE, K_PROXY_PORT, config.get(K_PROXY_PORT, PROXY_PORT_DEFAULT))

        username = config.get(K_PROXY_USERNAME)
        password_to_save = config.get(K_PROXY_PASSWORD) # Pega a senha vinda da UI, além do resultado do checkbox passwd_saved

        if username:
            logger.info("Salvando username do proxy no Keyring.")
            keyring.set_password(PROXY_KEYRING_SERVICE, K_PROXY_USERNAME, username)
            if password_to_save:
                logger.info("Salvando senha do proxy no Keyring.")
                keyring.set_password(PROXY_KEYRING_SERVICE, K_PROXY_PASSWORD, password_to_save)
        else:
            # Se não há username, remove username e senha
            logger.info("Nenhum username fornecido. Removendo username e senha do Keyring (se existirem).")
            delete_proxy_settings()

        logger.info("Configurações de proxy salvas com sucesso.")
        return True
    except Exception as e:
        logger.error(f"Erro ao salvar configurações de proxy no Keyring: {e}", exc_info=True)
        return False

def set_final_keyring_proxy():
    """
    Define as configurações finais do proxy no Keyring ao sair da aplicação.
    Se o salvamento da senha estiver desabilitado, remove os dados existentes.
    """
    config = get_proxy_settings()
    enabled_passwd_to_save = config.get(K_PROXY_PASSWORD_SAVED)
    if not enabled_passwd_to_save:
        logger.debug("Salvamento de senha desabilitado. Removendo dados existentes no Keyring (se houver)")
        delete_proxy_settings()

atexit.register(set_final_keyring_proxy)

execution_time = perf_counter() - start_time
logger.debug(f"Carregado CONFIG_MANAGER em {execution_time:.4f}s")