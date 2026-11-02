# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ["gui_qt.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "customtkinter"],
    noarchive=False,
    optimize=0,
)
# Qt 6.11 uses the Windows system ICU. The Codex build host also has Poppler on
# PATH, and PyInstaller would otherwise collect Poppler's incompatible ICU 78
# DLLs (which fail at runtime with a missing ucnv_open_1 entry point).
a.binaries = [
    entry
    for entry in a.binaries
    if entry[0].lower() not in {"icuuc.dll", "icudt78.dll"}
]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="buidl-gui",
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
)
