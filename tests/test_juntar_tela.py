"""1.11.0: no .exe, os scripts e os estilos da tela vão juntos num arquivo de cada."""

import re

from tools.juntar_tela import CSS, JS, UI, estilos_do_index, juntar, scripts_do_index


def test_junta_tudo_na_ordem_e_o_index_pede_um_de_cada(tmp_path):
    fonte = (UI / "index.html").read_text(encoding="utf-8")
    scripts, estilos = scripts_do_index(fonte), estilos_do_index(fonte)
    pasta = juntar(tmp_path / "tela")
    html = (pasta / "index.html").read_text(encoding="utf-8")
    assert scripts_do_index(html) == [JS]
    assert estilos_do_index(html) == [CSS]
    assert sorted(p.name for p in pasta.iterdir()) == sorted(["index.html", JS, CSS])

    js = (pasta / JS).read_text(encoding="utf-8")
    assert js.startswith('"use strict";\n')
    linhas = js.split("\n")
    partes = eval(re.search(r"window.OMAC_PARTES = (\[.*?\]);", js).group(1))  # noqa: S307 — lista de listas
    assert [nome for _, nome in partes] == scripts
    for inicio, nome in partes:  # cada arquivo começa na linha anotada (a faixa vermelha usa isso)
        primeira = (UI / nome).read_text(encoding="utf-8").split("\n")[0]
        assert linhas[inicio - 1] == primeira, nome

    css = (pasta / CSS).read_text(encoding="utf-8")
    posicoes = [css.index(f"/* ===== {nome} ===== */") for nome in estilos]
    assert posicoes == sorted(posicoes)


def test_o_resto_do_index_fica_igual(tmp_path):
    fonte = (UI / "index.html").read_text(encoding="utf-8")
    html = (juntar(tmp_path / "tela") / "index.html").read_text(encoding="utf-8")
    sem = lambda t: re.sub(r'^[ \t]*<link rel="stylesheet"[^\n]*\n|const OMAC_SCRIPTS = \[.*?\];', "", t, flags=re.S | re.M)  # noqa: E731
    assert sem(fonte) == sem(html)
