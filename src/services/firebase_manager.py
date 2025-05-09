import os, json, logging
import firebase_admin
from firebase_admin import credentials, storage, firestore # db, auth as firebase_auth
from threading import Lock

from src.utils import with_proxy
from src.services import credentials_manager
from src.settings import FB_STORAGE_BUCKET

from typing import Optional, Dict, Any, List, Set

@with_proxy()
def inicializar_firebase():
    """
    Inicializa o Firebase Admin SDK usando as credenciais seguras do
    credentials_manager e aplicando configurações de proxy/SSL quando necessário.
    """
    logger = logging.getLogger(__name__)
    if not firebase_admin._apps:  # Verifica se já foi inicializado
        try:
            # 1. Obter o JSON da chave de serviço descriptografado
            decrypted_json_str = credentials_manager.get_decrypted_service_key_json()

            if decrypted_json_str is None:
                # Se get_decrypted_service_key_json retorna None, as credenciais
                # não foram encontradas ou houve um erro ao descriptografar.
                logger.error("Falha ao inicializar Firebase: Credenciais não encontradas ou inválidas.")
                # Você pode querer levantar uma exceção específica aqui
                # raise CredentialsNotFoundError("Credenciais do Firebase não configuradas ou inacessíveis.")
                # Ou apenas retornar/sair, dependendo do fluxo do seu app.
                # Por enquanto, vamos levantar um ValueError genérico.
                raise ValueError("Credenciais do Firebase não configuradas ou inacessíveis via credentials_manager.")

            # 2. Parsear o JSON string para um dicionário Python
            try:
                credentials_dict = json.loads(decrypted_json_str)
                logger.debug("JSON da chave de serviço descriptografado e parseado com sucesso.")
            except json.JSONDecodeError as json_err:
                logger.error(f"Falha ao inicializar Firebase: Erro ao parsear o JSON da chave de serviço: {json_err}", exc_info=True)
                raise ValueError("O conteúdo da chave de serviço descriptografada não é um JSON válido.") from json_err

            # 3. Criar o objeto de credenciais do Firebase
            cred = credentials.Certificate(credentials_dict)
            logger.debug("Objeto de credenciais do Firebase criado.")

            # 4. Inicializar o app Firebase
            firebase_admin.initialize_app(cred, {
                'storageBucket': FB_STORAGE_BUCKET,
                #'databaseURL': FIREBASE_DB_URL,
                # Nota: O proxy/SSL é tratado pelo decorador @with_proxy
                # e variáveis de ambiente, não diretamente aqui na inicialização.
            })
            logger.info("Firebase Admin SDK inicializado com sucesso.")

        except ValueError as ve: # Captura os ValueErrors levantados acima
             logger.error(f"Erro de configuração das credenciais: {ve}")
             raise 
        except Exception as e:
            # Captura outras exceções que podem ocorrer durante initialize_app
            logger.error(f"Erro inesperado ao inicializar o Firebase: {e}", exc_info=True)
            raise # Re-levanta a exceção original
    else:
        logger.debug("Firebase_Admin já inicializado.")

class FbManagerStorage:
    """
    Gerencia operações no Firebase Storage.
    """
    def __init__(self, bucket_name=FB_STORAGE_BUCKET):
        """
        Inicializa a conexão com o Firebase Storage.

        Args:
            credenciais_path (str): Caminho para o arquivo JSON de credenciais do Firebase.
            bucket_name (str): Nome do bucket do Firebase Storage.
        """

        inicializar_firebase()  # Garante que o Firebase esteja inicializado
        self.lock = Lock()
        self.bucket_name = bucket_name            
        self.bucket = storage.bucket()
        from src.logger.logger import LoggerSetup
        self.logger = LoggerSetup.get_logger(__name__)

    def upload_file(self, local_file_path, storage_path):
        """
        Faz upload de um arquivo para o Firebase Storage.

        Args:
            local_file_path (str): Caminho do arquivo local.
            storage_path (str): Caminho no Firebase Storage.
        """
        # storage_path = os.path.basename(storage_path) ?
        with self.lock:
            blob = self.bucket.blob(storage_path)
            blob.upload_from_filename(local_file_path)
            print(f"{os.path.basename(local_file_path)}: Arquivo enviado para: {storage_path}")

    def upload_text(self, text, storage_path):
        """
        Faz upload de um texto para um arquivo no Firebase Storage.

        Args:
            text (str): Conteúdo a ser enviado.
            storage_path (str): Caminho no Firebase Storage.
        """
        with self.lock:
            blob = self.bucket.blob(storage_path)
            blob.upload_from_string(text, 
                                   content_type="text/plain; charset=utf-8", # 
                                   timeout=60)
            self.logger.debug(f"Texto salvo em: {storage_path}")

    def download_file(self, storage_path, local_file_path):
        """
        Faz o download de um arquivo do Firebase Storage.

        Args:
            storage_path (str): Caminho do arquivo no Firebase Storage.
            local_file_path (str): Caminho para salvar o arquivo localmente.
        """
        with self.lock:
            blob = self.bucket.blob(storage_path)
            blob.download_to_filename(local_file_path)
            print(f"{storage_path}: Arquivo baixado para: {os.path.basename(local_file_path)}")

    def get_text(self, storage_path):
        """
        Obtém o conteúdo de um arquivo de texto no Firebase Storage.

        Args:
            storage_path (str): Caminho do arquivo no Firebase Storage.

        Returns:
            str: Conteúdo do arquivo ou None se não existir.
        """
        with self.lock:
            blob = self.bucket.blob(storage_path)
            return blob.download_as_text(encoding='utf-8') if blob.exists() else ""

    def delete_file(self, storage_path):
        """
        Remove um arquivo do Firebase Storage.

        Args:
            storage_path (str): Caminho do arquivo no Firebase Storage.
        """
        with self.lock:
            blob = self.bucket.blob(storage_path)
            if blob.exists():
                blob.delete()
                print(f"Arquivo {storage_path} removido.")
            else:
                print(f"Arquivo {storage_path} não encontrado.")

    def list_files(self,  prefix=None):
        """
        Lista arquivos dentro de um determinado prefixo.

        Args:
            prefix (str, opcional): Prefixo do caminho (ex: "logs/").

        Returns:
            list: Lista de nomes dos arquivos.
        """
        with self.lock:
            blobs = self.bucket.list_blobs(prefix=prefix)
            return [blob.name for blob in blobs]
    

class FbManagerFirestore:
    """
    Gerencia operações no Firebase Firestore.
    """
    _db_client: Optional[Any] = None # Firestore client

    def __init__(self):
        """
        Inicializador do FirebaseManagerFirestore.
        Assume que o Firebase Admin SDK já foi inicializado externamente.
        """
        from src.logger.logger import LoggerSetup
        self.logger = LoggerSetup.get_logger(__name__)
        inicializar_firebase() # Garante que o Firebase esteja inicializado
        if FbManagerFirestore._db_client is None:
            try:
                FbManagerFirestore._db_client = firestore.client()
                self.logger.info("Cliente Firestore obtido com sucesso.")
            except Exception as e:
                self.logger.critical(f"Falha ao obter cliente Firestore. O Admin SDK foi inicializado corretamente? Erro: {e}", exc_info=True)
                # Poderia levantar um erro aqui para impedir a instanciação se o cliente é crucial
        self.db = FbManagerFirestore._db_client


    def save_user_api_key(self, user_id: str, service_name: str, api_key: str) -> bool:
        """
        Salva (ou atualiza) a chave de API de um serviço LLM para um usuário, criptografando-a.
        """
        if not self.db:
            self.logger.error("Firestore não inicializado, impossível salvar chave.")
            return False

        encrypted_key_bytes = credentials_manager.encrypt(api_key) # type: ignore
        if encrypted_key_bytes is None:
            self.logger.error(f"Falha ao criptografar a chave API para {user_id}/{service_name}.")
            return False

        try:
            doc_ref = self.db.collection('user_api_keys').document(user_id)
            doc_ref.set({service_name: encrypted_key_bytes.decode('latin-1')}, merge=True) # Salva/Atualiza
            # Firestore armazena bytes como strings se não for Blob; decode para evitar problemas com certos bytes.
            # Alternativamente, use firestore.Blob(encrypted_key_bytes)
            # doc_ref.set({service_name: firestore.Blob(encrypted_key_bytes)}, merge=True)
            self.logger.info(f"Chave API (criptografada) para {user_id}/{service_name} salva no Firestore.")
            return True
        except Exception as e:
            self.logger.error(f"Erro ao salvar chave no Firestore para {user_id}/{service_name}: {e}", exc_info=True)
            return False

    def get_user_api_key(self, user_id: str, service_name: str) -> Optional[str]:
        """
        Recupera e descriptografa a chave de API de um serviço LLM para um usuário.
        """
        if not self.db:
            self.logger.error("Firestore não inicializado, impossível obter chave.")
            return None

        try:
            doc_ref = self.db.collection('user_api_keys').document(user_id)
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                encrypted_key_stored = data.get(service_name)
                if encrypted_key_stored:
                    # Se foi salvo como string (após .decode('latin-1')), re-encode para bytes
                    encrypted_key_bytes = encrypted_key_stored.encode('latin-1')
                    # Se foi salvo como firestore.Blob, encrypted_key_stored já será bytes
                    # encrypted_key_bytes = encrypted_key_stored # se usou firestore.Blob

                    decrypted_key = credentials_manager.decrypt(encrypted_key_bytes) # type: ignore
                    if decrypted_key:
                        self.logger.info(f"Chave API descriptografada para {user_id}/{service_name}.")
                        return decrypted_key
                    else:
                        self.logger.error(f"Falha ao descriptografar chave API para {user_id}/{service_name}.")
                        return None
                else:
                    self.logger.info(f"Chave API para {service_name} não encontrada no documento de {user_id}.")
                    return None
            else:
                self.logger.info(f"Documento de chaves API não encontrado para user {user_id}.")
                return None
        except Exception as e:
            self.logger.error(f"Erro ao obter chave do Firestore para {user_id}/{service_name}: {e}", exc_info=True)
            return None

    def save_metrics(self, metric_data: Dict[str, Any]) -> bool:
        """
        Salva dados de métricas operacionais no Firestore.
        """
        if not self.db:
            self.logger.error("Firestore não inicializado, impossível salvar métricas.")
            return False
        try:
            self.db.collection('metrics').add(metric_data)
            self.logger.info(f"Métrica salva no Firestore: {metric_data.get('event_type', 'N/A')}")
            return True
        except Exception as e:
            self.logger.error(f"Erro ao salvar métrica no Firestore: {e}", exc_info=True)
            return False

    def get_user_prompts(self, user_id: str) -> Optional[Dict[str, str]]:
        """
        Recupera os prompts customizados salvos por um usuário do Firestore.
        """
        if not self.db:
            self.logger.error("Firestore não inicializado, impossível obter prompts.")
            return None
        try:
            doc_ref = self.db.collection('user_prompts').document(user_id)
            doc = doc_ref.get()
            if doc.exists:
                prompts = doc.to_dict()
                self.logger.info(f"Prompts customizados recuperados para user {user_id}.")
                return prompts # type: ignore
            else:
                self.logger.info(f"Nenhum prompt customizado encontrado para user {user_id}.")
                return None
        except Exception as e:
            self.logger.error(f"Erro ao obter prompts do Firestore para {user_id}: {e}", exc_info=True)
            return None

    def save_user_prompts(self, user_id: str, prompts: Dict[str, str]) -> bool:
        """
        Salva (ou atualiza) os prompts customizados de um usuário no Firestore.
        """
        if not self.db:
            self.logger.error("Firestore não inicializado, impossível salvar prompts.")
            return False
        try:
            doc_ref = self.db.collection('user_prompts').document(user_id)
            doc_ref.set(prompts, merge=True)
            self.logger.info(f"Prompts customizados salvos para user {user_id}.")
            return True
        except Exception as e:
            self.logger.error(f"Erro ao salvar prompts no Firestore para {user_id}: {e}", exc_info=True)
            return False

    def get_user_settings(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Recupera configurações gerais definidas para um usuário do Firestore.
        """
        if not self.db:
            self.logger.error("Firestore não inicializado, impossível obter settings.")
            return None
        try:
            doc_ref = self.db.collection('user_settings').document(user_id)
            doc = doc_ref.get()
            if doc.exists:
                settings_data = doc.to_dict()
                self.logger.info(f"Configurações recuperadas para user {user_id}.")
                return settings_data
            else:
                self.logger.info(f"Nenhuma configuração encontrada para user {user_id}.")
                return None # Ou um dict default
        except Exception as e:
            self.logger.error(f"Erro ao obter settings do Firestore para {user_id}: {e}", exc_info=True)
            return None
        

from rich.prompt import Confirm        
def sync_local_and_storage_files(
    storage_manager: FbManagerStorage,
    local_path: str,
    bucket_prefix: str
):
    """
    Compara arquivos entre um diretório local e um prefixo no Firebase Storage,
    e interativamente oferece opções de sincronização (download/upload).

    Args:
        storage_manager (FirebaseManagerStorage): Instância do gerenciador de storage.
        local_path (str): Caminho do diretório local para comparar.
        bucket_prefix (str): Prefixo no bucket do Firebase Storage para comparar.
                             Ex: "dados/imagens/" (deve terminar com / se for um "diretório").
    """
    logger = logging.getLogger(__name__)
    if not storage_manager or not storage_manager.bucket:
        logger.error("Gerenciador de Storage inválido ou não inicializado.")
        return

    logger.info(f"Iniciando sincronização entre local '{local_path}' e bucket '{storage_manager.bucket_name}/{bucket_prefix}'")

    # Garante que o bucket_prefix termine com '/' se não for vazio, para consistência na listagem
    if bucket_prefix and not bucket_prefix.endswith('/'):
        bucket_prefix += '/'

    # Listar arquivos no bucket
    try:
        with storage_manager.lock: # Usar o lock do manager para consistência
            bucket_blobs = list(storage_manager.bucket.list_blobs(prefix=bucket_prefix))
        # Extrai apenas o nome base do arquivo relativo ao prefixo
        # Ex: se blob.name é 'prefix/sub/file.txt', queremos 'sub/file.txt'
        # Se blob.name é 'prefix/file.txt', queremos 'file.txt'
        basefiles_in_bucket: Set[str] = set()
        for blob in bucket_blobs:
            if blob.name == bucket_prefix and not blob.size: # Ignora o "diretório" em si se for um blob vazio
                continue
            relative_name = blob.name[len(bucket_prefix):]
            if relative_name: # Adicionar apenas se houver um nome após o prefixo
                 basefiles_in_bucket.add(relative_name)

    except Exception as e:
        logger.error(f"Erro ao listar arquivos no bucket com prefixo '{bucket_prefix}': {e}", exc_info=True)
        return

    # Listar arquivos locais (recursivamente para corresponder ao comportamento do bucket)
    files_local_relative: Set[str] = set()
    if os.path.exists(local_path) and os.path.isdir(local_path):
        for root, _, files in os.walk(local_path):
            for file_name in files:
                full_path = os.path.join(root, file_name)
                relative_path = os.path.relpath(full_path, local_path).replace(os.sep, '/')
                files_local_relative.add(relative_path)
    else:
        logger.warning(f"Diretório local '{local_path}' não existe ou não é um diretório.")
        # Continuar mesmo assim para permitir download de tudo do bucket, se desejado.

    files_in_bucket_only = basefiles_in_bucket - files_local_relative
    logger.info(f"Arquivos somente no bucket ({len(files_in_bucket_only)}/{len(basefiles_in_bucket)}): {files_in_bucket_only if files_in_bucket_only else 'Nenhum'}")

    files_in_local_only = files_local_relative - basefiles_in_bucket
    logger.info(f"Arquivos somente local ({len(files_in_local_only)}/{len(files_local_relative)}): {files_in_local_only if files_in_local_only else 'Nenhum'}")

    files_in_sync = files_local_relative & basefiles_in_bucket
    logger.info(f"Arquivos sincronizados (presentes em local e no bucket): {len(files_in_sync)}")

    if files_in_bucket_only:
        print('\n') # Para rich.Confirm
        if Confirm.ask(f"Deseja baixar para '{local_path}' os {len(files_in_bucket_only)} arquivo(s) que constam somente no bucket?", default=True):
            for file_rel_path in files_in_bucket_only:
                storage_full_path = bucket_prefix + file_rel_path
                local_full_path = os.path.join(local_path, file_rel_path.replace('/', os.sep))
                logger.info(f"Baixando '{storage_full_path}' para '{local_full_path}'...")
                storage_manager.download_file(storage_full_path, local_full_path)

    if files_in_local_only:
        print('\n') # Para rich.Confirm
        if Confirm.ask(f"Deseja realizar uploads dos {len(files_in_local_only)} arquivo(s) que constam somente na pasta local '{local_path}'?", default=True):
            for file_rel_path in files_in_local_only:
                local_full_path = os.path.join(local_path, file_rel_path.replace('/', os.sep))
                storage_full_path = bucket_prefix + file_rel_path
                logger.info(f"Fazendo upload de '{local_full_path}' para '{storage_full_path}'...")
                storage_manager.upload_file(local_full_path, storage_full_path)
    
    logger.info("Sincronização concluída.")


# Exemplo de uso da função:

# storage_mgr = FirebaseManagerStorage(bucket_name=FB_STORAGE_BUCKET) # Ou deixe None para bucket padrão
# local_sync_path = 'bd/dfs_rdf_pje' # Seu caminho local
# bucket_sync_prefix = 'dfs_rdf_pje'   # Seu prefixo no bucket
# os.makedirs(local_sync_path, exist_ok=True) # Garante que o diretório local exista para o teste

# sync_local_and_storage_files(storage_mgr, local_sync_path, bucket_sync_prefix)




