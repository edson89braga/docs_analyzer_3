# test_flet_filepicker.py
import flet as ft
import os
import time
import shutil
import logging
from pathlib import Path
from typing import Optional

# --- Configuração de Logging Simples para o Teste ---
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(module)s - %(funcName)s - %(message)s')
logger = logging.getLogger("TestFilePicker")

# Silencia logs de bibliotecas 
logging.getLogger("flet_core").setLevel(logging.WARNING)
logging.getLogger("flet_runtime").setLevel(logging.WARNING)
logging.getLogger("flet_web").setLevel(logging.WARNING)
logging.getLogger("flet").setLevel(logging.WARNING)
logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("watchdog").setLevel(logging.WARNING)
logging.getLogger("uvicorn").setLevel(logging.INFO) # Pode voltar para INFO se o patch funcionar
logging.getLogger("uvicorn.error").setLevel(logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING) # Manter acesso em WARNING
logging.getLogger("starlette").setLevel(logging.WARNING)

# --- Constantes e Configuração ---
APP_TITLE_TEST = "Teste FilePicker Flet"
FLET_SECRET_KEY_TEST = "uma_chave_secreta_para_teste_12345" # Necessário para uploads web
UPLOAD_DIR_NAME_TEST = "uploads_test_picker"
UPLOAD_DIR_ABS_TEST = os.path.abspath(UPLOAD_DIR_NAME_TEST)

# Certifique-se de que FLET_SECRET_KEY está definida no ambiente para uploads web
if not os.getenv("FLET_SECRET_KEY"):
    os.environ["FLET_SECRET_KEY"] = FLET_SECRET_KEY_TEST

# Limpa e (re)cria o diretório de uploads de teste na inicialização do script
if os.path.exists(UPLOAD_DIR_ABS_TEST):
    shutil.rmtree(UPLOAD_DIR_ABS_TEST)
os.makedirs(UPLOAD_DIR_ABS_TEST, exist_ok=True)
logger.info(f"Diretório de uploads para teste limpo e criado em: {UPLOAD_DIR_ABS_TEST}")

# --- Variáveis de Estado Globais para o Teste (Simplicidade) ---
# Em uma app real, isso estaria em uma classe de controller ou na sessão da página.
status_text_global: Optional[ft.Text] = None
file_picker_global: Optional[ft.FilePicker] = None

# --- Callbacks do FilePicker ---
def on_dialog_result(e: ft.FilePickerResultEvent):
    global status_text_global
    logger.info(f"FilePicker on_dialog_result: Evento recebido - {e}")
    if status_text_global is None: return

    if e.files: # Para pick_files
        files_str = ", ".join([f.name for f in e.files])
        status_text_global.value = f"Arquivos selecionados para UPLOAD: {files_str}\n"
        status_text_global.value += f"  - Nome do primeiro arquivo: {e.files[0].name}\n"
        status_text_global.value += f"  - Tamanho do primeiro arquivo: {e.files[0].size} bytes\n"
        status_text_global.value += f"  - Caminho cliente (desktop): {e.files[0].path}\n" # Será None no modo web
        logger.info(f"Arquivos selecionados para upload: {files_str}")

        # Lógica de Upload (relevante para modo web)
        if not e.files[0].path: # Indica modo WEB (ou erro ao obter path no desktop)
            logger.info("Modo Web detectado (sem path cliente). Iniciando processo de upload para o servidor Flet.")
            upload_files_list = []
            for f_obj in e.files:
                if file_picker_global and file_picker_global.page: # Checa se page está disponível
                    try:
                        upload_url = file_picker_global.page.get_upload_url(f_obj.name, expires=60)
                        if upload_url:
                            upload_files_list.append(
                                ft.FilePickerUploadFile(name=f_obj.name, upload_url=upload_url)
                            )
                            logger.info(f"URL de upload gerada para {f_obj.name}: {upload_url[:50]}...")
                        else:
                            logger.error(f"Falha ao gerar URL de upload para {f_obj.name}.")
                            status_text_global.value += f"\nERRO: Falha ao obter URL de upload para {f_obj.name}."
                    except Exception as ex_url:
                        logger.error(f"Exceção ao gerar URL de upload para {f_obj.name}: {ex_url}", exc_info=True)
                        status_text_global.value += f"\nEXCEÇÃO URL: {ex_url} para {f_obj.name}."
                else:
                    logger.error("file_picker_global.page não está definido. Não é possível obter URL de upload.")
            
            if upload_files_list and file_picker_global:
                logger.info(f"Chamando file_picker.upload() com {len(upload_files_list)} arquivo(s).")
                status_text_global.value += "\nIniciando upload para o servidor Flet..."
                file_picker_global.upload(files=upload_files_list)
                # Um page.update() aqui pode ser necessário para o Flet processar o comando de upload
                if file_picker_global.page:
                    file_picker_global.page.update() 
                    logger.info("page.update() chamado após file_picker.upload().")
            elif not upload_files_list:
                 logger.warning("Nenhuma URL de upload pôde ser gerada. Upload não iniciado.")

        else: # Modo Desktop (path do cliente está disponível)
            logger.info(f"Modo Desktop. Caminho do primeiro arquivo: {e.files[0].path}")
            status_text_global.value += "\nModo Desktop: Arquivo(s) selecionado(s) localmente."

    elif e.path: # Para save_file
        status_text_global.value = f"Arquivo para SALVAR selecionado em: {e.path}"
        logger.info(f"Caminho selecionado para salvar: {e.path}")
        # Aqui você faria a lógica de escrita do arquivo
        try:
            with open(e.path, "w", encoding="utf-8") as f:
                f.write(f"Arquivo de teste salvo pelo Flet em: {time.ctime()}\n")
            status_text_global.value += "\nSUCESSO: Arquivo de teste escrito com sucesso!"
            logger.info(f"Arquivo de teste escrito em {e.path}")
        except Exception as ex_write:
            status_text_global.value += f"\nERRO ao escrever arquivo: {ex_write}"
            logger.error(f"Erro ao escrever arquivo em {e.path}: {ex_write}", exc_info=True)
    else:
        status_text_global.value = "Operação do FilePicker cancelada pelo usuário."
        logger.info("Operação do FilePicker cancelada.")
    
    if status_text_global.page: status_text_global.update()


def on_upload_progress(e: ft.FilePickerUploadEvent):
    global status_text_global
    logger.info(f"FilePicker on_upload_progress: Evento recebido - {e}")
    if status_text_global is None: return

    prog_value = e.progress if e.progress is not None else -1 # Para evitar None em float()
    
    if e.error:
        status_text_global.value = f"Erro no UPLOAD de '{e.file_name}': {e.error}"
        logger.error(f"Erro no upload de '{e.file_name}': {e.error}")
    elif prog_value < 1.0 and prog_value != -1 :
        status_text_global.value = f"Progresso do UPLOAD para '{e.file_name}': {prog_value*100:.0f}%"
        logger.debug(f"Progresso do upload para '{e.file_name}': {prog_value*100:.0f}%")
    else: # Upload concluído (progress == 1.0 ou None sem erro)
        uploaded_path_on_server = os.path.join(UPLOAD_DIR_ABS_TEST, e.file_name)
        status_text_global.value = f"UPLOAD de '{e.file_name}' concluído para o servidor Flet."
        logger.info(f"Upload de '{e.file_name}' concluído para o servidor Flet.")
        
        # Verificar se o arquivo existe no servidor (com retries)
        file_found = False
        for attempt in range(5): # Tenta 5 vezes
            if os.path.exists(uploaded_path_on_server):
                file_found = True
                status_text_global.value += f"\nArquivo '{e.file_name}' VERIFICADO no servidor em: {uploaded_path_on_server}"
                logger.info(f"Arquivo '{e.file_name}' verificado no servidor (tentativa {attempt + 1}).")
                # Aqui você poderia, por exemplo, ler o arquivo para processamento
                # with open(uploaded_path_on_server, "rb") as f_server:
                #     content = f_server.read()
                #     logger.info(f"Conteúdo do arquivo '{e.file_name}' lido do servidor (primeiros 100 bytes): {content[:100]}")
                break
            else:
                logger.warning(f"Arquivo '{e.file_name}' ainda não encontrado no servidor (tentativa {attempt + 1}). Listando diretório: {os.listdir(UPLOAD_DIR_ABS_TEST)}")
                time.sleep(0.5) # Pequeno delay entre tentativas
        
        if not file_found:
            status_text_global.value += f"\nAVISO: Arquivo '{e.file_name}' NÃO ENCONTRADO no servidor após upload em '{uploaded_path_on_server}'."
            logger.error(f"Arquivo '{e.file_name}' não encontrado no servidor após upload e retries.")

    if status_text_global.page: status_text_global.update()


# --- Handlers dos Botões ---
def handle_pick_files_click(e: ft.ControlEvent):
    global file_picker_global, status_text_global
    logger.info("Botão 'Selecionar Arquivo (Upload)' clicado.")
    if file_picker_global and status_text_global:
        status_text_global.value = "Aguardando seleção de arquivos para upload..."
        if status_text_global.page: status_text_global.update()
        
        # Reatribui o on_result para garantir que o callback correto seja usado
        file_picker_global.on_result = on_dialog_result
        file_picker_global.on_upload = on_upload_progress # Configura o handler de progresso
        
        logger.debug(f"Chamando pick_files. Modo Web: {file_picker_global.page.web if file_picker_global.page else 'N/A'}")
        file_picker_global.pick_files(
            dialog_title="Selecione um ou mais arquivos para Upload",
            allow_multiple=True,
            allowed_extensions=["txt", "pdf", "png", "jpg"] # Exemplo de extensões
        )
        # Adicionar um page.update() aqui pode ajudar no modo web
        if file_picker_global.page:
            file_picker_global.page.update()
            logger.info("page.update() chamado após pick_files().")
    else:
        logger.error("file_picker_global ou status_text_global não estão definidos.")

def handle_save_file_click(e: ft.ControlEvent):
    global file_picker_global, status_text_global
    logger.info("Botão 'Salvar Arquivo (Desktop)' clicado.")
    if file_picker_global and status_text_global:
        if file_picker_global.page and file_picker_global.page.web:
            status_text_global.value = "Operação 'Salvar Como' nativa não é ideal para Web. Use 'Download Arquivo (Web)'."
            logger.warning("Tentativa de save_file em modo Web. Não recomendado.")
            if status_text_global.page: status_text_global.update()
            return

        status_text_global.value = "Aguardando diálogo 'Salvar Como'..."
        if status_text_global.page: status_text_global.update()
        
        # Reatribui o on_result para garantir que o callback correto seja usado
        file_picker_global.on_result = on_dialog_result
        # on_upload não é relevante para save_file
        
        logger.debug("Chamando save_file...")
        
        # Tentativa de update antes, conforme sugestão para problemas de diálogo
        if file_picker_global.page:
            file_picker_global.page.update()
            logger.info("page.update() chamado ANTES de save_file().")

        try:
            file_picker_global.save_file(
                dialog_title="Salvar arquivo de teste como...",
                file_name="meu_arquivo_de_teste.txt",
                allowed_extensions=["txt", "log"],
                file_type=ft.FilePickerFileType.ANY # Ou .CUSTOM se quiser restringir
            )
            logger.info("Chamada a save_file() concluída (não implica que o diálogo apareceu).")
        except Exception as ex_save:
            logger.error(f"Exceção ao chamar save_file(): {ex_save}", exc_info=True)
            status_text_global.value = f"ERRO ao tentar chamar save_file(): {ex_save}"
            if status_text_global.page: status_text_global.update()

        # Um update aqui pode ser redundante se o save_file bloqueia, mas não custa para garantir
        # if file_picker_global.page:
        #     file_picker_global.page.update()
        #     logger.info("page.update() chamado APÓS save_file().")
            
    else:
        logger.error("file_picker_global ou status_text_global não estão definidos.")


def handle_download_web_click(e: ft.ControlEvent):
    global status_text_global
    logger.info("Botão 'Download Arquivo (Web)' clicado.")
    if status_text_global and status_text_global.page:
        # Simula um arquivo que estaria no servidor (ou poderia ser gerado dinamicamente)
        # Para este teste, vamos criar um arquivo temporário no UPLOAD_DIR_ABS_TEST
        # e então fornecer um endpoint para baixá-lo.
        # Em uma app real com FastAPI, o endpoint serviria o arquivo.
        # Aqui, apenas demonstramos o page.launch_url que o cliente usaria.

        # Cria um arquivo de exemplo para download no diretório de upload
        download_filename = "arquivo_para_web_download.txt"
        temp_file_path_for_download = os.path.join(UPLOAD_DIR_ABS_TEST, download_filename)
        try:
            with open(temp_file_path_for_download, "w", encoding="utf-8") as f:
                f.write(f"Conteúdo para download via web - {time.ctime()}")
            logger.info(f"Arquivo de exemplo para download web criado em: {temp_file_path_for_download}")

            # No Flet, quando não se usa FastAPI integrado, o "download" via launch_url
            # para arquivos locais no servidor onde Flet está rodando (Python backend)
            # é mais complexo. `page.launch_url` é para URLs externas.
            # Para servir arquivos locais, o Flet precisa expô-los.
            # O diretório `assets_dir` em `ft.app()` é para isso.
            # Vamos assumir que UPLOAD_DIR_ABS_TEST foi adicionado como `assets_dir`.
            
            # O caminho para launch_url deve ser relativo ao que o servidor Flet expõe.
            # Se UPLOAD_DIR_ABS_TEST é `C:\path\to\project\uploads_test_picker`
            # e foi passado como `assets_dir` ou `upload_dir` para `ft.app`,
            # o Flet o servirá na raiz ou sob um prefixo.
            # Se for servido na raiz (como `upload_dir` faz), a URL seria /nome_do_arquivo.
            
            # Verifique como seu ft.app está configurado (assets_dir, upload_dir)
            # Para upload_dir, os arquivos são servidos em /<upload_dir_name>/<file_name>
            # No nosso caso, seria /uploads_test_picker/arquivo_para_web_download.txt
            # (Assumindo que UPLOAD_DIR_NAME_TEST é 'uploads_test_picker')

            # Se o `ft.app(upload_dir=UPLOAD_DIR_ABS_TEST)` foi usado,
            # o Flet automaticamente serve os arquivos desse diretório.
            # A URL para `launch_url` seria o nome do arquivo se UPLOAD_DIR_ABS_TEST for
            # considerado a "raiz" para os uploads servidos.
            # Mais precisamente, Flet serve `upload_dir` em `/<nome_da_pasta_upload_dir>/<arquivo>`
            # Se UPLOAD_DIR_ABS_TEST é C:\path\to\project\uploads_test_picker,
            # e o nome da pasta é uploads_test_picker, então o caminho é /uploads_test_picker/arquivo...

            # Testando com o nome da pasta base do upload_dir
            #url_para_download = f"/{Path(UPLOAD_DIR_ABS_TEST).name}/{download_filename}"
            url_para_download = f"/{download_filename}"

            status_text_global.value = f"Tentando download web via launch_url: {url_para_download}"
            logger.info(f"Chamando page.launch_url('{url_para_download}')")
            status_text_global.page.launch_url(url_para_download, web_window_name="_blank")

        except Exception as ex_prep_dl:
            status_text_global.value = f"Erro ao preparar arquivo para download web: {ex_prep_dl}"
            logger.error(f"Erro ao preparar arquivo para download web: {ex_prep_dl}", exc_info=True)
        
        if status_text_global.page: status_text_global.update()
    else:
        logger.error("status_text_global ou sua page não estão definidos para download web.")


# --- Função Principal da Aplicação de Teste ---
def main(page: ft.Page):
    global status_text_global, file_picker_global
    page.title = APP_TITLE_TEST
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    logger.info(f"Página de teste iniciada. Modo Web: {page.web}")
    logger.info(f"Diretório de upload configurado para ft.app: {UPLOAD_DIR_ABS_TEST}")


    # Instanciar e configurar o FilePicker global
    file_picker_global = ft.FilePicker(
        on_result=on_dialog_result, # Callback unificado inicial
        on_upload=on_upload_progress
    )
    page.overlay.append(file_picker_global) # Adiciona ao overlay uma vez

    # Controle para exibir status
    status_text_global = ft.Text("Status: Aguardando ação...", selectable=True, width=600, max_lines=10, overflow=ft.TextOverflow.VISIBLE)

    # Botões
    pick_button = ft.ElevatedButton(
        "1. Selecionar Arquivo (Upload Desktop/Web)",
        icon=ft.icons.UPLOAD_FILE,
        on_click=handle_pick_files_click
    )
    save_button = ft.ElevatedButton(
        "2. Salvar Arquivo (Desktop Nativo)",
        icon=ft.icons.SAVE_AS,
        on_click=handle_save_file_click,
        # Desabilitar save_file em modo web, pois não funciona como esperado
        disabled=page.web, 
        tooltip="Abre o diálogo 'Salvar Como' do sistema (funciona melhor no Desktop)."
    )
    download_web_button = ft.ElevatedButton(
        "3. Download Arquivo (Simulação Web)",
        icon=ft.icons.CLOUD_DOWNLOAD,
        on_click=handle_download_web_click,
        # Habilitar apenas em modo web
        disabled=not page.web,
        tooltip="Simula um download para aplicações web (usa page.launch_url)."
    )

    page.add(
        ft.Column(
            [
                ft.Text(APP_TITLE_TEST, style=ft.TextThemeStyle.HEADLINE_MEDIUM),
                ft.Text(f"Rodando em modo: {'WEB' if page.web else 'DESKTOP'}"),
                ft.Text(f"Diretório de Upload/Assets (para simulação web): {UPLOAD_DIR_ABS_TEST}"),
                ft.Divider(),
                pick_button,
                save_button,
                download_web_button,
                ft.Divider(),
                ft.Text("Status das Operações:", weight=ft.FontWeight.BOLD),
                ft.Container(content=status_text_global, padding=10, border=ft.border.all(1, ft.colors.BLACK26), border_radius=5)
            ],
            alignment=ft.MainAxisAlignment.START,
            horizontal_alignment=ft.CrossAxisAlignment.START,
            spacing=15,
            width=700, # Para melhor visualização
            #scroll=ft.ScrollMode.ADAPTIVE
        )
    )
    page.update()

if __name__ == "__main__":
    logger.info("Iniciando aplicação de teste FilePicker Flet...")
    ft.app(
        target=main,
        assets_dir=UPLOAD_DIR_ABS_TEST, # Para que o Flet sirva arquivos deste diretório no modo web
        upload_dir=UPLOAD_DIR_ABS_TEST, # Para uploads no modo web
        #view=None
        #view=ft.AppView.WEB_BROWSER # Mude para None ou ft.AppView.FLET_APP para testar modo desktop
        # port=8555 # Opcional, para definir a porta
    )

