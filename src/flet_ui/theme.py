# src/flet_ui/theme.py
"""
Define o tema visual, cores, fontes e estilos reutilizáveis para a aplicação Flet.
"""
import flet as ft
from datetime import datetime

# --- Paleta de Cores Principal (Exemplo - Azul) ---
# Você pode definir suas cores hexadecimais aqui ou usar as pré-definidas do Flet
SEED_COLOR = ft.Colors.BLUE_700 # Cor base para gerar o esquema de cores

# --- Cores Semânticas Adicionais (se necessário) ---
COLOR_SUCCESS = ft.Colors.GREEN_600
COLOR_WARNING = ft.Colors.ORANGE_500
COLOR_ERROR = ft.Colors.RED_600
COLOR_INFO = ft.Colors.LIGHT_BLUE_500

# --- Definições de Espaçamento e Padding ---
PADDING_XS = 2
PADDING_S = 5
PADDING_M = 10
PADDING_L = 20
PADDING_XL = 30

# --- Definições de Fonte (Opcional - Flet usa Roboto por padrão) ---
# FONT_FAMILY_DEFAULT = "Roboto"
# FONT_FAMILY_HEADINGS = "Roboto Slab" # Exemplo

# --- Estilos de Texto Reutilizáveis (Exemplos) ---
# TextTheme do Flet já define muitos estilos, mas você pode customizar
# ou criar novos aqui se necessário.
# Exemplo:
# TITLE_LARGE = ft.TextStyle(size=22, weight=ft.FontWeight.BOLD, font_family=FONT_FAMILY_HEADINGS)
# BODY_MEDIUM_ITALIC = ft.TextStyle(italic=True)

# --- Tema Principal da Aplicação ---
# Usaremos um esquema de cores gerado a partir da SEED_COLOR
APP_THEME = ft.Theme(
    color_scheme_seed=SEED_COLOR,
    # Use use_material3=True para o design mais recente (recomendado)
    use_material3=True,
    appbar_theme=ft.AppBarTheme(
        bgcolor=ft.Colors.BLACK26, # BLUE_GREY_100, # Para tema claro
        foreground_color=ft.Colors.BLACK,
    ),
    # Você pode sobrescrever elementos específicos do tema aqui, se desejar:
    # appbar_theme=ft.AppBarTheme(
    #     background_color=ft.Colors.BLUE_GREY_800,
    #     foregroundColor=ft.Colors.WHITE
    # ),
    # text_theme=ft.TextTheme(
    #     title_large=TITLE_LARGE, # Usando o estilo definido acima
    # ),
    # navigation_rail_theme=ft.NavigationRailThemeData(
    #     selected_label_text_style=ft.TextStyle(weight=ft.FontWeight.BOLD)
    # )
)

# --- Tema Escuro (Opcional, mas recomendado) ---
APP_DARK_THEME = ft.Theme(
    color_scheme_seed=SEED_COLOR, # Pode usar a mesma seed ou outra
    use_material3=True,
    #appbar_theme=ft.AppBarTheme(
    #    bgcolor=ft.Colors.BLUE_GREY_800, # Para tema escuro
    #    foreground_color=ft.Colors.BLACK,
    #),
    # Customizações específicas para o tema escuro, se necessário
)

# --- Outras Configurações de Estilo Globais ---
# Exemplo: Configuração padrão para bordas de TextField
# INPUT_BORDER_STYLE = ft.InputBorder.OUTLINE

APP_YEAR = datetime.now().year

APP_PRIMARY_COLOR = ft.Colors.BLUE_GREY_700

# Cores de Material Design (exemplo)
PRIMARY = APP_PRIMARY_COLOR # Pode ser referenciada diretamente como PRIMARY
SURFACE_VARIANT = ft.Colors.BLUE_GREY_100
ON_SURFACE = ft.Colors.BLACK87

# Função básica de configuração de tema
def configure_theme(page: ft.Page):
    """Configura o tema claro e escuro básico para a aplicação."""
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(
        color_scheme=ft.ColorScheme(
            primary=APP_PRIMARY_COLOR,
            primary_container=ft.Colors.with_opacity(0.1, APP_PRIMARY_COLOR),
            # Você pode adicionar outras cores do esquema aqui
        ),
        # Exemplo de tema para controles específicos, se necessário
        # control_theme=ft.ControlTheme(
        #     padding=PADDING_M # Padding padrão para controles
        # )
    )
    page.dark_theme = ft.Theme(
        color_scheme=ft.ColorScheme(
            primary=ft.Colors.BLUE_GREY_300, # Uma cor primária mais clara para o tema escuro
            primary_container=ft.Colors.with_opacity(0.1, ft.Colors.BLUE_GREY_300),
            # ... outras cores do esquema para o tema escuro
        ),
        # control_theme=ft.ControlTheme(
        #     padding=PADDING_M
        # )
    )
    # print("Tema configurado a partir de src/flet_ui/theme.py")

WIDTH_CONTAINER_CONFIGS = 700

# Cores para Cards e Panels
PANEL_HEADER_BGCOLOR = ft.Colors.with_opacity(0.05, ft.Colors.SECONDARY) # Usando PRIMARY que já deve estar definido
PANEL_CONTENT_BGCOLOR = ft.colors.BACKGROUND # SURFACE Ou ft.colors.BACKGROUND, ou uma cor customizada