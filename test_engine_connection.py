# test_engine_connection.py
import requests
import time
import subprocess
import os
import sys

ENGINE_PATH = os.path.abspath("ml_engine/engine.exe") # AJUSTE ESTE CAMINHO
API_URL = "http://127.0.0.1:8001"

def is_engine_running():
    """Verifica se o motor está respondendo corretamente."""
    try:
        response = requests.post(f"{API_URL}/embed", json={"text_list": ["test"]}, timeout=3)
        if response.status_code == 200:
            print("✅ SUCESSO: Motor de ML está respondendo corretamente ao endpoint /embed.")
            return True
        else:
            print(f"⚠️ AVISO: Motor respondeu, mas com status inesperado: {response.status_code}")
            return False
    except requests.RequestException as e:
        print(f"❌ FALHA: Não foi possível conectar ao motor de ML. Erro: {e}")
        return False

def main():
    print("--- INICIANDO TESTE DE CONEXÃO DO MOTOR DE ML ---")

    # 1. Verifica se o engine.exe existe
    if not os.path.exists(ENGINE_PATH):
        print(f"ERRO CRÍTICO: Executável não encontrado em '{ENGINE_PATH}'. Verifique o caminho.")
        return

    # 2. Verifica se o engine já está rodando
    print("\nPasso 1: Verificando se o motor já está em execução...")
    if is_engine_running():
        print("O motor já estava em execução. Teste de conexão bem-sucedido.")
        input("Pressione Enter para encerrar o teste.")
        return
    else:
        print("O motor não está respondendo. Tentando iniciá-lo...")

    # 3. Inicia o engine.exe como subprocesso
    process = None
    log_file_path = os.path.join(os.path.dirname(ENGINE_PATH), "test_engine_output.log")
    try:
        print(f"\nPasso 2: Iniciando '{os.path.basename(ENGINE_PATH)}'...")
        print(f"   Os logs de saída serão salvos em: {log_file_path}")
        
        log_file = open(log_file_path, "w", encoding="utf-8")
        
        process = subprocess.Popen(
            [ENGINE_PATH],
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        print(f"   Processo iniciado com PID: {process.pid}")

        # 4. Aguarda e verifica a conexão
        print("\nPasso 3: Aguardando o servidor ficar pronto (máx 60 segundos)...")
        max_wait_time = 60
        start_time = time.time()
        server_ready = False
        while time.time() - start_time < max_wait_time:
            print(f"   Aguardando... ({int(time.time() - start_time)}s)")
            if is_engine_running():
                server_ready = True
                break
            time.sleep(2)

        if not server_ready:
            print("\n--- DIAGNÓSTICO DE FALHA ---")
            print("O motor de ML foi iniciado, mas não respondeu a tempo.")
            print("Causas prováveis:")
            print("1. O antivírus/firewall está bloqueando a execução ou a rede.")
            print("2. O executável 'engine.exe' está travando na inicialização.")
            print(f"VERIFIQUE o conteúdo do arquivo de log: {log_file_path}")
            print("-----------------------------")

    except Exception as e:
        print(f"ERRO CRÍTICO ao tentar iniciar o processo: {e}")
    finally:
        if process:
            print("\nPasso 4: Encerrando o processo do motor de ML...")
            process.terminate()
            try:
                process.wait(timeout=5)
                print("   Processo encerrado com sucesso.")
            except subprocess.TimeoutExpired:
                process.kill()
                print("   Processo forçado a encerrar.")
        
        input("Pressione Enter para fechar o terminal de teste.")

if __name__ == "__main__":
    main()