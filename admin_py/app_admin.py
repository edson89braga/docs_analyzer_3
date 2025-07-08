# admin_py/app_admin.py
import logging
logger = logging.getLogger(__name__)

from time import perf_counter
start_time = perf_counter()
logger.info(f"[DEBUG] {start_time:.4f}s - Iniciando app_admin.py")

import flet as ft
import sys, os, json, threading, re
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, date

# --- Configuração de Path para importações corretas ---
# Adiciona o diretório raiz ao path para encontrar os pacotes 'src' e 'admin_py'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# --- Imports da Aplicação Principal e Admin ---
from src.logger.logger import LoggerSetup
from src.flet_ui.layout import create_app_bar, create_navigation_rail
from src.flet_ui.router import route_change_content_only 

from src.flet_ui.components import (
    show_snackbar, CardWithHeader, show_loading_overlay, hide_loading_overlay, wrapper_cotainer_1
)
from src.flet_ui import theme
from src.services.firebase_manager import (
    inicializar_firebase, FbManagerFirestore, FbManagerStorage, FbManagerAdminAuth
)

# Importa as funções refatoradas dos scripts administrativos
from admin_py.set_admin import set_user_admin_status
from admin_py.admin_llm_providers import (
    read_providers_from_firestore, 
    write_providers_to_firestore
)
from admin_py.upload_prompts import upload_prompt_templates
from admin_py.cleanup_cloud_logs import run_cloud_log_cleanup
from admin_py.local_data_manager import get_available_users, get_filtered_logs, ADMIN_DATA_DIR, ADMIN_METRICS_DIR
from admin_py.export_data import process_filtered_data_for_export, export_data_to_excel

from src.settings import CLOUD_LOGGER_FOLDER

TITLE_GUI = "Painel Administrativo - IA Assistente"

# --- Infraestrutura de Roteamento e Layout Específica do Admin ---

# Define os destinos de navegação para o painel de admin
ADMIN_NAV_DESTINATIONS = [
    {"label": "Dashboard", "icon": ft.Icons.DASHBOARD_OUTLINED, "selected_icon": ft.Icons.DASHBOARD, "route": "/admin/dashboard"},
    {"label": "Dados & Logs", "icon": ft.Icons.STORAGE_OUTLINED, "selected_icon": ft.Icons.STORAGE, "route": "/admin/data"},
    {"label": "Usuários", "icon": ft.Icons.SUPERVISED_USER_CIRCLE_OUTLINED, "selected_icon": ft.Icons.SUPERVISED_USER_CIRCLE, "route": "/admin/users"},
    {"label": "Configurações", "icon": ft.Icons.TUNE_OUTLINED, "selected_icon": ft.Icons.TUNE, "route": "/admin/config"},
]

# Mapeia as rotas para seus índices na navigation rail
ADMIN_ROUTE_TO_INDEX_MAP = {item["route"]: i for i, item in enumerate(ADMIN_NAV_DESTINATIONS)}

def get_actions_appbar(page: ft.Page) -> List[ft.Control]:
    
    def toggle_theme_mode(e: ft.ControlEvent) -> None:
        """
        Alterna entre os modos de tema CLARO e ESCURO da aplicação.

        Args:
            e (ft.ControlEvent): Evento de controle que disparou a função.
        """
        if page.theme_mode == ft.ThemeMode.LIGHT:
            page.theme_mode = ft.ThemeMode.DARK
        elif page.theme_mode == ft.ThemeMode.DARK:
            page.theme_mode = ft.ThemeMode.LIGHT
        else:
            page.theme_mode = ft.ThemeMode.LIGHT
        page.update()

    return [
        ft.IconButton(
            ft.Icons.BRIGHTNESS_4_OUTLINED,
            tooltip="Mudar tema",
            padding=ft.padding.only(left=theme.PADDING_XL, right=theme.PADDING_XL),
            on_click=toggle_theme_mode,
            icon_size=26
        )
    ]

# --- Classe Principal da Aplicação Admin ---
class AdminApp:
    """Encapsula a lógica e a UI da aplicação de administração."""
    def __init__(self, page: ft.Page):
        self.page = page
        self.logger = LoggerSetup.get_logger(__name__)
        self.fs_manager: Optional[FbManagerFirestore] = None
        self.storage_manager: Optional[FbManagerStorage] = None
        self.auth_manager: Optional[FbManagerAdminAuth] = None
        self.user_id_to_name_map: Dict[str, str] = {}

        self._initialize_services()

        # Define o mapeamento de rotas para as funções que criam o conteúdo
        self._content_creators: Dict[str, Callable[[], ft.Control]] = {
            "/admin/dashboard": self._create_dashboard_view,
            "/admin/data": self._create_data_view,
            "/admin/users": self._create_user_management_view,
            "/admin/config": self._create_config_view,
        }

        # Configuração inicial da página e UI persistente
        self._setup_page_layout()

        # Controles para a view de Dados e Logs
        self.user_filter_dd = ft.Dropdown(label="Filtrar por Usuário", width=250, on_change=self._update_log_viewer_filters)
        self.type_filter_dd = ft.Dropdown(
            label="Filtrar por Tipo",
            width=200,
            on_change=self._update_log_viewer_filters,
            options=[
                ft.dropdown.Option(key="ALL", text="Todos os Tipos"),
                ft.dropdown.Option(key="log", text="Logs"),
                ft.dropdown.Option(key="metric", text="Métricas")
            ],
            value="ALL"
        )
        self.level_filter_dd = ft.Dropdown(
            label="Filtrar por Nível de Log",
            width=250,
            on_change=self._update_log_viewer_filters,
            options=[
                ft.dropdown.Option("ALL"), ft.dropdown.Option("INFO"),
                ft.dropdown.Option("WARNING"), ft.dropdown.Option("ERROR"), ft.dropdown.Option("CRITICAL")
            ],
            value="ALL"
        )

        self.date_filter_field = ft.TextField(label="Filtrar por Data", width=150, read_only=True, value=date.today().strftime("%d/%m/%Y"))
        self.date_picker = ft.DatePicker(on_change=self._on_date_picked, first_date=date(2025, 1, 1), last_date=date.today())
        self.page.overlay.append(self.date_picker)
    
        self.data_display_list = ft.ListView(expand=True, spacing=1, auto_scroll=True, height=600)

        self.save_file_picker = ft.FilePicker(on_result=self._on_save_excel_result)
        self.page.overlay.append(self.save_file_picker)
        
        self._data_to_export: Optional[List[Dict[str, Any]]] = None
        
    def _initialize_services(self):
        """Inicializa os serviços de backend (Firebase)."""
        try:
            inicializar_firebase()
            self.fs_manager = FbManagerFirestore()
            self.storage_manager = FbManagerStorage()
            self.auth_manager = FbManagerAdminAuth()
            self._populate_user_map() # Popula o mapa de usuários
            self.logger.info("AdminApp: Managers do Firebase e mapa de usuários inicializados.")

        except Exception as e:
            self.logger.critical(f"AdminApp: Falha crítica ao inicializar Firebase: {e}", exc_info=True)
            # Exibe erro diretamente na página se a inicialização falhar
            error_message = ft.Column([
                ft.Icon(ft.Icons.ERROR, color=theme.COLOR_ERROR, size=50),
                ft.Text("Erro Crítico de Inicialização", style=ft.TextThemeStyle.HEADLINE_SMALL),
                ft.Text(f"Não foi possível conectar aos serviços de backend: {e}")
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
            self.page.add(ft.Container(content=error_message, alignment=ft.alignment.center, expand=True))
            self.page.update()

    def _setup_page_layout(self):
        """Configura os elementos de layout persistentes da página."""
        self.page.title = TITLE_GUI
        self.page.vertical_alignment = ft.MainAxisAlignment.START
        self.page.horizontal_alignment = ft.CrossAxisAlignment.START
        
        self.page.theme = theme.APP_THEME
        self.page.dark_theme = theme.APP_DARK_THEME
        self.page.theme_mode = ft.ThemeMode.SYSTEM

        if self.page.data is None:
            self.page.data = {}

        # Reutiliza a infraestrutura de componentes globais
        if "global_update_lock" not in self.page.data:
            self.page.data["global_update_lock"] = threading.Lock()
        if "global_snackbar" not in self.page.data:
            page_snackbar = ft.SnackBar(content=ft.Text(""), show_close_icon=True, action_color=ft.Colors.WHITE) 
            self.page.overlay.append(page_snackbar)
            self.page.data["global_snackbar"] = page_snackbar            
        if "global_loading_overlay" not in self.page.data:
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
            self.page.overlay.append(page_loading_overlay)
            self.page.data["global_loading_overlay"] = page_loading_overlay
            self.page.data["global_loading_text"] = page_loading_text


        # UI Persistente
        self.app_bar = create_app_bar(self.page, TITLE_GUI, get_actions_appbar=get_actions_appbar)
        self.nav_rail = create_navigation_rail(self.page, self.page.route or "/admin/dashboard", 
                                               route_to_base_nav_index=ADMIN_ROUTE_TO_INDEX_MAP,
                                               icones_navegacao=ADMIN_NAV_DESTINATIONS)

        self.content_view = ft.Container(expand=True, padding=20)

        # Router
        self.page.on_route_change = lambda route_event: route_change_content_only(
            self.page,
            self.app_bar, 
            self.nav_rail,
            self.content_view,
            route_event.route,
            admin_routes = True,
            route_to_base_nav_index = ADMIN_ROUTE_TO_INDEX_MAP,
            content_creators = self._content_creators,
            view_module_map = None,
            initial_route = "/admin/dashboard"
        )
        self.page.go("/admin/dashboard")

    # --- Funções de sincronização de dados ---

    def _populate_user_map(self):
        """Busca usuários do Firebase Auth e cria um mapa UID -> nome amigável."""
        try:
            for user in self.auth_manager.list_users().iterate_all():
                if user.email:
                    self.user_id_to_name_map[user.uid] = user.email.split('@')[0]
                else:
                    self.user_id_to_name_map[user.uid] = user.uid # Fallback para o UID
        except Exception as e:
            logger.error(f"Erro ao popular mapa de usuários: {e}", exc_info=True)

    def _open_date_picker(self):
        self.date_picker.open = True
        self.page.update(self.date_picker)

    def _on_date_picked(self, e: ft.ControlEvent):
        """Callback do DatePicker. Atualiza o campo de texto e os filtros."""
        if e.control.value: # Verifica se uma data foi realmente selecionada
            selected_date = e.control.value.date()
            self.date_filter_field.value = selected_date.strftime("%d/%m/%Y")
        # O DatePicker fecha automaticamente, e o on_change é disparado.
        # A atualização dos filtros já é feita pelo on_change, não precisa chamar novamente.
        self._update_log_viewer_filters() # Chamando explicitamente para garantir atua

    def _sync_cloud_data_to_local_worker(self):
        """
        Worker em thread para baixar logs do Storage e métricas do Firestore.
        Otimizado para baixar apenas arquivos que ainda não existem localmente,
        preservando a estrutura de pastas da nuvem.
        """
        try:
            logger.info("Iniciando a sincronização de dados da nuvem...")
            
            # Sincronizar Logs do Storage
            logger.info("Verificando logs no Firebase Storage...")
            all_logs_blobs = self.storage_manager.bucket.list_blobs(prefix=CLOUD_LOGGER_FOLDER)
            for blob in all_logs_blobs:
                # Ignora os "diretórios" vazios que o Storage pode criar
                if blob.name.endswith('/'):
                    continue

                # O caminho local espelhará o caminho do blob dentro de ADMIN_DATA_DIR
                # Ex: se blob.name é "logs/2025/07/08/file.log", o local será "admin_data/logs/2025/07/08/file.log"
                local_path = os.path.join(ADMIN_DATA_DIR, blob.name.replace('/', os.sep))
                
                if not os.path.exists(local_path):
                    # Cria os diretórios pais se não existirem
                    os.makedirs(os.path.dirname(local_path), exist_ok=True)
                    logger.debug(f"Baixando log: {blob.name} para {local_path}")
                    blob.download_to_filename(local_path)

            # Sincronizar Métricas do Firestore
            logger.info("Verificando métricas no Firestore...")
            all_user_ids = {user.uid for user in self.auth_manager.list_users().iterate_all()}
            for user_id in all_user_ids:
                metrics_collection_path = f'user_metrics/{user_id}/metrics'
                metrics_ref = self.fs_manager.db.collection(metrics_collection_path).stream()

                for metric_doc in metrics_ref:
                    local_user_metric_dir = os.path.join(ADMIN_METRICS_DIR, user_id)
                    os.makedirs(local_user_metric_dir, exist_ok=True)
                    local_metric_path = os.path.join(local_user_metric_dir, f"{metric_doc.id}.json")
                    
                    if not os.path.exists(local_metric_path):
                        logger.debug(f"Baixando métrica para usuário '{user_id}': {metric_doc.id}")
                        try:
                            with open(local_metric_path, 'w', encoding='utf-8') as f:
                                json.dump(metric_doc.to_dict(), f, indent=2, ensure_ascii=False)
                        except Exception as write_err:
                            logger.error(f"Erro ao salvar arquivo de métrica local '{local_metric_path}': {write_err}")

            show_snackbar(self.page, "Sincronização de dados concluída!", theme.COLOR_SUCCESS)
            if self.page.route == "/admin/data":
                self.page.run_thread(self._update_log_viewer_filters)

        except Exception as e:
            logger.error(f"Erro durante a sincronização de dados: {e}", exc_info=True)
            show_snackbar(self.page, f"Erro ao sincronizar: {e}", theme.COLOR_ERROR)
        finally:
            hide_loading_overlay(self.page)
 
    def _sync_data_handler(self, e: ft.ControlEvent):
        """Manipulador de clique que inicia a thread de sincronização."""
        show_loading_overlay(self.page, "Sincronizando dados da nuvem...")
        threading.Thread(target=self._sync_cloud_data_to_local_worker, daemon=True).start()

    def _update_log_viewer_filters(self, e: Optional[ft.ControlEvent] = None):
        """Atualiza a lista de logs e métricas com base nos filtros selecionados."""
        hide_loading_overlay(self.page)
        show_loading_overlay(self.page, "Filtrando dados...")
        
        # Popula o dropdown de usuários
        available_users = get_available_users(self.user_id_to_name_map)
        current_user_selection = self.user_filter_dd.value
        self.user_filter_dd.options = [ft.dropdown.Option(key="ALL", text="Todos os Usuários")] + \
                                    [ft.dropdown.Option(key=uid, text=name) for name, uid in available_users]
        if current_user_selection not in [opt.key for opt in self.user_filter_dd.options]:
            self.user_filter_dd.value = "ALL"
            
        selected_user = self.user_filter_dd.value or "ALL"
        selected_type = self.type_filter_dd.value or "ALL"  
        selected_level = self.level_filter_dd.value or "ALL"

        try:
            selected_date = datetime.strptime(self.date_filter_field.value, "%d/%m/%Y").date()
        except (ValueError, TypeError):
            selected_date = date.today() # Fallback para data de hoje
            self.date_filter_field.value = selected_date.strftime("%d/%m/%Y")

        self.data_display_list.controls.clear()
        # Passa o novo filtro para a função de busca
        filtered_data = get_filtered_logs(selected_user, selected_level, selected_date, selected_type, self.user_id_to_name_map)
        
        if not filtered_data:
            self.data_display_list.controls.append(ft.Text("Nenhuma entrada encontrada para os filtros selecionados."))
        else:
            for entry in filtered_data:
                # O f-string já lida com 'log' ou 'metric'
                self.data_display_list.controls.append( # 
                    ft.Text(f"{entry['user_name']}: [{entry['type'].upper()}]: {entry['content']}", font_family="monospace", size=12, selectable=True)
                )
        
        hide_loading_overlay(self.page)
        self.page.update()

    # --- Funções de exportação ---

    def _start_export_process(self, data_to_export: List[Dict[str, Any]]):
        """
        Orquestra a geração do arquivo Excel e o salvamento/download.
        Lida com os modos Web e Desktop.
        """
        hide_loading_overlay(self.page) # Esconde o "Preparando dados..."
        
        # Gera o nome do arquivo
        selected_date_str = datetime.now().strftime('%Y%m%d')
        try:
            selected_date_str = datetime.strptime(self.date_filter_field.value, "%d/%m/%Y").strftime('%Y%m%d')
        except (ValueError, TypeError):
            pass # Usa a data atual como fallback
        
        default_filename = f"relatorio_filtrado_{selected_date_str}.xlsx"

        # Modo Web: Gera o arquivo no servidor e oferece para download
        if self.page.web:
            show_loading_overlay(self.page, "Gerando arquivo para download...")
            
            # Diretório temporário para os exports (relativo a 'assets')
            # O Flet serve o diretório 'assets' automaticamente
            temp_exports_path = os.path.join("assets", "temp_admin_exports")
            os.makedirs(temp_exports_path, exist_ok=True)
            
            # Caminho completo do arquivo no servidor
            server_save_path = os.path.join(temp_exports_path, default_filename)
            
            success = export_data_to_excel(data_to_export, server_save_path)
            hide_loading_overlay(self.page)

            if success:
                # O URL de download é relativo à raiz do servidor Flet
                download_url = f"/temp_admin_exports/{default_filename}"
                self.page.launch_url(download_url, web_window_name="_blank")
                show_snackbar(self.page, f"Download de '{default_filename}' iniciado.", theme.COLOR_SUCCESS)
            else:
                show_snackbar(self.page, "Falha ao gerar arquivo para download.", theme.COLOR_ERROR)

        # Modo Desktop: Usa o FilePicker para "Salvar Como"
        else:
            if not self.save_file_picker:
                show_snackbar(self.page, "Erro: Seletor de arquivos não está pronto.", theme.COLOR_ERROR)
                return
            
            # Armazena temporariamente os dados que serão salvos no callback
            self._data_to_export = data_to_export
            
            # Chama o FilePicker para salvar o arquivo
            self.save_file_picker.save_file(
                dialog_title="Salvar Relatório Excel",
                file_name=default_filename,
                allowed_extensions=["xlsx"]
            )
            
    def _handle_export_click(self, e: ft.ControlEvent):
        """Inicia o processo de exportação em uma thread separada."""

        def export_data_worker():
            """Prepara os dados em background."""
            try:
                # Coleta os filtros atuais da UI
                selected_user = self.user_filter_dd.value or "ALL"
                selected_level = self.level_filter_dd.value or "ALL"
                selected_type = self.type_filter_dd.value or "ALL"
                selected_date = datetime.strptime(self.date_filter_field.value, "%d/%m/%Y").date()

                data = process_filtered_data_for_export(
                    selected_user, selected_level, selected_date, selected_type, self.user_id_to_name_map
                )

                if not data:
                    hide_loading_overlay(self.page)
                    show_snackbar(self.page, "Nenhum dado encontrado para exportar.", theme.COLOR_WARNING)
                    return

                # Dados prontos, chama o processo de salvamento/download na thread principal
                self.page.run_thread(self._start_export_process, data)
            
            except Exception as ex:
                logger.error(f"Erro no worker de exportação: {ex}", exc_info=True)
                hide_loading_overlay(self.page)
                show_snackbar(self.page, f"Erro ao preparar dados: {ex}", theme.COLOR_ERROR)

        show_loading_overlay(self.page, "Preparando dados para exportação...")
        threading.Thread(target=export_data_worker, daemon=True).start()

    def _on_save_excel_result(self, e: ft.FilePickerResultEvent):
        """
        Callback chamado após o usuário selecionar um local para salvar o arquivo Excel (APENAS DESKTOP).
        """
        if not e.path:
            show_snackbar(self.page, "Exportação cancelada.", theme.COLOR_INFO)
            self._data_to_export = None
            return

        if self._data_to_export is None:
            show_snackbar(self.page, "Erro: dados para exportação não disponíveis.", theme.COLOR_ERROR)
            return
        
        save_path = e.path
        show_loading_overlay(self.page, "Gerando arquivo Excel...")
        
        # A geração real do arquivo acontece aqui no modo desktop
        success = export_data_to_excel(self._data_to_export, save_path)
        
        hide_loading_overlay(self.page)
        
        if success:
            show_snackbar(self.page, f"Relatório salvo com sucesso em: {save_path}", theme.COLOR_SUCCESS)
        else:
            show_snackbar(self.page, "Falha ao salvar o arquivo Excel.", theme.COLOR_ERROR)
        
        # Limpa os dados temporários após a tentativa
        self._data_to_export = None

    # --- Funções que criam o conteúdo para cada view ---

    def _create_dashboard_view(self, page: ft.Page) -> ft.Control:
        sync_card = CardWithHeader(
            "Sincronização de Dados",
            ft.Column([
                ft.Text("Baixe os logs e métricas mais recentes da nuvem para o seu disco local para análise."),
                ft.Row([
                    ft.ElevatedButton("Atualizar Logs e Métricas", on_click=self._sync_data_handler, icon=ft.Icons.CLOUD_DOWNLOAD_OUTLINED)
                ], alignment=ft.MainAxisAlignment.END)
            ])
        )
        return ft.Column([
            ft.Text("Dashboard Administrativo", style=ft.TextThemeStyle.HEADLINE_MEDIUM),
            sync_card,
        ], spacing=20)

    def _create_config_view(self, page: ft.Page) -> ft.Control:
        # --- Card Provedores LLM ---
        json_editor_llm = ft.TextField(label="Configuração de Provedores LLM (JSON)", multiline=True, min_lines=12, expand=True)
        
        def load_llm_config(e):
            show_loading_overlay(self.page, "Carregando...")
            providers = read_providers_from_firestore(self.fs_manager)
            json_editor_llm.value = json.dumps(providers, indent=2, ensure_ascii=False)
            hide_loading_overlay(self.page)
            json_editor_llm.update()

        def save_llm_config(e):
            show_loading_overlay(self.page, "Salvando...")
            try:
                data_list = json.loads(json_editor_llm.value)
                if write_providers_to_firestore(self.fs_manager, data_list):
                    show_snackbar(self.page, "Configuração salva!", theme.COLOR_SUCCESS)
                else:
                    show_snackbar(self.page, "Falha ao salvar.", theme.COLOR_ERROR)
            except json.JSONDecodeError as ex:
                show_snackbar(self.page, f"Erro no formato JSON: {ex}", theme.COLOR_ERROR)
            finally:
                hide_loading_overlay(self.page)
        
        llm_card = CardWithHeader(
            "Gerenciar Provedores LLM",
            ft.Column([
                ft.Text("Edite a lista de provedores e modelos. A alteração afeta todos os usuários."),
                json_editor_llm,
                ft.Row([
                    ft.ElevatedButton("Carregar Atuais", on_click=load_llm_config),
                    ft.ElevatedButton("Salvar Alterações", on_click=save_llm_config, color=ft.Colors.WHITE, bgcolor=theme.COLOR_SUCCESS),
                ], alignment=ft.MainAxisAlignment.END)
            ]), expand=True
        )

        embd_card = CardWithHeader(
            "Gerenciar Provedores Embeddings",
            ft.Column([
                ft.Text("Edite a lista de provedores e modelos. A alteração afeta todos os usuários."),
                ft.Text("..."),
                ft.Row([
                    ft.ElevatedButton("Carregar Atuais"),
                    ft.ElevatedButton("Salvar Alterações", color=ft.Colors.WHITE, bgcolor=theme.COLOR_SUCCESS),
                ], alignment=ft.MainAxisAlignment.END)
            ]), expand=True
        )

        # --- Card Templates de Prompt ---
        def do_upload_prompts(e):
            show_loading_overlay(self.page, "Enviando templates...")
            success = upload_prompt_templates()
            hide_loading_overlay(self.page)
            if success:
                show_snackbar(self.page, "Templates de prompt enviados com sucesso!", theme.COLOR_SUCCESS)
            else:
                show_snackbar(self.page, "Falha ao enviar templates.", theme.COLOR_ERROR)
        
        prompts_card = CardWithHeader(
            "Gerenciar Templates de Prompt",
            ft.Column([
                ft.Text("Esta ação sobrescreverá os prompts base no banco de dados com a versão definida no código do projeto (`repo_prompts.py`). Use quando houver atualizações nos prompts."),
                ft.Row([ft.ElevatedButton("Fazer Upload dos Templates", on_click=do_upload_prompts, icon=ft.Icons.UPLOAD, disabled=True)], 
                       alignment=ft.MainAxisAlignment.END)
            ])
        )
        
        content_column = ft.Column([prompts_card, llm_card, embd_card], scroll=ft.ScrollMode.ADAPTIVE, expand=True, spacing=20)
        return wrapper_cotainer_1(content_column) 

    def _create_user_management_view(self, page: ft.Page) -> ft.Control:
        users_list_view = ft.ListView(expand=True, spacing=5)

        def refresh_list(e=None):
            show_loading_overlay(self.page, "Carregando usuários...")
            users_list_view.controls.clear()
            try:
                for user in self.auth_manager.list_users().iterate_all():
                    is_admin = user.custom_claims.get('admin', False) if user.custom_claims else False
                    def handler_factory(email, current_status):
                        def on_toggle(ev):
                            set_user_admin_status(email, ev.control.value)
                        return on_toggle
                    
                    user_row = ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.PERSON),
                            ft.Column(
                                [
                                    ft.Text(user.display_name.title() or "Sem Nome", weight=ft.FontWeight.BOLD),
                                    ft.Text(user.email, size=12, color=ft.Colors.with_opacity(0.8, ft.Colors.ON_SURFACE)),
                                ],
                                spacing=2,
                                expand=True, # Permite que esta coluna expanda e ocupe o espaço
                            ),
                            ft.Switch(
                                label="Admin", 
                                value=is_admin, 
                                on_change=handler_factory(user.email, is_admin), 
                                tooltip="Tornar usuário um administrador",
                                width=105
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    )
                    
                    users_list_view.controls.append(
                        ft.Container(
                            content=user_row,
                            padding=ft.padding.symmetric(vertical=8, horizontal=12),
                            border=ft.border.only(bottom=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
                        )
                    )
            except Exception as ex:
                logger.error(f"Erro ao carregar a lista de usuários na GUI: {ex}", exc_info=True)
                show_snackbar(self.page, "Erro ao carregar lista de usuários.", theme.COLOR_ERROR)
            finally:
                hide_loading_overlay(self.page)
        
        threading.Thread(target=refresh_list, daemon=True).start()
        
        users_card = CardWithHeader(
            "Gerenciar Usuários", 
            users_list_view, 
            header_actions=[ft.IconButton(ft.Icons.REFRESH, on_click=refresh_list, tooltip="Atualizar lista de usuários")]
        )
        content_column = ft.Column([users_card], scroll=ft.ScrollMode.ADAPTIVE, expand=True)
        return wrapper_cotainer_1(content_column) 

    def _create_data_view(self, page: ft.Page) -> ft.Control:
        # Chama a função para popular os filtros na primeira vez que a view é criada
        self._update_log_viewer_filters() 
        #threading.Thread(target=self._update_log_viewer_filters).start()

        filters_row = ft.Row([
            self.user_filter_dd, 
            self.type_filter_dd,
            self.level_filter_dd,
            self.date_filter_field,
            ft.IconButton(icon=ft.Icons.CALENDAR_MONTH, on_click=lambda _: self._open_date_picker(), tooltip="Selecionar Data"),
            ft.Container(expand=True), # Espaçador
            ft.ElevatedButton("Exportar para Excel", icon=ft.Icons.TABLE_VIEW, on_click=self._handle_export_click, tooltip="Exportar dados filtrados")
        ], alignment=ft.MainAxisAlignment.START, spacing=10)

        days_to_keep_field = ft.TextField(label="Manter logs dos últimos (dias)", value="30", width=250, input_filter=ft.InputFilter(r"[0-9]"))
        dry_run_switch = ft.Switch(label="Apenas simular (Dry Run)", value=True)
        log_output_area = ft.ListView(expand=True, spacing=2, auto_scroll=True)

        data_viewer_card = CardWithHeader(
            "Visualizador de Logs e Métricas",
            ft.Column([
                filters_row,
                ft.Divider(),
                ft.Container(
                    content=self.data_display_list,
                    border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                    border_radius=5,
                    padding=10,
                    expand=True
                )
            ])
        )
        
        # Mantém o card de limpeza
        days_to_keep_field = ft.TextField(label="Manter logs dos últimos (dias)", value="30", width=250, input_filter=ft.InputFilter(r"[0-9]"))
        dry_run_switch = ft.Switch(label="Apenas simular (Dry Run)", value=True)

        def cleanup_thread_worker(days: int, is_dry_run: bool):
            """Função que executa a tarefa demorada em background."""
            try:
                success = run_cloud_log_cleanup(days, is_dry_run)
                if success:
                    show_snackbar(self.page, "Operação de limpeza concluída. Verifique os logs do console para detalhes.", theme.COLOR_SUCCESS)
                else:
                    show_snackbar(self.page, "Operação de limpeza falhou. Verifique os logs do console.", theme.COLOR_ERROR)
            except Exception as e:
                logger.error(f"Erro inesperado na thread de limpeza de logs: {e}", exc_info=True)
                show_snackbar(self.page, f"Erro inesperado: {e}", theme.COLOR_ERROR)
            finally:
                # Garante que o overlay seja sempre fechado
                hide_loading_overlay(self.page)

        def do_cleanup(e: ft.ControlEvent):
            """Handler do botão que inicia a thread de limpeza."""
            try:
                days = int(days_to_keep_field.value)
                is_dry_run = dry_run_switch.value
                
                # Mostra o overlay ANTES de iniciar a thread
                show_loading_overlay(self.page, "Executando limpeza de logs...")
                
                # Inicia a tarefa demorada em uma nova thread
                threading.Thread(
                    target=cleanup_thread_worker,
                    args=(days, is_dry_run),
                    daemon=True
                ).start()

            except ValueError:
                show_snackbar(self.page, "Por favor, insira um número válido de dias.", theme.COLOR_ERROR)
            except Exception as ex:
                logger.error(f"Erro ao iniciar a thread de limpeza: {ex}", exc_info=True)
                hide_loading_overlay(self.page)
                show_snackbar(self.page, "Não foi possível iniciar a operação de limpeza.", theme.COLOR_ERROR)

        cleanup_card = CardWithHeader(
            "Limpeza de Logs na Nuvem",
            ft.Column([
                ft.Text("Remove arquivos de log antigos do Firebase Storage para controlar custos e manter a organização."),
                ft.Row([days_to_keep_field, dry_run_switch], vertical_alignment=ft.CrossAxisAlignment.END),
                ft.Row([ft.ElevatedButton("Executar Limpeza", on_click=do_cleanup, icon=ft.Icons.CLEANING_SERVICES)], alignment=ft.MainAxisAlignment.END),
                # ft.Divider(),
                # ft.Text("Resultado da Simulação/Execução:"),
                # ft.Container(log_output_area, border=ft.border.all(1, ft.Colors.OUTLINE), expand=True, padding=5)
            ])
        )
        
        content_column = ft.Column([data_viewer_card, cleanup_card], scroll=ft.ScrollMode.ADAPTIVE, expand=True, spacing=20)
        return wrapper_cotainer_1(content_column) 
        

def main(page: ft.Page):
    """Ponto de entrada para a aplicação Flet de administração."""
    # Logger para o próprio app admin
    AdminApp(page)

execution_time = perf_counter() - start_time
logger.info(f"[DEBUG] Carregado APP_ADMIN.py em {execution_time:.4f}s")

