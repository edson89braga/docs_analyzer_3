import os, json
from rich.prompt import Confirm

import firebase_admin
from firebase_admin import credentials, storage # db, 
from threading import Lock

from src.utils import with_proxy
from src.services import credentials_manager
from src.settings import FB_STORAGE_BUCKET

from src.logger.logger import LoggerSetup
logger = LoggerSetup.get_logger(__name__)

@with_proxy()
def inicializar_firebase():
    """
    Inicializa o Firebase Admin SDK usando as credenciais seguras do
    credentials_manager e aplicando configurações de proxy/SSL quando necessário.
    """
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

class FirebaseManagerStorage:
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
            logger.debug(f"Texto salvo em: {storage_path}")

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
    
    def check_files_by_pathlocal(self, path_local, prefix_bucket):
        with self.lock:
            blobs = list(self.bucket.list_blobs(prefix=prefix_bucket))
            basefiles_in_bucket = {os.path.basename(blob.name) for blob in blobs}
        
        files_local = set(os.listdir(path_local))
        
        files_in_bucket_only = basefiles_in_bucket - files_local
        logger.info(f'Arquivos somente no bucket: {len(files_in_bucket_only)}/{len(basefiles_in_bucket)}')
        
        files_in_local_only = files_local - basefiles_in_bucket
        logger.info(f'Arquivos somente local: {len(files_in_local_only)}/{len(files_local)}')
        
        files_in_sync = files_local & basefiles_in_bucket
        logger.info(f'Arquivos sincronizados (presentes em local e no bucket): {len(files_in_sync)}')
        print('\n')
        ret1 = Confirm.ask("Deseja baixar na pasta local os arquivos que constam somente no bucket?", default=True)
        if ret1:
            for file_path in files_in_bucket_only:
                self.download_file(f"{prefix_bucket}/{file_path}", os.path.join(path_local, file_path))
        print('\n')
        ret2 = Confirm.ask("Deseja realizar uploads dos os arquivos que constam somente na pasta local?", default=True)
        if ret2:
            for file_path in files_in_local_only:
                self.upload_file(os.path.join(path_local, file_path), f"{prefix_bucket}/{file_path}")
        
        '''
        self = FirebaseManagerStorage()
        path_local = 'bd\\dfs_rdf_pje'
        prefix_bucket = 'dfs_rdf_pje'
        self.check_files_by_pathlocal(path_local, prefix_bucket)
        '''
    
'''
Exemplo de uso do método .check_files_by_pathlocal():

fb_manager = FirebaseManagerStorage()
path_local = 'bd\\dfs_rdf_pje'
prefix_bucket = 'dfs_rdf_pje'

fb_manager.check_files_by_pathlocal(path_local, prefix_bucket)

'''


'''
# FirebaseManagerStorage está sendo usado para salvar logs de execução (txt), e arquivos-resultados (pck) de execuções encerradas (RPAFlowController._save_dados_bd).

O uso de Lock garante que, caso os métodos de FirebaseManagerStorage sejam chamados simultaneamente por diferentes threads em outro ponto do código, 
apenas uma thread execute as operações no Firebase Storage por vez. Isso previne condições de corrida e possíveis inconsistências.

# FirebaseManager_rtdb está sendo usado para substituir dicionários_json que salvam pesquisas realizadas (dict_areas_assunto e dict_procs_conferidos).

O Firebase Realtime Database já implementa mecanismos internos para garantir a consistência dos dados em operações concorrentes, 
especialmente com transações (transaction) e listeners em tempo real.

No entanto, se essa aplicação utilizasse múltiplas threads para chamadas simultâneas a métodos de FirebaseManager_rtdb, 
poderia ser útil adicionar um Lock para evitar acessos concorrentes locais.
'''
