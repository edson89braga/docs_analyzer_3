# upload_prompts.py

from src.services.firebase_manager import FbManagerFirestore
from OLD_prompts import ALL_lists, ALL_prompts
from src.logger.logger import LoggerSetup
from src.settings import PROMPTS_COLLECTION, PROMPTS_DOCUMENT_ID

def main():
    """
    Envia os dicionários base ALL_lists e ALL_prompts para o Firestore.
    A aplicação usará esses dicionários para construir os prompts finais em tempo de execução.
    """
    logger = LoggerSetup.get_logger(__name__)
    logger.info("Iniciando o script de upload dos COMPONENTES BASE de prompts...")

    try:
        firestore_manager = FbManagerFirestore()
        logger.info("Conexão com o Firebase estabelecida.")
    except Exception as e:
        logger.error(f"Não foi possível inicializar o Firebase Admin SDK: {e}")
        return

    # O documento no Firestore terá duas chaves principais: 'ALL_lists' e 'ALL_prompts'
    # Cada uma conterá o respectivo dicionário.
    data_to_upload = {
        "ALL_lists": ALL_lists,
        "ALL_prompts": ALL_prompts
    }

    logger.info("Estrutura de dados para upload preparada.")
    logger.debug(f"Chaves principais: {list(data_to_upload.keys())}")

    try:
        doc_ref = firestore_manager.db.collection(PROMPTS_COLLECTION).document(PROMPTS_DOCUMENT_ID)
        doc_ref.set(data_to_upload)
        
        logger.info("=" * 50)
        logger.info("SUCESSO!")
        logger.info(f"Componentes base de prompts enviados para a coleção: '{PROMPTS_COLLECTION}'")
        logger.info(f"ID do Documento: '{PROMPTS_DOCUMENT_ID}'")
        logger.info("=" * 50)

    except Exception as e:
        logger.error(f"Falha ao enviar componentes de prompts para o Firestore: {e}", exc_info=True)

if __name__ == "__main__":
    main()

