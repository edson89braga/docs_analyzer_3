# -*- mode: python ; coding: utf-8 -*-

import os
import shutil
from PyInstaller.utils.hooks import collect_all, collect_data_files

# --- Coleta de dependências complexas ---
# collect_all retorna (datas, binaries, hiddenimports)

# Coleta de 'transformers'
transformers_datas, transformers_binaries, transformers_hiddenimports = collect_all('transformers')

# Coleta de 'sentence-transformers'
s_t_datas, s_t_binaries, s_t_hiddenimports = collect_all('sentence_transformers')

# Coleta de 'torch'
torch_datas, torch_binaries, torch_hiddenimports = collect_all('torch')

# --- Bloco de Análise: Identifica todos os arquivos e dependências ---
a = Analysis(
    ['app_test_docx_v2.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Inclui a pasta de assets original
        ('assets', 'assets'),
        (r'C:\Users\edson.eab\AppData\Local\pypoetry\Cache\virtualenvs\docs-analyzer-3-DJ3PQuGu-py3.13\Lib\site-packages\flet_web\web', 'flet_web/web'),
        *transformers_datas,
        *s_t_datas,
        *torch_datas
    ],
    hiddenimports=[
        # Imports padrão do teste
        'docx',
        'lxml',
        # Imports ocultos das bibliotecas de ML
        'keyring.backends.Windows', # Incluído por boa prática
        *transformers_hiddenimports,
        *s_t_hiddenimports,
        *torch_hiddenimports
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    [],
    name='app_test_docx_v2',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False, # Mantido como False para testes rápidos
    runtime_tmpdir=None,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='app_test_docx_v2'
)

# --- Bloco Pós-Build: Move os assets para o local correto ---
dist_path = os.path.join(DISTPATH, 'app_test_docx_v2')
internal_assets_path = os.path.join(dist_path, '_internal', 'assets')
root_assets_path = os.path.join(dist_path, 'assets')

if os.path.exists(internal_assets_path):
    print(f"Movendo assets de '{internal_assets_path}' para '{root_assets_path}'...")
    if os.path.exists(root_assets_path):
        shutil.rmtree(root_assets_path)
    shutil.move(internal_assets_path, root_assets_path)
    print("Assets movidos com sucesso.")
else:
    print(f"AVISO: Pasta de assets não encontrada em '{internal_assets_path}'. O script pós-build não fez nada.")