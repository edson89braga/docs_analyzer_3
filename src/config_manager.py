# src/utils/config_manager.py

import keyring
import logging
from typing import Dict, Any, Optional

# Importa APP_NAME para consistência (ou definir centralmente no futuro)
from .services.credentials_manager import APP_NAME

# Constantes Keyring Proxy -> rótulos fixos para uso no keyring
PROXY_KEYRING_SERVICE = f"{APP_NAME}_Proxy"
PROXY_ENABLED_USER = "proxy_enabled"
PROXY_PASSWORD_SAVED_USER = "password_saved"
PROXY_IP_USER = "ip_address"
PROXY_PORT_USER = "port"
PROXY_USERNAME_USER = "username"
PROXY_PASSWORD_USER = "password" 

# --- Funções de Gerenciamento de Configuração ---

def get_proxy_settings() -> Optional[Dict[str, Any]]:
    """
    Recupera as configurações de proxy (EXCETO SENHA) salvas no Keyring.

    Returns:
        Optional[Dict[str, Any]]: Dicionário com 'enabled', 'ip', 'port', 'username',
                                  ou {'enabled': False} se não configurado/erro.
    """
    from src.logger.logger import LoggerSetup
    logger = LoggerSetup.get_logger(__name__)

    logger.debug(f"Buscando config proxy (sem senha) do Keyring (Service: {PROXY_KEYRING_SERVICE})")
    config = {'proxy_enabled': False, 'password_saved': False, 'ip': None, 'port': None, 'username': None}
    try:
        enabled_str = keyring.get_password(PROXY_KEYRING_SERVICE, PROXY_ENABLED_USER)
        config['proxy_enabled'] = enabled_str is not None and enabled_str.lower() in ('true', '1')
        pwd_saved_str = keyring.get_password(PROXY_KEYRING_SERVICE, PROXY_PASSWORD_SAVED_USER)
        config['password_saved'] = pwd_saved_str is not None and pwd_saved_str.lower() in ('true', '1')
        logger.info(f"Proxy settings: Enabled={config['proxy_enabled']}")

        if config['proxy_enabled']:
            config['ip'] = keyring.get_password(PROXY_KEYRING_SERVICE, PROXY_IP_USER)
            config['port'] = keyring.get_password(PROXY_KEYRING_SERVICE, PROXY_PORT_USER)
            config['username'] = keyring.get_password(PROXY_KEYRING_SERVICE, PROXY_USERNAME_USER)            
            logger.info(f"Proxy details loaded: IP={config.get('ip')}, Port={config.get('port')}, User={config.get('username')}")
            # Validação básica
            if not config.get('ip') or not config.get('port'):
                logger.warning("Proxy habilitado no Keyring, mas IP ou Porta estão faltando!")
                # Considerar desabilitar ou retornar None aqui? Por ora, retorna o que achou.
        return config

    except Exception as e:
        logger.error(f"Erro ao buscar configuração de proxy do Keyring: {e}", exc_info=True)
        # Retorna um estado seguro (desabilitado) em caso de erro na leitura
        return {'proxy_enabled': False, 'password_saved': False, 'ip': None, 'port': None, 'username': None}

def save_proxy_settings(config: Dict[str, Any]) -> bool:
    """
    Salva as configurações de proxy no Keyring. Salva/Deleta a senha separadamente.

    Args:
        config (Dict[str, Any]): Dicionário da UI. Espera chaves 'enabled'(bool),
            'ip'(str), 'port'(str), 'username'(Optional[str]), 'password'(Optional[str]).

    Returns:
        bool: True se sucesso, False caso contrário.
    """
    from src.logger.logger import LoggerSetup
    logger = LoggerSetup.get_logger(__name__)

    logger.info(f"Salvando config proxy no Keyring (Service: {PROXY_KEYRING_SERVICE})")
    try:
        # Salva enabled, ip, port, username (como antes)
        enabled_str = "true" if config.get('proxy_enabled', False) else "false"
        passwd_saved_str = "true" if config.get('password_saved', False) else "false"
        keyring.set_password(PROXY_KEYRING_SERVICE, PROXY_ENABLED_USER, enabled_str)
        keyring.set_password(PROXY_KEYRING_SERVICE, PROXY_PASSWORD_SAVED_USER, passwd_saved_str)
        keyring.set_password(PROXY_KEYRING_SERVICE, PROXY_IP_USER, config.get('ip', ''))
        keyring.set_password(PROXY_KEYRING_SERVICE, PROXY_PORT_USER, config.get('port', ''))

        username = config.get('username')
        enabled_passwd_to_save = config.get('password_saved') 
        password_to_save = config.get('password') # Pega a senha vinda da UI, além do resultado do checkbox passwd_saved

        if username:
            keyring.set_password(PROXY_KEYRING_SERVICE, PROXY_USERNAME_USER, username)

            if enabled_passwd_to_save and password_to_save:
                logger.debug("Salvando senha do proxy no Keyring.")
                keyring.set_password(PROXY_KEYRING_SERVICE, PROXY_PASSWORD_USER, password_to_save)
            else:
                logger.debug("Nenhuma senha fornecida ou vazia. Removendo senha existente do Keyring (se houver).")
                try: keyring.delete_password(PROXY_KEYRING_SERVICE, PROXY_PASSWORD_USER)
                except keyring.errors.PasswordDeleteError: logger.debug("Senha não existia para deletar.") # Ignora se não existia
        else:
            # Se não há username, remove username e senha
            logger.debug("Nenhum username fornecido. Removendo username e senha do Keyring (se existirem).")
            try: keyring.delete_password(PROXY_KEYRING_SERVICE, PROXY_USERNAME_USER)
            except keyring.errors.PasswordDeleteError: logger.debug("Username não existia para deletar.")
            try: keyring.delete_password(PROXY_KEYRING_SERVICE, PROXY_PASSWORD_USER)
            except keyring.errors.PasswordDeleteError: logger.debug("Senha não existia para deletar.")

        logger.info("Configurações de proxy (com tratamento de senha) salvas com sucesso.")
        return True
    except Exception as e:
        logger.error(f"Erro ao salvar configurações de proxy no Keyring: {e}", exc_info=True)
        return False