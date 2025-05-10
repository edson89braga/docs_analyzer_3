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

from src.services.firebase_client import FirebaseClientStorage
from src.services.firebase_manager import FbManagerStorage

from src.logger.logger import LoggerSetup


# Instanciar managers de storage
_client_storage_for_logger = None
try:
    _client_storage_for_logger = FirebaseClientStorage()
except Exception as e_cli:
    print(f"AVISO em run.py: Falha ao instanciar FirebaseClientStorage para logger: {e_cli}")

_admin_storage_for_logger = None
try:
    _admin_storage_for_logger = FbManagerStorage() # Pode retornar None se não configurado
except Exception as e_adm:
    print(f"AVISO em run.py: Falha ao instanciar FbManagerStorage (Admin) para logger: {e_adm}")

if not _client_storage_for_logger and not _admin_storage_for_logger:
    print("AVISO CRÍTICO em run.py: Nenhum gerenciador de storage Firebase disponível. Logs na nuvem DESABILITADOS.")

try:
    LoggerSetup.initialize(
        routine_name="DocsAnalyzer3",
        firebase_client_storage=_client_storage_for_logger,
        fb_manager_storage_admin=_admin_storage_for_logger
    )
    # Logger para o próprio run.py
    _run_logger = LoggerSetup.get_logger(__name__)
    _run_logger.info("Logger inicializado a partir de run.py.")

except Exception as e:
    print(f"Falha CRÍTICA ao inicializar o logger em run.py: {e}")
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.error("Logger principal falhou ao inicializar. Usando fallback básico.")
    # Não levantar exceção aqui para permitir que a app Flet tente iniciar mesmo assim.


# --- Monkey Patching Uvicorn Logging ---
# Tentar importar DefaultFormatter. Se falhar, o patch não é necessário/possível.
#try:
#    from uvicorn.logging import DefaultFormatter
#
#    # Criação de uma subclasse segura
#    class SafeUvicornDefaultFormatter(DefaultFormatter):
#        def __init__(self, *args, **kwargs):
#            # Força 'use_colors' para False, independentemente de isatty
#            kwargs['use_colors'] = False
#            # Chama o __init__ original, mas com cores desabilitadas
#            try:
#                super().__init__(*args, **kwargs)
#            except TypeError as te:
#                # Lidar com possíveis mudanças na assinatura do __init__ do uvicorn
#                logging.warning(f"Potencial incompatibilidade no __init__ do DefaultFormatter: {te}. Tentando inicialização básica.")
#                # Tenta inicialização mais básica de logging.Formatter
#                logging.Formatter.__init__(self, *args, **kwargs)
#    # Substitui a classe original pela nossa versão segura
#    import uvicorn.logging
#    uvicorn.logging.DefaultFormatter = SafeUvicornDefaultFormatter
#    logging.info("Uvicorn DefaultFormatter monkey-patched para desabilitar cores/isatty check.")
#
#except ImportError:
#    logging.warning("Não foi possível importar uvicorn.logging.DefaultFormatter. O monkey patch não será aplicado.")
#except Exception as patch_err:
#    logging.error(f"Erro durante o monkey patching do Uvicorn: {patch_err}", exc_info=True)
# --- Fim do Monkey Patching ---

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


# Verifica se este script está sendo executado diretamente
if __name__ == "__main__":
    # Configura e inicia a aplicação Flet
    ft.app(
        target=main,                 # Função principal a ser executada
        view=ft.AppView.WEB_BROWSER, # Executa como uma aplicação web no navegador padrão
        port=8550                    # Porta em que a aplicação será servida (ex: http://localhost:8550)
        # assets_dir="assets"        # Descomente se você tiver uma pasta 'assets' na raiz
        # Para uploads no modo web, Flet precisa de FLET_SECRET_KEY e upload_dir
        # os.environ["FLET_SECRET_KEY"] = "sua_chave_secreta_aqui_para_desenvolvimento" # Defina de forma segura
        # upload_dir=os.path.abspath("temp_flet_uploads") # Crie este diretório
    )

'''
TODO:
Segurança do Token: O idToken tem um tempo de vida (geralmente 1 hora). Para aplicações de longa duração, precisaMOS implementar a lógica de atualização 
do token usando o refreshToken (que também é retornado por authenticate_user_get_all_data). 
'''