# src/services/update_manager.py
import logging
import sys
import os
import json
import requests
import subprocess
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Dict

# packaging é uma biblioteca robusta para comparar versões (ex: "1.10.0" > "1.9.0")
# É uma dependência do Flet, então já deve estar disponível.
from packaging.version import parse as parse_version

from SOURCE.settings import APP_VERSION, VERSION_INFO_URL

logger = logging.getLogger(__name__)

@dataclass
class UpdateStatus:
    """Estrutura para armazenar o resultado da verificação de atualização."""
    update_available: bool = False
    is_forced: bool = False
    update_info: Optional[Dict] = None
    error_message: Optional[str] = None

def check_for_component_update(component_key: str, local_version_str: str) -> UpdateStatus:
    """
    Verifica se há uma nova versão para um componente específico (ex: 'app' ou 'ml_engine').

    1. Baixa e lê o arquivo version.json.
    2. Compara a versão local com a remota.
    3. Calcula se o prazo para atualização forçada foi atingido.

    Returns:
        UpdateStatus: Um objeto contendo o status da verificação.
    """
    if not VERSION_INFO_URL or not component_key or not local_version_str:
        msg = "URL de verificação de versão não configurada."
        logger.warning(msg)
        return UpdateStatus(error_message=msg)

    try:
        logger.info(f"Verificando atualizações para o componente '{component_key}' em: {VERSION_INFO_URL}")
        response = requests.get(VERSION_INFO_URL, timeout=10)
        response.raise_for_status()
        remote_config = response.json()

        component_info = remote_config.get(component_key, {})
        remote_version_str = component_info.get("version")
        if not remote_version_str:
            raise ValueError(f"'version' não encontrada na configuração remota para '{component_key}'.")

        local_version = parse_version(local_version_str)
        remote_version = parse_version(remote_version_str)

        if remote_version > local_version:
            logger.info(f"Nova versão encontrada: {remote_version} (local: {local_version})")
            
            release_date_str = component_info.get("release_date")
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

            return UpdateStatus(update_available=True, is_forced=is_forced, update_info=component_info)
        else:
            logger.info(f"O componente '{component_key}' está atualizado.")
            return UpdateStatus(update_available=False, update_info=component_info)

    except requests.RequestException as e:
        msg = f"Não foi possível verificar atualizações (erro de rede): {e}"
        logger.warning(msg)
        return UpdateStatus(error_message=msg)
    except (json.JSONDecodeError, ValueError) as e:
        msg = f"Não foi possível processar o arquivo de versão: {e}"
        logger.error(msg)
        return UpdateStatus(error_message=msg)

def run_updater(update_info: Dict, target_dir_override: Optional[str] = None):
    """
    Inicia o updater.exe, passando os argumentos necessários, e encerra a aplicação principal.
    """
    try:
        # Usa o override do diretório de destino se fornecido, senão calcula o padrão.
        app_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(sys.argv[0]))   
        target_dir = target_dir_override or app_dir     
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
        args = [updater_path]

        if getattr(sys, 'frozen', False):
            current_exe_name = os.path.basename(sys.executable)
            args.extend(["--restart-exe", current_exe_name])
        else: # Modo de desenvolvimento
            current_script_name = os.path.basename(sys.argv[0]) # ex: run.py
            args.extend([
                "--restart-exe", sys.executable, # python.exe
                "--restart-arg", current_script_name # run.py
            ])        
        args.extend([
            "--url", download_url,
            "--filename", filename,
            "--target-dir", target_dir,
            "--pid", str(os.getpid()) # Passa o PID do processo atual
        ])
        
        logger.info(f"Iniciando o atualizador com os seguintes argumentos: {args}")
        # No Windows, usar DETACHED_PROCESS desvincula o updater do processo pai,
        # permitindo que o pai encerre sem afetar o filho.
        creationflags = subprocess.DETACHED_PROCESS if sys.platform == "win32" else 0
        subprocess.Popen(args, creationflags=creationflags)

        logger.info("Aplicação principal encerrando para permitir a atualização...")
        return 'exit'

    except Exception as e:
        logger.critical(f"Falha crítica ao tentar executar o updater.exe: {e}", exc_info=True)



