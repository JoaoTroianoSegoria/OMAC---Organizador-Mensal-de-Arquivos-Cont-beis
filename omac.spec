# Receita do PyInstaller para gerar o OMAC.exe (um arquivo só, sem console).
#   pyinstaller omac.spec

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
    a.binaries,
    a.datas,
    [],
    name="OMAC",
    icon="assets/omac.ico",
    console=False,
    upx=False,
    debug=False,
    strip=False,
    runtime_tmpdir=None,
)
