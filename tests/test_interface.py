"""Conferências dos arquivos da tela (omac/ui) que não precisam de navegador."""

import re
from collections import defaultdict
from pathlib import Path

UI = Path(__file__).resolve().parent.parent / "omac" / "ui"

# Declarações no nível de cima de cada script: todos dividem o mesmo escopo global.
_DECLARACAO = re.compile(r"^(?:async\s+)?(?:function\s*\*?\s*|const\s+|let\s+|var\s+|class\s+)([A-Za-z_$][\w$]*)", re.M)


def test_scripts_nao_repetem_nomes_globais():
    """Dois scripts com a mesma função: o último carregado vence e o outro quebra calado."""
    onde = defaultdict(list)
    for js in sorted(UI.glob("*.js")):
        for nome in _DECLARACAO.findall(js.read_text(encoding="utf-8")):
            onde[nome].append(js.name)
    repetidos = {nome: arquivos for nome, arquivos in onde.items() if len(arquivos) > 1}
    assert repetidos == {}


def test_index_carrega_todos_os_scripts_e_estilos():
    html = (UI / "index.html").read_text(encoding="utf-8")
    for arquivo in UI.iterdir():
        if arquivo.suffix == ".js":
            assert f'<script src="{arquivo.name}"></script>' in html, arquivo.name
        if arquivo.suffix == ".css":
            assert f'href="{arquivo.name}"' in html, arquivo.name
