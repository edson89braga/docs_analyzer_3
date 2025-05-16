# src/flet_ui/app.py
import flet as ft
import time, os
from typing import Dict, Any

from ..settings import APP_TITLE, APP_VERSION, FLET_SECRET_KEY

from .layout import create_app_bar, create_navigation_rail
#from .components import ...
from .router import route_change_content_only 
from . import theme
error_color = theme.COLOR_ERROR if hasattr(theme, 'COLOR_ERROR') else ft.colors.RED

from src.services.firebase_client import FbManagerAuth

# Importa o logger
from src.logger.logger import LoggerSetup
logger = LoggerSetup.get_logger(__name__)


# Função para carregar o estado de autenticação (exemplo)
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
        current_logger.error("Falha ao atualizar ID Token. O usuário pode precisar logar novamente.")
        # O refresh token pode ter expirado ou sido revogado.
        # Limpar todos os tokens para forçar novo login.
        from src.flet_ui.layout import handle_logout # Importação tardia e local
        handle_logout(page) # Força logout
        return False
    
def main(page: ft.Page, dev_mode: bool = False): 
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
    global_file_picker = ft.FilePicker()
    page.overlay.append(global_file_picker)
    page.data["global_file_picker"] = global_file_picker

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
        load_auth_state_from_storage(page)
        # A função check_and_refresh_token_if_needed já é chamada dentro de load_auth_state_from_storage
        # e também é chamada por _execute_sensitive_action em FbManagerAuth.
        # Não precisa chamar aqui explicitamente fora do dev_mode, a menos que haja um novo requisito.

    # --- Limpeza ao Fechar ---
    def on_disconnect(e):
        logger.info("Cliente desconectado ou aplicação Flet fechando...")
        LoggerSetup.set_cloud_user_context(None, None)
        logger.info("Contexto do logger de nuvem limpo ao desconectar.")
    page.on_disconnect = on_disconnect

    # --- Navegar para a Rota Inicial ---
    # O router agora lida com o redirecionamento para /login se não autenticado.
    logger.info(f"Disparando navegação inicial para: {initial_route}")
    page.go(initial_route) # Dispara o on_route_change

    # Para uploads no modo web, Flet precisa de FLET_SECRET_KEY e upload_dir
    if not os.getenv("FLET_SECRET_KEY"):
        os.environ["FLET_SECRET_KEY"] = FLET_SECRET_KEY

def OLD_main(page: ft.Page):
    '''
    Este modelo baseado em ft.View empilhadas foi substituído por um modelo de "Single Page Application (SPA)" acima;
    '''
    app_router = None
    logger.info(f"Aplicação Flet '{APP_TITLE}' v{APP_VERSION} iniciando...")
    page.title = APP_TITLE
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.horizontal_alignment = ft.CrossAxisAlignment.START

    # --- Aplicar Temas ---
    page.theme = theme.APP_THEME
    page.dark_theme = theme.APP_DARK_THEME
    page.theme_mode = ft.ThemeMode.SYSTEM
    
    # Tenta carregar o estado de autenticação persistido
    load_auth_state_from_storage(page)

    # --- Conectar o Roteador ---
    page.on_route_change = lambda route_event: app_router(page, route_event.route)
    
    # --- Limpeza ao Fechar ---
    def on_disconnect(e):
        logger.info("Cliente desconectado ou aplicação Flet fechando...")
        # Limpar contexto do logger de nuvem ao desconectar
        LoggerSetup.set_cloud_user_context(None, None)
        logger.info("Contexto do logger de nuvem limpo ao desconectar.")
        # ... (outras limpezas como fechar sessão DB, se houver) ...

    page.on_disconnect = on_disconnect
    
    # --- Navegar para a Rota Inicial ---
    # O router agora lida com o redirecionamento para /login se não autenticado.
    # Se a rota for / ou vazia, o router pode decidir para onde ir (ex: /home se logado, /login se não).
    initial_route = page.route
    if not initial_route or initial_route == "/":
        # O app_router decidirá se vai para /login ou /home baseado na autenticação
        initial_route = "/home" # Ou deixe o router decidir implicitamente indo para "/"
                                 # e sendo redirecionado.
                                 # Mas page.go("/") pode ser mais explícito.

    logger.info(f"Disparando navegação inicial para: {initial_route}")
    page.go(initial_route) # Dispara o on_route_change
