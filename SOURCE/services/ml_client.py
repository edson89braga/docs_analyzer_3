# SOURCE/services/ml_client.py
import os
import logging
import requests
import numpy as np
from typing import List

from SOURCE.config.provider import is_local_mode
from SOURCE.settings import ML_ENGINE_API_URL

logger = logging.getLogger(__name__)

def get_embeddings_from_engine(text_list: List[str]) -> np.ndarray:
    """
    Envia uma lista de textos para o serviço de ML e retorna os embeddings.
    Resolve a URL dinamicamente com base no ambiente (local vs server).
    """
    if not text_list:
        return np.array([])

    if is_local_mode():
        # No modo local, o engine roda no localhost gerenciado pelo run.py
        target_url = ML_ENGINE_API_URL
    else:
        # No modo server (Docker), busca pelo nome do container na rede interna
        target_url = os.getenv("ML_ENGINE_URL", "http://ml-engine:8001")

    # Ignora proxy para comunicação interna entre containers ou localhost
    proxies = {"http": None, "https": None}

    try:
        logger.info(f"Requisitando embeddings ao motor de ML ({target_url}) para {len(text_list)} textos...")
        response = requests.post(
            f"{target_url}/embed", 
            json={"text_list": text_list}, 
            timeout=180, 
            proxies=proxies
        )
        response.raise_for_status()
        data = response.json()
        return np.array(data.get("embeddings", []))
    except requests.RequestException as e:
        logger.error(f"Falha ao conectar ao motor de ML em '{target_url}'. Erro: {e}", exc_info=True)
        return np.array([])