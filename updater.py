# updater.py
import argparse
import logging
import os, sys, tempfile
import requests, zipfile, re
import shutil, time
import subprocess, psutil
import tkinter as tk
from tkinter import messagebox
from typing import List

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Configuração do Logging ---
# Loga para o console e para um arquivo para facilitar a depuração
LOG_FILE = os.path.join(BASE_DIR, "updater.log")

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
    """Aguarda um pouco e encerra o processo da aplicação principal pelo seu PID."""
    # Adiciona uma pequena pausa para garantir que o processo pai tenha tempo de se registrar
    # antes de tentarmos encerrá-lo, especialmente em modo de desenvolvimento.
    time.sleep(1) 

    for attempt in range(3): # Tenta por até 3 segundos
        try:
            if psutil.pid_exists(pid):
                logging.info(f"Tentativa {attempt + 1}: Encerrando a aplicação principal (PID: {pid})...")
                process = psutil.Process(pid)
                process.terminate()
                process.wait(timeout=5)
                logging.info("Aplicação principal encerrada com sucesso.")
                return # Sai da função se teve sucesso
            else:
                logging.info("Processo principal já não está mais em execução.")
                return # Sai da função se o processo já terminou
        except psutil.NoSuchProcess:
            logging.warning(f"Processo com PID {pid} não encontrado na tentativa {attempt + 1}. Provavelmente já foi fechado.")
            return # Processo já não existe
        except psutil.TimeoutExpired:
            logging.warning(f"Timeout ao esperar o processo {pid} encerrar. Forçando (kill)...")
            psutil.Process(pid).kill()
            return
        except Exception as e:
            logging.error(f"Erro ao tentar encerrar o processo principal: {e}")
        time.sleep(1) # Espera 1 segundo antes de tentar novamente

    logging.warning(f"Não foi possível encerrar o processo principal (PID: {pid}) após múltiplas tentativas, pode já ter sido fechado.")

def download_file(url: str, dest_path: str, chunk_size=8192):
    """Baixa um arquivo da URL, exibindo o progresso no console."""
    logging.info(f"Baixando atualização de: {url}")
    try:
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            downloaded = 0
            with open(dest_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
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
    # Usa o diretório temporário do sistema para extração
    temp_extract_dir = tempfile.mkdtemp(prefix="update_")

    logging.info(f"Diretório temporário de extração criado em: {temp_extract_dir}")
    logging.info(f"Extraindo '{os.path.basename(zip_path)}' para o diretório temporário...")

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(temp_extract_dir)
    logging.info("Extração concluída.")

    # --- Lógica para encontrar o diretório de origem ---
    extracted_items = os.listdir(temp_extract_dir)
    # Verifica se o ZIP continha uma única pasta raiz
    if len(extracted_items) == 1 and os.path.isdir(os.path.join(temp_extract_dir, extracted_items[0])):
        # Se sim, os arquivos de origem estão dentro dessa pasta
        source_items_dir = os.path.join(temp_extract_dir, extracted_items[0])
        logging.info(f"Conteúdo do ZIP extraído de uma pasta raiz: {source_items_dir}")
    else:
        # Se não, os arquivos de origem estão na raiz do diretório de extração
        source_items_dir = temp_extract_dir
        logging.info(f"Conteúdo do ZIP extraído diretamente para a raiz: {source_items_dir}")

    backup_files: List[str] = []
    newly_moved_items: List[str] = []
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
            source_path = os.path.join(source_items_dir, item_name)
            shutil.move(source_path, target_dir)
            newly_moved_items.append(item_name)
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
        # 1. Primeiro, remove os arquivos/pastas que acabaram de ser movidos
        logging.info("Rollback: Removendo arquivos recém-movidos...")
        for item_name in newly_moved_items:
            path_to_remove = os.path.join(target_dir, item_name)
            try:
                if os.path.isdir(path_to_remove):
                    shutil.rmtree(path_to_remove)
                else:
                    os.remove(path_to_remove)
            except Exception as remove_err:
                logging.error(f"ERRO no Rollback: não foi possível remover o novo item '{path_to_remove}'. Erro: {remove_err}")

        # 2. Agora, restaura os backups        
        for backup_path in backup_files:
            original_path = backup_path.replace(".bak", "")
            try:
                if os.path.exists(backup_path):
                    os.rename(backup_path, original_path)
                    logging.info(f"  - Restaurado: {os.path.basename(original_path)}")
            except Exception as rollback_err:
                logging.error(f"ERRO CRÍTICO no Rollback: não foi possível restaurar '{backup_path}'. A instalação pode estar corrompida. Erro: {rollback_err}")
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
    parser.add_argument("--restart-arg", help="Argumento opcional para o executável a ser reiniciado.")
    args = parser.parse_args()

    logging.info("--- ATUALIZADOR INICIADO ---")
    logging.info(f"Argumentos recebidos: {args}")

    try:
        # 1. Encerrar aplicação principal
        kill_process(int(args.pid))
        
        # 2. Baixar o arquivo de atualização
        # Usa o diretório temporário do sistema para downloads
        temp_download_dir = tempfile.mkdtemp(prefix="updater_dl_")
        zip_path = os.path.join(temp_download_dir, args.filename)
        download_file(args.url, zip_path)

        # 3. Executar a atualização segura
        perform_safe_update(zip_path, args.target_dir)

        # 4. Reiniciar a aplicação
        logging.info(f"Atualização concluída. Reiniciando '{args.restart_exe}'...")
        restart_path = os.path.join(args.target_dir, args.restart_exe)
        
        command = [restart_path]
        if args.restart_arg:
            command.append(args.restart_arg)
        subprocess.Popen(command)

    except Exception as e:
        show_error_and_exit(f"Um erro inesperado ocorreu durante a atualização: {e}")
    finally:
        # Limpeza final
        if 'temp_download_dir' in locals() and os.path.exists(temp_download_dir):
            shutil.rmtree(temp_download_dir, ignore_errors=True)
        logging.info("--- ATUALIZADOR FINALIZADO ---")

if __name__ == "__main__":
    main()
    _ = input("Pressione qualquer tecla para encerrar...")

# >>> pyinstaller --name updater --onefile --add-data "C:\Users\edson.eab\AppData\Local\pypoetry\Cache\virtualenvs\docs-analyzer-3-DJ3PQuGu-py3.13\Lib\site-packages\psutil;psutil" updater.py

