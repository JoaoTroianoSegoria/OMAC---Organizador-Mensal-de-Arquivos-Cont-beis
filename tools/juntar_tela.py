"""Junta os scripts e os estilos da tela num arquivo de cada, para o .exe (1.11.0).

Os arquivos-fonte continuam separados em omac/ui (é onde se trabalha). Na hora de gerar o
.exe, o omac.spec chama `juntar()`: sai uma cópia da pasta com um `omac.js` (os scripts na
ordem do OMAC_SCRIPTS) e um `omac.css` (os estilos na ordem dos <link>). Assim a tela pede
2 arquivos em vez de 28; no .exe de 32 bits eles carregavam um por vez, então abrir fica mais
rápido. O carregador do index.html continua o mesmo, com as novas tentativas e a faixa vermelha.

Um erro de script aponta uma linha do omac.js: `OMAC_PARTES` (linha inicial de cada arquivo)
deixa a faixa vermelha dizer o arquivo e a linha de verdade.

    python -m tools.juntar_tela <destino>
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
UI = RAIZ / "omac" / "ui"
JS, CSS = "omac.js", "omac.css"

_RE_SCRIPTS = re.compile(r"const OMAC_SCRIPTS = \[(.*?)\];", re.S)
_RE_LINK = re.compile(r'^[ \t]*<link rel="stylesheet" href="([\w.-]+\.css)">[ \t]*\n', re.M)
_ESTRITO = '"use strict";'
# Comentários no começo podem vir antes do "use strict" (ele continua valendo).
_RE_ESTRITO = re.compile(r'\s*(?:/\*.*?\*/\s*|//[^\n]*\n\s*)*"use strict";', re.S)


def scripts_do_index(html: str) -> list[str]:
    m = _RE_SCRIPTS.search(html)
    if not m:
        raise ValueError("Não achei o OMAC_SCRIPTS no index.html.")
    return re.findall(r'"([\w.-]+\.js)"', m.group(1))


def estilos_do_index(html: str) -> list[str]:
    return _RE_LINK.findall(html)


def _js(origem: Path, nomes: list[str]) -> str:
    partes, corpo = [], []
    linha = 3  # 1: "use strict"; 2: OMAC_PARTES
    for nome in nomes:
        texto = (origem / nome).read_text(encoding="utf-8")
        if not texto.endswith("\n"):
            texto += "\n"
        partes.append([linha, nome])
        corpo.append(texto)
        linha += texto.count("\n")
    # Todos os scripts são "use strict": no arquivo junto, a primeira linha vale para todos.
    return f"{_ESTRITO}\nwindow.OMAC_PARTES = {json.dumps(partes)};\n" + "".join(corpo)


def _css(origem: Path, nomes: list[str]) -> str:
    return "".join(f"/* ===== {nome} ===== */\n" + (origem / nome).read_text(encoding="utf-8").rstrip() + "\n"
                   for nome in nomes)


def juntar(destino: Path, origem: Path = UI) -> Path:
    """Escreve em `destino` a tela pronta para o .exe e devolve a pasta."""
    destino = Path(destino)
    html = (origem / "index.html").read_text(encoding="utf-8")
    scripts, estilos = scripts_do_index(html), estilos_do_index(html)
    if (sorted(scripts) != sorted(p.name for p in origem.glob("*.js"))
            or sorted(estilos) != sorted(p.name for p in origem.glob("*.css"))):
        raise ValueError("O index.html não carrega todos os .js e .css da pasta: confira antes de gerar o .exe.")
    for nome in scripts:
        if not _RE_ESTRITO.match((origem / nome).read_text(encoding="utf-8")):
            raise ValueError(f"{nome} não começa com \"use strict\".")

    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir(parents=True)
    for p in origem.iterdir():  # o que não é script nem estilo (o index.html é reescrito abaixo)
        if p.is_file() and p.suffix not in (".js", ".css") and p.name != "index.html":
            shutil.copy2(p, destino / p.name)

    (destino / JS).write_text(_js(origem, scripts), encoding="utf-8")
    (destino / CSS).write_text(_css(origem, estilos), encoding="utf-8")

    primeiro = True

    def um_link(m: re.Match) -> str:
        nonlocal primeiro
        if not primeiro:
            return ""
        primeiro = False
        return m.group(0).replace(m.group(1), CSS)

    html = _RE_LINK.sub(um_link, html)
    html = _RE_SCRIPTS.sub(f'const OMAC_SCRIPTS = ["{JS}"];', html, count=1)
    (destino / "index.html").write_text(html, encoding="utf-8")
    return destino


if __name__ == "__main__":
    print(juntar(Path(sys.argv[1] if len(sys.argv) > 1 else RAIZ / "build" / "tela")))
