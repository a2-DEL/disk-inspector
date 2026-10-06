# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['D:/ruanjianxiazai/磁盘统计助手/main.py'],
    pathex=[],
    binaries=[],
    datas=[('config/rules.json', 'config')],
    hiddenimports=['PyQt6.QtSvg'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='磁盘文件检视工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['D:/ruanjianxiazai/磁盘统计助手/icon.ico'],
)
