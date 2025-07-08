# admin_py/admin_llm_providers.py
import logging
import json
import os
import sys
from typing import List, Dict, Any, Optional

# Adiciona o diretório raiz ao path para encontrar o pacote 'src'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.services.firebase_manager import FbManagerFirestore

logger = logging.getLogger(__name__)

# --- Constantes ---
PROVIDERS_COLLECTION_ADMIN = "llm_providers_config"
DEFAULT_PROVIDERS_DOC_ID_ADMIN = "default_list"
PROVIDERS_FIELD_NAME_IN_DOC = "all_providers"

# --- Funções de Lógica ---

def read_providers_from_firestore(fs_manager: FbManagerFirestore) -> List[Dict[str, Any]]:
    """
    Lê a lista de provedores do Firestore a partir de uma instância do FbManagerFirestore.

    Args:
        fs_manager: Instância do FbManagerFirestore já inicializada.

    Returns:
        Uma lista de dicionários, cada um representando um provedor LLM.
        Retorna uma lista vazia em caso de erro ou se nenhum provedor for encontrado.
    """
    if not fs_manager or not fs_manager.db:
        logger.error("read_providers_from_firestore: Cliente Firestore não disponível.")
        return []
    try:
        doc_ref = fs_manager.db.collection(PROVIDERS_COLLECTION_ADMIN).document(DEFAULT_PROVIDERS_DOC_ID_ADMIN)
        doc_snapshot = doc_ref.get()

        if doc_snapshot.exists:
            doc_data = doc_snapshot.to_dict()
            if doc_data and PROVIDERS_FIELD_NAME_IN_DOC in doc_data:
                providers_list = doc_data[PROVIDERS_FIELD_NAME_IN_DOC]
                if isinstance(providers_list, list):
                    logger.info("Lista de provedores lida do Firestore com sucesso.")
                    return providers_list
            logger.warning(f"Documento '{DEFAULT_PROVIDERS_DOC_ID_ADMIN}' existe, mas o campo '{PROVIDERS_FIELD_NAME_IN_DOC}' está ausente ou não é uma lista.")
            return []
        else:
            logger.warning(f"Documento de configuração de provedores '{DEFAULT_PROVIDERS_DOC_ID_ADMIN}' não encontrado no Firestore.")
            return []
    except Exception as e:
        logger.error(f"Erro ao ler provedores do Firestore: {e}", exc_info=True)
        return []

def write_providers_to_firestore(fs_manager: FbManagerFirestore, providers_list: List[Dict[str, Any]]) -> bool:
    """
    Escreve (sobrescreve) a lista completa de provedores no Firestore.

    Args:
        fs_manager: Instância do FbManagerFirestore já inicializada.
        providers_list: A lista completa de dicionários de provedores a ser salva.

    Returns:
        True se a operação for bem-sucedida, False caso contrário.
    """
    if not fs_manager or not fs_manager.db:
        logger.error("write_providers_to_firestore: Cliente Firestore não disponível.")
        return False
    try:
        data_to_set = {PROVIDERS_FIELD_NAME_IN_DOC: providers_list}
        doc_ref = fs_manager.db.collection(PROVIDERS_COLLECTION_ADMIN).document(DEFAULT_PROVIDERS_DOC_ID_ADMIN)
        doc_ref.set(data_to_set)
        logger.info(f"Lista de provedores escrita com sucesso no Firestore em '{PROVIDERS_COLLECTION_ADMIN}/{DEFAULT_PROVIDERS_DOC_ID_ADMIN}'.")
        return True
    except Exception as e:
        logger.error(f"Erro ao escrever provedores no Firestore: {e}", exc_info=True)
        return False

def load_providers_from_file(filepath: str) -> Optional[List[Dict[str, Any]]]:
    """
    Carrega a lista de provedores de um arquivo JSON local.

    Args:
        filepath: O caminho para o arquivo JSON.

    Returns:
        Uma lista de dicionários de provedores se o arquivo for válido, ou None em caso de erro.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list) and all(isinstance(item, dict) for item in data):
            return data
        else:
            logger.error("O arquivo JSON deve conter uma lista de dicionários de provedores.")
            return None
    except FileNotFoundError:
        logger.error(f"Arquivo de provedores não encontrado: {filepath}")
        return None
    except json.JSONDecodeError:
        logger.error(f"Arquivo de provedores não é um JSON válido: {filepath}")
        return None
    except Exception as e:
        logger.error(f"Erro ao carregar arquivo de provedores: {e}", exc_info=True)
        return None