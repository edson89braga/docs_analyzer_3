#set_admin.py

from src.services.firebase_manager import FbManagerAdminAuth  
import sys

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python set_admin.py <email_do_usuario> <true|false>")
        sys.exit(1)

    email = sys.argv[1]
    is_admin_str = sys.argv[2].lower()

    if is_admin_str not in ['true', 'false']:
        print("O segundo argumento deve ser 'true' ou 'false'.")
        sys.exit(1)

    is_admin_bool = is_admin_str == 'true'

    # Instancia a classe correta
    admin_auth_manager = FbManagerAdminAuth()
    success = admin_auth_manager.set_admin_claim(email, is_admin_bool)

    if success:
        print(f"Sucesso! Claim 'admin' para {email} definido como {is_admin_bool}.")
    else:
        print(f"Falha ao definir o claim para {email}.")

# Para executar: python set_admin.py usuario@exemplo.com true

