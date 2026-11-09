# Receita do PyInstaller para gerar o OMAC (uma pasta com OMAC.exe e _internal, sem console).
#   pyinstaller omac.spec
#
# É uma pasta, e não um .exe único, porque o arquivo único se descompacta em uma pasta
# temporária a cada abertura, o que costuma disparar alarme falso nos antivírus.

import re
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

datas = [("omac/ui", "omac/ui")]
binaries = []
hiddenimports = []

# pdfium (leitor de PDF): a DLL e o version.json do pacote
for pacote in ("pypdfium2", "pypdfium2_raw"):
    d, b, h = collect_all(pacote)
    datas += d
    binaries += b
    hiddenimports += h



def propriedades_do_arquivo():
    """Nome, versão e autor no .exe: um programa sem isso parece mais suspeito para o antivírus."""
    if sys.platform != "win32":
        return None
    from PyInstaller.utils.win32.versioninfo import (
        FixedFileInfo,
        StringFileInfo,
        StringStruct,
        StringTable,
        VarFileInfo,
        VarStruct,
        VSVersionInfo,
    )

    versao = re.search(r'__version__ = "(.+)"', Path("omac/__init__.py").read_text(encoding="utf-8"))[1]
    numeros = tuple(int(n) for n in (versao.split(".") + ["0", "0", "0"])[:4])
    return VSVersionInfo(
        ffi=FixedFileInfo(filevers=numeros, prodvers=numeros, mask=0x3F, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0),
        kids=[
            StringFileInfo([StringTable("041604B0", [
                StringStruct("CompanyName", "João Troiano Segoria"),
                StringStruct("FileDescription", "OMAC - Organizador Mensal de Arquivos Contábeis"),
                StringStruct("FileVersion", versao),
                StringStruct("InternalName", "OMAC"),
                StringStruct("LegalCopyright", "João Troiano Segoria"),
                StringStruct("OriginalFilename", "OMAC.exe"),
                StringStruct("ProductName", "OMAC"),
                StringStruct("ProductVersion", versao),
            ])]),
            VarFileInfo([VarStruct("Translation", [0x0416, 1200])]),
        ],
    )


a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "unittest", "pydoc", "PIL", "reportlab", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="OMAC",
    icon="assets/omac.ico",
    console=False,
    upx=False,
    debug=False,
    strip=False,
    version=propriedades_do_arquivo(),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="OMAC",
)
