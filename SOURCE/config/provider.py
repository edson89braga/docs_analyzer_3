# SOURCE/config/provider.py
import os
import keyring
from typing import Optional

APP_MODE = os.getenv("APP_MODE", "local")  # 'local' ou 'server'

def get_secret(service: str, key: str) -> Optional[str]:
    """Recupera segredos de acordo com o modo de execução."""
    if APP_MODE == "server":
        # No servidor, busca em variáveis de ambiente
        # Ex: DPF_SECRET_FIREBASE_KEY
        env_var = f"DPF_SECRET_{service.upper()}_{key.upper()}"
        return os.getenv(env_var)
    
    # Modo local usa o Keyring do SO
    try:
        return keyring.get_password(service, key)
    except Exception:
        return None

def set_secret(service: str, key: str, value: str):
    if APP_MODE == "server":
        # Servidor é stateless; em produção, usar Secret Manager (AWS/GCP/Vault)
        # Por ora, logamos um aviso de que persistência em server requer integração externa
        os.environ[f"DPF_SECRET_{service.upper()}_{key.upper()}"] = value
    else:
        keyring.set_password(service, key, value)
        
def is_local_mode() -> bool:
    return APP_MODE == "local"