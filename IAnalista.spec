# -*- mode: python ; coding: utf-8 -*-

import os
import sys

block_cipher = None

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets', 'assets'),
        (r'C:\Users\edson.eab\AppData\Local\pypoetry\Cache\virtualenvs\docs-analyzer-3-DJ3PQuGu-py3.13\Lib\site-packages\flet_web\web', 'flet_web/web'),
        (r'C:\Users\edson.eab\AppData\Local\pypoetry\Cache\virtualenvs\docs-analyzer-3-DJ3PQuGu-py3.13\Lib\site-packages\tiktoken_ext', 'tiktoken_ext')
    ],
    hiddenimports=[
        'keyring.backends.Windows',
        'src.flet_ui.views.login_view',
        'src.flet_ui.views.signup_view',
        'src.flet_ui.views.home_view',
        'src.flet_ui.views.profile_view',
        'src.flet_ui.views.proxy_settings_view',
        'src.flet_ui.views.llm_settings_view',
        'src.flet_ui.views.nc_analyze_view',
        'src.flet_ui.views.others_view',
        'unidecode',
        'sentence_transformers',
        'tiktoken_ext.cl100k_base',
        'jaraco.text',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pytest',
        'setuptools',
        'pip',
        'wheel',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='IAnalista',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,         # Equivalente a --noconsole
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon1.ico', # Caminho relativo para o ícone
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='IAnalista', # Nome da pasta que será criada dentro de 'dist'
)