# run.py
import logging
import flet as ft
# Importa a função 'main' do seu módulo app dentro de flet_ui
from src.flet_ui.app import main

# REMOVIDO daqui managers de storage para tentar tornar a inicialização da aplicação mais rápida (movido para app.py):
# from src.services.firebase_client import FirebaseClientStorage
# from src.services.firebase_manager import FbManagerStorage
# 
# # Instanciar managers de storage
# _client_storage_for_logger = None
# try:
#     _client_storage_for_logger = FirebaseClientStorage()
# except Exception as e_cli:
#     print(f"AVISO em run.py: Falha ao instanciar FirebaseClientStorage para logger: {e_cli}")
# 
# _admin_storage_for_logger = None
# try:
#     _admin_storage_for_logger = FbManagerStorage() # Pode retornar None se não configurado
# except Exception as e_adm:
#     print(f"AVISO em run.py: Falha ao instanciar FbManagerStorage (Admin) para logger: {e_adm}")
# 
# if not _client_storage_for_logger and not _admin_storage_for_logger:
#     print("AVISO CRÍTICO em run.py: Nenhum gerenciador de storage Firebase disponível. Logs na nuvem DESABILITADOS.")

from src.logger.logger import LoggerSetup
try:
    LoggerSetup.initialize(
        routine_name="DocsAnalyzer3",
        #firebase_client_storage=_client_storage_for_logger,
        #fb_manager_storage_admin=_admin_storage_for_logger
    )
    # Logger para o próprio run.py
    _run_logger = LoggerSetup.get_logger(__name__)
    _run_logger.info("Logger inicializado a partir de run.py.")

except Exception as e:
    print(f"Falha CRÍTICA ao inicializar o logger em run.py: {e}")
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.error("Logger principal falhou ao inicializar. Usando fallback básico.")
    # Não levantar exceção aqui para permitir que a app Flet tente iniciar mesmo assim.

# Silencia logs de bibliotecas 
logging.getLogger("flet_core").setLevel(logging.WARNING)
logging.getLogger("flet_runtime").setLevel(logging.WARNING)
logging.getLogger("flet_web").setLevel(logging.WARNING)
logging.getLogger("flet").setLevel(logging.WARNING)
logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("watchdog").setLevel(logging.WARNING)
logging.getLogger("uvicorn").setLevel(logging.INFO) # Pode voltar para INFO se o patch funcionar
logging.getLogger("uvicorn.error").setLevel(logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING) # Manter acesso em WARNING
logging.getLogger("starlette").setLevel(logging.WARNING)

from src.settings import UPLOAD_TEMP_DIR, ASSETS_DIR_ABS

# Verifica se este script está sendo executado diretamente
if __name__ == "__main__":
    ...
    # Configura e inicia a aplicação Flet
    ft.app(
        target=main,                 # Função principal a ser executada
        view=ft.AppView.WEB_BROWSER, # Executa como uma aplicação web no navegador padrão
        port=8550,                   # Porta em que a aplicação será servida (ex: http://localhost:8550)
        assets_dir=ASSETS_DIR_ABS,         # Descomente se você tiver uma pasta 'assets' na raiz
        upload_dir=UPLOAD_TEMP_DIR
    )

    # >>> python run.py  ou
    # >>> flet run -w run.py
    # >>> flet run run.py -d -r --ignore-dirs=logs,__pycache__,.git,.pytest_cache,storage --web -p 8550


'''
Quanto à FLET_SECRET_KEY, na compilação com pyinstaller:
    Tentar ler do ambiente (os.getenv) primeiro (para casos onde um administrador de TI ou usuário avançado queira definir).
    Se não encontrar, tentar ler do Keyring (para persistência na máquina local).
    Se não encontrar no Keyring, gerar uma nova chave aleatória, usá-la E salvá-la no Keyring para futuras sessões naquela máquina.


TODO:
> CreateUser: Tratar erro "message": "EMAIL_EXISTS"

> Não apagar análise feita (nas alterações de views), até que seja recarregado ou upload ou solicitado nova análise
> Viabilizar análise conjunta de multiplos arquivos PDFs (particionados)

> panel de métricas: tempo de processamento de extração, de classificação, total; pages ininteligíveis; pages semelhantes; pages semelhantes com relevância; pages semelhantes com similaridade; pages semelhantes com relevância e similaridade.
> Fields: Prompt, Provedor; Modelo; Modo de consulta; Processador de PDF;

> prompt refinado
> novo layout formulário para respostas da LLM

FIX:
> Check se remove uploads está sendo garantido

'''