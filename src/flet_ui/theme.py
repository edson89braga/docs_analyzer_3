# src/flet_ui/theme.py
"""
Define o tema visual, cores, fontes e estilos reutilizáveis para a aplicação Flet.
"""
import flet as ft

# --- Paleta de Cores Principal (Exemplo - Azul) ---
# Você pode definir suas cores hexadecimais aqui ou usar as pré-definidas do Flet
SEED_COLOR = ft.colors.BLUE_700 # Cor base para gerar o esquema de cores

# --- Cores Semânticas Adicionais (se necessário) ---
COLOR_SUCCESS = ft.colors.GREEN_600
COLOR_WARNING = ft.colors.ORANGE_500
COLOR_ERROR = ft.colors.RED_600
COLOR_INFO = ft.colors.LIGHT_BLUE_500

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
    # Você pode sobrescrever elementos específicos do tema aqui, se desejar:
    # appbar_theme=ft.AppBarTheme(
    #     background_color=ft.colors.BLUE_GREY_800,
    #     foregroundColor=ft.colors.WHITE
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
    # Customizações específicas para o tema escuro, se necessário
)

# --- Outras Configurações de Estilo Globais ---
# Exemplo: Configuração padrão para bordas de TextField
# INPUT_BORDER_STYLE = ft.InputBorder.OUTLINE