# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['test_app.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Caminho para os assets da sua aplicação
        ('assets', 'assets'),
        # Caminho absoluto para os assets web do Flet (MUITO IMPORTANTE)
        # Use o caminho exato do seu ambiente virtual
        (r'C:\Users\edson.eab\AppData\Local\pypoetry\Cache\virtualenvs\docs-analyzer-3-DJ3PQuGu-py3.13\Lib\site-packages\flet_web\web', 'flet_web/web')
    ],
    hiddenimports=[
        'keyring.backends.Windows',
        'jaraco.text', # Adicionando proativamente com base no erro anterior
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TestApp',
    debug=True,            # Ativa o modo de depuração para ver mais logs
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,             # Desativa UPX para compilação muito mais rápida
    console=True,          # ESSENCIAL: Mantém o console aberto para ver os erros
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.png',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='TestApp'
)