# src/flet_ui/layout.py
"""
Define elementos de layout reutilizáveis como AppBar e NavigationRail.

"""
import logging
logger = logging.getLogger(__name__)

from time import perf_counter
start_time = perf_counter()
logger.debug(f"{start_time:.4f}s - Iniciando layout.py")

import flet as ft
from typing import List, Dict, Any, Optional
# Importa definições de tema se necessário (ex: para padding ou cores)
from src.flet_ui import theme

from src.logger.logger import LoggerSetup

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
    """
    Encontra o índice da NavigationRail correspondente a uma dada rota.

    Prioriza rotas mais específicas (maiores) e lida com sub-rotas.

    Args:
        route (str): A rota atual da página.

    Returns:
        int: O índice do item da NavigationRail que deve ser selecionado.
    """
    selected_index = 0  # Índice padrão para a rota de início/dashboard
    best_match_len = 0

    # A rota base "/" deve ter prioridade baixa se outra rota mais específica corresponder.
    # Define um comprimento mínimo para a raiz para que rotas mais específicas a substituam.
    if route == "/":
        best_match_len = 1

    for base_route, index in route_to_base_nav_index.items():
        # Ignora a rota raiz "/" na checagem de prefixo se a rota atual for diferente dela,
        # pois a rota "/" é um caso especial que já foi tratado ou será tratado por correspondência exata.
        if base_route == "/" and route != "/":
            continue

        is_exact_match = (route == base_route)
        # Verifica se a rota atual começa com a rota base seguida por um '/' (indicando uma sub-rota).
        # Exclui o caso de `base_route` ser apenas "/" para evitar correspondências indesejadas.
        is_prefix_match = (base_route != "/" and route.startswith(base_route + "/"))

        if is_exact_match or is_prefix_match:
            current_match_len = len(base_route)
            # Se a rota base atual for mais longa (mais específica) que a melhor encontrada até agora,
            # atualiza o melhor índice.
            if current_match_len > best_match_len:
                best_match_len = current_match_len
                selected_index = index
            # Caso especial: Se a rota atual for EXATAMENTE igual a uma rota base de mesmo comprimento
            # que a melhor encontrada, e o índice for diferente, prioriza a correspondência exata.
            # Isso é uma medida defensiva para garantir a seleção correta em cenários ambíguos,
            # embora improvável com a estrutura de rotas atual.
            elif current_match_len == best_match_len and is_exact_match and selected_index != index:
                selected_index = index

    return selected_index

def create_app_bar(page: ft.Page, app_title: str) -> ft.AppBar:
    """
    Cria a AppBar padrão para a aplicação, incluindo funcionalidades como
    alternar o tema, exibir termos de uso e acesso a configurações do usuário.

    Args:
        page (ft.Page): A instância da página Flet atual.
        app_title (str): O título a ser exibido na AppBar.

    Returns:
        ft.AppBar: O componente AppBar configurado.
    """

    def toggle_theme_mode(e: ft.ControlEvent) -> None:
        """
        Alterna entre os modos de tema CLARO e ESCURO da aplicação.

        Args:
            e (ft.ControlEvent): Evento de controle que disparou a função.
        """
        if page.theme_mode == ft.ThemeMode.LIGHT:
            page.theme_mode = ft.ThemeMode.DARK
        elif page.theme_mode == ft.ThemeMode.DARK:
            page.theme_mode = ft.ThemeMode.LIGHT
        else:
            page.theme_mode = ft.ThemeMode.LIGHT
        page.update()

    def show_terms_dialog(e: ft.ControlEvent) -> None:
        """
        Exibe um diálogo modal com os termos de uso e responsabilidade da aplicação.

        Args:
            e (ft.ControlEvent): Evento de controle que disparou a função.
        """
        terms_dialog = None

        def close_dialog(e: ft.ControlEvent) -> None:
            """
            Fecha o diálogo de termos de uso.

            Args:
                e (ft.ControlEvent): Evento de controle que disparou a função.
            """
            terms_dialog.open = False
            page.update()
            page.overlay.remove(terms_dialog)

        terms_text = """
### Diretrizes de Uso e Limitações da IA

Ao utilizar esta aplicação, você concorda e compreende os seguintes pontos:

*   **Ferramenta de Suporte**: A IA é um assistente para otimizar a análise preliminar de documentos. Ela não substitui a expertise, o julgamento crítico e a decisão final do analista humano.
*   **Verificação Obrigatória**: É de sua inteira responsabilidade verificar, corrigir e validar todas as informações extraídas, classificadas e resumidas pela IA. Os resultados podem conter imprecisões, omissões ou erros.
*   **Alucinações e Vieses**: Modelos de linguagem podem gerar informações que parecem factuais, mas não estão presentes no documento original (alucinações) ou refletir vieses contidos em seus dados de treinamento. Redobre a atenção em dados críticos como nomes, datas, valores e tipificações.
*   **Responsabilidade**: Todas as ações, decisões e documentos oficiais gerados a partir do uso desta ferramenta são de responsabilidade exclusiva do usuário que os executa e subscreve.
*   O sistema registra métricas de uso para fins de auditoria e aprimoramento.
*   As tipificações penais e classificações sugeridas pela IA são baseadas em padrões e não constituem parecer jurídico formal. A decisão final sobre o enquadramento legal cabe à autoridade competente.

---

### Políticas de Provedores de IA

Ao utilizar a funcionalidade de análise via LLM, o conteúdo textual (anonimizado, se a opção estiver ativa) é enviado para processamento por provedores de IA de terceiros, como a OpenAI. O uso desta funcionalidade está sujeito às políticas do provedor selecionado.

Para mais detalhes, consulte:
*   [Política de Privacidade da OpenAI](https://openai.com/pt-BR/policies/row-privacy-policy/)
*   [Termos de Uso da OpenAI](https://openai.com/pt-BR/policies/row-terms-of-use/)
*   [Adendo de Processamento de Dados da OpenAI (DPA)](https://openai.com/policies/data-processing-addendum/)

**Nota Importante:** Conforme a política da OpenAI, os dados enviados via API **não são utilizados** para treinar os modelos da OpenAI.

"""
        terms_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Termos de Uso e Responsabilidade"),
            content=ft.Container(
                content=ft.Markdown(
                    terms_text,
                    selectable=True,
                    extension_set=ft.MarkdownExtensionSet.COMMON_MARK,
                    auto_follow_links=True,
                ),
                width=600,
            ),
            actions=[
                ft.TextButton("Fechar", on_click=close_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            scrollable=True
        )

        page.overlay.append(terms_dialog)
        terms_dialog.open = True
        page.update()

    def show_history_placeholder(e: ft.ControlEvent) -> None:
        """
        Exibe um snackbar informando que a funcionalidade de histórico de uso
        ainda não está implementada.

        Args:
            e (ft.ControlEvent): Evento de controle que disparou a função.
        """
        from src.flet_ui.components import show_snackbar
        show_snackbar(
            page,
            "Visualização do Histórico de Uso ainda não implementada.",
            color=theme.COLOR_WARNING
        )

    user_display_name = page.session.get("auth_display_name") or \
                        (page.client_storage.get("auth_display_name") if page.client_storage else None)

    user_greeting_or_empty = []
    if user_display_name:
        user_greeting_or_empty.append(
            ft.Text(f"Olá, {user_display_name.split(' ')[0]}",
                    size=14,
                    font_family="Roboto",
                    weight=ft.FontWeight.NORMAL,
                    opacity=0.8,
                    italic=True)
        )
        user_greeting_or_empty.append(ft.Container(width=10))

    home_button = ft.IconButton(
        ft.Icons.HOME_OUTLINED,
        tooltip="Ir para Início",
        on_click=lambda _: page.go("/home"),
        padding=ft.padding.only(left=theme.PADDING_XL, right=theme.PADDING_XL),
        icon_size=40
    )

    app_bar_actions = [
        ft.PopupMenuButton(
            tooltip="Configurações do Usuário",
            icon=ft.Icons.SETTINGS,
            icon_size=26,
            padding=ft.padding.only(left=theme.PADDING_XL, right=theme.PADDING_XL),
            items=[
                ft.PopupMenuItem(text="Perfil", icon=ft.Icons.PERSON_OUTLINE, on_click=lambda _: page.go("/profile")),
                ft.PopupMenuItem(text="Histórico de Uso", icon=ft.Icons.HISTORY, on_click=show_history_placeholder),
                ft.PopupMenuItem(text="Provedores LLM", icon=ft.Icons.MODEL_TRAINING_OUTLINED, on_click=lambda _: page.go("/settings/llm")),
                ft.PopupMenuItem(text="Configs. Proxy", icon=ft.Icons.VPN_KEY_OUTLINED, on_click=lambda _: page.go("/settings/proxy")),
                ft.PopupMenuItem(text="Termos e Condições", icon=ft.Icons.POLICY_OUTLINED, on_click=show_terms_dialog),
                ft.PopupMenuItem(),
                ft.PopupMenuItem(text="Sair", icon=ft.Icons.LOGOUT, on_click=lambda _: handle_logout(page))
            ]
        ),
        ft.IconButton(
            ft.Icons.BRIGHTNESS_4_OUTLINED,
            tooltip="Mudar tema",
            padding=ft.padding.only(left=theme.PADDING_XL, right=theme.PADDING_XL),
            on_click=toggle_theme_mode,
            icon_size=26
        ),
    ]

    return ft.AppBar(
        title=ft.Text(app_title),
        center_title=False,
        actions=app_bar_actions,
    )

def create_navigation_rail(page: ft.Page, selected_route: str) -> ft.NavigationRail:
    """
    Cria o componente NavigationRail, que serve como o painel de navegação lateral
    principal da aplicação. O item selecionado é determinado com base na rota atual.

    Args:
        page (ft.Page): A instância da página Flet atual.
        selected_route (str): A rota atual da página, usada para destacar o item correto.

    Returns:
        ft.NavigationRail: O componente NavigationRail configurado.
    """
    selected_index = _find_nav_index_for_route(selected_route)

    def navigate(e: ft.ControlEvent) -> None:
        """
        Manipula o evento de mudança de seleção na NavigationRail, navegando para a rota
        correspondente ao item selecionado.

        Args:
            e (ft.ControlEvent): Evento de controle que disparou a função.
        """
        target_index = e.control.selected_index
        target_route = icones_navegacao[target_index]["route"]

        # Adquire o Lock global antes de chamar page.go() para garantir segurança de thread.
        update_lock = page.data.get("global_update_lock")
        if update_lock:
            with update_lock:
                page.go(target_route)
        else:
            # Fallback se o lock não for encontrado (deve ser raro em um ambiente Flet bem configurado).
            page.go(target_route)

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
    """
    Cria o componente NavigationDrawer, que é um painel de navegação deslizante
    geralmente usado em telas menores ou como alternativa à NavigationRail.

    Args:
        page (ft.Page): A instância da página Flet atual.
        selected_route (str): A rota atual da página, usada para destacar o item correto.

    Returns:
        ft.NavigationDrawer: O componente NavigationDrawer configurado.
    """
    selected_index = _find_nav_index_for_route(selected_route)

    # A função navigate_and_close_drawer não é diretamente usada como on_change
    # para o NavigationDrawer, pois a navegação é tratada pelos on_click dos ListTiles.
    # No entanto, a lógica de fechar o drawer após a navegação é importante.
    def navigate_and_close_drawer(e: ft.ControlEvent) -> None:
        """
        Função auxiliar para fechar o NavigationDrawer.
        A navegação real é feita pelos `on_click` dos `ListTile`s individuais.

        Args:
            e (ft.ControlEvent): Evento de controle que disparou a função.
        """
        page.drawer.open = False
        page.update()

    drawer_tiles = []
    for i, modulo in enumerate(icones_navegacao):
        is_selected = (selected_index == i)
        drawer_tiles.append(
            ft.ListTile(
                title=ft.Text(modulo["label"]),
                leading=ft.Icon(modulo["selected_icon"] if is_selected else modulo["icon"]),
                on_click=lambda _, route=modulo["route"]: (
                    setattr(page.drawer, 'open', False),  # Fecha o drawer
                    page.go(route)  # Navega
                ),
                selected=is_selected,
            )
        )

    return ft.NavigationDrawer(
        controls=drawer_tiles,
    )

def create_footer(page: ft.Page) -> ft.BottomAppBar:
    """
    Cria um rodapé simples para a aplicação, exibindo informações de copyright
    e um botão de suporte.

    Args:
        page (ft.Page): A instância da página Flet atual.

    Returns:
        ft.BottomAppBar: O componente BottomAppBar configurado como rodapé.
    """
    return ft.BottomAppBar(
        content=ft.Row(
            [
                ft.Text(f"© {theme.APP_YEAR} ERP BRG. Todos os direitos reservados."),
                ft.Container(expand=True),  # Espaçador para empurrar o botão para a direita
                ft.TextButton("Suporte"),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
        ),
        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
        padding=ft.padding.symmetric(horizontal=theme.PADDING_M)
    )

import threading
from src.flet_ui.components import hide_loading_overlay
from src.logger.cloud_logger_handler import ClientLogUploader

def handle_logout(page: ft.Page) -> None:
    """
    Limpa o estado de autenticação do usuário (sessão e armazenamento local)
    e redireciona para a tela de login. Garante que os logs pendentes sejam
    enviados antes de limpar o contexto do usuário.

    Args:
        page (ft.Page): A instância da página Flet atual.
    """
    def _logout_logic() -> None:
        """
        Lógica interna de logout, executada na thread principal do Flet.
        """
        hide_loading_overlay(page)
        user_id_logged_out = page.session.get("auth_user_id") or \
                            (page.client_storage.get("auth_user_id") if page.client_storage else "Desconhecido")
        logger.info(f"Usuário '{user_id_logged_out}' deslogando.")

        # FLUSH ANTES DE LIMPAR O CONTEXTO DO USUÁRIO
        if LoggerSetup._active_cloud_handler_instance:
            uploader_in_use = LoggerSetup._active_cloud_handler_instance.uploader
            # Só faz flush se o uploader for o ClientLogUploader, pois ele depende do token do usuário
            # que está prestes a ser removido. O AdminLogUploader pode continuar logando depois.
            if isinstance(uploader_in_use, ClientLogUploader) and uploader_in_use._current_user_token:
                logger.debug("Logout: Forçando flush do CloudLogHandler para logs do usuário atual (ClientUploader)...")
                try:
                    LoggerSetup._active_cloud_handler_instance.flush()
                    logger.debug("Flush solicitado. O upload ocorrerá em segundo plano.")
                except Exception as e_flush:
                    logger.error(f"Erro ao tentar forçar flush no logout: {e_flush}")

        auth_keys_to_clear = [
            "auth_id_token", "auth_user_id", "auth_user_email",
            "auth_display_name", "auth_refresh_token", "auth_id_token_expires_at",
            "is_admin"
        ]

        # Busca e remove qualquer chave de API descriptografada da sessão
        decrypted_api_keys = [k for k in page.session.get_keys() if k.startswith("decrypted_api_key_")]
        auth_keys_to_clear.extend(decrypted_api_keys)

        if page.client_storage:
            for key in auth_keys_to_clear:
                if key.startswith("auth_") or key.startswith("decrypted_api_key_"):
                    if page.client_storage.contains_key(key):
                        page.client_storage.remove(key)
            logger.debug("Dados de autenticação removidos do client_storage (se existiam).")

        for key in auth_keys_to_clear:
            if key.startswith("auth_") or key.startswith("decrypted_api_key_"):
                if page.session.contains_key(key):
                    page.session.remove(key)
        logger.debug("Dados de autenticação removidos da sessão Flet.")

        LoggerSetup.set_cloud_user_context(None, None)
        logger.debug("Contexto do logger de nuvem limpo.") # Alterado de info para debug, pois é uma ação interna.

        page.go("/login")

    if threading.current_thread() is threading.main_thread():
        logger.debug("handle_logout chamado da thread principal. Executando lógica diretamente.")
        _logout_logic()
    else:
        logger.debug("handle_logout chamado de uma thread de background. Agendando lógica na thread principal.")
        page.run_thread(_logout_logic)

from src.flet_ui.components import show_snackbar, ValidatedTextField, ManagedAlertDialog

def show_proxy_settings_dialog(page: ft.Page) -> None:
    """
    Exibe um diálogo modal para configurar as opções de proxy da aplicação.
    Permite habilitar/desabilitar proxy, definir host, porta, usuário e senha,
    além de salvar as credenciais de forma segura.

    Args:
        page (ft.Page): A instância da página Flet atual.
    """
    logger.debug("Abrindo diálogo de configurações de proxy.")

    from src.settings import (K_PROXY_ENABLED, K_PROXY_PASSWORD_SAVED, K_PROXY_IP_URL, K_PROXY_PORT, K_PROXY_USERNAME, K_PROXY_PASSWORD,
                            PROXY_URL_DEFAULT, PROXY_PORT_DEFAULT)
    from src.config_manager import get_proxy_settings, save_proxy_settings

    def host_validator(value: str) -> Optional[str]:
        """
        Valida o campo do host do proxy.

        Args:
            value (str): O valor atual do campo host.

        Returns:
            Optional[str]: Uma mensagem de erro se a validação falhar, caso contrário, None.
        """
        if not value and proxy_enabled_switch.value:
            return "O host não pode estar vazio se o proxy estiver habilitado."
        return None

    def port_validator(value: str) -> Optional[str]:
        """
        Valida o campo da porta do proxy.

        Args:
            value (str): O valor atual do campo porta.

        Returns:
            Optional[str]: Uma mensagem de erro se a validação falhar, caso contrário, None.
        """
        if not value and proxy_enabled_switch.value:
            return "A porta não pode estar vazia se o proxy estiver habilitado."
        if value and (not value.isdigit() or not (1 <= int(value) <= 65535)):
            return "Porta inválida (deve ser um número entre 1 e 65535)."
        return None

    current_settings = get_proxy_settings()

    security_warning_text = ft.Text(
        "Atenção: As configurações de proxy, incluindo o nome de usuário, são salvas localmente neste computador."
        "Se 'Salvar Senha' estiver marcado, a senha também será armazenada de forma segura no Keyring do sistema operacional."
        "Se este NÃO é seu computador pessoal, desmarque 'Salvar Senha' ou remova as configurações ao sair.",
        size=12,
        italic=True,
        color=ft.Colors.with_opacity(0.7, ft.Colors.ON_SURFACE),
    )

    proxy_enabled_switch = ft.Switch(
        label="Habilitar Proxy",
        value=current_settings.get(K_PROXY_ENABLED, False)
    )

    proxy_host_field = ValidatedTextField(
        label="Host do Proxy",
        value=current_settings.get(K_PROXY_IP_URL, ""),
        validator=host_validator,
        hint_text="ex: 192.168.1.100 ou proxy.empresa.com"
    )
    proxy_port_field = ValidatedTextField(
        label="Porta do Proxy",
        value=str(current_settings.get(K_PROXY_PORT, "")),
        validator=port_validator,
        keyboard_type=ft.KeyboardType.NUMBER
    )
    proxy_user_field = ft.TextField(
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
    save_password_checkbox = ft.Checkbox(
        label="Salvar Senha",
        value=current_settings.get(K_PROXY_PASSWORD_SAVED, False)
    )

    def on_save_button_click(e: ft.ControlEvent) -> Optional[Dict[str, Any]]:
        """
        Manipula o clique do botão 'Salvar' no diálogo de configurações de proxy.
        Valida os campos, salva as configurações e retorna um resultado para o callback de fechamento.

        Args:
            e (ft.ControlEvent): Evento de controle que disparou a função.

        Returns:
            Optional[Dict[str, Any]]: Um dicionário com o resultado da operação se bem-sucedida,
                                      ou False se a validação falhar (mantendo o diálogo aberto).
        """
        logger.info("Botão Salvar (proxy) clicado.")
        is_enabled = proxy_enabled_switch.value
        host_valid = True
        port_valid = True

        if is_enabled:
            host_valid = proxy_host_field.validate(show_error=True)
            port_valid = proxy_port_field.validate(show_error=True)
        else:
            # Limpa erros visuais se o proxy for desabilitado
            proxy_host_field.text_field.error_text = None
            proxy_port_field.text_field.error_text = None
            proxy_host_field.update()
            proxy_port_field.update()

        if not host_valid or not port_valid:
            show_snackbar(page, "Corrija os erros no formulário.", color=theme.COLOR_ERROR)
            return False

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
            logger.info("Configurações de proxy salvas no Keyring.")
            return {"action": "saved", "message": "Configurações de proxy salvas com sucesso!", "color": theme.COLOR_SUCCESS}
        else:
            logger.error("Falha ao salvar configurações de proxy no Keyring.")
            show_snackbar(page, "Erro ao salvar configurações de proxy.", color=theme.COLOR_ERROR)
            return False

    def on_delete_button_click(e: ft.ControlEvent) -> Optional[Dict[str, Any]]:
        """
        Manipula o clique do botão 'Remover Tudo' no diálogo de configurações de proxy.
        Limpa todas as configurações de proxy salvas e atualiza a interface.

        Args:
            e (ft.ControlEvent): Evento de controle que disparou a função.

        Returns:
            Optional[Dict[str, Any]]: Um dicionário com o resultado da operação se bem-sucedida,
                                      ou False se a operação falhar (mantendo o diálogo aberto).
        """
        logger.info("Botão Remover Tudo (proxy) clicado.")
        settings_to_delete = {
            K_PROXY_ENABLED: False,
            K_PROXY_IP_URL: PROXY_URL_DEFAULT,
            K_PROXY_PORT: PROXY_PORT_DEFAULT,
            K_PROXY_USERNAME: "",
            K_PROXY_PASSWORD: "",
            K_PROXY_PASSWORD_SAVED: False
        }
        if save_proxy_settings(settings_to_delete):
            logger.info("Configurações de proxy removidas do Keyring.")
            # Atualiza os campos do formulário para refletir as configurações padrão/removidas
            proxy_enabled_switch.value = False
            proxy_host_field.value = PROXY_URL_DEFAULT
            proxy_port_field.value = PROXY_PORT_DEFAULT
            proxy_user_field.value = ""
            proxy_password_field.value = ""
            save_password_checkbox.value = False
            # Força a atualização visual dos campos no diálogo
            if dialog_proxy_instance and dialog_proxy_instance.content:
                dialog_proxy_instance.content.update()

            return {"action": "deleted", "message": "Configurações de proxy removidas.", "color": theme.COLOR_INFO}
        else:
            logger.error("Falha ao remover configurações de proxy.")
            show_snackbar(page, "Erro ao remover configurações de proxy.", color=theme.COLOR_ERROR)
            return False

    def on_cancel_button_click(e: ft.ControlEvent) -> Dict[str, str]:
        """
        Manipula o clique do botão 'Cancelar' no diálogo de configurações de proxy.

        Args:
            e (ft.ControlEvent): Evento de controle que disparou a função.

        Returns:
            Dict[str, str]: Um dicionário sinalizando que a operação foi cancelada.
        """
        logger.debug("Botão Cancelar (proxy) clicado.")
        return {"action": "cancelled"}

    def after_proxy_dialog_closed(result_data: Any) -> None:
        """
        Callback executado após o diálogo de configurações de proxy ser totalmente fechado.
        Exibe um snackbar com o resultado da operação (salvar, deletar, cancelar).

        Args:
            result_data (Any): Dados retornados pela ação do diálogo (salvar/deletar/cancelar).
        """
        logger.debug(f"Callback after_proxy_dialog_closed chamado com: {result_data}")
        if isinstance(result_data, dict) and result_data.get("message"):
            show_snackbar(page, result_data["message"], color=result_data.get("color", theme.COLOR_INFO))
        elif result_data == "cancelled":
            logger.debug("Operação de proxy cancelada pelo usuário.")

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
        ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
        security_warning_text
        ],
        tight=True, scroll=ft.ScrollMode.ADAPTIVE, width=560
    )

    dialog_proxy_instance = ManagedAlertDialog(
        page_ref=page,
        title="Configurações de Proxy",
        content=dialog_content_column,
        actions=actions_list,
        on_dialog_fully_closed=after_proxy_dialog_closed
    )
    dialog_proxy_instance.show()



execution_time = perf_counter() - start_time
logger.debug(f"Carregado LAYOUT.py em {execution_time:.4f}s")
