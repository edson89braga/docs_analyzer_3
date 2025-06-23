# upload_prompts.py

from src.services.firebase_manager import FbManagerFirestore
import src.core.prompts as local_prompts
from src.logger.logger import LoggerSetup

# --- Constantes (ajuste se necessário) ---
PROMPTS_COLLECTION = "prompt_templates"
PROMPTS_DOCUMENT_ID = "initial_analysis_v1"
# -----------------------------------------

def main():
    """
    Lê os prompts declarados na lista __all__ de src/core/prompts.py
    e os envia para um documento específico no Firestore.
    """
    logger = LoggerSetup.get_logger(__name__)
    logger.info("Iniciando o script de upload de prompts para o Firestore...")

    try:
        firestore_manager = FbManagerFirestore()
        logger.info("Conexão com o Firebase estabelecida.")
    except Exception as e:
        logger.error(f"Não foi possível inicializar o Firebase Admin SDK: {e}")
        logger.error("Verifique se suas credenciais de serviço (credentials_manager) estão configuradas corretamente.")
        return

    if not hasattr(local_prompts, '__all__'):
        logger.error("Erro: A lista '__all__' não está definida em 'src/core/prompts.py'.")
        logger.error("Por favor, adicione a lista __all__ contendo os nomes das variáveis de prompt a serem enviadas.")
        return

    prompts_to_upload = {
        key: getattr(local_prompts, key)
        for key in local_prompts.__all__
        if hasattr(local_prompts, key)
    }

    if not prompts_to_upload:
        logger.error("Nenhum prompt encontrado para upload com base na lista __all__.")
        return

    logger.info(f"Encontrados {len(prompts_to_upload)} objetos de prompt para upload com base na lista __all__.")
    logger.debug(f"Chaves a serem enviadas: {list(prompts_to_upload.keys())}")

    try:
        doc_ref = firestore_manager.db.collection(PROMPTS_COLLECTION).document(PROMPTS_DOCUMENT_ID)
        doc_ref.set(prompts_to_upload)
        
        logger.info("=" * 50)
        logger.info("SUCESSO!")
        logger.info(f"Prompts enviados para a coleção: '{PROMPTS_COLLECTION}'")
        logger.info(f"ID do Documento: '{PROMPTS_DOCUMENT_ID}'")
        logger.info("=" * 50)

    except Exception as e:
        logger.error(f"Falha ao enviar prompts para o Firestore: {e}", exc_info=True)

if __name__ == "__main__":
    main()

