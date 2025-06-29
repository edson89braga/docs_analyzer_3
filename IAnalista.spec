# -*- mode: python ; coding: utf-8 -*-

import os
import shutil
from PyInstaller.utils.hooks import collect_all

# --- Bloco 1: Coleta automática de dependências complexas ---
# Esta seção usa os hooks do PyInstaller para encontrar todos os dados, binários e imports ocultos das bibliotecas de Machine Learning.

print("Coletando dependências de 'transformers'...")
transformers_datas, transformers_binaries, transformers_hiddenimports = collect_all('transformers')

print("Coletando dependências de 'sentence_transformers'...")
s_t_datas, s_t_binaries, s_t_hiddenimports = collect_all('sentence_transformers')

print("Coletando dependências de 'torch'...")
torch_datas, torch_binaries, torch_hiddenimports = collect_all('torch')

print("Coleta de dependências de ML concluída.")

# --- Bloco 2: Análise principal da aplicação ---
a = Analysis(
    ['run.py'],  # O ponto de entrada da sua aplicação
    pathex=[],
    binaries=transformers_binaries + s_t_binaries + torch_binaries,
    datas=[
        # 1. Inclui a pasta 'assets' principal do seu projeto.
        ('assets', 'assets'),
        (r'C:\Users\edson.eab\AppData\Local\pypoetry\Cache\virtualenvs\docs-analyzer-3-DJ3PQuGu-py3.13\Lib\site-packages\flet_web\web', 'flet_web/web'),
        (r'C:\Users\edson.eab\AppData\Local\pypoetry\Cache\virtualenvs\docs-analyzer-3-DJ3PQuGu-py3.13\Lib\site-packages\tiktoken_ext', 'tiktoken_ext'),
        (r'C:\Users\edson.eab\AppData\Roaming\nltk_data', 'nltk_data'),
        *transformers_datas,
        *s_t_datas,
        *torch_datas,
    ],
    hiddenimports=[
        # Imports que o PyInstaller pode não detectar automaticamente.
        'keyring.backends.Windows',  # Para run.py
        'unidecode',                 # Para utils.py
        'langdetect',                # Para pdf_processor.py
        'docx', 'lxml',              # Para doc_generator.py

        # Imports dinâmicos das views (essencial para o roteador)
        'src.flet_ui.views.login_view',
        'src.flet_ui.views.signup_view',
        'src.flet_ui.views.home_view',
        'src.flet_ui.views.profile_view',
        'src.flet_ui.views.llm_settings_view',
        'src.flet_ui.views.nc_analyze_view',
        'src.flet_ui.views.others_view',
        
        # Imports ocultos coletados das bibliotecas de ML.
        'sentence_transformers',
        'tiktoken_ext.cl100k_base',
        'jaraco.text',
        *transformers_hiddenimports,
        *s_t_hiddenimports,
        *torch_hiddenimports,

        # Imports para garantir a robustez da validação JWT
        #'cryptography',
        #'cryptography.hazmat.backends.openssl',
        #'cryptography.hazmat.primitives.asymmetric.rsa'

    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
        excludes=[
        'pytest'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# --- Bloco 3: Geração do Executável e Coleta de Arquivos ---
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    [],
    name='IAnalista',         # Nome distinto para o executável de debug
    debug=False,              # Habilita saídas de debug do bootloader
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,   # Causa travamentos silenciosos no PyTorch e bibliotecas SSL. Substituir por compressor externo (7-Zip)
    runtime_tmpdir=None,
    console=False,            # Mostra a janela do console
    icon='assets/icon1.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,   
    name='IAnalista'
)

# --- Bloco 4: Script Pós-Build ---
# Move a pasta 'assets' da subpasta '_internal' para o diretório raiz da aplicação.
dist_path = os.path.join(DISTPATH, 'IAnalista')

internal_assets_path = os.path.join(dist_path, '_internal', 'assets')
root_assets_path = os.path.join(dist_path, 'assets')

internal_nltk_path = os.path.join(dist_path, '_internal', 'nltk_data')
root_nltk_path = os.path.join(dist_path, 'nltk_data')

if os.path.exists(internal_assets_path):
    print(f"Movendo assets de '{internal_assets_path}' para '{root_assets_path}'...")
    
    if os.path.exists(root_assets_path):
        shutil.rmtree(root_assets_path)
    shutil.move(internal_assets_path, root_assets_path)
    
    if os.path.exists(root_nltk_path):
        shutil.rmtree(root_nltk_path)
    shutil.move(internal_nltk_path, root_nltk_path)
    
    print("Assets movidos com sucesso.")
else:
    print(f"AVISO: Pasta 'assets' não encontrada em '{internal_assets_path}'. O script pós-build não fez nada.")