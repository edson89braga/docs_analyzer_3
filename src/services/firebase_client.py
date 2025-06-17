# src/services/firebase_client.py

from time import perf_counter
start_time = perf_counter()
print(f"{start_time:.4f}s - Iniciando firebase_client.py")

import requests, json, re, secrets, logging, time
import urllib.parse
from datetime import datetime
from typing import Optional, Dict, Any, List, Union, Callable
import base64 # Para codificar/decodificar bytes para Firestore bytesValue

from src.settings import APP_VERSION, PROJECT_ID, FB_STORAGE_BUCKET, FIREBASE_WEB_API_KEY
from src.utils import with_proxy

from flet import Page as ft_Page

# --- Constantes para APIs REST ---
FIRESTORE_BASE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"
STORAGE_BASE_URL = f"https://firebasestorage.googleapis.com/v0/b/{FB_STORAGE_BUCKET}/o"

# --- Funções Auxiliares para Conversão de Tipos do Firestore ---

def _to_firestore_value(value: Any) -> Dict[str, Any]:
    """Converte um valor Python para o formato de valor do Firestore REST API."""
    current_logger = logging.getLogger(__name__)
    if isinstance(value, str):
        return {"stringValue": value}
    elif isinstance(value, bool):
        return {"booleanValue": value}
    elif isinstance(value, int):
        return {"integerValue": str(value)} # Firestore API espera string para inteiros
    elif isinstance(value, float):
        return {"doubleValue": value}
    elif isinstance(value, bytes):
        return {"bytesValue": base64.b64encode(value).decode('utf-8')}
    elif isinstance(value, list):
        return {"arrayValue": {"values": [_to_firestore_value(v) for v in value]}}
    elif isinstance(value, dict):
        return {"mapValue": {"fields": {k: _to_firestore_value(v) for k, v in value.items()}}}
    elif value is None:
        return {"nullValue": None}
    else:
        current_logger.warning(f"Tipo não suportado para conversão Firestore: {type(value)}. Convertendo para string.")
        return {"stringValue": str(value)}

def _from_firestore_value(fs_value: Dict[str, Any]) -> Any:
    """Converte um valor do Firestore REST API para o formato Python."""
    current_logger = logging.getLogger(__name__)
    if "stringValue" in fs_value:
        return fs_value["stringValue"]
    elif "booleanValue" in fs_value:
        return fs_value["booleanValue"]
    elif "integerValue" in fs_value:
        return int(fs_value["integerValue"])
    elif "doubleValue" in fs_value:
        return fs_value["doubleValue"]
    elif "bytesValue" in fs_value:
        return base64.b64decode(fs_value["bytesValue"])
    elif "arrayValue" in fs_value:
        values = fs_value["arrayValue"].get("values", [])
        return [_from_firestore_value(v) for v in values]
    elif "mapValue" in fs_value:
        fields = fs_value["mapValue"].get("fields", {})
        return {k: _from_firestore_value(v) for k, v in fields.items()}
    elif "nullValue" in fs_value:
        return None
    # Outros tipos como timestampValue, geoPointValue podem ser adicionados se necessário
    current_logger.warning(f"Tipo de valor Firestore não reconhecido para conversão: {list(fs_value.keys())}")
    return None


class FirebaseClientStorage:
    """
    Gerencia operações no Firebase Storage utilizando a API REST e token de ID do usuário.
    """

    def __init__(self):
        """
        Inicializa o cliente de Storage.
        """
        from src.logger.logger import LoggerSetup
        self.logger = LoggerSetup.get_logger(__name__)

        # Nenhuma inicialização complexa necessária aqui, pois usaremos requests.
        self.logger.info(f"FirebaseClientStorage inicializado. Target Bucket: {FB_STORAGE_BUCKET}")

    @with_proxy() # Aplica proxy e tratamento SSL se configurado
    def _make_storage_request(
        self,
        method: str,
        user_token: str,
        object_path: str, # Caminho completo do objeto no bucket
        params: Optional[Dict[str, str]] = None,
        data: Optional[Union[str, bytes]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        content_type: Optional[str] = None,
        timeout: int = 30
    ) -> requests.Response:
        """
        Método auxiliar para fazer requisições à API REST do Firebase Storage.
        """
        headers = {
            "Authorization": f"Bearer {user_token}"
        }
        if content_type:
            headers["Content-Type"] = content_type

        # O caminho do objeto já deve estar URL-encoded se necessário antes de chamar esta função.
        # No entanto, a API do Storage espera que o nome do objeto (object_path) seja parte da URL,
        # e ele deve ser URL encoded.
        encoded_object_path = urllib.parse.quote(object_path, safe='')
        url = f"{STORAGE_BASE_URL}/{encoded_object_path}"

        self.logger.debug(f"Storage Request: {method} {url} | Params: {params} | Content-Type: {content_type}")

        try:
            response = requests.request(
                method,
                url,
                headers=headers,
                params=params, # Para query parameters (ex: ?alt=media para download)
                data=data,     # Para corpo da requisição (upload de bytes/string)
                json=json_data, # Para corpo da requisição JSON (metadados)
                timeout=timeout
            )
            if not (method.upper() == "GET" and response.status_code == 404):
                response.raise_for_status() # Levanta HTTPError para respostas 4xx/5xx
            return response
        except requests.exceptions.HTTPError as http_err:
            status_code = http_err.response.status_code
            try:
                error_details = http_err.response.json()
                error_message = error_details.get("error", {}).get("message", "Erro desconhecido do Storage")
                self.logger.error(f"Erro HTTP {status_code} do Storage para {object_path}: {error_message} | Detalhes: {error_details}")
                error_details_msg = f"Detalhes: {error_details}"
            except json.JSONDecodeError:
                self.logger.error(f"Erro HTTP {status_code} do Storage para {object_path}. Resposta não JSON: {http_err.response.text}")
                error_details_msg = f"Resposta não JSON: {error_message}"

            if status_code == 403:
                self.logger.error(
                    f"Erro de Permissão (403) do Storage para {method} {object_path}: {error_message}. "
                    f"Verifique as Regras de Segurança do Firebase Storage e o status do token do usuário. {error_details_msg}"
                )
            else:
                self.logger.error(f"Erro HTTP {status_code} do Storage para {method} {object_path}: {error_message}. {error_details_msg}")
            raise
        except requests.exceptions.RequestException as req_err:
            self.logger.error(f"Erro de requisição para Storage em {object_path}: {req_err}", exc_info=True)
            raise
        except Exception as e:
            self.logger.error(f"Erro inesperado em _make_storage_request para {object_path}: {e}", exc_info=True)
            raise

    def upload_text_user(self, user_token: str, user_id: str, text_content: str, storage_path_suffix: str) -> bool:
        """
        Faz upload de um conteúdo de texto para o Firebase Storage no caminho do usuário.

        Args:
            user_token (str): Token de ID do Firebase do usuário.
            user_id (str): ID único do usuário (para construir o caminho).
            text_content (str): Conteúdo de texto a ser enviado.
            storage_path_suffix (str): Caminho relativo dentro do diretório do usuário
                                       (ex: "logs/session1/app.log").

        Returns:
            bool: True se o upload for bem-sucedido, False caso contrário.
        """
        if not all([user_token, user_id, storage_path_suffix]):
            self.logger.error("upload_text_user: Argumentos inválidos (token, user_id ou path suffix faltando).")
            return False

        # Constrói o caminho completo no bucket, isolando por usuário
        full_storage_path = f"users/{user_id}/{storage_path_suffix.lstrip('/')}"
        self.logger.debug(f"Tentando upload de texto para Storage: {full_storage_path}")

        try:
            self._make_storage_request(
                method="POST", # Upload simples de bytes/string usa POST
                user_token=user_token,
                object_path=full_storage_path,
                data=text_content.encode('utf-8'),
                content_type="text/plain; charset=utf-8",
                params={"uploadType": "media", "name": full_storage_path} # 'name' aqui é o caminho completo
            )
            self.logger.debug(f"Texto enviado com sucesso para Storage: {full_storage_path}")
            return True
        except Exception as e:
            self.logger.error(f"Falha no upload de texto para Storage ({full_storage_path}): {e}")
            return False

    def get_text_user(self, user_token: str, user_id: str, storage_path_suffix: str) -> Optional[str]:
        """
        Obtém o conteúdo de um arquivo de texto do Firebase Storage do caminho do usuário.

        Args:
            user_token (str): Token de ID do Firebase do usuário.
            user_id (str): ID único do usuário.
            storage_path_suffix (str): Caminho relativo dentro do diretório do usuário.

        Returns:
            Optional[str]: Conteúdo do arquivo ou None se não existir ou erro.
        """
        if not all([user_token, user_id, storage_path_suffix]):
            self.logger.error("get_text_user: Argumentos inválidos.")
            return None

        full_storage_path = f"users/{user_id}/{storage_path_suffix.lstrip('/')}"
        self.logger.info(f"Tentando obter texto do Storage: {full_storage_path}")

        try:
            response = self._make_storage_request(
                method="GET",
                user_token=user_token,
                object_path=full_storage_path,
                params={"alt": "media"} # Para obter o conteúdo do arquivo
            )
            content = response.text # requests decodifica automaticamente com base no charset (ou utf-8)
            self.logger.debug(f"Texto obtido com sucesso do Storage: {full_storage_path}")
            return content
        except requests.exceptions.HTTPError as http_err:
            if http_err.response.status_code == 404:
                self.logger.warning(f"Arquivo não encontrado no Storage: {full_storage_path}")
                return ""
            self.logger.error(f"Erro HTTP ao obter texto do Storage ({full_storage_path}): {http_err}")
            return None
        except Exception as e:
            self.logger.error(f"Falha ao obter texto do Storage ({full_storage_path}): {e}")
            return None

    # Outros métodos como delete_file_user, list_files_user podem ser adicionados aqui seguindo o mesmo padrão.


class FirebaseClientFirestore:
    """
    Gerencia operações no Firebase Firestore utilizando a API REST e token de ID do usuário.
    """

    def __init__(self):
        """
        Inicializa o cliente de Firestore.
        """
        from src.logger.logger import LoggerSetup
        self.logger = LoggerSetup.get_logger(__name__)

        self.logger.info(f"FirebaseClientFirestore inicializado. Target Project: {PROJECT_ID}")

    @with_proxy()
    def _make_firestore_request(
        self,
        method: str,
        user_token: str,
        document_path: str, # Ex: "collectionName/documentId" ou "collectionName" para list/create
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: int = 30
    ) -> requests.Response:
        """
        Método auxiliar para fazer requisições à API REST do Firestore.
        """
        headers = {
            "Authorization": f"Bearer {user_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        url = f"{FIRESTORE_BASE_URL}/{document_path}"

        self.logger.debug(f"Firestore Request: {method} {url} | Params: {params} | JSON: {json_data is not None}")

        try:
            response = requests.request(
                method,
                url,
                headers=headers,
                json=json_data,
                params=params,
                timeout=timeout
            )
            if not (method.upper() == "GET" and response.status_code == 404):
                response.raise_for_status() # Levanta HTTPError para outros erros 4xx/5xx ou para 404 em não-GET
            return response
        except requests.exceptions.HTTPError as http_err:
            status_code = http_err.response.status_code
            try:
                error_details = http_err.response.json()
                error_message = error_details.get("error", {}).get("message", "Erro desconhecido do Firestore")
                self.logger.error(f"Erro HTTP {status_code} do Firestore para {document_path}: {error_message} | Detalhes: {error_details}")
                error_details_msg = f"Detalhes: {error_details}"
            except json.JSONDecodeError:
                self.logger.error(f"Erro HTTP {status_code} do Firestore para {document_path}. Resposta não JSON: {http_err.response.text}")
                error_details_msg = f"Resposta não JSON: {error_message}"
                        
            if status_code == 403:
                self.logger.error(
                    f"Erro de Permissão (403) do Firestore para {method} {document_path}: {error_message}. "
                    f"Verifique as Regras de Segurança do Firestore e o status do token do usuário. {error_details_msg}"
                )
            else:
                self.logger.error(f"Erro HTTP {status_code} do Firestore para {method} {document_path}: {error_message}. {error_details_msg}")
            raise
        except requests.exceptions.RequestException as req_err:
            self.logger.error(f"Erro de requisição para Firestore em {document_path}: {req_err}", exc_info=True)
            raise
        except Exception as e:
            self.logger.error(f"Erro inesperado em _make_firestore_request para {document_path}: {e}", exc_info=True)
            raise

    def save_user_api_key_client(self, user_token: str, user_id: str, service_name: str, encrypted_api_key_bytes: bytes) -> bool:
        """
        Salva (ou atualiza) a chave de API de um serviço LLM (criptografada) para um usuário.

        Args:
            user_token (str): Token de ID do Firebase.
            user_id (str): ID do usuário.
            service_name (str): Nome do serviço (ex: "openai_pessoal").
            encrypted_api_key_bytes (bytes): A chave API já criptografada.

        Returns:
            bool: True se sucesso, False caso contrário.
        """
        if not all([user_token, user_id, service_name, encrypted_api_key_bytes]):
            self.logger.error("save_user_api_key_client: Argumentos inválidos.")
            return False

        document_path = f"user_api_keys/{user_id}"
        # Para atualizar campos específicos sem sobrescrever o documento inteiro (merge=true),
        # a API REST usa PATCH com updateMask.
        # Payload para PATCH:
        # {
        #   "fields": {
        #     "service_name_dynamic": { "bytesValue": "..." }
        #   }
        # }
        # E params: {"updateMask.fieldPaths": [service_name]}

        firestore_payload = {
            "fields": {
                service_name: _to_firestore_value(encrypted_api_key_bytes)
            }
        }
        # O updateMask garante que apenas este campo seja atualizado (merge)
        query_params = {"updateMask.fieldPaths": [service_name]}

        self.logger.info(f"Tentando salvar chave API (cliente) para Firestore: {document_path}/{service_name}")
        try:
            # Usamos PATCH para criar/atualizar de forma idempotente com merge.
            # Se o documento não existir, o PATCH pode criá-lo dependendo das regras
            # ou podemos precisar de uma lógica de "verificar e criar/atualizar".
            # A forma mais simples é tentar um GET e depois POST ou PATCH.
            # No entanto, um PATCH com updateMask em um campo de um documento que não existe
            # geralmente resulta em erro.
            #
            # Para uma lógica de "set com merge", o SDK Admin faria isso.
            # Com REST, para fazer um "set com merge" é mais fácil usar POST na coleção
            # e deixar o Firestore gerar o ID se for um novo doc, ou PATCH no doc específico.
            #
            # Se `user_api_keys/{user_id}` é o documento, e `service_name` é um campo nele:
            # A API REST para "set com merge=true" em um documento específico é feita com PATCH
            # no path do documento `collection/docId`, e os campos a serem merged no payload.
            # O `updateMask` é essencial para o comportamento de merge. Se omitido,
            # o PATCH pode sobrescrever o documento apenas com os campos fornecidos.

            self._make_firestore_request(
                method="PATCH",
                user_token=user_token,
                document_path=document_path,
                json_data=firestore_payload,
                params=query_params
            )
            self.logger.info(f"Chave API (cliente) salva com sucesso para Firestore: {document_path}/{service_name}")
            return True
        except requests.exceptions.HTTPError as http_err:
            # Se o documento não existe (404) e tentamos PATCH, pode falhar.
            # Precisamos criar o documento primeiro se for o caso.
            if http_err.response.status_code == 404:
                self.logger.info(f"Documento {document_path} não encontrado, tentando criar com a chave...")
                try:
                    # Cria o documento com o campo inicial
                    self._make_firestore_request(
                        method="POST", # Cria um novo documento se o ID não for especificado no path
                                       # Ou usa PATCH no path do documento se o ID é user_id
                        user_token=user_token,
                        # Para criar com ID específico (user_id), usamos PATCH sem updateMask (ou POST e especificamos o ID)
                        # É mais simples usar PATCH no path completo do documento: `user_api_keys/{user_id}`
                        # e o payload contém os campos. Se o doc não existe, ele cria.
                        # Para o método POST, o path seria `user_api_keys?documentId={user_id}`
                        document_path=f"user_api_keys?documentId={user_id}",
                        json_data=firestore_payload
                        # Nota: Esta criação não faz "merge". Ela define o documento com esses campos.
                        # Se o objetivo é "set com merge", e o doc pode não existir,
                        # é mais seguro ler primeiro, depois construir o payload completo e usar PATCH.
                        # Por simplicidade, este POST criará/sobrescreverá.
                        # Para um verdadeiro "set com merge", a lógica seria:
                        # 1. GET doc
                        # 2. Se existe, merge localmente, PATCH com updateMask
                        # 3. Se não existe, POST para criar com os campos.
                        # Ou, mais simples para REST:
                        # Sempre use PATCH em `user_api_keys/{user_id}`.
                        # Se o doc não existe, ele será criado com os campos do payload.
                        # Se existe, os campos especificados em updateMask são atualizados.
                        # Se updateMask for omitido, todo o doc é substituído pelos campos do payload.
                        # -> Vamos usar PATCH em `user_api_keys/{user_id}` e incluir o `service_name` no `updateMask`.
                        # Isso DEVE funcionar para criar ou atualizar, contanto que as permissões estejam corretas.
                    )
                    self.logger.info(f"Documento {document_path} criado com a chave API (cliente).")
                    return True
                except Exception as create_err:
                    self.logger.error(f"Falha ao criar documento {document_path} com chave API (cliente): {create_err}")
                    return False
            return False # Falha por outra razão HTTP
        except Exception as e:
            self.logger.error(f"Falha ao salvar chave API (cliente) para Firestore ({document_path}): {e}")
            return False

    def get_user_api_key_client(self, user_token: str, user_id: str, service_name: str) -> Optional[bytes]:
        """
        Recupera e descriptografa a chave de API de um serviço LLM para um usuário.

        Args:
            user_token (str): Token de ID do Firebase.
            user_id (str): ID do usuário.
            service_name (str): Nome do serviço.

        Returns:
            Optional[bytes]: A chave API criptografada como bytes, ou None se não encontrada/erro.
                             A descriptografia é responsabilidade do chamador.
        """
        if not all([user_token, user_id, service_name]):
            self.logger.error("get_user_api_key_client: Argumentos inválidos.")
            return None

        document_path = f"user_api_keys/{user_id}"
        self.logger.info(f"Tentando obter chave API (cliente) do Firestore: {document_path}/{service_name}")

        try:
            response = self._make_firestore_request(
                method="GET",
                user_token=user_token,
                document_path=document_path
            )
            data = response.json()
            fields = data.get("fields", {})
            
            if service_name in fields:
                encrypted_key_fs_value = fields[service_name]
                encrypted_key_bytes = _from_firestore_value(encrypted_key_fs_value) # Deve ser bytes
                if isinstance(encrypted_key_bytes, bytes):
                    self.logger.info(f"Chave API (cliente, criptografada) obtida do Firestore para {service_name}.")
                    return encrypted_key_bytes
                else:
                    self.logger.error(f"Valor recuperado para {service_name} não é bytes após conversão.")
                    return None
            else:
                self.logger.warning(f"Chave API para {service_name} não encontrada no documento de {user_id}.")
                return None
        except requests.exceptions.HTTPError as http_err:
            if http_err.response.status_code == 404:
                self.logger.warning(f"Documento de chaves API não encontrado para user {user_id} no Firestore.")
            else:
                self.logger.error(f"Erro HTTP ao obter chave API (cliente) do Firestore: {http_err}")
            return None
        except Exception as e:
            self.logger.error(f"Falha ao obter chave API (cliente) do Firestore: {e}")
            return None

    def save_metrics_client(self, user_token: str, user_id: str, metric_data: Dict[str, Any]) -> bool:
        """
        Salva dados de métricas no Firestore sob o caminho do usuário, usando um ID de documento cronológico.

        Args:
            user_token (str): Token de ID do Firebase.
            user_id (str): ID do usuário.
            metric_data (Dict[str, Any]): Dicionário com os dados da métrica.

        Returns:
            bool: True se sucesso, False caso contrário.
        """
        if not all([user_token, user_id, metric_data]):
            self.logger.error("save_metrics_client: Argumentos inválidos.")
            return False

        # Gerar ID de documento cronológico
        # Formato: YYYYMMDDHHMMSSmmm_EventType (para legibilidade e ordenação)
        # O timestamp deve ser UTC para consistência global se a aplicação for usada em diferentes fusos.
        # Por simplicidade, usaremos o tempo local, mas UTC é recomendado para produção.
        now = datetime.now() # Considere datetime.utcnow()
        # Adiciona uma pequena parte aleatória ou contador para evitar colisões se muitas escritas no mesmo milissegundo
        random_suffix = secrets.token_hex(3) # Sufixo aleatório curto (6 caracteres hex)

        metric_event_type_safe = re.sub(r'[^a-zA-Z0-9_]', '', metric_data.get("event_type", "unknown")).lower()[:20]
        document_id = f"{now.strftime('%Y%m%d%H%M%S%f')[:-3]}_{metric_event_type_safe}_{random_suffix}" # Inclui milissegundos

        collection_path = f"user_metrics/{user_id}/metrics"
        full_document_path = f"{collection_path}/{document_id}"

        # Adiciona o timestamp ao próprio dado da métrica se não existir
        if "timestamp_iso" not in metric_data:
            metric_data["timestamp_iso"] = now.isoformat()
        if "client_doc_id" not in metric_data: # Guarda o ID que geramos
            metric_data["client_doc_id"] = document_id

        firestore_payload = {"fields": {k: _to_firestore_value(v) for k, v in metric_data.items()}}

        self.logger.info(f"Tentando salvar métrica (cliente) para Firestore em: {full_document_path}")
        try:
            # Usamos PATCH no caminho completo do documento para criá-lo com o ID especificado.
            # Se o documento já existir (improvável com este ID), ele seria sobrescrito.
            # A API REST para "criar com ID específico" é feita com PATCH no path do documento.
            self._make_firestore_request(
                method="PATCH", # Ou PUT, mas PATCH é mais flexível para criar/sobrescrever
                user_token=user_token,
                document_path=full_document_path, # Path do documento, incluindo o novo ID
                json_data=firestore_payload
                # Não é necessário documentId no query params quando o ID está no path para PATCH/PUT
            )
            self.logger.info(f"Métrica (cliente) salva com sucesso para Firestore: {full_document_path}")
            return True
        except Exception as e:
            self.logger.error(f"Falha ao salvar métrica (cliente) para Firestore ({full_document_path}): {e}")
            return False

    def save_analysis_metrics(self, user_id, user_token, filenames_uploaded, proc_meta_session, tokens_embeddings_session, llm_meta_session,
            current_settings, default_settings, llm_response_obj, fields_to_log=[]):
        """
        Coleta os metadados da análise e os envia para registro no Firestore.
        """
        self.logger.info("Coletando e enviando métricas da análise.")
        try:
            if not user_id or not user_token:
                self.logger.error("Não foi possível registrar métricas: usuário não autenticado na sessão.")
                return False

            # 2. Processing Metadata
            # Adicionar o timestamp do evento da LLM para referência no feedback_metric
            processing_metadata_to_log = {
                "total_pages_processed": proc_meta_session.get("total_pages_processed"),
                "relevant_pages_global_keys_formatted": proc_meta_session.get("relevant_pages_global_keys_formatted"),
                "unintelligible_pages_global_keys_formatted": proc_meta_session.get("unintelligible_pages_global_keys_formatted"),
                "final_aggregated_tokens": proc_meta_session.get("final_aggregated_tokens"),
                "processing_time": proc_meta_session.get("processing_time")
            }
            
            if tokens_embeddings_session:
                processing_metadata_to_log["tokens_embeddings_session"] = tokens_embeddings_session[0]
                processing_metadata_to_log["vectorization_model"] = tokens_embeddings_session[1]      
                processing_metadata_to_log["calculated_embedding_cost_usd"] = proc_meta_session.get("calculated_embedding_cost_usd")

            processing_metadata_to_log = {k: v for k, v in processing_metadata_to_log.items() if v is not None}

            # 3. LLM Analysis Metadata           
            llm_analysis_metadata_to_log = {
                "input_tokens": llm_meta_session.get("input_tokens"),
                "cached_tokens": llm_meta_session.get("cached_tokens"),
                "output_tokens": llm_meta_session.get("output_tokens"),
                "total_cost_usd": llm_meta_session.get("total_cost_usd"),
                "llm_provider_used": llm_meta_session.get("llm_provider_used"),
                "llm_model_used": llm_meta_session.get("llm_model_used"),
                "processing_time": llm_meta_session.get("processing_time"), # Tempo da LLM
                "event_timestamp_iso": llm_meta_session.get("event_timestamp_iso"), 
            } 
            
            # Remover chaves com valor None para não poluir o Firestore
            llm_analysis_metadata_to_log = {k: v for k, v in llm_analysis_metadata_to_log.items() if v is not None}

            # 4. LLM Parsed Response Fields
            llm_parsed_response_fields = {}
            if fields_to_log:
                for field_name in fields_to_log:
                    if hasattr(llm_response_obj, field_name):
                        llm_parsed_response_fields[field_name] = getattr(llm_response_obj, field_name)

            # 5. Analysis Settings Overrides
            analysis_settings_overrides = {}
            for key, current_val in current_settings.items():
                default_val = default_settings.get(key)
                # Garantir comparação de tipos consistentes, especialmente para números que podem ser strings
                current_val_typed = current_val
                default_val_typed = default_val
                if isinstance(default_val, (int, float)) and isinstance(current_val, str):
                    try:
                        if isinstance(default_val, int): current_val_typed = int(current_val)
                        elif isinstance(default_val, float): current_val_typed = float(current_val)
                    except ValueError:
                        pass # Mantém current_val_typed como string se não puder converter
                
                if current_val_typed != default_val_typed:
                    analysis_settings_overrides[key] = current_val # Salva o valor da sessão (pode ser string ou número)

            metric_data = {
                "app_version": APP_VERSION,
                "event_type": "pdf_analysis_completed",
                "timestamp_event": datetime.now().isoformat(),
                "filenames_uploaded": filenames_uploaded,
                "processing_metadata": processing_metadata_to_log,
                "llm_analysis_metadata": llm_analysis_metadata_to_log,
                "llm_parsed_response_fields": llm_parsed_response_fields,
                "analysis_settings_overrides": analysis_settings_overrides
            }

            # Envia a métrica
            if not self.save_metrics_client(user_token, user_id, metric_data):
                self.logger.error("Falha ao registrar métricas da análise no Firestore.")
            else:
                self.logger.info("Métricas da análise registradas com sucesso no Firestore.")
                return True
            return False

        except Exception as e:
            self.logger.error(f"Erro ao coletar ou enviar métricas da análise: {e}", exc_info=True)

    def save_feedback_data(self, user_id, user_token, feedback_data_list: List[Dict[str, Any]], llm_metadata_session, reanalysis_occurrence=None, related_batch_name="N/A"):
        """
        Salva os dados detalhados de feedback do usuário no Firestore como um documento separado,
        referenciando a análise LLM principal através de um timestamp.
        """
        self.logger.info("Salvando dados de feedback detalhado do usuário...")
        try:
            if not user_id or not user_token:
                self.logger.error("Não foi possível salvar feedback: usuário não autenticado.")
                return False

            # Tenta obter um timestamp de referência da análise LLM principal, se existir
            # Este timestamp viria dos metadados da LLM que foram salvos na sessão
            analysis_timestamp_ref = None
            if llm_metadata_session and isinstance(llm_metadata_session.get("event_timestamp_iso"), str): # Supondo que salvaremos isso
                analysis_timestamp_ref = llm_metadata_session["event_timestamp_iso"]
            else:
                # Fallback: usar o timestamp atual se o da análise não estiver disponível
                # Isso pode acontecer se o feedback for dado antes de _log_analysis_metrics ser chamado
                # ou se a estrutura de llm_metadata_session mudar.
                analysis_timestamp_ref = datetime.now().isoformat()
                self.logger.warning(f"Timestamp de referência da análise principal não encontrado em llm_metadata. Usando timestamp atual para feedback: {analysis_timestamp_ref}")

            # Preparar os campos de feedback, removendo valores originais/atuais para tipos específicos
            processed_feedback_fields = []
            for field_data in feedback_data_list:
                field_copy = field_data.copy() # Trabalha com uma cópia
                tipo_campo = field_copy.get("tipo_campo", "")
                
                if tipo_campo in ["textfield_multiline", "textfield_lista"]:
                    field_copy.pop("valor_original_llm", None)
                    field_copy.pop("valor_atual_ui", None)
                field_copy.pop("foi_editado", None)
                processed_feedback_fields.append(field_copy)

            feedback_document_payload = {
                "app_version": APP_VERSION, # Definido em settings.py
                "feedback_submission_timestamp": datetime.now().isoformat(),
                "analysis_timestamp_ref": analysis_timestamp_ref,
                "related_batch_name": related_batch_name,
                "feedback_fields_details": processed_feedback_fields # Lista de dicts
            }
            
            # Ajustamos o payload para se assemelhar mais a uma "métrica" para reutilizar a função
            metric_like_feedback_payload = {
                "event_type": "llm_feedback", # Tipo de evento específico para feedback
                "timestamp_event": feedback_document_payload["feedback_submission_timestamp"], # Timestamp do feedback
                "app_version": feedback_document_payload["app_version"],
                "details": { # Agrupa os dados específicos do feedback
                    "analysis_timestamp_ref": feedback_document_payload["analysis_timestamp_ref"],
                    "related_batch_name": feedback_document_payload["related_batch_name"],
                    "feedback_fields": feedback_document_payload["feedback_fields_details"]
                }
            }
           
            if reanalysis_occurrence:
                metric_like_feedback_payload["reanalysis_occurrence"] = 1

            if self.save_metrics_client(user_token, user_id, metric_like_feedback_payload):
                self.logger.info("Dados de feedback detalhado salvos com sucesso no Firestore.")
                return True
            else:
                self.logger.error("Falha ao salvar dados de feedback detalhado no Firestore.")
        except Exception as e:
            self.logger.error(f"Erro ao salvar dados de feedback detalhado: {e}", exc_info=True)
        return False

    

class FbManagerAuth:
    """
    Gerencia a autenticação de usuários com o Firebase Authentication
    utilizando a API REST.
    """
    def __init__(self):
        """
        Inicializador do FirebaseManagerAuth.
        """
        from src.logger.logger import LoggerSetup
        self.logger = LoggerSetup.get_logger(__name__)
        # A API Key da Web é necessária para a API REST de autenticação.
        # A inicialização do Admin SDK (feita externamente) não a supre para este caso.
        self.firebase_web_api_key = FIREBASE_WEB_API_KEY # type: ignore
        if not self.firebase_web_api_key or self.firebase_web_api_key == "SUA_FIREBASE_WEB_API_KEY_AQUI":
           self.logger.critical("Firebase Web API Key não configurada em config/settings.py. Autenticação falhará.")
            # Considerar levantar um erro se a chave for essencial para a classe funcionar.

        self.identity_toolkit_base_url = "https://identitytoolkit.googleapis.com/v1/accounts"

    @with_proxy()
    def authenticate_user(self, email: str, password: str) -> Optional[str]:
        """
        Autentica um usuário usando a API REST do Firebase Authentication (signInWithPassword).

        Args:
            email (str): O email do usuário.
            password (str): A senha do usuário.

        Returns:
            Optional[str]: O Firebase User ID (localId) se a autenticação for bem-sucedida,
                           None em caso de falha.
        """
        self.logger.info(f"Tentando autenticar usuário: {email}")

        if not self.firebase_web_api_key or self.firebase_web_api_key == "SUA_FIREBASE_WEB_API_KEY_AQUI":
            self.logger.error("Autenticação falhou: Firebase Web API Key não configurada.")
            return None

        rest_api_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={self.firebase_web_api_key}"
        payload = json.dumps({
            "email": email,
            "password": password,
            "returnSecureToken": True
        })
        headers = {"Content-Type": "application/json"}

        try:
            response = requests.post(rest_api_url, headers=headers, data=payload, timeout=15)
            response.raise_for_status()

            response_data = response.json()
            user_id = response_data.get("localId")

            if user_id:
                self.logger.info(f"Usuário {email} autenticado com sucesso. User ID: {user_id}")
                return user_id
            else:
                self.logger.error(f"Autenticação falhou para {email}: Resposta 200 OK, mas 'localId' ausente. Resposta: {response.text}")
                return None

        except requests.exceptions.HTTPError as http_err:
            status_code = http_err.response.status_code
            try:
                error_data = http_err.response.json()
                error_message = error_data.get("error", {}).get("message", "Erro desconhecido")
                self.logger.error(f"Erro HTTP {status_code} na autenticação para {email}: {error_message}. Resposta: {http_err.response.text}")
            except json.JSONDecodeError:
                self.logger.error(f"Erro HTTP {status_code} na autenticação para {email}. Não foi possível decodificar erro: {http_err.response.text}")
            return None
        except requests.exceptions.Timeout:
            self.logger.error(f"Timeout durante a tentativa de autenticação para {email}.")
            return None
        except requests.exceptions.ConnectionError as conn_err:
            self.logger.error(f"Erro de conexão durante a tentativa de autenticação para {email}: {conn_err}")
            return None
        except requests.exceptions.RequestException as req_err:
            self.logger.error(f"Erro inesperado na requisição de autenticação para {email}: {req_err}")
            return None
        except Exception as e:
            self.logger.error(f"Erro inesperado genérico durante autenticação para {email}: {e}", exc_info=True)
            return None

    @with_proxy()
    def authenticate_user_get_all_data(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Autentica um usuário usando a API REST do Firebase Authentication (signInWithPassword)
        e retorna o dicionário completo da resposta, incluindo idToken e localId.

        Args:
            email (str): O email do usuário.
            password (str): A senha do usuário.

        Returns:
            Optional[Dict[str, Any]]: Dicionário com os dados da resposta da autenticação
                                      (incluindo 'idToken', 'localId', 'email', 'expiresIn', etc.)
                                      ou None em caso de falha.
        """
        self.logger.info(f"Tentando autenticar usuário (dados completos): {email}")

        if not self.firebase_web_api_key or self.firebase_web_api_key == "SUA_FIREBASE_WEB_API_KEY_AQUI":
            self.logger.error("Autenticação (dados completos) falhou: Firebase Web API Key não configurada.")
            return None

        rest_api_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={self.firebase_web_api_key}"
        payload = json.dumps({
            "email": email,
            "password": password,
            "returnSecureToken": True
        })
        headers = {"Content-Type": "application/json"}

        try:
            response = requests.post(rest_api_url, headers=headers, data=payload, timeout=15)
            response.raise_for_status() # Levanta HTTPError para respostas 4xx/5xx

            response_data = response.json()
            # Verifica se os campos essenciais estão presentes
            if response_data.get("localId") and response_data.get("idToken"):
                self.logger.info(f"Usuário {email} autenticado com sucesso (dados completos). User ID: {response_data.get('localId')}")
                return response_data # Retorna todo o JSON de resposta
            else:
                self.logger.error(f"Autenticação (dados completos) falhou para {email}: Resposta OK, mas dados ('localId' e/ou 'idToken') ausentes. Resposta: {response.text}")
                return None

        except requests.exceptions.HTTPError as http_err:
            status_code = http_err.response.status_code
            try:
                error_data = http_err.response.json()
                error_message = error_data.get("error", {}).get("message", "Erro desconhecido")
                self.logger.error(f"Erro HTTP {status_code} na autenticação (dados completos) para {email}: {error_message}. Resposta: {http_err.response.text}")
            except json.JSONDecodeError:
                self.logger.error(f"Erro HTTP {status_code} na autenticação (dados completos) para {email}. Não foi possível decodificar erro: {http_err.response.text}")
            return None
        except requests.exceptions.RequestException as req_err: # Captura Timeout, ConnectionError, etc.
            self.logger.error(f"Erro de requisição na autenticação (dados completos) para {email}: {req_err}", exc_info=True)
            return None
        except Exception as e:
            self.logger.error(f"Erro inesperado genérico durante autenticação (dados completos) para {email}: {e}", exc_info=True)
            return None

    @with_proxy()
    def create_user(self, email: str, password: str, display_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Registra um novo usuário (signUp).

        Returns:
            Optional[Dict[str, Any]]: Dicionário com 'localId', 'idToken', etc., ou None em falha.
        """
        self.logger.info(f"Tentando criar novo usuário: {email}")
        if not self.firebase_web_api_key or self.firebase_web_api_key == "SUA_FIREBASE_WEB_API_KEY_AQUI": return None

        rest_api_url = f"{self.identity_toolkit_base_url}:signUp?key={self.firebase_web_api_key}"
        payload_dict = {"email": email, "password": password, "returnSecureToken": True}
        if display_name:
            payload_dict["displayName"] = display_name
        payload = json.dumps(payload_dict)
        headers = {"Content-Type": "application/json"}

        try:
            response = requests.post(rest_api_url, headers=headers, data=payload, timeout=15)
            response.raise_for_status()
            response_data = response.json()
            self.logger.info(f"Usuário {email} criado com sucesso. User ID: {response_data.get('localId')}")
            return response_data
        except requests.exceptions.HTTPError as http_err:
            # ... (tratamento de erro similar ao authenticate_user) ...
            self.logger.error(f"Erro HTTP ao criar usuário {email}: {http_err.response.status_code} - {http_err.response.text}")
            return None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Erro de requisição ao criar usuário {email}: {e}", exc_info=True)
            return None

    @with_proxy()
    def send_password_reset_email(self, email: str) -> bool:
        """
        Envia um email de redefinição de senha para o usuário.
        """
        self.logger.info(f"Solicitando redefinição de senha para: {email}")
        if not self.firebase_web_api_key or self.firebase_web_api_key == "SUA_FIREBASE_WEB_API_KEY_AQUI": return False

        rest_api_url = f"{self.identity_toolkit_base_url}:sendOobCode?key={self.firebase_web_api_key}"
        payload = json.dumps({"requestType": "PASSWORD_RESET", "email": email})
        headers = {"Content-Type": "application/json"}

        try:
            response = requests.post(rest_api_url, headers=headers, data=payload, timeout=15)
            response.raise_for_status()
            self.logger.info(f"Email de redefinição de senha enviado para {email}.")
            return True
        except requests.exceptions.HTTPError as http_err:
            self.logger.error(f"Erro HTTP ao enviar email de redefinição para {email}: {http_err.response.status_code} - {http_err.response.text}")
            return False
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Erro de requisição ao enviar email de redefinição para {email}: {e}", exc_info=True)
            return False

    @with_proxy()
    def refresh_id_token(self, refresh_token_str: str) -> Optional[Dict[str, Any]]:
        """
        Atualiza um ID Token usando um Refresh Token.

        Args:
            refresh_token_str: O refresh token do usuário.

        Returns:
            Optional[Dict[str, Any]]: Dicionário com os novos tokens ('id_token', 'refresh_token', 
                                      'expires_in', 'user_id') ou None em falha.
                                      O Firebase retorna 'id_token' (novo ID token), 
                                      'refresh_token' (pode ser o mesmo ou um novo),
                                      'expires_in' (nova duração em segundos),
                                      'user_id' (o localId do usuário).
        """
        self.logger.info("Tentando atualizar ID Token usando Refresh Token.")
        if not self.firebase_web_api_key or self.firebase_web_api_key == "SUA_FIREBASE_WEB_API_KEY_AQUI":
            self.logger.error("Refresh de token falhou: Firebase Web API Key não configurada.")
            return None
        if not refresh_token_str:
            self.logger.error("Refresh de token falhou: Refresh token não fornecido.")
            return None

        # A URL para refresh de token é diferente
        rest_api_url = f"https://securetoken.googleapis.com/v1/token?key={self.firebase_web_api_key}"
        payload = json.dumps({
            "grant_type": "refresh_token",
            "refresh_token": refresh_token_str
        })
        headers = {"Content-Type": "application/json"}

        try:
            response = requests.post(rest_api_url, headers=headers, data=payload, timeout=15)
            response.raise_for_status()
            response_data = response.json() # Contém id_token, refresh_token, expires_in, user_id

            # Firebase pode retornar 'id_token' ou 'access_token'. O SDK geralmente usa 'id_token'.
            # A API de refresh token retorna 'id_token' para o novo ID token e 'user_id' para localId.
            if response_data.get("id_token") and response_data.get("user_id"):
                self.logger.info(f"ID Token atualizado com sucesso para user ID: {response_data.get('user_id')}")
                # Adicionar o timestamp de expiração calculado
                expires_in_seconds = int(response_data.get("expires_in", 3600)) # Default 1 hora
                response_data["id_token_expires_at"] = time.time() + expires_in_seconds - 60 # -60s de buffer
                return response_data
            else:
                self.logger.error(f"Refresh de token falhou: Resposta não contém 'id_token' ou 'user_id'. Resposta: {response_data}")
                return None
        except requests.exceptions.ConnectionError as e: # Captura ConnectionError
            self.logger.error(f"Erro de CONEXÃO ao atualizar token: {e}", exc_info=True)
            return {"error_type": "CONNECTION_ERROR", "message": str(e)} # Retorna dict de erro
        except requests.exceptions.HTTPError as http_err:
            self.logger.error(f"Erro HTTP ao atualizar token: {http_err.response.status_code} - {http_err.response.text}")
            return {"error_type": "HTTP_ERROR", "status_code": http_err.response.status_code, "message": http_err.response.text}
        except requests.exceptions.RequestException as e: # Outros erros de requests
            self.logger.error(f"Erro de requisição ao atualizar token: {e}", exc_info=True)
            return {"error_type": "REQUEST_EXCEPTION", "message": str(e)}

    def _execute_sensitive_action(
        self,
        page: ft_Page, # Necessário para obter tokens da sessão e para o refresh_token_if_needed
        action_callable: Callable[..., Any], # A função sensível a ser chamada (ex: self.change_password)
        *args: Any, # Argumentos para a action_callable (ex: new_password para change_password)
        # **kwargs: Any # Se a action_callable precisar de kwargs, adicione aqui
    ) -> Any: # Retorna o que a action_callable retornar, ou um erro específico/None
        """
        Executa uma ação sensível, tratando CREDENTIAL_TOO_OLD_LOGIN_AGAIN com refresh de token.
        Se o refresh não resolver, indica a necessidade de reautenticação.

        Args:
            page: A instância da página Flet para acesso à sessão e refresh.
            action_callable: A função do FbManagerAuth a ser executada (ex: self.change_password).
                             Esta função DEVE aceitar o id_token como seu PRIMEIRO argumento,
                             seguido por *args.
            *args: Argumentos para a action_callable (após o id_token).

        Returns:
            O resultado da action_callable em sucesso, ou um dicionário de erro específico
            se a reautenticação for necessária, ou None/False em outras falhas.
        """
        current_id_token = page.session.get("auth_id_token")
        if not current_id_token:
            self.logger.error("_execute_sensitive_action: Nenhum ID token na sessão.")
            # Forçar logout se não há token para uma ação sensível
            from src.flet_ui.layout import handle_logout # Import tardio
            handle_logout(page)
            return {"error": "NO_TOKEN_SESSION_LOGOUT"} # Sinaliza que o logout foi forçado

        max_attempts = 2 # Tentativa inicial + 1 tentativa após refresh
        for attempt in range(max_attempts):
            try:
                self.logger.debug(f"Tentativa {attempt + 1} de executar ação sensível: {action_callable.__name__}")
                # A action_callable (ex: self.change_password) espera o id_token como primeiro argumento
                result = action_callable(current_id_token, *args)
                return result # Sucesso na primeira ou segunda tentativa
            
            except requests.exceptions.HTTPError as http_err:
                if http_err.response and http_err.response.status_code == 400:
                    try:
                        error_data = http_err.response.json()
                        api_error_message = error_data.get("error", {}).get("message")
                        
                        if api_error_message == "CREDENTIAL_TOO_OLD_LOGIN_AGAIN":
                            self.logger.warning(f"Ação sensível falhou com CREDENTIAL_TOO_OLD (tentativa {attempt + 1}).")
                            if attempt < max_attempts - 1: # Se ainda há tentativas (só tentamos refresh uma vez)
                                self.logger.info("Tentando refresh forçado do token...")
                                # Presume que check_and_refresh_token_if_needed está acessível
                                # Idealmente, passá-lo ou tê-lo em um local comum.
                                
                                from src.flet_ui.app import check_and_refresh_token_if_needed # Ajuste o caminho se necessário
                                
                                if check_and_refresh_token_if_needed(page, force_refresh=True):
                                    current_id_token = page.session.get("auth_id_token") # Pega o novo token
                                    if not current_id_token: # Se refresh falhou e deslogou
                                        self.logger.error("Refresh do token falhou e usuário foi deslogado.")
                                        return {"error": "REFRESH_FAILED_LOGOUT"}
                                    self.logger.info("Token atualizado. Repetindo ação sensível.")
                                    continue # Próxima iteração do loop para tentar novamente
                                else: # check_and_refresh_token_if_needed retornou False (provavelmente deslogou)
                                    self.logger.error("Refresh do token falhou (check_and_refresh_token_if_needed retornou False).")
                                    return {"error": "REFRESH_FAILED_LOGOUT"}
                            else: # Última tentativa já falhou com CREDENTIAL_TOO_OLD
                                self.logger.error("Ação sensível falhou com CREDENTIAL_TOO_OLD mesmo após refresh. Reautenticação necessária.")
                                return {"error": "CREDENTIAL_TOO_OLD_RELOGIN_REQUIRED"}
                        else: # Outro erro 400
                            self.logger.error(f"Erro HTTP 400 (não CREDENTIAL_TOO_OLD) na ação sensível: {api_error_message or http_err.response.text}")
                            return {"error": api_error_message or "HTTP_400_ERROR", "details": error_data if 'error_data' in locals() else http_err.response.text}
                    except json.JSONDecodeError:
                        self.logger.error(f"Erro HTTP 400 (resposta não JSON) na ação sensível: {http_err.response.text}")
                        return {"error": "HTTP_400_NON_JSON", "details": http_err.response.text}
                else: # Erro HTTP não 400
                    self.logger.error(f"Erro HTTP {http_err.response.status_code if http_err.response else 'N/A'} na ação sensível: {http_err}", exc_info=True)
                    raise # Re-levanta outros erros HTTP para serem tratados pelo chamador original
            
            except Exception as e: # Outras exceções (RequestException, etc.)
                self.logger.error(f"Exceção inesperada ao executar ação sensível: {e}", exc_info=True)
                raise # Re-levanta para tratamento genérico

        # Se sair do loop sem sucesso (improvável com a lógica acima, mas como fallback)
        self.logger.error("Saiu do loop de tentativas para ação sensível sem um resultado claro.")
        return {"error": "UNKNOWN_SENSITIVE_ACTION_FAILURE"}

    @with_proxy() # O decorador ainda é útil para a chamada de rede final
    def _raw_change_password(self, id_token: str, new_password: str) -> Dict[str, Any]: # Renomeado para indicar que é a chamada crua
        """Chamada API crua para alterar senha. Usado por _execute_sensitive_action."""
        self.logger.debug(f"API Call: Tentando alterar senha (raw) para token: {id_token[:10]}...")
        if not self.firebase_web_api_key or self.firebase_web_api_key == "SUA_FIREBASE_WEB_API_KEY_AQUI": 
            # _execute_sensitive_action não deve chegar aqui se o token não existir, mas como defesa
            raise ValueError("Firebase Web API Key não configurada.")

        rest_api_url = f"{self.identity_toolkit_base_url}:update?key={self.firebase_web_api_key}"
        payload = json.dumps({
            "idToken": id_token,
            "password": new_password,
            "returnSecureToken": False 
        })
        headers = {"Content-Type": "application/json"}
        response = requests.post(rest_api_url, headers=headers, data=payload, timeout=15)
        response.raise_for_status() # Deixa _execute_sensitive_action tratar HTTPError
        self.logger.info("API Call: Senha alterada com sucesso (raw).")
        return response.json() # Retorna o JSON da resposta (geralmente dados do usuário atualizados ou vazio)

    def change_password(self, page: ft_Page, new_password: str) -> bool: # Agora recebe 'page'
        """
        Altera a senha do usuário autenticado, com tratamento de token antigo.
        """
        self.logger.info("Interface: Solicitado alteração de senha.")
        # _execute_sensitive_action espera que a action_callable receba id_token como primeiro arg
        # e os demais args depois. _raw_change_password já está assim.
        result = self._execute_sensitive_action(page, self._raw_change_password, new_password)
        
        if isinstance(result, dict) and result.get("error"):
            self.logger.error(f"Falha ao alterar senha: {result.get('error')} - {result.get('details', '')}")
            if result.get("error") == "CREDENTIAL_TOO_OLD_RELOGIN_REQUIRED":
                # A UI deve ser notificada para forçar re-login
                from src.flet_ui.layout import handle_logout # Import tardio
                from src.flet_ui.components import show_snackbar # Import tardio
                from src.flet_ui import theme # Import tardio
                show_snackbar(page, "Sua sessão é muito antiga para esta ação. Por favor, faça login novamente.", color=theme.COLOR_ERROR, duration=7000)
                handle_logout(page)
            return False
        elif isinstance(result, dict): # Sucesso (resposta JSON da API)
            return True # A API de changePassword retorna dados do usuário ou vazio em sucesso.
        return False # Falha não tratada explicitamente

    # Similarmente para update_profile e delete_user_account:

    @with_proxy()
    def _raw_update_profile(self, id_token: str, display_name: Optional[str] = None,
                            photo_url: Optional[str] = None, delete_attributes: Optional[List[str]] = None) -> Dict[str, Any]:
        self.logger.debug(f"API Call: Tentando atualizar perfil (raw) para token: {id_token[:10]}...")
        # ... (lógica da API call como estava em update_profile antes, sem o try/except complexo)
        if not self.firebase_web_api_key or self.firebase_web_api_key == "SUA_FIREBASE_WEB_API_KEY_AQUI":
            raise ValueError("Firebase Web API Key não configurada.")
            
        rest_api_url = f"{self.identity_toolkit_base_url}:update?key={self.firebase_web_api_key}"
        payload_dict = {"idToken": id_token, "returnSecureToken": False}
        if display_name is not None: payload_dict["displayName"] = display_name
        if photo_url is not None: payload_dict["photoUrl"] = photo_url
        if delete_attributes: payload_dict["deleteAttribute"] = delete_attributes

        if len(payload_dict) <= 2 and not delete_attributes: # Só idToken e returnSecureToken
             self.logger.info("API Call: Nenhuma alteração de perfil para enviar (raw).")
             return {"message": "No profile changes to apply."} # Simula uma resposta de sucesso vazia

        payload = json.dumps(payload_dict)
        headers = {"Content-Type": "application/json"}
        response = requests.post(rest_api_url, headers=headers, data=payload, timeout=15)
        response.raise_for_status()
        self.logger.info("API Call: Perfil atualizado com sucesso (raw).")
        return response.json()

    def update_profile(self, page: ft_Page, display_name: Optional[str] = None,
                       photo_url: Optional[str] = None, delete_attributes: Optional[List[str]] = None) -> bool:
        self.logger.info("Interface: Solicitado atualização de perfil.")
        if display_name is None and photo_url is None and not delete_attributes:
            self.logger.info("Nenhuma alteração de perfil solicitada na interface.")
            return True # Considera sucesso

        result = self._execute_sensitive_action(page, self._raw_update_profile, display_name, photo_url, delete_attributes)
        
        if isinstance(result, dict) and result.get("error"):
            self.logger.error(f"Falha ao atualizar perfil: {result.get('error')} - {result.get('details', '')}")
            if result.get("error") == "CREDENTIAL_TOO_OLD_RELOGIN_REQUIRED":
                from src.flet_ui.layout import handle_logout
                from src.flet_ui.components import show_snackbar
                from src.flet_ui import theme
                show_snackbar(page, "Sua sessão é muito antiga para esta ação. Por favor, faça login novamente.", color=theme.COLOR_ERROR, duration=7000)
                handle_logout(page)
            return False
        elif isinstance(result, dict): # Sucesso
            return True
        return False


    @with_proxy()
    def _raw_delete_user_account(self, id_token: str) -> Dict[str, Any]:
        self.logger.debug(f"API Call: Tentando excluir conta (raw) com token: {id_token[:10]}...")
        # ... (lógica da API call como estava em delete_user_account antes)
        if not self.firebase_web_api_key or self.firebase_web_api_key == "SUA_FIREBASE_WEB_API_KEY_AQUI":
            raise ValueError("Firebase Web API Key não configurada.")

        rest_api_url = f"{self.identity_toolkit_base_url}:delete?key={self.firebase_web_api_key}"
        payload = json.dumps({"idToken": id_token})
        headers = {"Content-Type": "application/json"}
        response = requests.post(rest_api_url, headers=headers, data=payload, timeout=15)
        response.raise_for_status()
        self.logger.info("API Call: Conta do usuário excluída com sucesso (raw).")
        return response.json() # Geralmente um JSON vazio {}

    def delete_user_account(self, page: ft_Page) -> bool: # Agora recebe 'page'
        self.logger.info("Interface: Solicitado exclusão de conta.")
        result = self._execute_sensitive_action(page, self._raw_delete_user_account)
        
        if isinstance(result, dict) and result.get("error"):
            self.logger.error(f"Falha ao excluir conta: {result.get('error')} - {result.get('details', '')}")
            if result.get("error") == "CREDENTIAL_TOO_OLD_RELOGIN_REQUIRED":
                from src.flet_ui.layout import handle_logout
                from src.flet_ui.components import show_snackbar
                from src.flet_ui import theme
                show_snackbar(page, "Sua sessão é muito antiga para esta ação. Por favor, faça login novamente.", color=theme.COLOR_ERROR, duration=7000)
                handle_logout(page)
            return False
        elif isinstance(result, dict): # Sucesso
            return True
        return False
    

# --- Imports para a Função de Teste ---
import getpass
from src.services import credentials_manager # Para simular criptografia de API key

def test_firebase_clients():
    """
    Função para testar interativamente as classes FirebaseClientStorage e FirebaseClientFirestore.
    Requer que as credenciais do Firebase Admin SDK estejam configuradas e que
    um usuário de teste exista no Firebase Authentication.
    """
    print("--- Iniciando Teste Interativo dos Clientes Firebase (Storage & Firestore) ---")

    # 1. Obter Token de Usuário
    print("\nPasso 1: Autenticação do Usuário de Teste")
    fb_auth_manager = FbManagerAuth()
    email = input("Email do usuário de teste: ")
    password = getpass.getpass("Senha do usuário de teste: ")

    user_auth_data = fb_auth_manager.authenticate_user_get_all_data(email, password) # Supondo que você tenha esta função

    if not user_auth_data or not user_auth_data.get("idToken") or not user_auth_data.get("localId"):
        print("Falha na autenticação. Verifique as credenciais e a configuração.")
        print(f"Dados de autenticação recebidos: {user_auth_data}")
        return

    user_token = user_auth_data["idToken"]
    user_id = user_auth_data["localId"]
    print(f"Usuário autenticado com sucesso. User ID: {user_id}")

    # --- Testando FirebaseClientStorage ---
    print("\n--- Testando FirebaseClientStorage ---")
    storage_client = FirebaseClientStorage()
    test_storage_suffix = f"test_data/client_storage_test_{int(time.time())}.txt"
    test_content = f"Conteúdo de teste para Storage - {user_id} @ {time.ctime()}"

    from src.logger.logger import LoggerSetup
    LoggerSetup.initialize(
        routine_name="DocsAnalyzer3",  
        firebase_client_storage = storage_client
    )
    LoggerSetup.set_cloud_user_context(user_token, user_id)
    logger = LoggerSetup.get_logger(__name__)

    logger.debug(f"Testando Logger com ClientLogUploader!  [DEBUG]")
    logger.info(f"Testando Logger com ClientLogUploader!  [INFO]")
    logger.warning(f"Testando Logger com ClientLogUploader!  [WARN]")
    logger.error(f"Testando Logger com ClientLogUploader!  [ERROR]")

    # Teste upload_text_user
    print(f"\nPasso 2.1: Testando upload_text_user para '{test_storage_suffix}'")
    upload_success = storage_client.upload_text_user(user_token, user_id, test_content, test_storage_suffix)
    if upload_success:
        print(f"SUCESSO: upload_text_user para '{test_storage_suffix}'")
    else:
        print(f"FALHA: upload_text_user para '{test_storage_suffix}'")
        # Não continuar com get se o upload falhou
        return

    # Teste get_text_user
    print(f"\nPasso 2.2: Testando get_text_user de '{test_storage_suffix}'")
    retrieved_content = storage_client.get_text_user(user_token, user_id, test_storage_suffix)
    if retrieved_content == test_content:
        print(f"SUCESSO: get_text_user retornou o conteúdo esperado.")
        print(f"Conteúdo recuperado: '{retrieved_content[:100]}...'")
    elif retrieved_content is None:
        print(f"FALHA: get_text_user não encontrou o arquivo ou erro.")
    else:
        print(f"FALHA: get_text_user retornou conteúdo diferente do esperado.")
        print(f"Esperado: '{test_content}'")
        print(f"Recebido: '{retrieved_content}'")

    # --- Testando FirebaseClientFirestore ---
    print("\n--- Testando FirebaseClientFirestore ---")
    firestore_client = FirebaseClientFirestore()
    test_service_name = f"test_service_{int(time.time())}"
    original_api_key = f"sk-testkey123abcXYZ-{user_id}-{int(time.time())}"

    # Simular criptografia da chave (como seria feito na UI/lógica da aplicação)
    if not credentials_manager.get_encryption_key():
        print("\nAVISO: Chave de criptografia local (Fernet) não encontrada no Keyring.")
        print("Isso é necessário para testar o save/get_user_api_key_client com criptografia real.")
        print("Você pode precisar rodar o setup de credenciais do `credentials_manager` primeiro.")
        print("Continuando teste sem criptografia real para API key (usará string simples).")
        encrypted_api_key_bytes = original_api_key.encode('utf-8') # Apenas para o teste prosseguir
    else:
        encrypted_api_key_bytes_maybe = credentials_manager.encrypt(original_api_key)
        if not encrypted_api_key_bytes_maybe:
            print("FALHA: Não foi possível criptografar a API key de teste com credentials_manager.")
            return
        encrypted_api_key_bytes = encrypted_api_key_bytes_maybe

    # Teste save_user_api_key_client
    print(f"\nPasso 3.1: Testando save_user_api_key_client para serviço '{test_service_name}'")
    save_key_success = firestore_client.save_user_api_key_client(
        user_token, user_id, test_service_name, encrypted_api_key_bytes
    )
    if save_key_success:
        print(f"SUCESSO: save_user_api_key_client para '{test_service_name}'")
    else:
        print(f"FALHA: save_user_api_key_client para '{test_service_name}'")
        # Não continuar com get se o save falhou
        return

    # Teste get_user_api_key_client
    print(f"\nPasso 3.2: Testando get_user_api_key_client para '{test_service_name}'")
    retrieved_encrypted_bytes = firestore_client.get_user_api_key_client(
        user_token, user_id, test_service_name
    )

    if retrieved_encrypted_bytes:
        print("Chave criptografada recuperada do Firestore.")
        # Simular descriptografia
        decrypted_api_key = None
        if credentials_manager.get_encryption_key(): # Tenta descriptografar apenas se a chave Fernet existe
            decrypted_api_key = credentials_manager.decrypt(retrieved_encrypted_bytes)

        if decrypted_api_key == original_api_key:
            print(f"SUCESSO: get_user_api_key_client retornou a chave esperada (após descriptografia).")
        elif not credentials_manager.get_encryption_key() and retrieved_encrypted_bytes.decode('utf-8', errors='ignore') == original_api_key:
            # Caso de teste onde a criptografia foi pulada
            print("SUCESSO (parcial): Chave recuperada corresponde à original (teste sem criptografia real).")
        elif not decrypted_api_key and credentials_manager.get_encryption_key():
            print("FALHA: Não foi possível descriptografar a chave recuperada.")
        else:
            print(f"FALHA: Chave descriptografada não corresponde à original.")
            print(f"   Original: {original_api_key}")
            print(f"   Descriptografada: {decrypted_api_key}")
            print(f"   Bytes Criptografados Recuperados (início): {retrieved_encrypted_bytes[:30]}...")

    elif retrieved_encrypted_bytes is None:
        print(f"FALHA: get_user_api_key_client não encontrou a chave ou erro.")
    else:
        print(f"FALHA: get_user_api_key_client retornou um valor inesperado (não bytes ou None).")


    # Teste save_metrics_client
    print(f"\nPasso 3.3: Testando save_metrics_client")
    test_metric_data = {
        "event_type": "test_event",
        "timestamp": time.time(),
        "details": {"user_id": user_id, "test_run": int(time.time())},
        "value": 123.45
    }
    save_metric_success = firestore_client.save_metrics_client(user_token, user_id, test_metric_data)
    if save_metric_success:
        print(f"SUCESSO: save_metrics_client para evento '{test_metric_data['event_type']}'")
    else:
        print(f"FALHA: save_metrics_client para evento '{test_metric_data['event_type']}'")

    print("\n--- Teste Interativo dos Clientes Firebase Concluído ---")
    print("Verifique o Firebase Console para confirmar os dados criados/modificados.")
    print(f"Lembre-se: Arquivo de teste no Storage em 'users/{user_id}/{test_storage_suffix}'")
    print(f"           Chave API de teste no Firestore em 'user_api_keys/{user_id}' campo '{test_service_name}'")
    print(f"           Métrica de teste no Firestore em 'user_metrics/{user_id}/metrics/' (ID gerado automaticamente)")

    #if LoggerSetup._active_cloud_handler_instance: # Verifica se o handler foi criado
    #    print("\nForçando flush do CloudLogHandler...")
    #    LoggerSetup._active_cloud_handler_instance.flush()
    #    print("Flush solicitado. Aguardando um momento para o upload...")
    #    time.sleep(5) # Dê um tempo para o upload HTTP concluir
    #else:
    #    print("\nCloudLogHandler não está ativo, flush não realizado.")

def test_firebase_auth():
    """
    Função para testar interativamente os métodos de gerenciamento de usuário da classe FbManagerAuth.
    """

    def new_autenticate():
        auth_email = input(f"Email para autenticar (padrão: {created_user_email or 'email@example.com'}): ") 
        auth_password = getpass.getpass(f"Senha para {auth_email}: ")
        ...
        auth_data = auth_manager.authenticate_user_get_all_data(auth_email, auth_password)
        if auth_data and auth_data.get("idToken") and auth_data.get("localId"):
            test_logger.info(f"SUCESSO: Usuário {auth_email} autenticado.")
            # Se a criação falhou, mas o login funcionou, precisamos do email para reset de senha
            if not created_user_email: created_user_email = auth_email
            return 
        else:
            test_logger.error(f"FALHA ao autenticar {auth_email}. Resposta: {auth_data}")
            test_logger.warning("Alguns testes subsequentes podem falhar ou ser pulados.")
            raise Exception(f"FALHA ao autenticar {auth_email}. Resposta: {auth_data}")
        

    print("\n--- Iniciando Teste Interativo de FbManagerAuth ---")

    # 0. Inicialização (FbManagerAuth não precisa do Admin SDK, apenas da WEB_API_KEY)
    # No entanto, a inicialização do logger pode ser útil se feita antes.
    try:
        from src.logger.logger import LoggerSetup # Import local para o teste
        # Configuração mínima do logger para o teste, se não inicializado globalmente
        if not LoggerSetup._initialized:
             LoggerSetup.initialize("fb_auth_test_run", "test_user_auth", "0.0.0")
        test_logger = LoggerSetup.get_logger("FbManagerAuthTest")
        test_logger.info("Logger para teste de FbManagerAuth configurado.")
    except ImportError:
        print("AVISO: LoggerSetup não encontrado, usando prints para o teste.")
        class TestLoggerFallback: # Fallback simples se o logger não estiver disponível
            def info(self, msg): print(f"INFO: {msg}")
            def warning(self, msg): print(f"WARN: {msg}")
            def error(self, msg): print(f"ERROR: {msg}")
        test_logger = TestLoggerFallback()


    auth_manager = FbManagerAuth()
    if not auth_manager.firebase_web_api_key or auth_manager.firebase_web_api_key == "SUA_FIREBASE_WEB_API_KEY_AQUI":
        test_logger.error("FIREBASE_WEB_API_KEY não configurada! Testes de autenticação não podem prosseguir.")
        return

    # Variáveis para armazenar dados entre os passos do teste
    created_user_email = None
    created_user_password = None
    user_id_token = None
    user_local_id = None

    # --- 1. Criar Novo Usuário ---
    print("\n--- Passo 1: Criar Novo Usuário (signUp) ---")
    timestamp = int(time.time())
    test_email = input(f"Email para novo usuário (ex: testuser{timestamp}@example.com): ") or f"testuser{timestamp}@example.com"
    test_password = getpass.getpass(f"Senha para {test_email} (mín. 6 caracteres): ")
    test_display_name = input(f"Nome de exibição para {test_email} (opcional): ") or f"Test User {timestamp}"

    if len(test_password) < 6:
        test_logger.error("Senha muito curta. Teste de criação de usuário deve ser abortado.")
    #else:
    creation_response = auth_manager.create_user(test_email, test_password, test_display_name)
    if creation_response and creation_response.get("idToken") and creation_response.get("localId"):
        test_logger.info(f"SUCESSO: Usuário {test_email} criado.")
        test_logger.info(f"  Local ID: {creation_response.get('localId')}")
        test_logger.info(f"  ID Token (curto): {creation_response.get('idToken', '')[:20]}...")
        created_user_email = test_email
        created_user_password = test_password
        user_id_token = creation_response.get("idToken") # Salva para os próximos passos
        user_local_id = creation_response.get("localId")
    else:
        test_logger.error(f"FALHA ao criar usuário {test_email}. Resposta: {creation_response}")

    input("Pressione Enter para continuar...")

    # --- 2. Autenticar Usuário Criado (ou um existente se a criação falhou) ---
    print("\n--- Passo 2: Autenticar Usuário (signInWithPassword) ---")
    if user_id_token:
        test_logger.info(f"Usuário {created_user_email} já autenticado durante a criação. Pulando re-autenticação.")
    else:
        auth_data = new_autenticate()
        user_id_token = auth_data.get("idToken")
        user_local_id = auth_data.get("localId")

    input("Pressione Enter para continuar...")

    # --- 3. Enviar Email de Redefinição de Senha ---
    print("\n--- Passo 3: Enviar Email de Redefinição de Senha (sendOobCode) ---")
    if created_user_email: # Usa o email do usuário criado ou logado
        email_for_reset = created_user_email
    else:
        email_for_reset = input("Email para enviar link de redefinição de senha: ")

    if email_for_reset:
        reset_sent = auth_manager.send_password_reset_email(email_for_reset)
        if reset_sent:
            test_logger.info(f"SUCESSO: Solicitação de email de redefinição enviada para {email_for_reset}.")
            test_logger.info("Verifique a caixa de entrada (pode levar alguns minutos).")
        else:
            test_logger.error(f"FALHA ao enviar email de redefinição para {email_for_reset}.")
    else:
        test_logger.warning("Nenhum email fornecido para redefinição de senha. Teste pulado.")

    input("Pressione Enter para continuar...")

    # --- 4. Alterar Senha (requer ID Token) ---
    print("\n--- Passo 4: Alterar Senha (update) ---")
    if user_id_token:
        new_password = getpass.getpass("Digite a NOVA senha para o usuário autenticado: ")
        if len(new_password) >= 6:
            changed_password = auth_manager.change_password(user_id_token, new_password)
            if changed_password:
                test_logger.info("SUCESSO: Senha alterada.")
                created_user_password = new_password # Atualiza para o teste de exclusão
                # O ID Token antigo ainda é válido por um tempo, mas idealmente você re-autenticaria para obter um novo.
                # Para este teste, vamos assumir que ainda é válido para as próximas operações.
                test_logger.warning("Para operações futuras com a nova senha, seria ideal re-autenticar para obter um novo ID Token.")

                auth_data = new_autenticate()
                user_id_token = auth_data.get("idToken")
                user_local_id = auth_data.get("localId")

            else:
                test_logger.error("FALHA ao alterar senha.")
        else:
            test_logger.error("Nova senha muito curta. Teste de alteração de senha abortado.")
    else:
        test_logger.warning("Nenhum usuário autenticado (ID Token ausente). Teste de alteração de senha pulado.")

    input("Pressione Enter para continuar...")

    # --- 5. Atualizar Perfil (requer ID Token) ---
    print("\n--- Passo 5: Atualizar Perfil (update) ---")
    if user_id_token:
        new_display_name = input(f"Novo nome de exibição (atual: '{test_display_name}', deixe em branco para não mudar): ")
        new_photo_url = input("Nova URL da foto (deixe em branco para não mudar, ex: http://example.com/photo.png): ")
        
        attributes_to_delete = []
        if input("Deseja remover o nome de exibição? (s/N): ").lower() == 's':
            attributes_to_delete.append("DISPLAY_NAME")
        if input("Deseja remover a URL da foto? (s/N): ").lower() == 's':
            attributes_to_delete.append("PHOTO_URL")

        # Apenas chama update_profile se houver algo para mudar ou deletar
        if new_display_name or new_photo_url or attributes_to_delete:
            profile_updated = auth_manager.update_profile(
                user_id_token,
                display_name=new_display_name if new_display_name else None, # Passa None se vazio
                photo_url=new_photo_url if new_photo_url else None,
                delete_attributes=attributes_to_delete if attributes_to_delete else None
            )
            if profile_updated:
                test_logger.info("SUCESSO: Perfil atualizado (ou nenhuma alteração solicitada).")
                if new_display_name: test_display_name = new_display_name # Atualiza para o teste
            else:
                test_logger.error("FALHA ao atualizar perfil.")
        else:
            test_logger.info("Nenhuma alteração de perfil solicitada. Teste de atualização pulado.")
    else:
        test_logger.warning("Nenhum usuário autenticado (ID Token ausente). Teste de atualização de perfil pulado.")

    input("Pressione Enter para continuar...")

    # --- 6. Excluir Conta (requer ID Token) ---
    print("\n--- Passo 6: Excluir Conta (delete) ---")
    if user_id_token:
        if input(f"Tem CERTEZA que deseja excluir a conta de '{created_user_email or user_local_id}'? Esta ação é IRREVERSÍVEL. (s/N): ").lower() == 's':
            deleted = auth_manager.delete_user_account(user_id_token)
            if deleted:
                test_logger.info(f"SUCESSO: Conta de '{created_user_email or user_local_id}' excluída.")
                user_id_token = None # Invalida o token localmente
                created_user_email = None
            else:
                test_logger.error(f"FALHA ao excluir conta de '{created_user_email or user_local_id}'.")
        else:
            test_logger.info("Exclusão de conta cancelada pelo usuário.")
    else:
        test_logger.warning("Nenhum usuário autenticado (ID Token ausente). Teste de exclusão de conta pulado.")

    print("\n--- Teste Interativo de FbManagerAuth Concluído ---")
    '''
    Teste de Permissão negada:
    storage_client = FirebaseClientStorage()
    fb_auth_manager = FbManagerAuth()
    user_auth_data = fb_auth_manager.authenticate_user_get_all_data('edson.bragga@gmail.com', 'teste...')
    full_storage_path = "users/other_path/teste.txt"
    text_content = 'texto teste'
    self=storage_client
    self._make_storage_request(...
    '''

# test_firebase_clients()
# test_firebase_auth()

execution_time = perf_counter() - start_time
print(f"Carregado FIREBASE_CLIENT em {execution_time:.4f}s")

'''
TODO: Os atributos de usuários não estão sendo exibidos no console do Firebase, mas conseguimos visualizar através do Admin SDK. A Checar novamente...
'''

