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


def _scripts_do_index(html: str) -> list[str]:
    lista = re.search(r"const OMAC_SCRIPTS = \[(.*?)\];", html, re.S).group(1)
    return re.findall(r'"([\w.-]+\.js)"', lista)


def test_index_carrega_todos_os_scripts_e_estilos():
    html = (UI / "index.html").read_text(encoding="utf-8")
    scripts = _scripts_do_index(html)
    assert scripts[0] == "nucleo.js" and len(scripts) == len(set(scripts))
    assert sorted(scripts) == sorted(p.name for p in UI.glob("*.js"))
    for arquivo in UI.glob("*.css"):
        assert f'href="{arquivo.name}"' in html, arquivo.name


def test_scripts_carregam_pelo_carregador_e_nao_pelo_domcontentloaded():
    """Os scripts entram um por vez (com nova tentativa); o DOMContentLoaded já passou quando rodam."""
    html = (UI / "index.html").read_text(encoding="utf-8")
    assert "<script src=" not in html
    for js in UI.glob("*.js"):
        assert "DOMContentLoaded" not in js.read_text(encoding="utf-8"), js.name
