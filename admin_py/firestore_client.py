# admin_py/firestore_client.py
import firebase_admin
from google.cloud import firestore

from SOURCE.services.firebase_manager import inicializar_firebase
from SOURCE.logger.logger import LoggerSetup

logger = LoggerSetup.get_logger(__name__)


def novo_cliente_firestore() -> firestore.Client:
    """Cria um cliente Firestore novo, com canal gRPC próprio (não usa o singleton).

    O singleton `FbManagerFirestore._db_client` vive o tempo todo do processo do
    Streamlit e o canal gRPC fixa a rota de rede (proxy ou direta) na primeira
    chamada. Se essa primeira chamada coincide com a janela do `@with_proxy`
    (que apaga HTTP(S)_PROXY de `os.environ`, global ao processo), o canal fica
    "direto" e continua falhando com `503 failed to connect to all addresses`
    mesmo depois de as variáveis serem restauradas. Um cliente novo por operação
    evita que uma colisão pontual envenene todas as sincronizações seguintes.

    Returns:
        Cliente `google.cloud.firestore.Client` autenticado com a credencial do
        Firebase Admin SDK já inicializado.
    """
    inicializar_firebase()
    app = firebase_admin.get_app()
    logger.debug("Criando novo cliente Firestore (canal gRPC independente do singleton).")
    return firestore.Client(project=app.project_id, credentials=app.credential.get_credential())
