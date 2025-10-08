# updater.py
import argparse
import logging
import os
import sys
import requests
import zipfile
import shutil
import time
import subprocess
import psutil
import tkinter as tk
from tkinter import messagebox
from typing import List

# --- Configuração do Logging ---
# Loga para o console e para um arquivo para facilitar a depuração
LOG_FILE = "updater.log"

# Limpa o log antigo se existir
if os.path.exists(LOG_FILE):
    os.remove(LOG_FILE)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout) # Mostra logs no console
    ]
)

def show_error_and_exit(message: str):
    """Exibe uma mensagem de erro em uma caixa de diálogo e encerra."""
    logging.critical(message)
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("Erro na Atualização", f"{message}\n\nConsulte o arquivo 'updater.log' para mais detalhes.")
    root.destroy()
    sys.exit(1)

def kill_process(pid: int):
    """Encerra o processo da aplicação principal pelo seu PID."""
    try:
        if psutil.pid_exists(pid):
            logging.info(f"Encerrando a aplicação principal (PID: {pid})...")
            process = psutil.Process(pid)
            process.terminate()
            process.wait(timeout=12)  # Espera até 12 segundos para o processo encerrar
            logging.info("Aplicação principal encerrada.")
    except psutil.NoSuchProcess:
        logging.warning(f"Processo com PID {pid} não encontrado. Pode já ter sido fechado.")
    except psutil.TimeoutExpired:
        logging.warning(f"Timeout ao esperar o processo {pid} encerrar. Forçando o encerramento (kill)...")
        psutil.Process(pid).kill()
    except Exception as e:
        logging.error(f"Erro ao tentar encerrar o processo principal: {e}")
        # Continua mesmo assim, pois o processo pode já ter sido encerrado

def download_file(url: str, dest_path: str):
    """Baixa um arquivo da URL, exibindo o progresso no console."""
    logging.info(f"Baixando atualização de: {url}")
    try:
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            block_size = 8192
            downloaded = 0
            with open(dest_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=block_size):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        # \r move o cursor para o início da linha
                        print(f"\rProgresso: {downloaded // 1024} KB / {total_size // 1024} KB ({progress:.1f}%)", end="")
        print("\nDownload concluído.")
        logging.info(f"Arquivo salvo em: {dest_path}")
    except requests.RequestException as e:
        show_error_and_exit(f"Erro de rede ao baixar a atualização: {e}")

def perform_safe_update(zip_path: str, target_dir: str):
    """
    Executa o processo de atualização de forma segura:
    1. Extrai para uma pasta temporária.
    2. Renomeia arquivos/pastas existentes para .bak.
    3. Move os novos arquivos para o local correto.
    4. Limpa os backups se tudo der certo.
    5. Tenta reverter em caso de falha.
    """
    temp_extract_dir = os.path.join(target_dir, "_update_temp")
    if os.path.exists(temp_extract_dir):
        shutil.rmtree(temp_extract_dir)
    os.makedirs(temp_extract_dir)

    logging.info(f"Extraindo '{zip_path}' para '{temp_extract_dir}'...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(temp_extract_dir)
    logging.info("Extração concluída.")

    # A pasta extraída geralmente tem o nome do zip ou um nome de build.
    # Vamos assumir que há apenas uma pasta dentro do diretório de extração.
    source_items_dir = os.path.join(temp_extract_dir, os.listdir(temp_extract_dir)[0])

    backup_files: List[str] = []
    try:
        # Etapa 1: Fazer backup dos itens existentes
        logging.info("Criando backups dos arquivos antigos...")
        for item_name in os.listdir(source_items_dir):
            source_item_path = os.path.join(source_items_dir, item_name)
            target_item_path = os.path.join(target_dir, item_name)
            if os.path.exists(target_item_path):
                backup_path = f"{target_item_path}.bak"
                # Remove backup antigo se existir
                if os.path.exists(backup_path):
                    if os.path.isdir(backup_path):
                        shutil.rmtree(backup_path)
                    else:
                        os.remove(backup_path)
                
                os.rename(target_item_path, backup_path)
                backup_files.append(backup_path)
                logging.info(f"  - Backup criado: {os.path.basename(backup_path)}")

        # Etapa 2: Mover os novos itens
        logging.info("Movendo novos arquivos para o diretório da aplicação...")
        for item_name in os.listdir(source_items_dir):
            shutil.move(os.path.join(source_items_dir, item_name), target_dir)
        logging.info("Novos arquivos movidos com sucesso.")

        # Etapa 3: Limpar backups
        logging.info("Limpando backups...")
        for backup_path in backup_files:
            if os.path.isdir(backup_path):
                shutil.rmtree(backup_path)
            else:
                os.remove(backup_path)
        logging.info("Backups limpos.")

    except Exception as e:
        logging.error(f"ERRO durante a atualização: {e}", exc_info=True)
        # Etapa de Rollback
        logging.info("Tentando reverter a atualização (rollback)...")
        for backup_path in backup_files:
            original_path = backup_path.replace(".bak", "")
            try:
                if os.path.exists(backup_path):
                    os.rename(backup_path, original_path)
                    logging.info(f"  - Restaurado: {os.path.basename(original_path)}")
            except Exception as rollback_err:
                logging.error(f"ERRO CRÍTICO no rollback: não foi possível restaurar {backup_path}. A instalação pode estar corrompida. Erro: {rollback_err}")
        show_error_and_exit(f"Ocorreu um erro e a atualização falhou. Uma tentativa de restauração foi feita, mas a aplicação pode estar instável. Erro: {e}")
    finally:
        # Limpa a pasta de extração temporária
        if os.path.exists(temp_extract_dir):
            shutil.rmtree(temp_extract_dir)

def main():
    parser = argparse.ArgumentParser(description="Application Updater")
    parser.add_argument("--url", required=True, help="URL do arquivo .zip da atualização.")
    parser.add_argument("--filename", required=True, help="Nome do arquivo .zip esperado.")
    parser.add_argument("--target-dir", required=True, help="Diretório de destino da aplicação.")
    parser.add_argument("--restart-exe", required=True, help="Nome do executável a ser reiniciado após a atualização.")
    parser.add_argument("--pid", required=True, help="PID do processo da aplicação principal a ser encerrado.")
    args = parser.parse_args()

    logging.info("--- ATUALIZADOR INICIADO ---")
    logging.info(f"Argumentos recebidos: {args}")

    try:
        # 1. Encerrar aplicação principal
        kill_process(int(args.pid))
        
        # 2. Baixar o arquivo de atualização
        temp_dir = os.path.join(args.target_dir, "_updater_downloads")
        os.makedirs(temp_dir, exist_ok=True)
        zip_path = os.path.join(temp_dir, args.filename)
        download_file(args.url, zip_path)

        # 3. Executar a atualização segura
        perform_safe_update(zip_path, args.target_dir)

        # 4. Reiniciar a aplicação
        logging.info(f"Atualização concluída. Reiniciando '{args.restart_exe}'...")
        restart_path = os.path.join(args.target_dir, args.restart_exe)
        subprocess.Popen([restart_path])

    except Exception as e:
        show_error_and_exit(f"Um erro inesperado ocorreu durante a atualização: {e}")
    finally:
        # Limpeza final
        if 'temp_dir' in locals() and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        logging.info("--- ATUALIZADOR FINALIZADO ---")

if __name__ == "__main__":
    main()

# >>> pyinstaller --name updater --onefile --add-data "C:/path/to/your/venv/Lib/site-packages/psutil;psutil" updater.py

