import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Em outro processo: sem a trava, o pdfium derruba o Python inteiro, e o pytest junto.
LEITURA_SIMULTANEA = """
import sys, threading
from pathlib import Path
from omac.pdf import extrair_paginas
from tests.fabrica import criar_pasta_exemplo

pasta = criar_pasta_exemplo(Path(sys.argv[1]) / "NFS-e 2026")
pdfs = list(pasta.glob("*.pdf")) + list((pasta / "Extratos").glob("*.pdf"))

def ler():
    for _ in range(15):
        for p in pdfs:
            extrair_paginas(p)

linhas = [threading.Thread(target=ler) for _ in range(3)]
for t in linhas: t.start()
for t in linhas: t.join()
print("ok")
"""


def test_ler_pdfs_em_varias_threads_nao_derruba_o_programa(tmp_path):
    r = subprocess.run([sys.executable, "-c", LEITURA_SIMULTANEA, str(tmp_path)], cwd=RAIZ,
                       capture_output=True, text=True, timeout=240)
    assert r.returncode == 0, r.stderr[-500:]
    assert r.stdout.strip() == "ok"
