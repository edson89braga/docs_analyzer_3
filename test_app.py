# test_app.py
import flet as ft
import keyring
import os
import sys

# Constantes para o teste do keyring
SERVICE_NAME = "PyInstallerKeyringTest"
USERNAME = "test_user"

def main(page: ft.Page):
    page.title = "Teste de Compilação PyInstaller"
    page.vertical_alignment = ft.MainAxisAlignment.CENTER

    status_text = ft.Text("Pronto para testar...", text_align=ft.TextAlign.CENTER)
    secret_field = ft.TextField(label="Segredo para Salvar", width=300)

    def save_secret(e):
        try:
            keyring.set_password(SERVICE_NAME, USERNAME, secret_field.value)
            status_text.value = f"SUCESSO: Segredo salvo no keyring para '{USERNAME}'."
            status_text.color = ft.Colors.GREEN
            print(status_text.value) # Log para o console de depuração
        except Exception as ex:
            status_text.value = f"ERRO ao salvar: {ex}"
            status_text.color = ft.Colors.RED
            print(status_text.value) # Log para o console de depuração
        page.update()

    def load_secret(e):
        try:
            secret = keyring.get_password(SERVICE_NAME, USERNAME)
            if secret:
                status_text.value = f"SUCESSO: Segredo recuperado: '{secret}'"
                status_text.color = ft.Colors.GREEN
            else:
                status_text.value = "AVISO: Nenhum segredo encontrado para este usuário."
                status_text.color = ft.Colors.ORANGE
            print(status_text.value)
        except Exception as ex:
            status_text.value = f"ERRO ao carregar: {ex}"
            status_text.color = ft.Colors.RED
            print(status_text.value)
        page.update()

    # Adiciona uma imagem para garantir que o --add-data 'assets' funcione
    try:
        logo_image = ft.Image(src="icon.png", width=100, height=100)
    except:
        logo_image = ft.Container()

    page.add(
        ft.Column(
            [
                logo_image,
                ft.Text("Teste Flet + Keyring", size=24, weight=ft.FontWeight.BOLD),
                status_text,
                secret_field,
                ft.Row(
                    [
                        ft.ElevatedButton("Salvar Segredo", on_click=save_secret),
                        ft.ElevatedButton("Carregar Segredo", on_click=load_secret),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=20,
        )
    )

if __name__ == "__main__":
    # Garante que a pasta de assets exista para o teste
    if not os.path.exists("assets"):
        os.makedirs("assets")
        print("Pasta 'assets' criada. Coloque um 'icon.png' nela para o teste da imagem.")

    # Essencial para o modo web do Flet
    os.environ["FLET_SECRET_KEY"] = "my_super_secret_test_key_12345"

    ft.app(
        target=main,
        view=ft.AppView.WEB_BROWSER,
        port=8551, # Porta diferente para não conflitar com seu app principal
        assets_dir="assets"
    )