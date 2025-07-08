# teste_interativo.py

# from src.logger.logger import test_cloud_logging
# from src.services.firebase_client import *
# from src.services.firebase_manager import *

# from src.utils import *
import logging, os
from time import perf_counter
from src.settings import ASSETS_DIR
from src import app_cache

logger = logging.getLogger(__name__)

def load_to_utils():
    # Antecipando, sob load_progressing_gui, outros imports que serão utilizados em utils.py:
    start_time_l = perf_counter()
    logger.info("[DEBUG] Start func.: load_to_utils")

    import unicodedata
    import pdfplumber, fitz
    from unidecode import unidecode
    from sentence_transformers import SentenceTransformer
    
    try:
        model_name = 'all-MiniLM-L6-v2'
        model_local_path = os.path.join(ASSETS_DIR, 'models', model_name)
        logger.info(f"Pré-carregando modelo SentenceTransformer de: {model_local_path}")
        app_cache.sentence_transformer_model = SentenceTransformer(model_local_path) # device='cpu'
        logger.info("Modelo SentenceTransformer pré-carregado e disponível globalmente.")
    except Exception as e:
        logger.critical(f"FALHA CRÍTICA ao pré-carregar o modelo SentenceTransformer: {e}", exc_info=True)
        # A aplicação pode continuar, mas a funcionalidade de vetorização falhará.
    finally:
        # CRUCIAL: Sinaliza que o processo de carregamento (com sucesso ou falha) terminou.
        app_cache.model_loading_event.set()

    execution_time_l = perf_counter() - start_time_l
    logger.info(f"[DEBUG] Finish func.: load_to_utils em {execution_time_l:.4f}s")

load_to_utils()

from src.core.pdf_processor import *
from src.core.ai_orchestrator import *

# pdf_path = input("Digite o caminho do PDF para composição do prompt_mesclado: ")
# generate_full_prompt_from_pdf(pdf_path)

