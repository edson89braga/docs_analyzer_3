import secrets
import base64
from cryptography.fernet import Fernet

# 1. Gera a FLET_SECRET_KEY
flet_key = base64.b64encode(secrets.token_bytes(32)).decode('utf-8')
print(f"FLET_SECRET_KEY={flet_key}")

# 2. Gera a Chave Mestre de Criptografia do Firebase/Fernet
fernet_key = Fernet.generate_key().decode('utf-8')
print(f"DPF_SECRET_SIST_OPERA_FIREBASE_ENCRYPTION_KEY={fernet_key}")