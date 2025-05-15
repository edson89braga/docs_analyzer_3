# NOVO ARQUIVO: src/flet_ui/views/llm_settings_view.py

import flet as ft
from typing import Optional, List, Dict, Any
import time # Para simular delays ou timestamps se necessário

from src.services.firebase_client import FirebaseClientFirestore # Para salvar/carregar chaves
from src.services import credentials_manager # Para criptografia local (encrypt/decrypt)
from src.flet_ui.components import (
    show_snackbar, 
    show_loading_overlay, 
    hide_loading_overlay,
    ValidatedTextField, # Se precisar de validação mais forte para URL
    CardWithHeader
)
from src.flet_ui import theme
from src.logger.logger import LoggerSetup
# from src.flet_ui.app import check_and_refresh_token_if_needed # Importar se for usar

_logger = LoggerSetup.get_logger(__name__)

# --- Dados Mockados/Configuráveis para LLMs (Provisório) ---
# No futuro, isso pode vir do Firestore ou de um arquivo de configuração.
SUPPORTED_PROVIDERS = {
    "OpenAI": {
        "display_name": "OpenAI",
        "models": [
            {"id": "gpt-4.1-nano", "name": "GPT-4.1 Nano"}, # 0.10 $ p/1M tokens
            {"id": "gpt-4.1-mini", "name": "GPT-4.1 Mini"}, # 0.40 $
            {"id": "o4-mini", "name": "OpenAI o4-mini"},    # 1.10 $
            {"id": "gpt-4.1", "name": "GPT-4.1"},           # 2.00 $
        ],
        "api_url_default": "https://api.openai.com/v1", # Exemplo, pode não ser editável pelo usuário
        "api_key_field_label": "Chave API OpenAI (sk-...)",
        "service_name_firestore": "openai_api_key" # Como será salvo no Firestore
    },
    # "azure_openai": { ... },
    # "anthropic": { ... },
}

class LLMConfigCard(CardWithHeader):
    def __init__(self, page: ft.Page, provider_id: str, provider_config: Dict[str, Any], firestore_manager: FirebaseClientFirestore):
        self.page = page
        self.provider_id = provider_id
        self.provider_config = provider_config
        self.firestore_manager = firestore_manager
        self.service_name_firestore = provider_config["service_name_firestore"]
        
        self.provider_dropdown = ft.Dropdown(
            label="Provedor LLM",
            options=[ft.dropdown.Option(list(SUPPORTED_PROVIDERS.keys()))],
            value=list(SUPPORTED_PROVIDERS.keys()), 
            #disabled=True, # Por ora, não editável a seleção do modelo aqui
            hint_text="Selecione um modelo"
        )
        # Controles do Card
        self.api_url_field = ft.TextField(
            label="URL Base da API", 
            value=provider_config["api_url_default"], 
            read_only=True, # Por ora, não editável
            # hint_text="Normalmente não precisa ser alterado"
        )
        self.model_dropdown = ft.Dropdown(
            label="Modelo LLM",
            options=[ft.dropdown.Option(model["id"], model["name"]) for model in provider_config["models"]],
            value=provider_config["models"][0]["id"] if provider_config["models"] else None, # Seleciona o primeiro por padrão
            #disabled=True, # Por ora, não editável a seleção do modelo aqui
            hint_text="Selecione um modelo"
        )
        self.api_key_field = ft.TextField(
            label=provider_config["api_key_field_label"],
            password=True,
            can_reveal_password=True,
            hint_text="Cole sua chave API aqui",
            # value será carregado
        )
        
        self.status_text = ft.Text("Carregando chave...", size=12, italic=True, color=theme.COLOR_INFO)

        save_button = ft.ElevatedButton("Salvar Chave API", icon=ft.icons.SAVE, on_click=self._handle_save_api_key)
        clear_button = ft.ElevatedButton("Deletar Chave API", icon=ft.icons.DELETE_OUTLINE, on_click=self._handle_clear_api_key)

        card_content = ft.Column(
            [   self.provider_dropdown,
                self.api_url_field,
                self.model_dropdown,
                self.api_key_field,
                self.status_text,
                ft.Row([clear_button, save_button], alignment=ft.MainAxisAlignment.END, spacing=10)
            ],
            spacing=15
        )
        
        super().__init__(
            title="Configurações atuais",
            content=card_content,
            card_elevation=2,
            header_bgcolor=ft.colors.with_opacity(0.3, theme.COLOR_INFO)
        )
        #self.load_saved_api_key() # Carrega a chave ao inicializar o card

    def _get_session_key_for_decrypted_api_key(self) -> str:
        """Gera uma chave única para armazenar a API key descriptografada na sessão."""
        return f"decrypted_api_key_{self.provider_id}_{self.service_name_firestore}"
    
    def did_mount(self):
        """
        Chamado pelo Flet após o controle ser adicionado à página e montado.
        Ideal para carregar dados iniciais que podem precisar de page.update().
        """
        _logger.debug(f"LLMConfigCard para {self.provider_id} did_mount. Carregando chave API salva.")
        self.load_saved_api_key()
        # Não é necessário chamar self.update() aqui explicitamente,
        # pois load_saved_api_key já chama self.update() no final se precisar.

    def update_card_content(self): # Método auxiliar para atualizar os controles internos do card
        """Atualiza os controles que podem mudar dentro do card, como status_text e api_key_field."""
        if self.api_key_field.page: self.api_key_field.update() # Se já estiver na página
        if self.status_text.page: self.status_text.update()
        # Se o CardWithHeader precisar de uma atualização geral (raro se os filhos atualizam)
        # super().update() ou self.update() se este método for chamado de fora após montagem.

    def _get_current_user_context(self) -> Optional[tuple[str, str]]:
        """Retorna (id_token, user_id) da sessão ou None."""
        # Importar check_and_refresh_token_if_needed aqui para quebrar ciclo se necessário
        from src.flet_ui.app import check_and_refresh_token_if_needed
        if not check_and_refresh_token_if_needed(self.page):
            return None # Já deve ter redirecionado para login
        
        id_token = self.page.session.get("auth_id_token")
        user_id = self.page.session.get("auth_user_id")
        if id_token and user_id:
            return id_token, user_id
        _logger.error(f"Contexto do usuário (token/ID) não encontrado na sessão para provedor {self.provider_id}.")
        show_snackbar(self.page, "Erro de sessão. Por favor, faça login novamente.", color=theme.COLOR_ERROR)
        self.page.go("/login")
        return None

    def load_saved_api_key(self):
        _logger.info(f"Carregando chave API salva para {self.provider_id}...")
        self.status_text.value = "Verificando chave salva..."
        self.status_text.color = theme.COLOR_INFO
        
        # Se o controle ainda não foi montado (ex: chamado antes de did_mount), 
        # não chame update ainda. did_mount garantirá a atualização inicial.
        if self.page and self.uid: # self.uid é uma boa indicação que foi adicionado/está sendo processado
            self.update_card_content() # Atualiza o status_text via método auxiliar

        context = self._get_current_user_context()
        if not context:
            self.status_text.value = "Erro de sessão ao carregar chave."
            self.status_text.color = theme.COLOR_ERROR
            if self.page and self.uid: self.update_card_content()
            return

        id_token, user_id = context
        session_key_decrypted = self._get_session_key_for_decrypted_api_key()

        # 1. Tenta carregar da sessão primeiro (cache)
        cached_decrypted_key = self.page.session.get(session_key_decrypted)
        if cached_decrypted_key:
            _logger.info(f"Chave API descriptografada para {self.service_name_firestore} encontrada na sessão (cache).")
            self.api_key_field.hint_text = "Chave API configurada (em cache). Preencha para alterar."
            self.api_key_field.value = "" # Não mostramos a chave
            self.status_text.value = "Chave API está configurada e pronta para uso."
            self.status_text.color = theme.COLOR_SUCCESS
            if self.page and self.uid: self.update_card_content()
            return
        
        # Não usar show_loading_overlay aqui se for chamado de did_mount,
        # pois o overlay pode cobrir a UI que está sendo montada.
        # Se for uma ação do usuário, aí sim.
        # Para a carga inicial, o "Carregando chave..." no status_text é suficiente.
        # show_loading_overlay(self.page, f"Carregando configuração de {self.provider_config['display_name']}...")
        try:
            encrypted_key_bytes = self.firestore_manager.get_user_api_key_client(
                id_token, user_id, self.service_name_firestore
            )
            # hide_loading_overlay(self.page) # Só se show_loading_overlay foi chamado

            if encrypted_key_bytes:
                _logger.info(f"Chave API criptografada encontrada para {self.service_name_firestore}.")
                self.api_key_field.hint_text = "Chave API configurada. Preencha para alterar."
                self.api_key_field.value = "" 
                self.status_text.value = "Chave API está configurada e salva."
                self.status_text.color = theme.COLOR_SUCCESS
            else:
                _logger.info(f"Nenhuma chave API encontrada para {self.service_name_firestore}.")
                self.api_key_field.hint_text = "Nenhuma chave API configurada."
                self.status_text.value = "Nenhuma chave API configurada para este serviço."
                self.status_text.color = theme.COLOR_WARNING
        except Exception as e:
            # hide_loading_overlay(self.page)
            _logger.error(f"Erro ao carregar chave API para {self.service_name_firestore}: {e}", exc_info=True)
            self.status_text.value = "Erro ao carregar configuração da chave."
            self.status_text.color = theme.COLOR_ERROR
        
        if self.page and self.uid:
            self.update_card_content() # Atualiza os campos e o status_text

    # _get_current_user_context, _handle_save_api_key, _handle_clear_api_key como antes,
    # mas chamando self.update_card_content() no final deles em vez de self.update() diretamente
    # para garantir que os filhos sejam atualizados.

    def _handle_save_api_key(self, e):
        new_api_key_value = self.api_key_field.value
        if not new_api_key_value:
            show_snackbar(self.page, "O campo da Chave API está vazio. Para remover uma chave, use 'Limpar Chave'.", color=theme.COLOR_WARNING)
            return

        _logger.info(f"Tentando salvar chave API para {self.provider_id}.")
        context = self._get_current_user_context()
        if not context: return
        id_token, user_id = context

        # Tarefa 1.3.5: Criptografia local
        _logger.debug("Criptografando chave API localmente...")
        encrypted_key_bytes: Optional[bytes] = None
        try:
            if not credentials_manager.get_encryption_key(): # Verifica se a chave Fernet existe no keyring
                _logger.error("Chave de criptografia Fernet local não encontrada no Keyring. Não é possível salvar a API key.")
                show_snackbar(self.page, "Erro de configuração local: Chave de criptografia principal não encontrada.", color=theme.COLOR_ERROR)
                self.status_text.value = "Erro: Chave de criptografia local ausente."
                self.status_text.color = theme.COLOR_ERROR
                self.update()
                return
            encrypted_key_bytes = credentials_manager.encrypt(new_api_key_value)
        except Exception as enc_ex:
            _logger.error(f"Falha ao criptografar chave API: {enc_ex}", exc_info=True)
            show_snackbar(self.page, "Erro ao proteger a chave API antes de salvar.", color=theme.COLOR_ERROR)
            return

        if not encrypted_key_bytes:
            show_snackbar(self.page, "Falha ao preparar a chave API para salvamento.", color=theme.COLOR_ERROR)
            return

        show_loading_overlay(self.page, f"Salvando chave para {self.provider_config['display_name']}...")
        try:
            # Tarefa 1.3.6: Salvar no Firestore
            success = self.firestore_manager.save_user_api_key_client(
                id_token, user_id, self.service_name_firestore, encrypted_key_bytes
            )
            hide_loading_overlay(self.page)
            
            session_key_decrypted = self._get_session_key_for_decrypted_api_key()
            if success:
                _logger.info(f"Chave API para {self.service_name_firestore} salva com sucesso.")
                self.page.session.set(session_key_decrypted, new_api_key_value)
                _logger.info(f"Chave API descriptografada para {self.service_name_firestore} armazenada na sessão.")
                show_snackbar(self.page, "Chave API salva com sucesso!", color=theme.COLOR_SUCCESS)
                self.api_key_field.value = "" # Limpa o campo após salvar
                self.api_key_field.hint_text = "Chave API configurada. Preencha para alterar."
                self.status_text.value = "Chave API atualizada e salva."
                self.status_text.color = theme.COLOR_SUCCESS
            else:
                # A falha pode ser por erro de API ou porque _execute_sensitive_action forçou logout
                # Se forçou logout, a UI já deve ter sido redirecionada.
                # Se não, mostramos o erro.
                if self.page.session.get("auth_id_token"): # Verifica se ainda está logado
                    show_snackbar(self.page, "Não foi possível salvar a chave API.", color=theme.COLOR_ERROR)
                    self.status_text.value = "Erro ao salvar a chave."
                    self.status_text.color = theme.COLOR_ERROR
                if self.page.session.contains_key(session_key_decrypted):
                    self.page.session.remove(session_key_decrypted)
                _logger.error(f"Falha ao salvar chave API para {self.service_name_firestore} no Firestore.")
        except Exception as ex:
            hide_loading_overlay(self.page)
            _logger.error(f"Erro inesperado ao salvar chave API: {ex}", exc_info=True)
            if self.page.session.contains_key(session_key_decrypted):
                self.page.session.remove(session_key_decrypted)
            show_snackbar(self.page, "Ocorreu um erro inesperado ao salvar a chave.", color=theme.COLOR_ERROR)
            self.status_text.value = "Erro inesperado ao salvar."
            self.status_text.color = theme.COLOR_ERROR
        
        self.update_card_content()

    def _handle_clear_api_key(self, e):
        _logger.info(f"Tentando limpar chave API para {self.provider_id}.")
        context = self._get_current_user_context()
        if not context: return
        id_token, user_id = context

        # Para "limpar", salvamos um valor nulo (ou bytes vazios, dependendo de como o Firestore trata)
        # Ou, melhor, o método save_user_api_key_client poderia ter um argumento para deletar um campo.
        # Por ora, vamos salvar bytes vazios criptografados para indicar "sem chave".
        # No entanto, uma abordagem mais limpa seria ter um método "delete_user_api_key_client" no Firestore manager.
        # Vamos simular a remoção salvando bytes vazios.
        empty_encrypted_key = credentials_manager.encrypt("") # Criptografa string vazia
        if empty_encrypted_key is None: # Deveria funcionar, mas por segurança
             show_snackbar(self.page, "Erro ao preparar limpeza da chave.", color=theme.COLOR_ERROR)
             return

        show_loading_overlay(self.page, f"Limpando chave para {self.provider_config['display_name']}...")

        session_key_decrypted = self._get_session_key_for_decrypted_api_key()
        if self.page.session.contains_key(session_key_decrypted):
            self.page.session.remove(session_key_decrypted)
            _logger.info(f"Chave API descriptografada para {self.service_name_firestore} removida da sessão.")

        try:
            success = self.firestore_manager.save_user_api_key_client(
                id_token, user_id, self.service_name_firestore, empty_encrypted_key 
                # Idealmente: self.firestore_manager.delete_field_user_api_key_client(id_token, user_id, self.service_name_firestore)
            )
            hide_loading_overlay(self.page)
            if success:
                _logger.info(f"Chave API para {self.service_name_firestore} limpa/removida.")
                show_snackbar(self.page, "Chave API removida com sucesso!", color=theme.COLOR_SUCCESS)
                self.api_key_field.value = ""
                self.api_key_field.hint_text = "Nenhuma chave API configurada."
                self.status_text.value = "Chave API foi removida."
                self.status_text.color = theme.COLOR_WARNING
            else:
                if self.page.session.get("auth_id_token"):
                    show_snackbar(self.page, "Não foi possível limpar a chave API.", color=theme.COLOR_ERROR)
                    self.status_text.value = "Erro ao limpar a chave."
                    self.status_text.color = theme.COLOR_ERROR
                _logger.error(f"Falha ao limpar chave API para {self.service_name_firestore} no Firestore.")
        except Exception as ex:
            hide_loading_overlay(self.page)
            _logger.error(f"Erro inesperado ao limpar chave API: {ex}", exc_info=True)
            show_snackbar(self.page, "Ocorreu um erro inesperado ao limpar a chave.", color=theme.COLOR_ERROR)
    
        self.update_card_content()


def create_llm_settings_view(page: ft.Page) -> ft.View:
    _logger.info("Criando a view de Configurações LLM.")

    if not page.session.get("auth_id_token"): # Verificação básica de autenticação
        _logger.warning("Usuário não autenticado tentou acessar Configurações LLM. Redirecionando.")
        page.go("/login")
        return ft.View(route="/settings/llm", controls=[ft.Text("Redirecionando para login...")])

    firestore_manager = FirebaseClientFirestore()
    
    llm_config_cards = []
    for provider_id, config in SUPPORTED_PROVIDERS.items():
        llm_config_cards.append(LLMConfigCard(page, provider_id, config, firestore_manager))
    
    # Botão para adicionar novo provedor (funcionalidade futura)
    add_provider_button = ft.ElevatedButton(
        "Adicionar Novo Provedor LLM", 
        icon=ft.icons.ADD_CIRCLE_OUTLINE,
        disabled=True, # Desabilitado por ora
        tooltip="Funcionalidade para versões futuras"
    )

    settings_content = ft.Column(
        [
            ft.Text("Configurações de Modelos de Linguagem (LLM)", size=28, weight=ft.FontWeight.BOLD),
            ft.Text(
                "Gerencie suas chaves de API para os serviços LLM utilizados pela aplicação. "
                "\nSuas chaves API são criptografadas localmente antes de serem salvas.",
                size=14, color=ft.colors.with_opacity(0.8, ft.colors.ON_SURFACE)
            ),
            ft.Divider(height=20),
            *llm_config_cards, # Desempacota a lista de cards
            ft.Divider(height=20),
            ft.Row([add_provider_button], alignment=ft.MainAxisAlignment.START)
        ],
        spacing=25,
        width=800, 
        # horizontal_alignment=ft.CrossAxisAlignment.CENTER
    )

    return ft.Container(content=ft.Column( 
                [settings_content] ,
                alignment=ft.MainAxisAlignment.START, 
                horizontal_alignment=ft.CrossAxisAlignment.CENTER, 
                expand=True, scroll=ft.ScrollMode.ADAPTIVE
            ),
            padding=ft.padding.symmetric(vertical=30, horizontal=20),
            alignment=ft.alignment.top_center, expand=True)

    return ft.View(
        route="/settings/llm",
        controls=[
            ft.Container(
                content=settings_content,
                alignment=ft.alignment.top_center,
                padding=ft.padding.symmetric(vertical=30, horizontal=20),
                expand=True
            )
        ],
        scroll=ft.ScrollMode.ADAPTIVE
    )

