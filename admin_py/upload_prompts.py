# admin_py/upload_prompts.py
import os
import sys

# Adiciona o diretório raiz ao path para encontrar 'src'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.services.firebase_manager import FbManagerFirestore, inicializar_firebase
from src.logger.logger import LoggerSetup
from src.settings import PROMPTS_COLLECTION, PROMPTS_DOCUMENT_ID
# A GUI admin deve ter seu próprio arquivo de prompts ou um método para carregá-los.
# Para manter a modularidade, o ideal é que os dados dos prompts sejam passados como argumento.
# No entanto, mantendo a estrutura original, o import de repo_prompts continua.
from admin_py.repo_prompts import ALL_lists, ALL_prompts

logger = LoggerSetup.get_logger(__name__)

def upload_prompt_templates() -> bool:
    """
    Envia os dicionários base ALL_lists e ALL_prompts para o Firestore.
    A aplicação usará esses dicionários para construir os prompts finais em tempo de execução.

    Returns:
        True se o upload foi bem-sucedido, False caso contrário.
    """
    logger.info("Iniciando upload dos COMPONENTES BASE de prompts...")
    try:
        # Garante que o Firebase esteja inicializado
        inicializar_firebase()
        firestore_manager = FbManagerFirestore()
        logger.info("Conexão com o Firebase estabelecida.")
    except Exception as e:
        logger.error(f"Não foi possível inicializar o Firebase Admin SDK: {e}", exc_info=True)
        return False

    # O documento no Firestore terá duas chaves principais: 'ALL_lists' e 'ALL_prompts'
    data_to_upload = {
        "ALL_lists": ALL_lists,
        "ALL_prompts": ALL_prompts
    }

    logger.debug(f"Estrutura de dados para upload preparada. Chaves: {list(data_to_upload.keys())}")

    try:
        doc_ref = firestore_manager.db.collection(PROMPTS_COLLECTION).document(PROMPTS_DOCUMENT_ID)
        doc_ref.set(data_to_upload)
        
        logger.info("=" * 50)
        logger.info("SUCESSO!")
        logger.info(f"Componentes base de prompts enviados para a coleção: '{PROMPTS_COLLECTION}'")
        logger.info(f"ID do Documento: '{PROMPTS_DOCUMENT_ID}'")
        logger.info("=" * 50)
        return True

    except Exception as e:
        logger.error(f"Falha ao enviar componentes de prompts para o Firestore: {e}", exc_info=True)
        return False