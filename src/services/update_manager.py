# src/services/update_manager.py
import logging
import sys
import os
import json
import requests
import subprocess
import tkinter as tk
from tkinter import messagebox
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Dict
from time import sleep

# packaging é uma biblioteca robusta para comparar versões (ex: "1.10.0" > "1.9.0")
# É uma dependência do Flet, então já deve estar disponível.
from packaging.version import parse as parse_version

from src.settings import APP_VERSION, VERSION_INFO_URL

logger = logging.getLogger(__name__)

@dataclass
class UpdateStatus:
    """Estrutura para armazenar o resultado da verificação de atualização."""
    update_available: bool = False
    is_forced: bool = False
    update_info: Optional[Dict] = None
    error_message: Optional[str] = None

def check_for_updates() -> UpdateStatus:
    """
    Verifica se há uma nova versão da aplicação disponível.

    1. Baixa e lê o arquivo version.json.
    2. Compara a versão local com a remota.
    3. Calcula se o prazo para atualização forçada foi atingido.

    Returns:
        UpdateStatus: Um objeto contendo o status da verificação.
    """
    if not VERSION_INFO_URL:
        msg = "URL de verificação de versão não configurada."
        logger.warning(msg)
        return UpdateStatus(error_message=msg)

    try:
        logger.info(f"Verificando atualizações em: {VERSION_INFO_URL}")
        response = requests.get(VERSION_INFO_URL, timeout=10)
        response.raise_for_status()
        remote_config = response.json()

        app_info = remote_config.get("app", {})
        remote_version_str = app_info.get("version")
        if not remote_version_str:
            raise ValueError("'version' não encontrada na configuração remota da 'app'.")

        local_version = parse_version(APP_VERSION)
        remote_version = parse_version(remote_version_str)

        if remote_version > local_version:
            logger.info(f"Nova versão encontrada: {remote_version} (local: {local_version})")
            
            release_date_str = app_info.get("release_date")
            force_update_days = remote_config.get("force_update_after_days", 7)
            is_forced = False

            if release_date_str:
                try:
                    release_date = datetime.fromisoformat(release_date_str).date()
                    days_since_release = (datetime.now().date() - release_date).days
                    
                    if days_since_release > force_update_days:
                        is_forced = True
                        logger.warning(f"Atualização necessária. Lançada há {days_since_release} dias (limite: {force_update_days}).")

                except (ValueError, TypeError) as e:
                    logger.error(f"Formato de 'release_date' inválido no version.json: '{release_date_str}'. Erro: {e}")

            return UpdateStatus(update_available=True, is_forced=is_forced, update_info=app_info)
        else:
            logger.info("A aplicação está atualizada.")
            return UpdateStatus(update_available=False, update_info=app_info)

    except requests.RequestException as e:
        msg = f"Não foi possível verificar atualizações (erro de rede): {e}"
        logger.warning(msg)
        return UpdateStatus(error_message=msg)
    except (json.JSONDecodeError, ValueError) as e:
        msg = f"Não foi possível processar o arquivo de versão: {e}"
        logger.error(msg)
        return UpdateStatus(error_message=msg)

def _show_update_dialog(status: UpdateStatus) -> bool:
    """
    Exibe um diálogo para o usuário com base no status da atualização.
    Usa tkinter para garantir que o diálogo apareça antes da UI do Flet.

    Returns:
        bool: True se o usuário decidiu atualizar, False caso contrário.
    """
    root = tk.Tk()
    root.withdraw()  # Esconde a janela principal do tkinter

    title = "Atualização Disponível"
    version = status.update_info.get('version', 'N/A')
    notes = status.update_info.get('notes', 'Sem notas da versão.')
    
    user_choice = False
    try:
        if status.is_forced:
            title = "Atualização Obrigatória"
            message = (
                f"Sua versão ({APP_VERSION}) está desatualizada e precisa ser atualizada para a v{version}.\n\n"
                f"Notas da versão:\n{notes}\n\nA aplicação será fechada para iniciar a atualização."
            )
            messagebox.showwarning(title, message)
            user_choice = True  # A atualização é a única opção
        else:
            title = "Atualização Disponível"
            message = (
                f"Uma nova versão (v{version}) está disponível!\n\n"
                f"Notas da versão:\n{notes}\n\nDeseja atualizar agora?"
            )
            user_choice = messagebox.askyesno(title, message)
    finally:
        root.destroy()
    
    return user_choice

def run_updater(update_info: Dict):
    """
    Inicia o updater.exe, passando os argumentos necessários, e encerra a aplicação principal.
    """
    try:
        # Determina o diretório da aplicação atual
        if getattr(sys, 'frozen', False):
            app_dir = os.path.dirname(sys.executable)
            current_exe_name = os.path.basename(sys.executable)
        else:
            app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            current_exe_name = os.path.basename(sys.argv[0]) # ex: run.py
        
        updater_path = os.path.join(app_dir, "updater.exe")

        if not os.path.exists(updater_path):
            logger.critical(f"updater.exe não encontrado em '{updater_path}'. A atualização automática não pode continuar.")
            # Poderíamos mostrar um diálogo de erro aqui também
            return

        download_url = update_info.get("download_url")
        filename = update_info.get("filename")

        if not download_url or not filename:
            logger.error("URL de download ou nome do arquivo ausente nas informações de atualização.")
            return

        # Argumentos para o updater.exe
        args = [
            updater_path,
            "--url", download_url,
            "--filename", filename,
            "--target-dir", app_dir,
            "--restart-exe", current_exe_name,
            "--pid", str(os.getpid()) # Passa o PID do processo atual
        ]
        
        logger.info(f"Iniciando o atualizador com os seguintes argumentos: {args}")
        # No Windows, usar DETACHED_PROCESS desvincula o updater do processo pai,
        # permitindo que o pai encerre sem afetar o filho.
        creationflags = subprocess.DETACHED_PROCESS if sys.platform == "win32" else 0
        subprocess.Popen(args, creationflags=creationflags)

        logger.info("Aplicação principal encerrando para permitir a atualização...")
        sys.exit(0)

    except Exception as e:
        logger.critical(f"Falha crítica ao tentar executar o updater.exe: {e}", exc_info=True)
        # Mostrar um diálogo de erro final
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Erro do Atualizador", f"Não foi possível iniciar o processo de atualização: {e}")
        root.destroy()

def handle_update_check():
    """
    Função principal que orquestra todo o processo de verificação de atualização.
    """
    # Só executa a verificação se estivermos em um ambiente compilado
    if not getattr(sys, 'frozen', False):
        logger.info("[DEBUG] Verificação de atualização pulada (ambiente de desenvolvimento).")
        return

    update_status = check_for_updates()

    if update_status.update_available:
        logging.info("Atualização disponível. Mostrando diálogo para o usuário...")
        user_wants_to_update = _show_update_dialog(update_status)
        logging.info(f"Escolha do usuário: Atualizar = {user_wants_to_update}")
        if user_wants_to_update:
            logging.info("Usuário confirmou a atualização. Chamando run_updater...")
            run_updater(update_status.update_info)
        elif update_status.is_forced:
            # Se a atualização é forçada e o usuário fechou o diálogo (ou clicou não em um askyesno),
            # a aplicação deve fechar.
            logger.info("Usuário não prosseguiu com a atualização obrigatória. Encerrando aplicação.")
            sleep(1)
            os._exit(0) # Força o encerramento de todo o processo

