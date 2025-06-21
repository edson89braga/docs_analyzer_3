# src/flet_ui/layout.py
"""
Define elementos de layout reutilizáveis como AppBar e NavigationRail.

"""

from time import perf_counter
start_time = perf_counter()
print(f"{start_time:.4f}s - Iniciando layout.py")

import flet as ft
from typing import List, Dict, Any, Optional
# Importa definições de tema se necessário (ex: para padding ou cores)
from src.flet_ui import theme

SIZE_ICONS_NAVRAIL = 30

icones_navegacao: List[Dict[str, Any]] = [
    {
        "label": "Início", # Imagem do departamento
        "icon": ft.Icon(ft.Icons.HOME_OUTLINED, size=SIZE_ICONS_NAVRAIL),
        "selected_icon": ft.Icon(ft.Icons.HOME, size=SIZE_ICONS_NAVRAIL),
        "route": "/home"
    },
    {
        "label": "Análise Inicial", # Antiga "Análise Inicial"
        "icon": ft.Icon(ft.Icons.FIND_IN_PAGE_OUTLINED, size=SIZE_ICONS_NAVRAIL),
        "selected_icon": ft.Icon(ft.Icons.FIND_IN_PAGE, size=SIZE_ICONS_NAVRAIL),
        "route": "/analyze_pdf" # Nova rota para a funcionalidade principal
    },
    {
        "label": "Chat with PDF",
        "icon": ft.Icon(ft.Icons.QUESTION_ANSWER_OUTLINED,size=SIZE_ICONS_NAVRAIL),
        "selected_icon": ft.Icon(ft.Icons.QUESTION_ANSWER,size=SIZE_ICONS_NAVRAIL),
        "route": "/chat_pdf"
    },
    {
        "label": "Banco Pareceres",
        "icon": ft.Icon(ft.Icons.LIBRARY_BOOKS_OUTLINED,size=SIZE_ICONS_NAVRAIL),
        "selected_icon": ft.Icon(ft.Icons.LIBRARY_BOOKS,size=SIZE_ICONS_NAVRAIL),
        "route": "/knowledge_base"
    },

    {
        "label": "Wiki PF - Rotinas",
        "icon": ft.Icon(ft.Icons.MENU_BOOK_OUTLINED, size=SIZE_ICONS_NAVRAIL),
        "selected_icon": ft.Icon(ft.Icons.MENU_BOOK, size=SIZE_ICONS_NAVRAIL),
        "route": "/wiki_rotinas"
    },
    {
        "label": "Correições", 
        "icon": ft.Icon(ft.Icons.RULE_FOLDER_OUTLINED,size=SIZE_ICONS_NAVRAIL),
        "selected_icon": ft.Icon(ft.Icons.RULE_FOLDER,size=SIZE_ICONS_NAVRAIL),
        "route": "/correicao_processos"
    },
    {
        "label": "Roteiros Investigação", 
        "icon": ft.Icon(ft.Icons.MAP_OUTLINED, size=SIZE_ICONS_NAVRAIL),
        "selected_icon": ft.Icon(ft.Icons.MAP, size=SIZE_ICONS_NAVRAIL),
        "route": "/roteiro_investigacoes"
    }
]

# Mapeamento inverso para destacar o item correto na NavRail principal
# AJUSTADO para as novas seções
route_to_base_nav_index: Dict[str, int] = {
    # Raiz do app, geralmente redireciona para /home ou /dashboard
    "/": 0,
    "/home": 0,
    "/analyze_pdf": 1,
    "/chat_pdf": 2, 
    "/knowledge_base": 3,
    "/wiki_rotinas": 4,
    "/correicao_processos": 5,
    "/roteiro_investigacoes": 6,
}

def _find_nav_index_for_route(route: str) -> int:
    """Encontra o índice da NavigationRail para uma dada rota (incluindo sub-rotas)."""
    selected_index = 0 # Default Dashboard
    best_match_len = 0
    # Rota base "/" deve ter prioridade baixa se outra rota mais específica corresponder
    if route == "/":
        best_match_len = 1 # Define um comprimento mínimo para a raiz

    for base_route, index in route_to_base_nav_index.items():
        # Ignora a rota raiz "/" na checagem de prefixo se a rota atual for diferente dela
        if base_route == "/" and route != "/":
            continue

        # Verifica se a rota atual é exatamente a rota base ou começa com a rota base + '/'
        is_exact_match = (route == base_route)
        # Garante que a rota base não seja apenas "/" para a checagem de prefixo
        is_prefix_match = (base_route != "/" and route.startswith(base_route + "/"))

        if is_exact_match or is_prefix_match:
            # Comprimento da rota base encontrada
            current_match_len = len(base_route)
            # Se esta rota base for mais longa (mais específica) que a melhor encontrada até agora
            if current_match_len > best_match_len:
                best_match_len = current_match_len
                selected_index = index
            # Caso especial: Se a rota atual for EXATAMENTE igual a uma rota base de mesmo comprimento
            # que a melhor encontrada (improvável com a estrutura atual, mas defensivo),
            # prioriza a correspondência exata.
            elif current_match_len == best_match_len and is_exact_match and selected_index != index:
                 selected_index = index

    return selected_index

def create_app_bar(page: ft.Page, app_title) -> ft.AppBar:
    """Cria a AppBar padrão para a aplicação."""
    
    def toggle_theme_mode(e):
        if page.theme_mode == ft.ThemeMode.LIGHT:
            page.theme_mode = ft.ThemeMode.DARK
        elif page.theme_mode == ft.ThemeMode.DARK:
            page.theme_mode = ft.ThemeMode.LIGHT
        else:
            page.theme_mode = ft.ThemeMode.LIGHT
        # Atualiza a cor da appbar explicitamente se necessário
        # page.appbar.bgcolor = ... # Se o tema não atualizar automaticamente
        page.update()

    def show_terms_dialog(e):
        terms_dialog = None

        def close_dialog(e):
            terms_dialog.open = False
            page.update()
            page.overlay.remove(terms_dialog)

        # Usando ft.Markdown para melhor formatação dos itens
        terms_text = """
### Diretrizes de Uso e Limitações da IA

Ao utilizar esta aplicação, você concorda e compreende os seguintes pontos:

*   **Ferramenta de Suporte**: A IA é um assistente para otimizar a análise preliminar de documentos. Ela não substitui a expertise, o julgamento crítico e a decisão final do analista humano.
*   **Verificação Obrigatória**: É de sua inteira responsabilidade verificar, corrigir e validar todas as informações extraídas, classificadas e resumidas pela IA. Os resultados podem conter imprecisões, omissões ou erros.
*   **Alucinações e Vieses**: Modelos de linguagem podem gerar informações que parecem factuais, mas não estão presentes no documento original (alucinações) ou refletir vieses contidos em seus dados de treinamento. Redobre a atenção em dados críticos como nomes, datas, valores e tipificações.
*   **Responsabilidade**: Todas as ações, decisões e documentos oficiais gerados a partir do uso desta ferramenta são de responsabilidade exclusiva do usuário que os executa e subscreve.
*   O sistema registra métricas de uso para fins de auditoria e aprimoramento.
*   As tipificações penais e classificações sugeridas pela IA são baseadas em padrões e não constituem parecer jurídico formal. A decisão final sobre o enquadramento legal cabe à autoridade competente.
"""
        terms_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Termos de Uso e Responsabilidade"),
            content=ft.Container(
                content=ft.Markdown(
                    terms_text,
                    selectable=True,
                    extension_set=ft.MarkdownExtensionSet.COMMON_MARK,
                ),
                width=600, # Controla a largura para melhor leitura
            ),
            actions=[
                ft.TextButton("Fechar", on_click=close_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        page.overlay.append(terms_dialog)
        terms_dialog.open = True
        page.update()

    # Recupera o nome do usuário para exibir na AppBar, se logado
    user_display_name = page.session.get("auth_display_name") or \
                        (page.client_storage.get("auth_display_name") if page.client_storage else None)
    
    user_greeting_or_empty = []
    if user_display_name:
        user_greeting_or_empty.append(
            ft.Text(f"Olá, {user_display_name.split(' ')[0]}", # Pega o primeiro nome
                    size=14,
                    font_family="Roboto", # Garante uma fonte consistente
                    weight=ft.FontWeight.NORMAL,
                    opacity=0.8, # Um pouco mais sutil
                    italic=True) 
        )
        user_greeting_or_empty.append(ft.Container(width=10)) # Pequeno espaçador

    # Botão Home - Adicionado no início das actions para aparecer mais à esquerda possível dentro das actions
    home_button = ft.IconButton(
        ft.Icons.HOME_OUTLINED,
        tooltip="Ir para Início",
        on_click=lambda _: page.go("/home"),
        padding = ft.padding.only(left=theme.PADDING_XL, right=theme.PADDING_XL),
        icon_size=40
    )
    
    app_bar_actions = [
        #*user_greeting_or_empty, # Desempacota a lista (pode ser vazia)
        #ft.IconButton(
        #    ft.Icons.SETTINGS_APPLICATIONS_OUTLINED, 
        #    tooltip="Configurações LLM",
        #    padding = ft.padding.only(left=theme.PADDING_XL, right=theme.PADDING_XL),
        #    on_click=lambda _: page.go("/settings/llm"),
        #    icon_size=40
        #),
        ft.PopupMenuButton(
            tooltip="Configurações do Usuário",
            icon=ft.Icons.SETTINGS, #SETTINGS_APPLICATIONS_OUTLINED, ACCOUNT_CIRCLE_OUTLINED,
            icon_size=26, 
            padding = ft.padding.only(left=theme.PADDING_XL, right=theme.PADDING_XL),
            items=[
                ft.PopupMenuItem(text="Perfil", icon=ft.Icons.PERSON_OUTLINE, on_click=lambda _: page.go("/profile")), # Rota de perfil
                ft.PopupMenuItem(text="Proxy", icon=ft.Icons.VPN_KEY_OUTLINED, on_click=lambda _: page.go("/settings/proxy")),
                ft.PopupMenuItem(text="Provedores LLM", icon=ft.Icons.MODEL_TRAINING_OUTLINED, on_click=lambda _: page.go("/settings/llm")), # Rota de perfil
                ft.PopupMenuItem(text="Termos de Uso", icon=ft.Icons.POLICY_OUTLINED, on_click=show_terms_dialog),
                ft.PopupMenuItem(),  # Divisor
                ft.PopupMenuItem(text="Sair", icon=ft.Icons.LOGOUT, on_click=lambda _: handle_logout(page)) # Ação de Logout
            ]
        ),
        ft.IconButton(
            ft.Icons.BRIGHTNESS_4_OUTLINED, # Ícone para tema
            tooltip="Mudar tema",
            padding = ft.padding.only(left=theme.PADDING_XL, right=theme.PADDING_XL),
            on_click=toggle_theme_mode,
            icon_size=26
        ),
    ]

    #if page.route != "/home": # Só adiciona o botão Home se não estivermos na Home
    #    app_bar_actions.insert(0, home_button)

    return ft.AppBar(
        title=ft.Text(app_title),
        center_title=False,
        actions=app_bar_actions,
        #bgcolor=theme.SURFACE_VARIANT
    )

def create_navigation_rail(page: ft.Page, selected_route: str) -> ft.NavigationRail:
    """Cria a NavigationRail, marcando o índice correto com base na rota.

    A NavigationRail (ou NavigationDrawer) é o painel lateral que contém os links
    para as diferentes seções do aplicativo. Aqui, criamos essa NavigationRail e
    fazemos com que ela seja configurada para marcar a seção correta com base na
    rota atual.

    :param page: A página atual do Flet (usada apenas para obter a rota atual)
    :param selected_route: A rota atual (usada para determinar o índice selecionado)
    :return: A NavigationRail configurada e pronta para uso
    """

    # Encontra o índice da NavigationRail para a rota atual
    selected_index = _find_nav_index_for_route(selected_route)

    # Define uma função que será executada quando a NavigationRail for alterada
    # (ou seja, quando o usuário clicar em um item diferente)
    def navigate(e):
        # Obtém o índice do item selecionado na NavigationRail
        target_index = e.control.selected_index
        # Obtém a rota para o item selecionado
        target_route = icones_navegacao[target_index]["route"]
        # Navega para a rota selecionada:
        # Adquire o Lock global antes de chamar page.go()
        update_lock = page.data.get("global_update_lock")
        if update_lock:
            with update_lock:
                page.go(target_route)
        else:
            # Fallback se o lock não for encontrado
            page.go(target_route)

    # Cria a NavigationRail com base nos dados de icones_navegacao
    # e configura o evento de mudança para a função navigate
    return ft.NavigationRail(
        selected_index=selected_index,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=100,
        min_extended_width=200,
        destinations=[
            ft.NavigationRailDestination(
                icon=modulo["icon"],
                selected_icon=modulo["selected_icon"],
                label=modulo["label"],
                
            ) for modulo in icones_navegacao
        ],
        on_change=navigate
    )

def create_navigation_drawer(page: ft.Page, selected_route: str) -> ft.NavigationDrawer:
    """Cria a NavigationDrawer."""
    selected_index = _find_nav_index_for_route(selected_route)

    def navigate_and_close_drawer(e):
        # target_index = e.control.selected_index # Drawer não tem selected_index no evento on_change
        # Precisamos encontrar o índice pelo label ou outra propriedade se o evento não der o índice
        # Para simplificar, vamos assumir que o controle do evento é o NavigationDrawerDestination
        # e podemos pegar a rota do seu label ou de um atributo data.
        # Flet pode passar o controle do destino clicado.
        # No entanto, o `on_change` do NavigationDrawer é mais simples e não retorna o destino clicado.
        # Uma abordagem mais robusta é usar o `data` de cada destino.

        # A forma mais direta é fechar o drawer e então navegar.
        # O on_change do drawer em si não é ideal para navegação direta
        # porque ele dispara antes de um destino ser 'selecionado'
        # É melhor que cada destino tenha seu próprio on_click.
        page.drawer.open = False # Fecha o drawer
        page.update()
        # A navegação real deve ser feita pelo on_click de cada tile/destino

    # Dentro do Drawer, usamos controles como ft.NavigationDrawerDestination
    # ou ft.ListTile para criar os itens navegáveis.
    
    drawer_destinations = []
    for i, modulo in enumerate(icones_navegacao):
        drawer_destinations.append(
            ft.NavigationDrawerDestination(
                icon_content=ft.Icon(modulo["icon"]),
                selected_icon_content=ft.Icon(modulo["selected_icon"]),
                label=modulo["label"],
            )
        )
        # O NavigationDrawerDestination em si não tem um evento on_click fácil
        # para navegação direta. Frequentemente se usa ListTile dentro do drawer.

    # Alternativa usando ListTile para melhor controle do clique
    drawer_tiles = []
    for i, modulo in enumerate(icones_navegacao):
        is_selected = (selected_index == i)
        drawer_tiles.append(
            ft.ListTile(
                title=ft.Text(modulo["label"]),
                leading=ft.Icon(modulo["selected_icon"] if is_selected else modulo["icon"]),
                on_click=lambda _, route=modulo["route"]: (
                    setattr(page.drawer, 'open', False), # Fecha o drawer
                    page.go(route) # Navega
                ),
                selected=is_selected,
                # Para o tema do ListTile selecionado funcionar bem,
                # você pode precisar envolver o NavigationDrawer em um Container com um tema
                # ou ajustar o tema global.
            )
        )

    return ft.NavigationDrawer(
        controls=drawer_tiles, # Usando os ListTiles
        # selected_index=selected_index # Isso ajuda a destacar visualmente
        # on_change=navigate_and_close_drawer # on_change pode ser usado para outras lógicas
    )

def create_footer(page: ft.Page) -> ft.BottomAppBar:
    """Cria um rodapé simples para a aplicação."""
    return ft.BottomAppBar(
        content=ft.Row(
            [
                ft.Text(f"© {theme.APP_YEAR} ERP BRG. Todos os direitos reservados."),
                ft.Container(expand=True), # Espaçador
                ft.TextButton("Suporte"),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
        ),
        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE), # Exemplo de cor
        padding=ft.padding.symmetric(horizontal=theme.PADDING_M)
    )

import threading
from src.flet_ui.components import hide_loading_overlay
from src.logger.cloud_logger_handler import ClientLogUploader
from src.logger.logger import LoggerSetup # Adicionado
_logger = LoggerSetup.get_logger(__name__)

def handle_logout(page: ft.Page):
    """Limpa o estado de autenticação e redireciona para a tela de login."""
    def _logout_logic():
        hide_loading_overlay(page)
        user_id_logged_out = page.session.get("auth_user_id") or \
                            (page.client_storage.get("auth_user_id") if page.client_storage else "Desconhecido")
        _logger.info(f"Usuário {user_id_logged_out} deslogando.")

        # FLUSH ANTES DE LIMPAR O CONTEXTO DO USUÁRIO
        if LoggerSetup._active_cloud_handler_instance: # Verifica se o handler foi criado e está ativo
            uploader_in_use = LoggerSetup._active_cloud_handler_instance.uploader
            # Só faz flush se o uploader for o ClientLogUploader, pois ele depende do token do usuário
            # que está prestes a ser removido. O AdminLogUploader pode continuar logando depois.
            if isinstance(uploader_in_use, ClientLogUploader) and uploader_in_use._current_user_token:
                _logger.info("Logout: Forçando flush do CloudLogHandler para logs do usuário atual (ClientUploader)...")
                try:
                    LoggerSetup._active_cloud_handler_instance.flush()
                    _logger.debug("Flush solicitado. O upload ocorrerá em segundo plano.")
                    # Não adicionar time.sleep() aqui, pois o flush é para a thread fazer.
                except Exception as e_flush:
                    _logger.error(f"Erro ao tentar forçar flush no logout: {e_flush}")

        # Limpa do client_storage se existir
        # auth_keys_to_clear = [
        #     "auth_id_token", "auth_user_id", "auth_user_email", 
        #     "auth_display_name", "auth_refresh_token", "auth_id_token_expires_at" # Adicionar novas chaves
        # ]
        auth_keys_to_clear = page.session.get_keys() # Pega todas as chaves
        if page.client_storage:
            for key in auth_keys_to_clear:
                if key.startswith("auth_") or key.startswith("decrypted_api_key_"):
                    if page.client_storage.contains_key(key): 
                        page.client_storage.remove(key)
            _logger.debug("Dados de autenticação removidos do client_storage (se existiam).")
        
        for key in auth_keys_to_clear:
            if key.startswith("auth_") or key.startswith("decrypted_api_key_"):
                if page.session.contains_key(key):
                    page.session.remove(key) 
        _logger.debug("Dados de autenticação removidos da sessão Flet.")
        
        LoggerSetup.set_cloud_user_context(None, None) # Limpa contexto do logger de nuvem
        _logger.info("Contexto do logger de nuvem limpo.")
        
        page.go("/login") # Esta chamada de page.go() é segura aqui porque _logout_logic será executada pela thread principal via page.run_thread 

    # Verifica se esta função está sendo chamada da thread principal ou de uma thread de background
    if threading.current_thread() is threading.main_thread():
        _logger.debug("handle_logout chamado da thread principal.")
        _logout_logic()
    else:
        _logger.debug("handle_logout chamado de uma thread de background. Agendando na thread principal.")
        page.run_thread(_logout_logic) # Garante que a lógica de logout (incluindo page.go) rode na thread principal

from src.flet_ui.components import show_snackbar, ValidatedTextField, ManagedAlertDialog

def show_proxy_settings_dialog(page: ft.Page):
    # dialog_funtion substituído por uma view própria
    _logger.info("Abrindo diálogo de configurações de proxy.")

    from src.settings import (K_PROXY_ENABLED, K_PROXY_PASSWORD_SAVED, K_PROXY_IP_URL, K_PROXY_PORT, K_PROXY_USERNAME, K_PROXY_PASSWORD, 
                            PROXY_URL_DEFAULT, PROXY_PORT_DEFAULT)
    from src.config_manager import get_proxy_settings, save_proxy_settings

    def host_validator(value: str) -> Optional[str]:
        # Validação básica, pode ser melhorada (ex: regex para IP/hostname)
        if not value: return "O host não pode estar vazio se o proxy estiver habilitado."
        return None

    def port_validator(value: str) -> Optional[str]:
        if not value: return "A porta não pode estar vazia se o proxy estiver habilitado."
        if not value.isdigit() or not (1 <= int(value) <= 65535):
            return "Porta inválida (deve ser um número entre 1 e 65535)."
        return None

    # Carregar configurações existentes
    current_settings = get_proxy_settings() # Retorna um dict ou {'proxy_enabled': False, ...}

    security_warning_text = ft.Text(
        "Atenção: As configurações de proxy, incluindo o nome de usuário, são salvas localmente neste computador."
        "Se 'Salvar Senha' estiver marcado, a senha também será armazenada de forma segura no Keyring do sistema operacional."
        "Se este NÃO é seu computador pessoal, desmarque 'Salvar Senha' ou remova as configurações ao sair.",
        size=12,
        italic=True,
        color=ft.Colors.with_opacity(0.7, ft.Colors.ON_SURFACE),
        # width=430 # Para quebrar linha dentro do diálogo
    )

    proxy_enabled_switch = ft.Switch(
        label="Habilitar Proxy",
        value=current_settings.get(K_PROXY_ENABLED, False)
    )
    
    # Usando ValidatedTextField para consistência e melhor feedback de erro
    proxy_host_field = ValidatedTextField(
        label="Host do Proxy",
        value=current_settings.get(K_PROXY_IP_URL, ""), # Usar as constantes do config_manager
        validator=host_validator,
        hint_text="ex: 192.168.1.100 ou proxy.empresa.com"
    )
    proxy_port_field = ValidatedTextField(
        label="Porta do Proxy",
        value=str(current_settings.get(K_PROXY_PORT, "")), # Porta é string no TextField
        validator=port_validator,
        keyboard_type=ft.KeyboardType.NUMBER
    )
    proxy_user_field = ft.TextField( # Usuário é opcional, não precisa de ValidatedTextField forte
        label="Usuário do Proxy",
        value=current_settings.get(K_PROXY_USERNAME, "")
    )
    proxy_password_field = ft.TextField(
        label="Senha do Proxy (deixe em branco se não mudou)",
        hint_text="Preencha apenas para definir/alterar a senha",
        password=True,
        can_reveal_password=True,
        expand=True
    )
    # Checkbox para indicar se a senha deve ser salva (controla o campo 'password_saved')
    save_password_checkbox = ft.Checkbox(
        label="Salvar Senha",
        value=current_settings.get(K_PROXY_PASSWORD_SAVED, False) # Vem do config_manager
    )

    def on_save_button_click(e):
        _logger.info("Botão Salvar (proxy) clicado - lógica interna.")
        is_enabled = proxy_enabled_switch.value
        host_valid = True
        port_valid = True
        if is_enabled:
            host_valid = proxy_host_field.validate(show_error=True)
            port_valid = proxy_port_field.validate(show_error=True)
        else: # Limpa erros se desabilitado
            proxy_host_field.text_field.error_text = None; proxy_port_field.text_field.error_text = None
            proxy_host_field.update(); proxy_port_field.update()

        if not host_valid or not port_valid:
            show_snackbar(page, "Corrija os erros no formulário.", color=theme.COLOR_ERROR)
            return False # Não fecha o diálogo

        new_settings = { 
            K_PROXY_ENABLED: is_enabled,
            K_PROXY_IP_URL: proxy_host_field.value,
            K_PROXY_PORT: proxy_port_field.value,
            K_PROXY_USERNAME: proxy_user_field.value,
            K_PROXY_PASSWORD_SAVED: save_password_checkbox.value
        }
        if proxy_password_field.value:
            new_settings[K_PROXY_PASSWORD] = proxy_password_field.value
        
        if save_proxy_settings(new_settings):
            _logger.info("Configurações de proxy salvas no Keyring.")
            # Retorna dados para o on_dialog_fully_closed
            return {"action": "saved", "message": "Configurações de proxy salvas com sucesso!", "color": theme.COLOR_SUCCESS}
        else:
            _logger.error("Falha ao salvar configurações de proxy no Keyring.")
            show_snackbar(page, "Erro ao salvar configurações de proxy.", color=theme.COLOR_ERROR)
            return False # Não fecha o diálogo

    def on_delete_button_click(e):
        _logger.info("Botão Remover Tudo (proxy) clicado - lógica interna.")
        settings_to_delete = { # ... (como antes) ...
            K_PROXY_ENABLED: False, 
            K_PROXY_IP_URL: PROXY_URL_DEFAULT, 
            K_PROXY_PORT: PROXY_PORT_DEFAULT,
            K_PROXY_USERNAME: "", 
            K_PROXY_PASSWORD: "", 
            K_PROXY_PASSWORD_SAVED: False
        }
        if save_proxy_settings(settings_to_delete):
            _logger.info("Configurações de proxy removidas do Keyring.")
            proxy_enabled_switch.value = False
            proxy_host_field.value = PROXY_URL_DEFAULT
            proxy_port_field.value = PROXY_PORT_DEFAULT
            proxy_user_field.value = ""
            proxy_password_field.value = ""
            save_password_checkbox.value = False
            # Atualizar o conteúdo do diálogo antes de sinalizar para fechar
            # Se o dialog_proxy_instance estiver acessível aqui (precisaria de ref ou ser parte de uma classe)
            # Ex: dialog_proxy_instance.content.update()
            # Por ora, a atualização dos campos será visível na próxima vez que abrir.
            # Para forçar update antes de fechar, a instância do diálogo é necessária.
            # No ManagedAlertDialog, o update() é chamado no próprio diálogo.
            # Para atualizar os campos *visualmente* antes do timer, seria:
            if dialog_proxy_instance and dialog_proxy_instance.content: # dialog_proxy_instance é a ManagedAlertDialog
                dialog_proxy_instance.content.update()

            return {"action": "deleted", "message": "Configurações de proxy removidas.", "color": theme.COLOR_INFO}
        else:
            _logger.error("Falha ao remover configurações de proxy.")
            show_snackbar(page, "Erro ao remover configurações de proxy.", color=theme.COLOR_ERROR)
            return False # Não fecha

    def on_cancel_button_click(e):
        _logger.info("Botão Cancelar (proxy) clicado.")
        return {"action": "cancelled"} # Sinaliza para fechar e passar "cancelled"
    
    # Callback que executa DEPOIS que o diálogo é totalmente fechado
    def after_proxy_dialog_closed(result_data: Any):
        _logger.info(f"Callback after_proxy_dialog_closed chamado com: {result_data}")
        if isinstance(result_data, dict) and result_data.get("message"):
            show_snackbar(page, result_data["message"], color=result_data.get("color", theme.COLOR_INFO))
        elif result_data == "cancelled":
             _logger.info("Operação de proxy cancelada pelo usuário.")
        # Aqui você pode adicionar qualquer outra lógica que precise rodar após o diálogo fechar e após a ação principal (salvar/deletar) ter sido concluída.

    actions_list = [
        ft.ElevatedButton("Cancelar", on_click=on_cancel_button_click, data="cancel_action_completed", width=150),
        ft.ElevatedButton("Salvar", on_click=on_save_button_click, data="save_action_completed", width=150),
        ft.ElevatedButton("Remover Tudo", on_click=on_delete_button_click, data="delete_action_completed", tooltip="Limpa todas as configurações de proxy salvas.", width=150)
        ]
    
    dialog_content_column = ft.Column(
        [ft.Container(content=proxy_enabled_switch, padding=ft.padding.only(bottom=10)),
        proxy_host_field,
        proxy_port_field,
        proxy_user_field,
        ft.Row([proxy_password_field, save_password_checkbox], expand=True),
        ft.Divider(height=10, color=ft.Colors.TRANSPARENT), # Espaçador
        security_warning_text
        ],
        tight=True, scroll=ft.ScrollMode.ADAPTIVE, width=560
    )
    
    # Instanciar e mostrar o ManagedAlertDialog
    dialog_proxy_instance = ManagedAlertDialog(
        page_ref=page,
        title="Configurações de Proxy",
        content=dialog_content_column,
        actions=actions_list,
        on_dialog_fully_closed=after_proxy_dialog_closed
        # actions_alignment=ft.MainAxisAlignment.END
    )
    dialog_proxy_instance.show()



execution_time = perf_counter() - start_time
print(f"Carregado LAYOUT.py em {execution_time:.4f}s")
