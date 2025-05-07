'''
TODO:
3) flet_ui: Criar LoginPage e CredentialsDialog;
4) Refazer plano operacional de tarefas baseado nos novos módulos;
5) Deletar Repo docs_analyzer_2;
'''

# run.py
import logging
import flet as ft
# Importa a função 'main' do seu módulo app dentro de flet_ui
from src.flet_ui.app import main

from src.services.firebase_manager import FbManagerStorage
from src.logger.logger import LoggerSetup

APP_USERNAME, APP_VERSION = "UserTest", "0.1.0"  # TODO Import das config do usuário

try:
    fb_manager = FbManagerStorage() # Pode retornar None se não configurado
    LoggerSetup.initialize(
        routine_name="DocsAnalyzer3",
        fb_manager=fb_manager, # Passe a instância
        username_app=APP_USERNAME,
        version_app=APP_VERSION
    )
except Exception as e:
     print(f"Falha CRÍTICA ao inicializar o logger: {e}")
     # Configurar um fallback muito básico se tudo falhar
     logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
     logging.error("Logger principal falhou ao inicializar. Usando fallback básico.")
     raise

# Verifica se este script está sendo executado diretamente
if __name__ == "__main__":
    # Configura e inicia a aplicação Flet
    ft.app(
        target=main,                 # Função principal a ser executada
        view=ft.AppView.WEB_BROWSER, # Executa como uma aplicação web no navegador padrão
        port=8550                    # Porta em que a aplicação será servida (ex: http://localhost:8550)
        # assets_dir="assets"        # Descomente se você tiver uma pasta 'assets' na raiz
    )
