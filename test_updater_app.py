# test_updater_app.py
import flet as ft
import os, sys, logging
import threading

# Importa o módulo que queremos testar
# É crucial que o settings.py tenha a constante VERSION_INFO_URL definida
from src.services import update_manager
from src.settings import APP_VERSION

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Configuração do Logging ---
# Loga para o console e para um arquivo para facilitar a depuração
LOG_FILE = os.path.join(BASE_DIR, "test_updater.log")

# --- Configuração de Logging para o App de Teste ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE, mode='w')]
)

class UpdateTestApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Teste do Atualizador Automático"
        self.page.vertical_alignment = ft.MainAxisAlignment.CENTER
        self.page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

        # UI Controls
        self.status_text = ft.Text("Aguardando verificação...", text_align=ft.TextAlign.CENTER, size=16)
        self.progress_ring = ft.ProgressRing(visible=False)
        self.local_version_text = ft.Text(f"Versão Local (APP_VERSION): {APP_VERSION}", weight=ft.FontWeight.BOLD)
        self.remote_version_text = ft.Text("Versão Remota: (não verificado)")
        self.check_button = ft.ElevatedButton("Verificar Atualizações", on_click=self.on_check_click)
        
        self.page.add(
            ft.Column(
                [
                    ft.Text("Teste do Módulo de Atualização", style=ft.TextThemeStyle.HEADLINE_MEDIUM),
                    ft.Divider(),
                    self.local_version_text,
                    self.remote_version_text,
                    ft.Container(height=20),
                    self.status_text,
                    self.progress_ring,
                    ft.Container(height=20),
                    self.check_button,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10
            )
        )
        # Inicia a verificação automática ao carregar
        threading.Timer(1.0, self.check_and_handle_updates).start()

    def on_check_click(self, e):
        """Handler para o clique do botão."""
        logging.info("Botão 'Verificar Atualizações' clicado.")
        self.check_and_handle_updates()

    def check_and_handle_updates(self):
        """Orquestra a verificação e a interação com o usuário na UI do Flet."""
        self.page.run_thread(self._update_ui_state, "checking")
        
        # A chamada de rede é feita em uma thread para não bloquear a UI
        status = update_manager.check_for_updates()
        
        self.page.run_thread(self._update_ui_state, "idle")

        if status.error_message:
            logging.error(f"Erro na verificação de atualização: {status.error_message}")
            self.page.run_thread(self._update_status_text, f"Erro: {status.error_message}", "red")
            return

        remote_version = status.update_info.get("version") if status.update_info else "N/A"
        self.page.run_thread(self._update_remote_version_text, remote_version)

        if status.update_available:
            logging.info(f"Atualização encontrada: v{remote_version}. Forçada: {status.is_forced}")
            is_forced_str = "(Obrigatória)" if status.is_forced else "(Opcional)"
            self.page.run_thread(self._update_status_text, f"Nova versão {remote_version} disponível! {is_forced_str}", "green")
            self.page.run_thread(self.show_flet_update_dialog, status)
        else:
            self.page.run_thread(self._update_status_text, "A aplicação está atualizada.", "blue")
    
    def show_flet_update_dialog(self, status: update_manager.UpdateStatus):
        """Mostra um diálogo de confirmação usando Flet em vez de tkinter."""
        def on_update_confirm(e):
            logging.info("Usuário confirmou a atualização.")
            dialog.open = False
            self.page.update()
            # Chama nossa função de simulação
            update_manager.run_updater(status.update_info)

        def on_update_cancel(e):
            logging.info("Usuário cancelou a atualização.")
            dialog.open = False
            self.page.update()
            if status.is_forced:
                logging.warning("Atualização obrigatória cancelada pelo usuário.")
                self.status_text.value = "Atualização obrigatória cancelada. A aplicação seria encerrada."
                self.status_text.color = "orange"
                self.page.update()
        
        version = status.update_info.get('version', 'N/A')
        notes = status.update_info.get('notes', 'Sem notas da versão.')
        message = f"Uma nova versão ({version}) está disponível!\n\nNotas: {notes}"
        title = "Atualização Obrigatória" if status.is_forced else "Atualização Disponível"

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[
                ft.ElevatedButton("Atualizar Agora", on_click=on_update_confirm),
                ft.TextButton("Depois", on_click=on_update_cancel, visible=not status.is_forced),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def show_final_success_message(self, update_info: dict):
        """Atualiza a UI para mostrar a mensagem de sucesso da simulação."""
        version = update_info.get('version')
        self.status_text.value = f"Simulação concluída! O updater foi chamado para instalar a v{version}."
        self.status_text.color = "purple"
        self.check_button.disabled = True
        self.page.update()

    # Funções auxiliares para atualizar a UI a partir de threads
    def _update_ui_state(self, state: str):
        if state == "checking":
            self.status_text.value = "Verificando..."
            self.status_text.color = "grey"
            self.progress_ring.visible = True
            self.check_button.disabled = True
        else: # idle
            self.progress_ring.visible = False
            self.check_button.disabled = False
        self.page.update()

    def _update_status_text(self, message: str, color: str):
        self.status_text.value = message
        self.status_text.color = color
        self.page.update()
    
    def _update_remote_version_text(self, version: str):
        self.remote_version_text.value = f"Versão Remota: {version}"
        self.page.update()

app_instance = None
def main(page: ft.Page):
    global app_instance
    app_instance = UpdateTestApp(page)

if __name__ == "__main__":
    # --- IMPORTANTE ---
    # Agora vamos usar a URL real definida em settings.py
    # Certifique-se de que a constante VERSION_INFO_URL em 'src/settings.py'
    # está configurada com o link de download direto do seu version.json no Google Drive.
    
    ft.app(
        target=main,
        view=ft.AppView.WEB_BROWSER
    )

# pyinstaller --name test_updater --onefile test_updater_app.py
# (r'C:\Users\edson.eab\AppData\Local\pypoetry\Cache\virtualenvs\docs-analyzer-3-DJ3PQuGu-py3.13\Lib\site-packages\flet_web\web', 'flet_web/web'),
