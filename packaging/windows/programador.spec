# -*- mode: python ; coding: utf-8 -*-
# PyInstaller: gera dist/ProgramadorRadios/ (modo pasta, inicia rápido).
# Uso (na raiz do projeto):  pyinstaller packaging/windows/programador.spec

import os
import re

from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo,
    VarStruct, VSVersionInfo)

ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))
with open(os.path.join(ROOT, "launcher", "__init__.py"), encoding="utf-8") as fh:
    VERSION = re.search(r'__version__ = "([^"]+)"', fh.read()).group(1)
nums = tuple(int(x) for x in VERSION.split(".")) + (0,)

version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=nums, prodvers=nums),
    kids=[
        StringFileInfo([StringTable("041604B0", [
            StringStruct("FileDescription", "Programador de Rádios"),
            StringStruct("ProductName", "Programador de Rádios"),
            StringStruct("FileVersion", VERSION),
            StringStruct("ProductVersion", VERSION),
            StringStruct("OriginalFilename", "ProgramadorRadios.exe"),
            StringStruct("LegalCopyright", "GPLv3"),
        ])]),
        VarFileInfo([VarStruct("Translation", [0x0416, 1200])]),
    ],
)

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, "assets"), "assets")],
    hiddenimports=[
        "ts2000prog.gui", "ts2000prog.simulator", "icomprog.gui",
        "icomprog.simulator", "serial.tools.list_ports",
    ],
    excludes=["numpy", "pandas", "matplotlib", "PIL", "IPython", "pytest",
              "pydoc_data", "conda", "conda_package_handling"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="ProgramadorRadios",
    console=False,
    icon=os.path.join(ROOT, "assets", "app.ico"),
    version=version_info,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="ProgramadorRadios",
               upx=False)
