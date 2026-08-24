# src/flet_ui/app.py

import logging
logger = logging.getLogger(__name__)

DEV_MODE = False

from time import perf_counter
start_time = perf_counter()
logger.debug(f"{start_time:.4f}s - Iniciando app.py")

import flet as ft
import time, os, threading, jwt
from typing import Optional

from ..settings import (APP_TITLE, APP_VERSION, APP_DEFAULT_SETTINGS_COLLECTION,
                        ANALYZE_PDF_DEFAULTS_DOC_ID, CHAT_DOCS_DEFAULTS_DOC_ID, KEY_SESSION_CLOUD_ANALYSIS_DEFAULTS,
                        KEY_SESSION_CLOUD_CHAT_DEFAULTS,
                        FALLBACK_ANALYSIS_SETTINGS, LLM_PROVIDERS_CONFIG_COLLECTION,
                        LLM_PROVIDERS_DEFAULT_DOC_ID, KEY_SESSION_LOADED_LLM_PROVIDERS,
                        LLM_EMBEDDINGS_CONFIG_COLLECTION, LLM_EMBEDDINGS_DEFAULT_DOC_ID,
                        KEY_SESSION_NC_ANALYZE_SETTINGS, KEY_SESSION_CHAT_SETTINGS,
                        KEY_SESSION_MODEL_EMBEDDINGS_LIST)

from .layout import show_snackbar, create_app_bar, create_navigation_rail, handle_logout
#from .components import ...
from .router import route_change_content_only 
from . import theme
error_color = theme.COLOR_ERROR if hasattr(theme, 'COLOR_ERROR') else ft.Colors.RED

from SOURCE import app_cache
from SOURCE.services import credentials_manager
from SOURCE.services.firebase_client import FbManagerAuth, FirebaseClientFirestore, _from_firestore_value
from SOURCE.services.local_db_manager import LocalDBManager
from SOURCE.config.provider import is_local_mode
from SOURCE.logger.logger import LoggerSetup

# --- Rastreamento Global de Conexões ---
global_active_sessions = set()
global_active_sessions_lock = threading.Lock()

auth_manager = FbManagerAuth()
firestore_client = FirebaseClientFirestore()

def load_default_analysis_settings(page: ft.Page):
    """
    Carrega as configurações para as views `nc_analyze` e `chat`.
    A lógica é: SQLite local > Padrões da Nuvem (Firestore) > Fallback local.
    """
    logger.info("Carregando configurações de análise para as views...")
    user_token = page.session.get("auth_id_token")
    user_id = page.session.get("auth_user_id")
    db_manager = LocalDBManager()

    # --- Fallbacks para usuário não autenticado ---
    if not user_token or not user_id:
        logger.warning("Token/ID de usuário não encontrado. Usando fallbacks locais para configurações.")
        page.session.set(KEY_SESSION_LOADED_LLM_PROVIDERS, [])
        page.session.set(KEY_SESSION_MODEL_EMBEDDINGS_LIST, [])
        page.session.set(KEY_SESSION_CLOUD_ANALYSIS_DEFAULTS, FALLBACK_ANALYSIS_SETTINGS.copy())
        page.session.set(KEY_SESSION_NC_ANALYZE_SETTINGS, FALLBACK_ANALYSIS_SETTINGS.copy())
        chat_fallback_settings = FALLBACK_ANALYSIS_SETTINGS.copy()
        chat_fallback_settings["reasoning_effort"] = "minimal"  # Chat inicia com thinking desativado (nc_analyze mantém "low"/ativo)
        page.session.set(KEY_SESSION_CLOUD_CHAT_DEFAULTS, chat_fallback_settings.copy())
        page.session.set(KEY_SESSION_CHAT_SETTINGS, chat_fallback_settings)
        return

    # --- Carregamento de dados globais (Provedores, Custos, Padrões da Nuvem) ---
    # Esta parte é executada uma vez para popular a sessão com dados de referência.
    _load_global_providers_and_costs(page, user_token)

    # Carrega os defaults base para nc_analyze
    nc_analyze_defaults = _load_specific_cloud_defaults(
        page, user_token, ANALYZE_PDF_DEFAULTS_DOC_ID
    )
    page.session.set(KEY_SESSION_CLOUD_ANALYSIS_DEFAULTS, nc_analyze_defaults.copy())

    # Carrega os overrides para chat_docs e os mescla
    chat_docs_overrides = _load_specific_cloud_defaults(
        page, user_token, CHAT_DOCS_DEFAULTS_DOC_ID
    )
    chat_defaults = nc_analyze_defaults.copy()
    chat_defaults.update(chat_docs_overrides) # Aplica as personalizações do chat
    if "reasoning_effort" not in chat_docs_overrides:
        chat_defaults["reasoning_effort"] = "minimal"  # Chat inicia com thinking desativado, salvo override explícito na nuvem
    page.session.set(KEY_SESSION_CLOUD_CHAT_DEFAULTS, chat_defaults.copy())

    # --- Carregamento das Configurações Específicas de cada View ---
    # 1. Carregar para NC Analyze View
    nc_analyze_settings = db_manager.get_setting(KEY_SESSION_NC_ANALYZE_SETTINGS, user_id=user_id)
    if nc_analyze_settings:
        page.session.set(KEY_SESSION_NC_ANALYZE_SETTINGS, nc_analyze_settings)
        logger.info("Configurações para 'Análise de Documentos' carregadas do banco de dados local.")
    else:
        page.session.set(KEY_SESSION_NC_ANALYZE_SETTINGS, nc_analyze_defaults.copy())
        logger.info("Configurações para 'Análise de Documentos' definidas a partir dos padrões da nuvem (não encontradas localmente).")

    # 2. Carregar para Chat View
    chat_settings = db_manager.get_setting(KEY_SESSION_CHAT_SETTINGS, user_id=user_id)
    if chat_settings:
        page.session.set(KEY_SESSION_CHAT_SETTINGS, chat_settings)
        logger.info("Configurações para 'Chat com Documentos' carregadas do banco de dados local.")
    else:
        page.session.set(KEY_SESSION_CHAT_SETTINGS, chat_defaults.copy())
        logger.info("Configurações para 'Chat com Documentos' definidas a partir dos padrões da nuvem (não encontradas localmente).")

def _load_global_providers_and_costs(page: ft.Page, user_token: str):
    """Carrega a lista de provedores LLM e custos de embedding do Firestore."""
    # Carregar Lista de Provedores LLM
    loaded_providers_list = []
    providers_doc_path = f"{LLM_PROVIDERS_CONFIG_COLLECTION}/{LLM_PROVIDERS_DEFAULT_DOC_ID}"
    try:
        response = firestore_client._make_firestore_request("GET", user_token, providers_doc_path)
        if response.status_code == 200:
            data = response.json()
            values = data.get("fields", {}).get("all_providers", {}).get("arrayValue", {}).get("values", [])
            loaded_providers_list = [_from_firestore_value(v) for v in values if "mapValue" in v]
            logger.info(f"{len(loaded_providers_list)} provedores LLM carregados.")
    except Exception as e:
        logger.error(f"Exceção ao carregar provedores LLM: {e}", exc_info=True)
    page.session.set(KEY_SESSION_LOADED_LLM_PROVIDERS, loaded_providers_list)

    # Carregar Custos de Modelos de Embedding
    loaded_embeddings_list = []
    embeddings_doc_path = f"{LLM_EMBEDDINGS_CONFIG_COLLECTION}/{LLM_EMBEDDINGS_DEFAULT_DOC_ID}"
    try:
        response = firestore_client._make_firestore_request("GET", user_token, embeddings_doc_path)
        if response.status_code == 200:
            data = response.json()
            values = data.get("fields", {}).get("all_models", {}).get("arrayValue", {}).get("values", [])
            for v in values:
                if "mapValue" in v:
                    embedding_dict = _from_firestore_value(v)
                    if isinstance(embedding_dict, dict) and "name" in embedding_dict and "cost_per_million" in embedding_dict:
                        try:
                            embedding_dict["cost_per_million"] = float(embedding_dict["cost_per_million"])
                            loaded_embeddings_list.append(embedding_dict)
                        except (ValueError, TypeError):
                            pass # Log warning se necessário
            logger.info(f"{len(loaded_embeddings_list)} custos de embedding carregados.")
    except Exception as e:
        logger.error(f"Exceção ao carregar custos de embedding: {e}", exc_info=True)
    page.session.set(KEY_SESSION_MODEL_EMBEDDINGS_LIST, loaded_embeddings_list)

def _load_specific_cloud_defaults(page: ft.Page, user_token: str, doc_id: str) -> dict:
    """Carrega um documento de configurações específico do Firestore, com fallback local."""
    analysis_defaults = FALLBACK_ANALYSIS_SETTINGS.copy()
    defaults_doc_path = f"{APP_DEFAULT_SETTINGS_COLLECTION}/{doc_id}"
    try:
        response = firestore_client._make_firestore_request("GET", user_token, defaults_doc_path)
        if response.status_code == 200:
            fields = response.json().get("fields", {})
            if fields:
                raw_cloud_defaults = {k: _from_firestore_value(v) for k, v in fields.items()}
                logger.info(f"Configurações padrão carregadas do Firestore (doc: {doc_id}).")
                return raw_cloud_defaults # Retorna apenas os dados do Firestore
        else:
            logger.warning(f"Documento de defaults '{doc_id}' não encontrado ou erro ({response.status_code}). Retornando dict vazio.")
            return {}
    except Exception as e:
        logger.error(f"Exceção ao carregar defaults de '{doc_id}': {e}. Retornando dict vazio.", exc_info=True)
        return {}
    
    return {} # Retorna vazio em caso de falha, para que a base não seja sobrescrita por um fallback

def check_and_refresh_token_if_needed(page: ft.Page, force_refresh: bool = False) -> bool:
    """
    Verifica a validade e o tempo de vida de um ID token da sessão.

    Esta função é o ponto central para garantir uma sessão de usuário válida.
    1. Verifica criptograficamente o token atual (assinatura, emissor, audiência).
    2. Se o token for inválido por razões de segurança, encerra a sessão.
    3. Se o token for válido mas estiver prestes a expirar (ou `force_refresh` for True), tenta renová-lo.
    4. Se o token estiver apenas expirado, também tenta renová-lo.

    Args:
        page: A instância da página Flet.
        force_refresh: Se True, força a tentativa de renovação mesmo que o token pareça válido.

    Returns:
        True se, ao final do processo, a sessão contém um token válido.
        False se a validação falhar ou a renovação não for possível.
    """
    logger.debug("Verificando validade e necessidade de refresh do token.")
    id_token = page.session.get("auth_id_token")
    refresh_token_str = page.session.get("auth_refresh_token")

    if not id_token or not refresh_token_str:
        logger.debug("Não há token ou refresh token na sessão para validar/renovar.")
        return False

    auth_manager = FbManagerAuth()
    needs_refresh = force_refresh
    is_expired = False

    # Etapa 1: Verificação Criptográfica de Segurança
    try:
        auth_manager.verify_id_token(id_token)
        logger.debug("Token de ID verificado com sucesso (assinatura e claims válidos).")
    except jwt.ExpiredSignatureError:
        logger.warning("Token de ID está expirado. A renovação será necessária.")
        is_expired = True
        needs_refresh = True
    except (jwt.InvalidTokenError, Exception) as e:
        logger.error(f"Token de ID inválido por razões de segurança: {e}. Deslogando usuário.")
        show_snackbar(page, "Sessão inválida. Por favor, faça login novamente.", color=theme.COLOR_ERROR)
        handle_logout(page) # Função de logout que limpa tudo
        return False

    # Etapa 2: Verificação de Tempo de Vida (para refresh proativo)
    if not needs_refresh: # Só faz essa checagem se o token não estiver já marcado para refresh
        expires_at = page.session.get("auth_id_token_expires_at")
        if expires_at and time.time() >= float(expires_at) - (5 * 60): # 5 min de buffer
            logger.info("Token de ID próximo da expiração. Tentando refresh proativo.")
            needs_refresh = True
        elif not expires_at:
             logger.warning("Timestamp de expiração do token não encontrado. Tentando refresh por precaução.")
             needs_refresh = True

    if not needs_refresh:
        logger.debug("Token de ID ainda é válido e não precisa de refresh.")
        return True

    # Etapa 3: Execução da Renovação
    logger.info(f"Solicitando renovação do ID Token (Motivo: Expirado={is_expired}, Forçado={force_refresh}).")
    new_token_data = auth_manager.refresh_id_token(refresh_token_str)

    if new_token_data and new_token_data.get("id_token"):
        new_id_token = new_token_data["id_token"]
        new_refresh_token = new_token_data["refresh_token"]
        new_expires_in = int(new_token_data.get("expires_in", 3600))
        new_expires_at = time.time() + new_expires_in - 60

        logger.info("ID Token renovado com sucesso.")
        page.session.set("auth_id_token", new_id_token)
        page.session.set("auth_refresh_token", new_refresh_token)
        page.session.set("auth_id_token_expires_at", new_expires_at)
        
        try: 
            if page.client_storage and page.client_storage.contains_key("auth_refresh_token"):
                page.client_storage.set("auth_id_token", new_id_token)
                page.client_storage.set("auth_refresh_token", new_refresh_token)
                page.client_storage.set("auth_id_token_expires_at", new_expires_at)
                logger.debug("Tokens atualizados também no client_storage.")
        except Exception:
            logger.debug("client_storage indisponível ao persistir tokens renovados (conexão encerrada).")                

        LoggerSetup.set_cloud_user_context(
            user_id=page.session.get("auth_user_id"),
            user_email=page.session.get("auth_user_email"),
        )

        return True
    else:
        logger.error("Falha ao renovar o ID Token. Deslogando usuário.")
        # Lógica de snackbar e logout (como na versão anterior)
        if isinstance(new_token_data, dict) and new_token_data.get("error_type") == "CONNECTION_ERROR":
            show_snackbar(page, "Erro de conexão ao tentar renovar sessão.", color=theme.COLOR_ERROR, duration=7000)
        elif isinstance(new_token_data, dict) and new_token_data.get("error_type") == "HTTP_ERROR" and new_token_data.get("status_code") == 400:
            show_snackbar(page, "Sua sessão expirou ou é inválida. Por favor, faça login novamente.", color=theme.COLOR_ERROR, duration=7000)
        else:
            show_snackbar(page, "Não foi possível renovar sua sessão. Você será desconectado.", color=theme.COLOR_ERROR, duration=7000)
        handle_logout(page)
        return False
    
# --- Nova Thread para Renovação Automática de Token ---
_token_refresh_thread_stop_event: Optional[threading.Event] = None
_token_refresh_thread_instance: Optional[threading.Thread] = None

def _proactive_token_refresh_loop(page_ref: ft.Page, stop_event: threading.Event, interval_seconds: int = 30 * 60):
    """
    Loop que tenta renovar o token de ID proativamente.
    Executado em uma thread separada.

    Args:
        page_ref: Referência para a instância da página Flet.
        stop_event: Evento de threading para sinalizar a parada do loop.
        interval_seconds: Intervalo em segundos entre as verificações de refresh.
    """
    logger.debug("Thread de renovação proativa de token iniciada.")
    
    while not stop_event.is_set():
        try:
            # Verifica se o usuário ainda está autenticado na sessão Flet
            if page_ref.session and page_ref.session.contains_key("auth_id_token"):
                logger.debug(f"Verificação proativa do token (intervalo: {interval_seconds}s).")

                if not check_and_refresh_token_if_needed(page_ref): # Passa a referência da página
                    logger.warning("Renovação proativa de token falhou ou usuário foi deslogado.")
            else:
                logger.debug("Usuário não autenticado na sessão. Pausando renovação proativa.")
        except Exception as e:
            logger.error(f"Erro na thread de renovação proativa de token: {e}", exc_info=True)
            # Evita que a thread morra por uma exceção inesperada.
        
        # Espera pelo intervalo ou até o evento de parada ser sinalizado
        stop_event.wait(interval_seconds) 

    logger.debug("Thread de renovação proativa de token terminando.")

def load_auth_state_from_storage(page: ft.Page):
    """
    Carrega o estado de autenticação do client_storage, valida a sessão e,
    se necessário, tenta renová-la.
    """
    # Apenas verifica a presença do refresh_token como indicador de uma sessão salva
    if not (page.client_storage and page.client_storage.contains_key("auth_refresh_token")):
        logger.debug("Nenhum estado de autenticação persistente (refresh token) encontrado.")
        return

    logger.debug("Estado de autenticação encontrado. Tentando restaurar e validar sessão...")

    # Passo 1: Carrega todos os dados do storage para a sessão.
    # A função check_and_refresh_token_if_needed irá operar sobre estes dados.
    page.session.set("auth_id_token", page.client_storage.get("auth_id_token"))
    page.session.set("auth_user_id", page.client_storage.get("auth_user_id"))
    #page.session.set("is_admin", page.client_storage.get("is_admin"))
    page.session.set("auth_refresh_token", page.client_storage.get("auth_refresh_token"))
    page.session.set("auth_id_token_expires_at", page.client_storage.get("auth_id_token_expires_at"))
    page.session.set("auth_user_email", page.client_storage.get("auth_user_email"))
    page.session.set("auth_display_name", page.client_storage.get("auth_display_name"))

    # Passo 2: Chama o orquestrador de validação e renovação.
    if check_and_refresh_token_if_needed(page):
        # Se retornou True, a sessão é válida (seja a original ou a renovada).
        final_id_token = page.session.get("auth_id_token")
        final_user_id = page.session.get("auth_user_id")
        final_user_email = page.session.get("auth_user_email") or "Sem Email"
        
        logger.info(f"[MONITORIA] Sessão ativa/restaurada para: {final_user_email} (ID: {final_user_id}).")

        # Carrega proativamente as chaves de API para a sessão restaurada.
        credentials_manager.load_and_cache_all_api_keys(page, firestore_client)

        # Passo 3: Configurações pós-restauração
        LoggerSetup.set_cloud_user_context(
            user_id=final_user_id,
            user_email=page.session.get("auth_user_email"),
        )
        logger.debug(f"Contexto do logger de nuvem restaurado para usuário {final_user_id}.")

        try:
            if not LoggerSetup._active_cloud_handler_instance:
                LoggerSetup.add_cloud_logging(
                    user_token_for_client=final_id_token,
                    user_id_for_client=final_user_id
                )
                logger.debug("Cloud logging (cliente) configurado após restaurar sessão.")
        except Exception as e_rcl:
            logger.error(f"Falha ao configurar cloud logging (cliente) após restaurar sessão: {e_rcl}")
    else:
        # Se retornou False, a sessão era inválida e a função já cuidou de deslogar o usuário.
        logger.warning("Falha ao restaurar a sessão a partir do client_storage. O usuário foi deslogado.")
        
def main(page: ft.Page, dev_mode: bool = DEV_MODE):
    """
    Função principal que configura e inicia a aplicação Flet.

    Args:
        page: A instância da página Flet.
        dev_mode: Se True, inicia a aplicação em modo de desenvolvimento com dados mockados.
    """
    app_start_time = perf_counter()
    logger.debug(f"{app_start_time:.4f}s - Função main() iniciada.")

    global _token_refresh_thread_stop_event, _token_refresh_thread_instance

    if dev_mode:
        logger.info(f"Aplicação Flet '{APP_TITLE}' v{APP_VERSION} iniciando em MODO DE DESENVOLVIMENTO (UI Test).")
    else:
        logger.debug(f"Aplicação Flet '{APP_TITLE}' v{APP_VERSION} iniciando com layout persistente...")

    page.title = APP_TITLE
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.horizontal_alignment = ft.CrossAxisAlignment.START
    page.window_favicon_url = f"/favicon.png?v={int(time.time())}"

    # --- Aplicar Temas ---
    page.theme = theme.APP_THEME
    page.dark_theme = theme.APP_DARK_THEME
    page.theme_mode = ft.ThemeMode.SYSTEM # .LIGHT

    if page.data is None:
        page.data = {}
    
    # RLock (e não Lock): o mesmo thread pode reentrar no lock legitimamente — por
    # exemplo, `page.add()` dentro de uma seção crítica dispara `did_mount()` das
    # views, que por sua vez atualizam seus próprios controles via safe_control_update.
    # Com Lock simples isso travaria a própria thread até o timeout.
    page.data["global_update_lock"] = threading.RLock()
    
    # Adiciona ao overlay uma única vez.
    page_file_picker = ft.FilePicker()
    page.overlay.append(page_file_picker)
    page.data["global_file_picker"] = page_file_picker

    page_snackbar = ft.SnackBar(content=ft.Text(""), show_close_icon=True, action_color=ft.Colors.WHITE) # Configurações padrão
    page.overlay.append(page_snackbar)
    page.data["global_snackbar"] = page_snackbar

    page_loading_text = ft.Text("", size=16, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER)
    page_loading_overlay = ft.Container(
        content=ft.Column(
            [
                ft.ProgressRing(),
                ft.Container(height=10),
                page_loading_text,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            tight=True,
        ),
        alignment=ft.alignment.center,
        expand=True,
        bgcolor=ft.Colors.with_opacity(0.5, ft.Colors.BLACK),
        visible=False # Começa invisível
    )
    page.overlay.append(page_loading_overlay)
    page.data["global_loading_overlay"] = page_loading_overlay
    page.data["global_loading_text"] = page_loading_text # Para fácil acesso à mensagem

    # --- Elementos Persistentes do Layout ---
    # AppBar será atualizada pelo router se o título precisar mudar,
    # mas a instância base pode ser criada aqui.
    app_bar = create_app_bar(page, APP_TITLE) # Título inicial

    # NavigationRail (a rota inicial será usada para definir o selected_index)
    # A rota atual pode ser "/" ou uma rota específica se o usuário recarregar a página.
    # Se a rota inicial for de login, a NavRail não deve ser mostrada.
    # Isso será tratado pelo router.
    initial_route = page.route if page.route and page.route != "/" else "/login" # "/home"
    navigation_rail = create_navigation_rail(page, initial_route)

    content_container = ft.Container(
        content=ft.Column( # Para centralizar o ProgressRing
            [ft.ProgressRing()],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True
        ),
        expand=True,
        padding=theme.PADDING_L # Padding geral para a área de conteúdo
    )

    # --- Layout Principal da Página ---
    # Limpa a página de qualquer configuração anterior (caso Flet reutilize a page)
    page.clean()
    page.appbar = app_bar
    # O conteúdo principal (Row com NavRail e content_container)
    # só será adicionado se a rota não for de login/signup.
    # O router cuidará disso.

    # --- Conectar o Roteador ---
    page.on_route_change = lambda route_event: route_change_content_only(
        page,
        app_bar, # Passa a app_bar para que o título possa ser atualizado
        navigation_rail,
        content_container,
        route_event.route
    )
    page.on_view_pop = None # Não usamos a pilha de views padrão com este layout

    with global_active_sessions_lock:
        global_active_sessions.add(page.session_id)
        logger.info(f"[MONITORIA] Nova sessão. Usuários conectados agora: {len(global_active_sessions)}")

    # --- Limpeza ao Fechar ---
    def on_disconnect(e):
        """
        Lida com a desconexão do cliente Flet.

        Limpa o contexto do logger, o cache do usuário e, crucialmente,
        encerra completamente o processo do servidor para evitar que ele
        continue rodando em segundo plano.
        """
        from SOURCE.utils import cleanup_old_temp_files, clear_user_cache
        from SOURCE.settings import UPLOAD_TEMP_DIR, ASSETS_DIR, WEB_TEMP_EXPORTS_SUBDIR 
        
        logger.info("Cliente desconectado ou aplicação Flet fechando...")

        # --- Bloco de Limpeza Manual ---
        try:
            if is_local_mode():
                from SOURCE.config_manager import set_final_keyring_proxy
                from SOURCE.logger.cloud_logger_handler import CloudLogHandler
                
                # 1. Limpeza do Keyring do Proxy
                logger.debug("Executando limpeza manual: set_final_keyring_proxy()")
                set_final_keyring_proxy()

            # 2. Limpeza de Arquivos Temporários
            temp_exports_path = os.path.join(ASSETS_DIR, WEB_TEMP_EXPORTS_SUBDIR)
            cleanup_old_temp_files(temp_exports_path)
            cleanup_old_temp_files(UPLOAD_TEMP_DIR)
            
            if is_local_mode():
                # 3. Flush e Encerramento SEGURO do Logger da Nuvem
                if LoggerSetup._active_cloud_handler_instance:
                    logger.debug("Executando desligamento completo do CloudLogHandler...")
                    CloudLogHandler._force_upload_on_exit_static(LoggerSetup._active_cloud_handler_instance)
            else:
                if LoggerSetup._active_cloud_handler_instance:
                    LoggerSetup._active_cloud_handler_instance.flush()
                # 3. Apenas faz FLUSH dos logs pendentes deste usuário (Não desliga o logger global!)
        
        except:
            pass
        ...
        LoggerSetup.set_cloud_user_context(None, None)
        logger.debug("Contexto do logger de nuvem limpo ao desconectar.")

        if is_local_mode():
            # Para a thread de renovação de token
            if _token_refresh_thread_stop_event:
                logger.debug("Sinalizando parada para a thread de renovação proativa de token...")
                _token_refresh_thread_stop_event.set()
            if _token_refresh_thread_instance and _token_refresh_thread_instance.is_alive():
                logger.debug("Aguardando thread de renovação de token finalizar...")
                _token_refresh_thread_instance.join(timeout=6) # Espera um pouco
                if _token_refresh_thread_instance.is_alive():
                    logger.warning("Thread de renovação de token não finalizou a tempo.")
        else:
            # Encerra apenas a thread de renovação DESTA aba específica
            stop_event = page.data.get("refresh_stop_event")
            if stop_event:
                stop_event.set()  

        user_email_disconnected = page.session.get("auth_user_email") or "Anônimo"                                  

        with global_active_sessions_lock:
            global_active_sessions.discard(page.session_id)
            logger.info(f"[MONITORIA] Sessão encerrada ({user_email_disconnected}). Usuários conectados agora: {len(global_active_sessions)}")

        clear_user_cache(page)

        # Pausa opcional para garantir que o flush tenha tempo de iniciar o upload
        # Em produção, pode não ser necessário, mas ajuda em depuração.
        time.sleep(1) 

        # Encerra o processo do servidor
        # logger.info("Encerrando o processo do servidor agora.")
        # os._exit(0)  # Força a saída imediata e limpa do processo Python

        # O encerramento do servidor agora é gerenciado pelo wrapper em run.py
        # para permitir a janela de tolerância de refresh.
        logger.info("Lógica de limpeza da sessão Flet concluída.")

    page.on_disconnect = on_disconnect

    def threaded_load_settings(target_page: ft.Page):
        """
        Função a ser executada em uma thread separada para carregar as configurações
        de análise padrão e de LLM para a sessão Flet.

        Args:
            target_page: A instância da página Flet para a qual as configurações serão carregadas.
        """
        local_start_time = perf_counter()
        logger.debug(f"{local_start_time:.4f}s - Função threaded_load_settings iniciada.")
        load_default_analysis_settings(target_page)
        logger.debug("Thread de settings concluída. Dados carregados na sessão.")
        logger.debug(f"{perf_counter() - local_start_time:.4f}s - Analysis settings carregado.")
        # Opcional: notificar a UI principal que os dados estão prontos, se necessário.
        # Ex: page.pubsub.send_all("settings_loaded")
    
    page.data["load_settings_func"] = threaded_load_settings

    def _preload_heavy_modules_in_background():
        """
        Executado em uma thread para pré-carregar módulos pesados e evitar
        delay no primeiro acesso às views de análise.
        """
        preload_start_time = perf_counter()
        logger.info("Thread de pré-carregamento de módulos pesados iniciada...")
        try:
            from SOURCE.core import ai_orchestrator, pdf_processor, doc_generator, chat_llm_orchestrator
            from SOURCE.flet_ui.views import nc_analyze_view, chat_view

            # A importação por si só já força o carregamento dos módulos e suas dependências.
            # Não é necessário instanciar as classes aqui.

            preload_time = perf_counter() - preload_start_time
            logger.info(f"Pré-carregamento de módulos pesados concluído em {preload_time:.2f}s.")
        except Exception as e:
            logger.error(f"Erro durante o pré-carregamento de módulos: {e}", exc_info=True)
        finally:
            # Sinaliza que o processo terminou, com ou sem sucesso, para não bloquear as views indefinidamente.
            app_cache.heavy_imports_loading_event.set()

    # --- Lógica de Inicialização Principal ---
    def initialize_app_flow():
        """
        Inicializa o fluxo principal da aplicação Flet.

        Carrega o estado de autenticação, as configurações de análise e LLM,
        e gerencia a navegação inicial com base no status de autenticação do usuário.
        Também inicia a thread de renovação proativa de token se o usuário estiver autenticado.
        """
        # Tenta carregar a sessão do client_storage. Esta é a primeira etapa.
        load_auth_state_from_storage(page)
        logger.debug(f"{perf_counter() - app_start_time:.4f}s - Auth state carregado em main.")

        # Verifica se, após a tentativa de restauração ou um novo login, existe um token válido.
        # Este é o ponto central que confirma uma sessão autenticada.        
        # Se autenticado, carrega as configurações em uma thread
        if page.session.contains_key("auth_id_token"):
            logger.debug("Usuário autenticado. Disparando carregamento de settings em background.")

            if not app_cache.heavy_imports_loading_event.is_set():
                logger.debug("Iniciando pré-carregamento de módulos pesados em background (modo local).")
                threading.Thread(target=_preload_heavy_modules_in_background, daemon=True).start()          
            
            threading.Thread(target=threaded_load_settings, args=(page,), daemon=True).start()
            
            # Inicia thread de renovação de token (isso já é non-blocking)
            if "refresh_thread" not in page.data or not page.data["refresh_thread"].is_alive():
                stop_event = threading.Event()
                page.data["refresh_stop_event"] = stop_event
                page.data["refresh_thread"] = threading.Thread(
                    target=_proactive_token_refresh_loop,
                    args=(page, stop_event),
                    daemon=True
                )
                page.data["refresh_thread"].start()            
            
            # Navega para a home imediatamente após verificar a autenticação
            final_route = "/home"
        else:
            logger.debug("Usuário não autenticado na inicialização, thread de renovação proativa não iniciada.")
            # Garante que as chaves de settings estejam com fallback
            if not page.session.contains_key(KEY_SESSION_NC_ANALYZE_SETTINGS):
                page.session.set(KEY_SESSION_CLOUD_ANALYSIS_DEFAULTS, FALLBACK_ANALYSIS_SETTINGS.copy())
                page.session.set(KEY_SESSION_NC_ANALYZE_SETTINGS, FALLBACK_ANALYSIS_SETTINGS.copy())
                chat_fallback_settings = FALLBACK_ANALYSIS_SETTINGS.copy()
                chat_fallback_settings["reasoning_effort"] = "minimal"  # Chat inicia com thinking desativado (nc_analyze mantém "low"/ativo)
                page.session.set(KEY_SESSION_CLOUD_CHAT_DEFAULTS, chat_fallback_settings.copy())
                page.session.set(KEY_SESSION_CHAT_SETTINGS, chat_fallback_settings)
            final_route = "/login"

        # Dispara a navegação inicial
        logger.debug(f"Disparando navegação inicial para: {final_route}")
        logger.debug(f"{perf_counter() - app_start_time:.4f}s - Navegação inicial page.go() em main a ser chamada.")
        page.go(final_route)

    if dev_mode:
        logger.info("DEV_MODE: Populando page.session com dados mockados.")
        page.session.set("auth_id_token", "mock_dev_id_token_abcdef123456")
        page.session.set("auth_user_id", "mock_dev_user_id_xyz789")
        page.session.set("auth_refresh_token", "mock_dev_refresh_token_ghi987")
        page.session.set("auth_id_token_expires_at", time.time() + 7200) # Mock válido por 2 horas
        page.session.set("auth_user_email", "dev.user@example.com")
        page.session.set("auth_display_name", "Usuário DEV")
        
        # Mock de chave API para OpenAI (exemplo para llm_settings_view e ai_orchestrator)
        # A chave no nome do serviço Firestore é `provider_config["service_name_firestore"]`
        # Para OpenAI, é "openai_api_key".
        # O provider_id é "OpenAI".
        # A session key é: f"decrypted_api_key_{self.provider_id}_{self.service_name_firestore}"
        # Para OpenAI: "decrypted_api_key_OpenAI_openai_api_key"
        page.session.set("decrypted_api_key_OpenAI_openai_api_key", "sk-mockDevKeyOpenAI12345")

        # Em dev_mode, não tentamos configurar o logger de nuvem real aqui,
        # pois o LoggerSetup em run_dev.py já é simplificado.
        LoggerSetup.set_cloud_user_context(
            user_id=page.session.get("auth_user_id"),
            user_email=page.session.get("auth_user_email"),
        )
        logger.info("DEV_MODE: Logger context set with mock data (cloud logging likely disabled by run_dev init).")

        initial_route = "/home" # Em dev_mode, assumimos que já está "logado" e vamos para home.
                                # O router ainda fará a checagem, mas is_user_authenticated retornará True
                                # devido ao token mockado na sessão.
    else:
        # Inicia o fluxo de inicialização. Ele cuidará da navegação.
        initialize_app_flow()  


execution_time = perf_counter() - start_time
logger.debug(f"Carregado APP.py em {execution_time:.4f}s")