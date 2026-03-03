# setup_credentials_firebase.py
import os
import tkinter as tk
from tkinter import filedialog, messagebox

# Configura o logger ANTES de importar outros módulos do projeto
# para garantir que as mensagens de log sejam capturadas.
import logging
from SOURCE.logger.logger import LoggerSetup
LoggerSetup.initialize(routine_name="CredentialsSetup", dev_mode=True)
logger = logging.getLogger(__name__)

from SOURCE.services import credentials_manager

def run_credentials_setup():
    """
    Abre uma GUI simples com Tkinter para guiar o usuário no setup
    das credenciais de administrador do Firebase.
    """
    root = tk.Tk()
    root.withdraw()  # Esconde a janela principal do Tkinter

    # 1. Verifica se as credenciais já existem para evitar sobrescrever
    if credentials_manager.are_credentials_set_up():
        response = messagebox.askyesno(
            "Credenciais Encontradas",
            "As credenciais de administrador já parecem estar configuradas.\n\n"
            "Deseja sobrescrevê-las com um novo arquivo de chave de serviço?"
        )
        if not response:
            logger.info("Setup cancelado pelo usuário. As credenciais existentes foram mantidas.")
            messagebox.showinfo("Operação Cancelada", "As credenciais existentes não foram alteradas.")
            root.destroy()
            return

    # 2. Pede ao usuário para selecionar o arquivo JSON
    messagebox.showinfo(
        "Setup de Credenciais",
        "Por favor, selecione o arquivo 'firebase_service_key.json' que você baixou do console do Firebase."
    )
    
    json_path = filedialog.askopenfilename(
        title="Selecione o arquivo firebase_service_key.json",
        filetypes=[("JSON files", "*.json")]
    )

    if not json_path:
        logger.warning("Nenhum arquivo selecionado. O setup de credenciais foi cancelado.")
        messagebox.showwarning("Cancelado", "Nenhum arquivo selecionado. A operação foi cancelada.")
        root.destroy()
        return

    logger.info(f"Arquivo de chave de serviço selecionado: {json_path}")

    # 3. Lê o conteúdo do arquivo e executa o setup
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            json_content_str = f.read()
        
        success = credentials_manager.setup_credentials_from_file(json_content_str)
        
        if success:
            logger.info("Credenciais de administrador configuradas com sucesso!")
            messagebox.showinfo(
                "Sucesso",
                "As credenciais de administrador do Firebase foram configuradas com sucesso!\n\n"
                "Agora você pode executar o painel de administração (run_admin_streamlit.py)."
            )
        else:
            logger.error("Falha ao executar o setup de credenciais. Verifique os logs.")
            messagebox.showerror(
                "Erro",
                "Ocorreu um erro ao configurar as credenciais. Por favor, verifique o arquivo de log para mais detalhes."
            )
    except Exception as e:
        logger.critical(f"Erro inesperado durante o setup de credenciais: {e}", exc_info=True)
        messagebox.showerror("Erro Crítico", f"Ocorreu um erro inesperado: {e}")
    finally:
        root.destroy()

if __name__ == "__main__":
    run_credentials_setup()