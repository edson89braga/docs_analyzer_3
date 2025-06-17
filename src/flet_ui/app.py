# src/flet_ui/app.py

from time import perf_counter
start_time = perf_counter()
print(f"{start_time:.4f}s - Iniciando app.py")

import flet as ft
import time, os, threading
from typing import Dict, Any, Optional

from ..settings import (APP_TITLE, APP_VERSION, FLET_SECRET_KEY,
                        APP_DEFAULT_SETTINGS_COLLECTION, ANALYZE_PDF_DEFAULTS_DOC_ID,
                        KEY_SESSION_ANALYSIS_SETTINGS, KEY_SESSION_CLOUD_ANALYSIS_DEFAULTS,
                        FALLBACK_ANALYSIS_SETTINGS,
                        LLM_PROVIDERS_CONFIG_COLLECTION, LLM_PROVIDERS_DEFAULT_DOC_ID, 
                        KEY_SESSION_LOADED_LLM_PROVIDERS, KEY_SESSION_USER_LLM_PREFERENCES, 
                        USER_LLM_PREFERENCES_COLLECTION,
                        LLM_EMBEDDINGS_CONFIG_COLLECTION, LLM_EMBEDDINGS_DEFAULT_DOC_ID, 
                        KEY_SESSION_MODEL_EMBEDDINGS_LIST)

from .layout import show_snackbar, create_app_bar, create_navigation_rail, handle_logout
#from .components import ...
from .router import route_change_content_only 
from . import theme
error_color = theme.COLOR_ERROR if hasattr(theme, 'COLOR_ERROR') else ft.colors.RED

from src.services.firebase_client import FbManagerAuth, FirebaseClientFirestore, _from_firestore_value

# Importa o logger
from src.logger.logger import LoggerSetup
logger = LoggerSetup.get_logger(__name__)


def load_default_analysis_settings(page: ft.Page):
    """
    Carrega as configurações padrão de análise do Firestore para a sessão,
    incluindo a lista de provedores LLM e as preferências do usuário,
    que podem sobrepor os defaults.
    """
    logger.info("Carregando configurações de LLM (provedores, defaults e preferências do usuário)...")
    firestore_client = FirebaseClientFirestore()
    user_token = page.session.get("auth_id_token")
    user_id = page.session.get("auth_user_id")

    if not user_token or not user_id:
        logger.warning("load_default_analysis_settings: Token/ID de usuário não encontrado. Usando fallbacks.")
        page.session.set(KEY_SESSION_LOADED_LLM_PROVIDERS, []) # Lista vazia de provedores
        page.session.set(KEY_SESSION_USER_LLM_PREFERENCES, {}) # Prefs vazias
        page.session.set(KEY_SESSION_CLOUD_ANALYSIS_DEFAULTS, FALLBACK_ANALYSIS_SETTINGS.copy())
        page.session.set(KEY_SESSION_ANALYSIS_SETTINGS, FALLBACK_ANALYSIS_SETTINGS.copy())
        return

    # 1. Carregar Lista de Provedores LLM (Configuração Global)
    loaded_providers_list = []
    providers_doc_path = f"{LLM_PROVIDERS_CONFIG_COLLECTION}/{LLM_PROVIDERS_DEFAULT_DOC_ID}"
    try:
        response_providers = firestore_client._make_firestore_request("GET", user_token, providers_doc_path)
        if response_providers.status_code == 200:
            providers_doc_data = response_providers.json()
            providers_array_fs = providers_doc_data.get("fields", {}).get("all_providers", {}).get("arrayValue", {}).get("values", [])
            if providers_array_fs:
                # Cada item em providers_array_fs é um mapValue que precisa ser convertido
                for provider_map_fs in providers_array_fs:
                    if "mapValue" in provider_map_fs:
                        provider_dict = _from_firestore_value(provider_map_fs)
                        if isinstance(provider_dict, dict):
                            loaded_providers_list.append(provider_dict)
                logger.info(f"{len(loaded_providers_list)} provedores LLM carregados do Firestore.")
            else:
                logger.warning(f"Documento de provedores LLM '{providers_doc_path}' não contém 'all_providers' ou está vazio.")
        elif response_providers.status_code == 404:
            logger.warning(f"Documento de configuração de provedores LLM '{providers_doc_path}' não encontrado.")
        else:
            logger.error(f"Erro ao carregar provedores LLM: {response_providers.status_code} - {response_providers.text}")
    except Exception as e_prov:
        logger.error(f"Exceção ao carregar provedores LLM: {e_prov}", exc_info=True)
    page.session.set(KEY_SESSION_LOADED_LLM_PROVIDERS, loaded_providers_list)

    # NOVO: 1.B. Carregar Lista de Custos de Modelos de Embedding
    loaded_embeddings_list = []
    embeddings_doc_path = f"{LLM_EMBEDDINGS_CONFIG_COLLECTION}/{LLM_EMBEDDINGS_DEFAULT_DOC_ID}" # Reutiliza a coleção, mas doc ID diferente
    try:
        response_embeddings = firestore_client._make_firestore_request("GET", user_token, embeddings_doc_path)
        if response_embeddings.status_code == 200:
            embeddings_doc_data = response_embeddings.json()
            # Supondo que o documento tem um campo 'embeddings_costs' que é um array de maps
            embeddings_array_fs = embeddings_doc_data.get("fields", {}).get("all_models", {}).get("arrayValue", {}).get("values", [])
            if embeddings_array_fs:
                for embedding_map_fs in embeddings_array_fs:
                    if "mapValue" in embedding_map_fs:
                        embedding_dict = _from_firestore_value(embedding_map_fs)
                        if isinstance(embedding_dict, dict) and "name" in embedding_dict and "coust_per_million" in embedding_dict:
                            try: # Garante que o custo seja float
                                embedding_dict["coust_per_million"] = float(embedding_dict["coust_per_million"])
                                loaded_embeddings_list.append(embedding_dict)
                            except (ValueError, TypeError):
                                logger.warning(f"Custo inválido para embedding '{embedding_dict.get('name')}'. Pulando.")
                logger.info(f"{len(loaded_embeddings_list)} configurações de custo de embedding carregadas.")
            else:
                logger.warning(f"Documento de custos de embedding '{embeddings_doc_path}' não contém 'all_models' ou está vazio.")
        elif response_embeddings.status_code == 404:
            logger.warning(f"Documento de custos de embedding '{embeddings_doc_path}' não encontrado.")
        else:
            logger.error(f"Erro ao carregar custos de embedding: {response_embeddings.status_code} - {response_embeddings.text}")
    except Exception as e_emb:
        logger.error(f"Exceção ao carregar custos de embedding: {e_emb}", exc_info=True)
    page.session.set(KEY_SESSION_MODEL_EMBEDDINGS_LIST, loaded_embeddings_list)

    # 2. Carregar Preferências de LLM do Usuário
    user_llm_preferences = {}
    user_prefs_doc_path = f"{USER_LLM_PREFERENCES_COLLECTION}/{user_id}"
    try:
        response_prefs = firestore_client._make_firestore_request("GET", user_token, user_prefs_doc_path)
        if response_prefs.status_code == 200:
            prefs_doc_data = response_prefs.json()
            fields = prefs_doc_data.get("fields", {})
            if fields:
                user_llm_preferences = {k: _from_firestore_value(v) for k, v in fields.items()}
                logger.info(f"Preferências de LLM do usuário '{user_id}' carregadas: {user_llm_preferences}")
        elif response_prefs.status_code == 404:
            logger.info(f"Nenhuma preferência de LLM salva para o usuário '{user_id}'.")
        else:
            logger.error(f"Erro ao carregar preferências de LLM do usuário: {response_prefs.status_code} - {response_prefs.text}")
    except Exception as e_prefs:
        logger.error(f"Exceção ao carregar preferências de LLM do usuário: {e_prefs}", exc_info=True)
    page.session.set(KEY_SESSION_USER_LLM_PREFERENCES, user_llm_preferences)

    # 3. Carregar Configurações Padrão de Análise (analyze_pdf_defaults)
    analysis_defaults = FALLBACK_ANALYSIS_SETTINGS.copy() # Começa com o fallback local
    defaults_doc_path = f"{APP_DEFAULT_SETTINGS_COLLECTION}/{ANALYZE_PDF_DEFAULTS_DOC_ID}"
    try:
        response_defaults = firestore_client._make_firestore_request("GET", user_token, defaults_doc_path)
        if response_defaults.status_code == 200:
            defaults_data = response_defaults.json()
            fields = defaults_data.get("fields", {})
            if fields:
                raw_cloud_defaults = {k: _from_firestore_value(v) for k, v in fields.items()}
                # Mescla com fallback para garantir todos os campos e tipos corretos
                for key, fallback_value in FALLBACK_ANALYSIS_SETTINGS.items():
                    cloud_value = raw_cloud_defaults.get(key)
                    if cloud_value is not None:
                        try:
                            if isinstance(fallback_value, int): analysis_defaults[key] = int(cloud_value)
                            elif isinstance(fallback_value, float): analysis_defaults[key] = float(cloud_value)
                            else: analysis_defaults[key] = cloud_value # Assume string ou bool
                        except (ValueError, TypeError):
                            logger.warning(f"Valor inválido para '{key}' em defaults da nuvem, usando fallback local.")
                            analysis_defaults[key] = fallback_value # Mantém o do fallback local
                    # Se cloud_value for None, o valor do FALLBACK_ANALYSIS_SETTINGS já está em analysis_defaults
                logger.info("Configurações padrão de análise (defaults) carregadas do Firestore.")
            else:
                logger.warning(f"Documento de defaults '{defaults_doc_path}' vazio. Usando fallbacks locais.")
        elif response_defaults.status_code == 404:
            logger.warning(f"Documento de defaults '{defaults_doc_path}' não encontrado. Usando fallbacks locais.")
        else:
            logger.error(f"Erro ao carregar defaults de análise: {response_defaults.status_code} - {response_defaults.text}. Usando fallbacks locais.")
    except Exception as e_def:
        logger.error(f"Exceção ao carregar defaults de análise: {e_def}. Usando fallbacks locais.", exc_info=True)
    
    page.session.set(KEY_SESSION_CLOUD_ANALYSIS_DEFAULTS, analysis_defaults.copy())

    # 4. Aplicar Preferências do Usuário sobre os Defaults de Análise
    final_analysis_settings = analysis_defaults.copy() # Começa com os defaults (da nuvem ou fallback)
    pref_provider = user_llm_preferences.get("default_provider_system_name")
    pref_model = user_llm_preferences.get("default_model_id")

    if pref_provider and loaded_providers_list: # Se há preferência de provedor e provedores carregados
        # Valida se o provedor preferido existe na lista carregada
        chosen_provider_config = next((p for p in loaded_providers_list if p.get("system_name") == pref_provider), None)
        if chosen_provider_config:
            final_analysis_settings["llm_provider"] = pref_provider
            logger.info(f"Preferência de provedor do usuário ('{pref_provider}') aplicada.")
            if pref_model:
                # Valida se o modelo preferido existe para o provedor escolhido
                chosen_model_config = next((m for m in chosen_provider_config.get("models", []) if m.get("id") == pref_model), None)
                if chosen_model_config:
                    final_analysis_settings["llm_model"] = pref_model
                    logger.info(f"Preferência de modelo do usuário ('{pref_model}') aplicada.")
                else:
                    logger.warning(f"Modelo LLM preferido ('{pref_model}') não encontrado para o provedor '{pref_provider}'. Verificando primeiro modelo do provedor.")
                    if chosen_provider_config.get("models"): # Se o provedor tem modelos
                        first_model_id = chosen_provider_config["models"][0].get("id")
                        if first_model_id:
                            final_analysis_settings["llm_model"] = first_model_id
                            logger.info(f"Usando o primeiro modelo ('{first_model_id}') do provedor '{pref_provider}' como fallback.")
                        else: # Primeiro modelo do provedor não tem ID
                            logger.warning(f"Primeiro modelo do provedor '{pref_provider}' não tem ID. Mantendo modelo dos defaults globais.")
                    # Se não, mantém o modelo dos defaults globais
            # else: Se não há pref_model, mantém o modelo dos defaults globais
        else:
            logger.warning(f"Provedor LLM preferido ('{pref_provider}') não encontrado na lista de provedores carregados. Mantendo provedor dos defaults globais.")
    # else: Se não há pref_provider, mantém as configurações de llm_provider e llm_model dos defaults globais.

    page.session.set(KEY_SESSION_ANALYSIS_SETTINGS, final_analysis_settings)
    logger.info(f"Configurações finais de análise (KEY_SESSION_ANALYSIS_SETTINGS) definidas na sessão: {final_analysis_settings}")

def check_and_refresh_token_if_needed(page: ft.Page, force_refresh: bool = False) -> bool:
    """
    Verifica se o ID token precisa ser atualizado e tenta atualizá-lo.
    Retorna True se o token estiver válido (ou foi atualizado), False caso contrário (ex: refresh falhou).
    """
    # _logger_app.debug("Verificando necessidade de refresh do token.") # Use o logger apropriado
    current_logger = LoggerSetup.get_logger("auth_token_refresh") # Logger específico

    id_token = page.session.get("auth_id_token")
    refresh_token_str = page.session.get("auth_refresh_token")
    expires_at = page.session.get("auth_id_token_expires_at")

    if not id_token or not refresh_token_str:
        current_logger.debug("Não há token ou refresh token na sessão para verificar.")
        return False # Não há token para validar/refrescar

    # Verifica se o token expirou ou está prestes a expirar (ex: nos próximos 5 minutos)
    # O expires_at já tem um buffer de 60s. Podemos usar um buffer menor aqui para a verificação.
    needs_refresh = force_refresh
    if expires_at:
        if time.time() >= float(expires_at) - (5 * 60): # 5 minutos de buffer adicional
            needs_refresh = True
            current_logger.info(f"ID Token próximo da expiração (ou expirado: {time.time()} >= {float(expires_at) - (5*60)}). Tentando refresh.")
    else: # Se não há timestamp de expiração, considera que precisa de refresh por segurança
        needs_refresh = True
        current_logger.warning("Timestamp de expiração do ID Token não encontrado. Tentando refresh por precaução.")

    if not needs_refresh:
        current_logger.debug("ID Token ainda é considerado válido. Nenhum refresh necessário no momento.")
        return True

    auth_manager = FbManagerAuth()
    current_logger.info(f"Solicitando refresh do ID Token para user {page.session.get('auth_user_id')}.")
    
    new_token_data = auth_manager.refresh_id_token(refresh_token_str)

    if new_token_data and new_token_data.get("id_token"):
        new_id_token = new_token_data["id_token"]
        new_refresh_token = new_token_data["refresh_token"] # API sempre retorna um, pode ser o mesmo ou novo
        new_expires_in = int(new_token_data.get("expires_in", 3600))
        new_expires_at = time.time() + new_expires_in - 60 # -60s de buffer

        current_logger.info("ID Token atualizado com sucesso via refresh token.")
        page.session.set("auth_id_token", new_id_token)
        page.session.set("auth_refresh_token", new_refresh_token)
        page.session.set("auth_id_token_expires_at", new_expires_at)
        
        # Atualiza também no client_storage se estava lá originalmente
        if page.client_storage and page.client_storage.contains_key("auth_refresh_token"):
            page.client_storage.set("auth_id_token", new_id_token)
            page.client_storage.set("auth_refresh_token", new_refresh_token)
            page.client_storage.set("auth_id_token_expires_at", new_expires_at)
            current_logger.debug("Tokens atualizados também no client_storage.")
        
        # Atualiza contexto do logger de nuvem com o novo token
        LoggerSetup.set_cloud_user_context(new_id_token, page.session.get("auth_user_id"))
        return True
    else:
        current_logger.error("Falha ao atualizar ID Token.")
        if isinstance(new_token_data, dict) and new_token_data.get("error_type") == "CONNECTION_ERROR":
            show_snackbar(page, "Erro de conexão ao tentar renovar sessão. Verifique sua internet/proxy.", color=theme.COLOR_ERROR, duration=7000)
        elif isinstance(new_token_data, dict) and new_token_data.get("error_type") == "HTTP_ERROR" and new_token_data.get("status_code") == 400: # Exemplo de erro específico
            show_snackbar(page, "Sua sessão expirou ou é inválida. Por favor, faça login novamente.", color=theme.COLOR_ERROR, duration=7000)
        else:
            show_snackbar(page, "Não foi possível renovar sua sessão. Você será desconectado.", color=theme.COLOR_ERROR, duration=7000)
        handle_logout(page)
        return False

# --- Nova Thread para Renovação Automática de Token ---
_token_refresh_thread_stop_event: Optional[threading.Event] = None
_token_refresh_thread_instance: Optional[threading.Thread] = None

def _proactive_token_refresh_loop(page_ref: ft.Page, stop_event: threading.Event, interval_seconds: int = 30 * 60): # a cada 30 minutos
    """
    Loop que tenta renovar o token de ID proativamente.
    Executado em uma thread separada.
    """
    loop_logger = LoggerSetup.get_logger("proactive_token_refresh") # Logger específico
    loop_logger.info("Thread de renovação proativa de token iniciada.")
    
    while not stop_event.is_set():
        try:
            # Verifica se o usuário ainda está autenticado na sessão Flet
            if page_ref.session and page_ref.session.contains_key("auth_id_token"):
                loop_logger.debug(f"Verificação proativa do token (intervalo: {interval_seconds}s).")

                if not check_and_refresh_token_if_needed(page_ref): # Passa a referência da página
                    loop_logger.warning("Renovação proativa falhou ou usuário foi deslogado.")
            else:
                loop_logger.debug("Usuário não autenticado na sessão. Pausando renovação proativa.")
        except Exception as e:
            loop_logger.error(f"Erro na thread de renovação proativa de token: {e}", exc_info=True)
            # Evita que a thread morra por uma exceção inesperada.
        
        # Espera pelo intervalo ou até o evento de parada ser sinalizado
        stop_event.wait(interval_seconds) 

    loop_logger.info("Thread de renovação proativa de token terminando.")

def load_auth_state_from_storage(page: ft.Page):
    """
    Carrega o estado de autenticação do client_storage (se "Lembrar de mim" foi usado)
    para a sessão Flet da página atual.
    """
    if page.client_storage and page.client_storage.contains_key("auth_id_token"):
        logger.info("Restaurando estado de autenticação do client_storage para a sessão Flet.")
        # Pega todos os valores do client_storage e define na sessão
        id_token = page.client_storage.get("auth_id_token")
        user_id = page.client_storage.get("auth_user_id")
        refresh_token = page.client_storage.get("auth_refresh_token") 
        id_token_expires_at = page.client_storage.get("auth_id_token_expires_at")
        user_email = page.client_storage.get("auth_user_email")
        display_name = page.client_storage.get("auth_display_name")

        if id_token and user_id: # Garante que os dados essenciais existem
            page.session.set("auth_id_token", id_token)
            page.session.set("auth_user_id", user_id)
            if refresh_token: 
                page.session.set("auth_refresh_token", refresh_token)
            if id_token_expires_at: 
                page.session.set("auth_id_token_expires_at", id_token_expires_at)
            if user_email: # Email e display name são opcionais no client_storage
                 page.session.set("auth_user_email", user_email)
            if display_name:
                 page.session.set("auth_display_name", display_name)
            
            LoggerSetup.set_cloud_user_context(id_token, user_id)

            # TENTA ADICIONAR CLOUD LOGGING AQUI
            try:
                if not LoggerSetup._active_cloud_handler_instance:
                    LoggerSetup.add_cloud_logging(
                        user_token_for_client=id_token,
                        user_id_for_client=user_id
                    )
                    logger.info("Cloud logging (cliente) configurado após restaurar sessão.")
            except Exception as e_rcl:
                logger.error(f"Falha ao configurar cloud logging (cliente) após restaurar sessão: {e_rcl}")

            logger.info(f"Contexto do logger de nuvem restaurado para usuário {user_id} do client_storage.")
            # Verificar e tentar refresh se o token estiver perto de expirar ao carregar
            check_and_refresh_token_if_needed(page) # Chamada para nova função (ver abaixo)
        else:
            logger.warning("Dados de autenticação no client_storage estavam incompletos. Não restaurados para a sessão.")
            # Opcional: Limpar chaves incompletas do client_storage aqui
            page.client_storage.remove("auth_id_token") # etc.
    else:
        logger.info("Nenhum estado de autenticação persistente encontrado no client_storage.")


def main(page: ft.Page, dev_mode: bool = False): 
    app_start_time = perf_counter()
    logger.info(f"{app_start_time:.4f}s - Função main() iniciada.")

    global _token_refresh_thread_stop_event, _token_refresh_thread_instance

    # Para uploads no modo web, Flet precisa de FLET_SECRET_KEY e upload_dir
    if not os.getenv("FLET_SECRET_KEY"):
        os.environ["FLET_SECRET_KEY"] = FLET_SECRET_KEY

    if dev_mode:
        logger.info(f"Aplicação Flet '{APP_TITLE}' v{APP_VERSION} iniciando em MODO DE DESENVOLVIMENTO (UI Test).")
    else:
        logger.info(f"Aplicação Flet '{APP_TITLE}' v{APP_VERSION} iniciando com layout persistente...")

    page.title = APP_TITLE
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.horizontal_alignment = ft.CrossAxisAlignment.START

    # --- Aplicar Temas ---
    page.theme = theme.APP_THEME
    page.dark_theme = theme.APP_DARK_THEME
    page.theme_mode = ft.ThemeMode.LIGHT # .SYSTEM

    if page.data is None:
        page.data = {}
        
    # Adiciona ao overlay uma única vez.
    page_file_picker = ft.FilePicker()
    page.overlay.append(page_file_picker)
    page.data["global_file_picker"] = page_file_picker

    page_snackbar = ft.SnackBar(content=ft.Text(""), show_close_icon=True, action_color=ft.colors.WHITE) # Configurações padrão
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
        bgcolor=ft.colors.with_opacity(0.5, ft.colors.BLACK),
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

    # --- Limpeza ao Fechar ---
    def on_disconnect(e):
        logger.info("Cliente desconectado ou aplicação Flet fechando...")
        LoggerSetup.set_cloud_user_context(None, None)
        logger.info("Contexto do logger de nuvem limpo ao desconectar.")

        # Para a thread de renovação de token
        if _token_refresh_thread_stop_event:
            logger.info("Sinalizando parada para a thread de renovação proativa de token...")
            _token_refresh_thread_stop_event.set()
        if _token_refresh_thread_instance and _token_refresh_thread_instance.is_alive():
            logger.debug("Aguardando thread de renovação de token finalizar...")
            _token_refresh_thread_instance.join(timeout=5) # Espera um pouco
            if _token_refresh_thread_instance.is_alive():
                logger.warning("Thread de renovação de token não finalizou a tempo.")
        
        from src.flet_ui.views.nc_analyze_view import clear_user_cache
        clear_user_cache(page)

    page.on_disconnect = on_disconnect

    def threaded_load_settings(target_page: ft.Page):
        """Função a ser executada em uma thread para carregar settings."""
        local_start_time = perf_counter()
        logger.info(f"{local_start_time:.4f}s - Função Load_settings iniciada.")
        logger.info("Thread de settings iniciada.")
        load_default_analysis_settings(target_page)
        logger.info("Thread de settings concluída. Dados carregados na sessão.")
        logger.info(f"{perf_counter() - local_start_time:.4f}s - Analysis settings carregado.")
        # Opcional: notificar a UI principal que os dados estão prontos, se necessário.
        # Ex: page.pubsub.send_all("settings_loaded")

    # --- Lógica de Inicialização Principal ---
    def initialize_app_flow():
        """Função que executa a lógica de inicialização, incluindo chamadas de rede."""
        load_auth_state_from_storage(page)
        logger.info(f"{perf_counter() - app_start_time:.4f}s - Auth state carregado.")
        
        # Se autenticado, carrega as configurações em uma thread
        if page.session.contains_key("auth_id_token"):
            logger.info("Usuário autenticado. Disparando carregamento de settings em background.")
            threading.Thread(target=threaded_load_settings, args=(page,), daemon=True).start()
            
            # Inicia thread de renovação de token (isso já é non-blocking)
            global _token_refresh_thread_instance, _token_refresh_thread_stop_event
            if _token_refresh_thread_instance is None or not _token_refresh_thread_instance.is_alive():
                _token_refresh_thread_stop_event = threading.Event()
                _token_refresh_thread_instance = threading.Thread(
                    target=_proactive_token_refresh_loop,
                    args=(page, _token_refresh_thread_stop_event),
                    daemon=True
                )
                _token_refresh_thread_instance.start()
            
            # Navega para a home imediatamente após verificar a autenticação
            final_route = "/home"
        else:
            logger.info("Usuário não autenticado na inicialização, thread de renovação proativa não iniciada.")
            # Garante que as chaves de settings estejam com fallback
            if not page.session.contains_key(KEY_SESSION_ANALYSIS_SETTINGS):
                page.session.set(KEY_SESSION_CLOUD_ANALYSIS_DEFAULTS, FALLBACK_ANALYSIS_SETTINGS.copy())
                page.session.set(KEY_SESSION_ANALYSIS_SETTINGS, FALLBACK_ANALYSIS_SETTINGS.copy())
            final_route = "/login"

        # Dispara a navegação inicial
        logger.info(f"Disparando navegação inicial para: {final_route}")
        logger.info(f"{perf_counter() - app_start_time:.4f}s - Navegação inicial page.go() será chamada.")
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
        LoggerSetup.set_cloud_user_context( # Apenas para que o logger não falhe se tentar usar
            page.session.get("auth_id_token"),
            page.session.get("auth_user_id")
        )
        logger.info("DEV_MODE: Logger context set with mock data (cloud logging likely disabled by run_dev init).")

        initial_route = "/home" # Em dev_mode, assumimos que já está "logado" e vamos para home.
                                # O router ainda fará a checagem, mas is_user_authenticated retornará True
                                # devido ao token mockado na sessão.
    else:
        # Inicia o fluxo de inicialização. Ele cuidará da navegação.
        initialize_app_flow()  



execution_time = perf_counter() - start_time
print(f"Carregado APP.py em {execution_time:.4f}s")
