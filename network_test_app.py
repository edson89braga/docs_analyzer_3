# network_test_app.py
import tkinter as tk
from tkinter import scrolledtext, messagebox
import requests
import threading
import queue
import logging
import traceback
import sys
import os

# --- Configurações para o Teste ---
ENGINE_API_URL = "http://127.0.0.1:8001/embed"
EXTERNAL_URL = "https://www.google.com"

# --- Configuração para PyInstaller ---
# Comando para compilar:
# pyinstaller --name network_tester --onefile --windowed --hidden-import=certifi network_test_app.py
# O --hidden-import=certifi é uma salvaguarda para garantir que os certificados SSL sejam incluídos.

class QueueHandler(logging.Handler):
    """Handler de logging que envia registros para uma Queue."""
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(self.format(record))

class NetworkTesterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Testador de Conexão de Rede")
        self.root.geometry("800x600")

        # --- Frames para organização ---
        top_frame = tk.Frame(root, padx=10, pady=10)
        top_frame.pack(fill=tk.X)

        log_frame = tk.Frame(root, padx=10, pady=5)
        log_frame.pack(fill=tk.BOTH, expand=True)

        bottom_frame = tk.Frame(root, padx=10, pady=10)
        bottom_frame.pack(fill=tk.X)

        # --- Widgets ---
        self.test_google_btn = tk.Button(top_frame, text="1. Testar Conexão Externa (Google GET)", command=self.run_google_test)
        self.test_google_btn.pack(side=tk.LEFT, padx=5)

        self.test_engine_btn = tk.Button(top_frame, text="2. Testar Conexão com Engine.exe (POST)", command=self.run_engine_test)
        self.test_engine_btn.pack(side=tk.LEFT, padx=5)

        self.log_area = scrolledtext.ScrolledText(log_frame, state='disabled', wrap=tk.WORD, font=("Consolas", 10))
        self.log_area.pack(fill=tk.BOTH, expand=True)

        self.clear_btn = tk.Button(bottom_frame, text="Limpar Logs", command=self.clear_logs)
        self.clear_btn.pack(side=tk.LEFT, padx=5)
        
        self.copy_btn = tk.Button(bottom_frame, text="Copiar Logs para Área de Transferência", command=self.copy_logs)
        self.copy_btn.pack(side=tk.LEFT, padx=5)

        # --- Configuração de Logging e Fila ---
        self.log_queue = queue.Queue()
        self.queue_handler = QueueHandler(self.log_queue)
        logging.basicConfig(level=logging.INFO, 
                            format='%(asctime)s - %(levelname)s - %(message)s',
                            handlers=[self.queue_handler])
        
        self.root.after(100, self.process_log_queue)
        
        self.log_info("Aplicação de teste iniciada. Pressione os botões para iniciar os testes.")
        self.log_info("="*80)

    def log_info(self, message):
        logging.info(message)

    def log_error(self, message):
        logging.error(message)

    def _log_to_gui(self, message):
        """Insere mensagens na área de log da GUI de forma thread-safe."""
        self.log_area.configure(state='normal')
        self.log_area.insert(tk.END, message + '\n')
        self.log_area.configure(state='disabled')
        self.log_area.yview(tk.END) # Auto-scroll

    def process_log_queue(self):
        """Processa a fila de logs e atualiza a GUI."""
        while not self.log_queue.empty():
            try:
                record = self.log_queue.get(block=False)
                self._log_to_gui(record)
            except queue.Empty:
                break
        self.root.after(100, self.process_log_queue)

    def _toggle_buttons(self, enabled):
        """Habilita/desabilita os botões de teste."""
        state = 'normal' if enabled else 'disabled'
        self.test_google_btn.config(state=state)
        self.test_engine_btn.config(state=state)

    def _start_test_thread(self, target_func):
        """Inicia uma função de teste em uma nova thread."""
        self._toggle_buttons(False)
        thread = threading.Thread(target=target_func, daemon=True)
        thread.start()

    def run_google_test(self):
        self._start_test_thread(self._test_google_get)

    def run_engine_test(self):
        self._start_test_thread(self._test_engine_post)

    def _test_google_get(self):
        """Lógica para testar a conexão com o Google."""
        self.log_info("\n" + "="*80)
        self.log_info(f"INICIANDO TESTE GET para: {EXTERNAL_URL}")
        try:
            self.log_info("Verificando configurações de proxy detectadas por 'requests'...")
            proxies = requests.utils.getproxies()
            if proxies:
                self.log_info(f"Proxies detectados: {proxies}")
            else:
                self.log_info("Nenhum proxy detectado no ambiente.")

            self.log_info(f"Enviando requisição GET para {EXTERNAL_URL}...")
            response = requests.get(EXTERNAL_URL, timeout=15)
            self.log_info(f"SUCESSO! Resposta recebida.")
            self.log_info(f"Status Code: {response.status_code}")
            self.log_info(f"Primeiros 100 caracteres da resposta: {response.text[:100]}...")
        except Exception:
            self.log_error("FALHA NA REQUISIÇÃO!")
            self.log_error(traceback.format_exc())
        finally:
            self.log_info("TESTE GET FINALIZADO.")
            self.root.after(0, self._toggle_buttons, True)

    def _test_engine_post(self):
        """Lógica para testar a conexão com o engine.exe."""
        self.log_info("\n" + "="*80)
        self.log_info(f"INICIANDO TESTE POST para: {ENGINE_API_URL}")
        
        payload = {"text_list": ["teste de conexão"]}
        
        try:
            self.log_info("Verificando configurações de proxy detectadas por 'requests'...")
            proxies = requests.utils.getproxies()
            if proxies:
                self.log_info(f"Proxies detectados: {proxies}")
            else:
                self.log_info("Nenhum proxy detectado no ambiente.")

            # --- CORREÇÃO: Adicionar exceção para localhost na variável de ambiente NO_PROXY ---
            self.log_info("Configurando NO_PROXY para ignorar localhost e 127.0.0.1...")
            original_no_proxy = os.environ.get("NO_PROXY", "")
            no_proxy_list = [item.strip() for item in original_no_proxy.split(",") if item.strip()]
            if "127.0.0.1" not in no_proxy_list: no_proxy_list.append("127.0.0.1")
            if "localhost" not in no_proxy_list: no_proxy_list.append("localhost")
            os.environ["NO_PROXY"] = ",".join(no_proxy_list)
            self.log_info(f"NO_PROXY atual: {os.environ['NO_PROXY']}")

            self.log_info(f"Enviando requisição POST para {ENGINE_API_URL}...")
            self.log_info(f"Payload: {payload}")
            response = requests.post(ENGINE_API_URL, json=payload, timeout=30)
            self.log_info("SUCESSO! Resposta recebida.")
            self.log_info(f"Status Code: {response.status_code}")
            try:
                self.log_info(f"Resposta JSON: {response.json()}")
            except requests.exceptions.JSONDecodeError:
                self.log_info(f"Resposta não-JSON: {response.text}")

        except Exception:
            self.log_error("FALHA NA REQUISIÇÃO!")
            self.log_error(traceback.format_exc())
        finally:
            self.log_info("TESTE POST FINALIZADO.")
            os.environ["NO_PROXY"] = original_no_proxy
            self.root.after(0, self._toggle_buttons, True)

    def clear_logs(self):
        self.log_area.configure(state='normal')
        self.log_area.delete(1.0, tk.END)
        self.log_area.configure(state='disabled')

    def copy_logs(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.log_area.get(1.0, tk.END))
        messagebox.showinfo("Copiado", "O conteúdo do log foi copiado para a área de transferência.")

if __name__ == "__main__":
    # Workaround para PyInstaller encontrar o diretório base em modo --onefile
    if getattr(sys, 'frozen', False):
        os.chdir(sys._MEIPASS) # type: ignore

    root = tk.Tk()
    app = NetworkTesterApp(root)
    root.mainloop()