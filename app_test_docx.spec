# -*- mode: python ; coding: utf-8 -*-

import os
import shutil

# --- Bloco de Análise: Identifica todos os arquivos e dependências ---
a = Analysis(
    ['app_test_docx.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets_demo', 'assets_demo'),
        (r'C:\Users\edson.eab\AppData\Local\pypoetry\Cache\virtualenvs\docs-analyzer-3-DJ3PQuGu-py3.13\Lib\site-packages\flet_web\web', 'flet_web/web')
    ],
    hiddenimports=['docx', 'lxml'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# --- Bloco PYZ: Agrupa os módulos Python compilados ---
pyz = PYZ(a.pure)

# --- Bloco EXE: Cria apenas o executável, sem dados ou binários embutidos ---
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='app_test_docx',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# --- Bloco COLLECT: Monta o diretório final da aplicação ---
# Este bloco pega o executável e agrupa com todos os dados e binários.
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='app_test_docx'
)

# --- Bloco Pós-Build: Move os assets para o local correto ---
dist_path = os.path.join(DISTPATH, 'app_test_docx')
internal_assets_path = os.path.join(dist_path, '_internal', 'assets_demo')
root_assets_path = os.path.join(dist_path, 'assets_demo')

if os.path.exists(internal_assets_path):
    print(f"Movendo assets de '{internal_assets_path}' para '{root_assets_path}'...")
    if os.path.exists(root_assets_path):
        shutil.rmtree(root_assets_path)
    shutil.move(internal_assets_path, root_assets_path)
    print("Assets movidos com sucesso.")
else:
    print(f"AVISO: Pasta de assets não encontrada em '{internal_assets_path}'. O script pós-build não fez nada.")