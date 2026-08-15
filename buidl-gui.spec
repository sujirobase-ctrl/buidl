# -*- mode: python ; coding: utf-8 -*-

import os
import shutil
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files


# Some portable/uv Python distributions keep Tcl/Tk under the interpreter
# directory. Stage the runtime inside the workspace before Analysis so
# PyInstaller's tkinter hook can inspect and bundle it reliably.
python_tcl = Path(sys.base_prefix) / "tcl"
staged_tk = Path("build") / "tk-runtime"
if python_tcl.is_dir():
    shutil.copytree(python_tcl / "tcl8.6", staged_tk / "tcl8.6", dirs_exist_ok=True)
    shutil.copytree(python_tcl / "tk8.6", staged_tk / "tk8.6", dirs_exist_ok=True)
    os.environ["TCL_LIBRARY"] = str((staged_tk / "tcl8.6").resolve())
    os.environ["TK_LIBRARY"] = str((staged_tk / "tk8.6").resolve())

customtkinter_data = collect_data_files("customtkinter")

a = Analysis(
    ["gui.py"],
    pathex=["."],
    binaries=[],
    datas=customtkinter_data,
    hiddenimports=["customtkinter"],
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
