# src/utils/fb_credentials_manager.py

import logging
logger = logging.getLogger(__name__)

from time import perf_counter
start_time = perf_counter()
logger.debug(f"{start_time:.4f}s - Iniciando credentials_manager.py")

import keyring, json, os
from cryptography.fernet import Fernet, InvalidToken
from typing import Optional

from src.settings import (APP_NAME, APP_DATA_DIR, KEYRING_SERVICE_FIREBASE, KEYRING_USER_ENCRYPTION_KEY, 
ENCRYPTED_SERVICE_KEY_FILENAME, ENCRYPTED_SERVICE_KEY_PATH)

logger.debug(f"Credentials Manager usando diretório de dados: {APP_DATA_DIR}")
logger.debug(f"Caminho esperado para chave de serviço criptografada: {ENCRYPTED_SERVICE_KEY_PATH}")

# --- Funções Utilitárias de Credenciais ---

def get_encryption_key() -> Optional[bytes]:
    """
    Busca a chave de criptografia Fernet do Keyring do sistema.

    Returns:
        Optional[bytes]: A chave como bytes se encontrada, None caso contrário ou em erro.
    """
    logger.debug(f"Buscando chave Fernet do Keyring (Service: {KEYRING_SERVICE_FIREBASE}, User: {KEYRING_USER_ENCRYPTION_KEY})")
    try:
        key_str = keyring.get_password(KEYRING_SERVICE_FIREBASE, KEYRING_USER_ENCRYPTION_KEY)
        if key_str:
            logger.debug("Chave de criptografia encontrada no Keyring.")
            # Keyring retorna string, Fernet precisa de bytes. Assume UTF-8 ou compatível.
            return key_str.encode('utf-8')
        else:
            logger.warning("Chave de criptografia NÃO encontrada no Keyring.")
            return None
    except Exception as e:
        logger.error(f"Erro ao buscar chave de criptografia do Keyring: {e}", exc_info=True)
        return None

def _save_encryption_key(key: bytes):
    """
    Salva a chave de criptografia Fernet no Keyring do sistema.

    Args:
        key (bytes): A chave Fernet a ser salva.

    Raises:
        Exception: Propaga exceções do Keyring em caso de falha no salvamento.
    """
    logger.info(f"Salvando chave Fernet no Keyring (Service: {KEYRING_SERVICE_FIREBASE}, User: {KEYRING_USER_ENCRYPTION_KEY})")
    try:
        # Keyring armazena strings. Assume UTF-8 ou compatível.
        keyring.set_password(KEYRING_SERVICE_FIREBASE, KEYRING_USER_ENCRYPTION_KEY, key.decode('utf-8'))
        logger.info("Chave de criptografia salva com sucesso no Keyring.")
    except Exception as e:
        logger.error(f"Erro ao salvar chave de criptografia no Keyring: {e}", exc_info=True)
        raise # Propaga o erro para quem chamou lidar (ex: UI mostrando falha)

def _generate_encryption_key() -> bytes:
    """
    Gera uma nova chave de criptografia Fernet.

    Returns:
        bytes: A chave Fernet gerada.
    """
    logger.debug("Gerando nova chave de criptografia Fernet.")
    return Fernet.generate_key()

def _encrypt_data(data: str, fernet_instance: Fernet) -> bytes:
    """
    Criptografa dados (string) usando a instância Fernet fornecida.

    Args:
        data (str): A string a ser criptografada.
        fernet_instance (Fernet): A instância Fernet para criptografia.

    Returns:
        bytes: Os dados criptografados.

    Raises:
        Exception: Se ocorrer um erro durante a criptografia.
    """
    logger.debug("Criptografando dados...")
    try:
        encrypted_data = fernet_instance.encrypt(data.encode('utf-8'))
        logger.debug("Dados criptografados com sucesso.")
        return encrypted_data
    except Exception as e:
        logger.error(f"Erro durante a criptografia: {e}", exc_info=True)
        raise # Propaga

def _decrypt_data(encrypted_data: bytes, fernet_instance: Fernet) -> str:
    """
    Descriptografa dados usando a instância Fernet fornecida.

    Args:
        encrypted_data (bytes): Os dados criptografados.
        fernet_instance (Fernet): A instância Fernet para descriptografia.

    Returns:
        str: A string descriptografada.

    Raises:
        InvalidToken: Se o token for inválido (chave errada ou dados corrompidos).
        Exception: Se ocorrer um erro inesperado durante a descriptografia.
    """
    logger.debug("Descriptografando dados...")
    try:
        decrypted_data = fernet_instance.decrypt(encrypted_data).decode('utf-8')
        logger.debug("Dados descriptografados com sucesso.")
        return decrypted_data
    except InvalidToken:
        logger.error("Erro de descriptografia: Token inválido (chave errada ou dados corrompidos?).")
        raise # Propaga erro específico
    except Exception as e:
        logger.error(f"Erro inesperado durante a descriptografia: {e}", exc_info=True)
        raise # Propaga outros erros

def _save_encrypted_service_key(encrypted_content: bytes):
    """
    Salva o conteúdo criptografado da chave de serviço no arquivo local .enc.

    Args:
        encrypted_content (bytes): Os bytes criptografados a serem salvos.

    Raises:
        IOError: Se ocorrer um erro durante a escrita do arquivo.
        Exception: Para outros erros inesperados.
    """
    path_to_save = ENCRYPTED_SERVICE_KEY_PATH
    logger.info(f"Tentando salvar chave de serviço criptografada ({len(encrypted_content)} bytes) em: {path_to_save}")
    try:
        # Garante que o diretório pai existe (já feito na inicialização do módulo, mas seguro repetir)
        os.makedirs(os.path.dirname(path_to_save), exist_ok=True)
        with open(path_to_save, 'wb') as f:
            bytes_written = f.write(encrypted_content)
        logger.info(f"Arquivo .enc escrito com sucesso! {bytes_written} bytes escritos.")
        # Verificação pós-escrita
        if not os.path.exists(path_to_save):
             logger.error("VERIFICAÇÃO PÓS-ESCRITA FALHOU: Arquivo .enc NÃO existe!")
             raise IOError("Falha ao verificar a existência do arquivo .enc após a escrita.")
        else:
             logger.debug("VERIFICAÇÃO PÓS-ESCRITA OK: Arquivo .enc existe.")
    except IOError as e:
        logger.error(f"Erro de I/O ao salvar arquivo .enc em {path_to_save}: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Erro inesperado ao salvar arquivo .enc em {path_to_save}: {e}", exc_info=True)
        raise

def load_encrypted_service_key() -> Optional[bytes]:
    """
    Carrega o conteúdo criptografado da chave de serviço do arquivo local .enc.

    Returns:
        Optional[bytes]: Os bytes lidos do arquivo, ou None se o arquivo não for encontrado ou ocorrer erro.
    """
    path_to_load = ENCRYPTED_SERVICE_KEY_PATH
    logger.debug(f"Tentando carregar chave de serviço criptografada de: {path_to_load}")
    exists = os.path.exists(path_to_load)
    logger.debug(f"Resultado de os.path.exists({path_to_load}): {exists}")

    if not exists:
        logger.warning("Arquivo .enc NÃO encontrado.")
        return None
    try:
        with open(path_to_load, 'rb') as f:
            content = f.read()
        logger.info(f"Arquivo .enc carregado com sucesso ({len(content)} bytes).")
        return content
    except Exception as e:
        logger.error(f"Erro ao ler arquivo .enc {path_to_load}: {e}", exc_info=True)
        return None

# --- Funções de Orquestração (Interface Pública do Módulo) ---

def are_credentials_set_up() -> bool:
    """
    Verifica se as credenciais básicas (chave no Keyring E arquivo .enc) existem.

    Returns:
        bool: True se ambas as partes das credenciais parecem existir, False caso contrário.
    """
    logger.info("Verificando se as credenciais de serviço estão configuradas...")
    key_exists = get_encryption_key() is not None
    file_exists = os.path.exists(ENCRYPTED_SERVICE_KEY_PATH)
    logger.info(f"Status verificação: Chave Keyring={key_exists}, Arquivo .enc={file_exists}")
    return key_exists and file_exists

def get_decrypted_service_key_json() -> Optional[str]:
    """
    Orquestra a obtenção da chave de serviço Firebase descriptografada.

    1. Busca a chave de criptografia no Keyring.
    2. Carrega o arquivo .enc criptografado.
    3. Descriptografa o conteúdo usando a chave.
    4. Valida se o conteúdo descriptografado é JSON válido.

    Returns:
        Optional[str]: A string JSON da chave de serviço se todo o processo for
                       bem-sucedido, None caso contrário.
    """
    logger.info("Tentando obter a chave de serviço Firebase descriptografada...")
    encryption_key = get_encryption_key()
    if not encryption_key:
        logger.error("Falha ao obter chave de serviço: Chave de criptografia não encontrada no Keyring.")
        return None

    try:
        fernet_instance = Fernet(encryption_key)
        logger.debug("Instância Fernet criada.")
    except Exception as e:
         logger.error(f"Falha ao obter chave de serviço: Erro ao criar instância Fernet: {e}", exc_info=True)
         return None

    encrypted_content = load_encrypted_service_key()
    if not encrypted_content:
        logger.error("Falha ao obter chave de serviço: Arquivo .enc não encontrado ou erro na leitura.")
        return None

    try:
        decrypted_json = _decrypt_data(encrypted_content, fernet_instance)
        # Validação JSON
        json.loads(decrypted_json)
        logger.debug("Chave de serviço descriptografada e validada como JSON com sucesso.")
        return decrypted_json
    except InvalidToken:
         logger.error("Falha ao obter chave de serviço: Descriptografia falhou (token inválido/chave errada).")
         return None
    except json.JSONDecodeError as e:
        logger.error(f"Falha ao obter chave de serviço: Conteúdo descriptografado não é JSON válido: {e}")
        return None
    except Exception as e:
        logger.error(f"Falha ao obter chave de serviço: Erro inesperado na descriptografia/validação: {e}", exc_info=True)
        return None

def setup_credentials_from_file(json_content_str: str) -> bool:
    """
    Executa o processo completo de configuração inicial a partir do conteúdo JSON.

    1. Gera uma nova chave de criptografia Fernet.
    2. Salva a nova chave no Keyring.
    3. Criptografa o conteúdo JSON fornecido usando a nova chave.
    4. Salva o conteúdo criptografado no arquivo .enc.

    Args:
        json_content_str (str): O conteúdo do arquivo JSON original da chave de serviço.

    Returns:
        bool: True se todo o processo de setup for bem-sucedido, False caso contrário.
    """
    logger.info("Iniciando processo de setup de credenciais a partir do conteúdo JSON...")
    try:
        # Valida o JSON de entrada primeiro
        json.loads(json_content_str)
        logger.debug("JSON de entrada validado.")

        # Gera e salva a chave Fernet
        new_key = _generate_encryption_key()
        _save_encryption_key(new_key) # Propaga erro se falhar

        # Cria instância Fernet com a nova chave
        fernet_instance = Fernet(new_key)

        # Criptografa o conteúdo JSON
        encrypted_content = _encrypt_data(json_content_str, fernet_instance) # Propaga erro se falhar

        # Salva o conteúdo criptografado no arquivo .enc
        _save_encrypted_service_key(encrypted_content) # Propaga erro se falhar

        logger.info("Processo de setup de credenciais concluído com sucesso!")
        return True

    except json.JSONDecodeError as e:
         logger.error(f"Falha no setup: Conteúdo fornecido não é JSON válido: {e}")
         return False
    except Exception as e:
        # Captura erros propagados de _save_encryption_key, _encrypt_data, _save_encrypted_service_key
        logger.error(f"Falha durante o processo de setup de credenciais: {e}", exc_info=True)
        # Poderia tentar limpar a chave do keyring aqui se falhou depois de salvá-la?
        # Por enquanto, apenas reporta a falha.
        return False

def encrypt(data_str: str) -> Optional[bytes]:
    """
    Criptografa uma string usando a chave Fernet armazenada no Keyring.

    Args:
        data_str (str): A string a ser criptografada.

    Returns:
        Optional[bytes]: Os dados criptografados como bytes, ou None se a chave
                         de criptografia não for encontrada ou ocorrer um erro.
    """
    logger.debug("Solicitação para criptografar dados...")
    encryption_key = get_encryption_key()
    if not encryption_key:
        logger.error("Falha na criptografia: Chave Fernet não encontrada no Keyring.")
        return None
    try:
        fernet_instance = Fernet(encryption_key)
        encrypted_data = _encrypt_data(data_str, fernet_instance)
        return encrypted_data
    except Exception as e:
        logger.error(f"Falha durante a criptografia pública: {e}", exc_info=True)
        return None

def decrypt(encrypted_bytes: bytes) -> Optional[str]:
    """
    Descriptografa bytes usando a chave Fernet armazenada no Keyring.

    Args:
        encrypted_bytes (bytes): Os dados criptografados.

    Returns:
        Optional[str]: A string descriptografada, ou None se a chave Fernet
                       não for encontrada, a descriptografia falhar (token inválido)
                       ou ocorrer outro erro.
    """
    logger.debug("Solicitação para descriptografar dados...")
    encryption_key = get_encryption_key()
    if not encryption_key:
        logger.error("Falha na descriptografia: Chave Fernet não encontrada no Keyring.")
        return None
    try:
        fernet_instance = Fernet(encryption_key)
        decrypted_str = _decrypt_data(encrypted_bytes, fernet_instance)
        return decrypted_str
    except InvalidToken:
         logger.error("Falha na descriptografia pública: Token inválido (chave errada ou dados corrompidos).")
         return None
    except Exception as e:
        logger.error(f"Falha durante a descriptografia pública: {e}", exc_info=True)
        return None


execution_time = perf_counter() - start_time
logger.debug(f"Carregado CREDENTIALS_MANAGER em {execution_time:.4f}s")
