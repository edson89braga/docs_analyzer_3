# src/services/engine_manager.py
import subprocess
import atexit
import time
import requests
import sys
import os
import logging

logger = logging.getLogger(__name__)

class MLEngineManager:
    """Gerencia o ciclo de vida do processo do servidor de ML (engine.exe)."""

    def __init__(self, engine_path: str, host: str = "127.0.0.1", port: int = 8001):
        self.engine_path = engine_path
        self.api_url = f"http://{host}:{port}"
        self.process: subprocess.Popen | None = None

        # Registra o método de parada para ser chamado no encerramento do Python
        atexit.register(self.stop)

    def is_running(self) -> bool:
        """Verifica se a API do motor de ML está respondendo."""
        try:
            #response = requests.get(f"{self.api_url}/health", timeout=1)
            #return response.status_code == 200

            # Verificação mais robusta: tenta usar o endpoint /embed com um texto de teste.
            # Se isso funcionar, o servidor está realmente pronto para o trabalho.
            test_payload = {"text_list": ["teste"]}
            response = requests.post(f"{self.api_url}/embed", json=test_payload, timeout=5)
            
            # Verifica se a resposta foi bem-sucedida e se contém o campo esperado.
            if response.status_code == 200 and "embeddings" in response.json():
                return True
            # Se receber 503, significa que o servidor está no ar, mas não pronto. Retorna False.
            if response.status_code == 503:
                return False
            return False            
        except requests.ConnectionError:
            return False
        except requests.RequestException: # Captura outros erros de request (timeout, etc)
            return False            

    def start(self):
        """Inicia o processo do motor de ML se ele ainda não estiver em execução."""
        if self.is_running():
            logger.info("Motor de ML já está em execução.")
            return

        logger.info(f"Iniciando o motor de ML a partir de: {self.engine_path}...")
        if not os.path.exists(self.engine_path):
            logger.critical(f"ERRO CRÍTICO: Executável do motor de ML não encontrado em '{self.engine_path}'. A funcionalidade de embedding não funcionará.")
            # Poderíamos levantar uma exceção aqui para parar a aplicação principal
            return

        try:
            # No Windows, creationflags oculta a janela do console do subprocesso
            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NO_WINDOW
            
            # Cria uma cópia do ambiente atual e remove as variáveis de proxy
            # para evitar que o subprocesso as herde indevidamente.
            env = os.environ.copy()
            env.pop("HTTP_PROXY", None)
            env.pop("HTTPS_PROXY", None)
            env.pop("http_proxy", None)
            env.pop("https_proxy", None)

            self.process = subprocess.Popen([self.engine_path], creationflags=creationflags, env=env)
            logger.info(f"Processo do motor de ML iniciado com PID: {self.process.pid}.")

            # Aguarda o servidor ficar pronto
            self._wait_for_server()

        except (OSError, Exception) as e:
            logger.error(f"Falha ao iniciar o processo do motor de ML: {e}", exc_info=True)
            self.process = None

    def _wait_for_server(self, timeout: int = 180):
        """Aguarda o servidor da API se tornar disponível."""
        logger.info(f"Aguardando o servidor de ML ficar pronto (timeout: {timeout}s)...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.is_running():
                # Adiciona uma pequena pausa extra mesmo após o primeiro "ok",
                # para garantir que todos os recursos estejam alocados.
                logger.info("Servidor de ML respondeu ao teste. Aguardando 1s extra para estabilização...")
                time.sleep(1)
                logger.info(f"Servidor de ML pronto e estável em {self.api_url}.")
                return
            logger.debug(f"Aguardando servidor... {int(time.time() - start_time)}s")
            time.sleep(1)
        
        logger.error(f"Timeout! O servidor de ML não respondeu em {timeout} segundos.")
        self.stop() # Tenta parar o processo se ele não respondeu

    def stop(self):
        """Encerra o processo do motor de ML de forma sutil."""
        if self.process and self.process.poll() is None: # Se o processo existe e está rodando
            logger.info(f"Encerrando o processo do motor de ML (PID: {self.process.pid})...")
            try:
                self.process.terminate()  # Envia SIGTERM (mais sutil)
                self.process.wait(timeout=5)  # Espera 5 segundos para encerrar
                logger.info("Processo do motor de ML encerrado com sucesso.")
            except subprocess.TimeoutExpired:
                logger.warning("Processo do motor de ML não encerrou. Forçando (kill)...")
                self.process.kill()  # Força o encerramento (SIGKILL)
            except Exception as e:
                logger.error(f"Erro ao tentar encerrar o motor de ML: {e}")
        self.process = None

