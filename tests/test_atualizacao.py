from urllib.error import URLError

import pytest

from omac import __version__, sistema
from omac.app import Api
from omac.atualizacao import github as gh


def _release(tag="v99.0.0", arquivo="OMAC-64bits.exe"):
    return {
        "tag_name": tag,
        "body": "## What's Changed\n* Nova tela by @alguem in https://exemplo/1\n\n**Full Changelog**: https://exemplo",
        "assets": [{"name": arquivo}],
    }


# --- Versões ------------------------------------------------------------------------


@pytest.mark.parametrize("texto, esperado", [("v1.3.0", (1, 3, 0)), ("1.10", (1, 10)), ("v1.3.0-beta", None), ("", None)])
def test_numero_da_versao(texto, esperado):
    assert gh.numero_da_versao(texto) == esperado


def test_a_versao_do_app_e_entendida():
    assert gh.numero_da_versao(__version__) is not None


def test_compara_como_numero_e_nao_como_texto():
    assert gh.interpretar(_release("v1.10.0"), atual="1.9.0", bits=64).numero == "1.10.0"


@pytest.mark.parametrize("tag", ["v1.3.0", "v1.2.9", "beta", ""])
def test_nao_oferece_a_mesma_versao_nem_uma_mais_antiga(tag):
    assert gh.interpretar(_release(tag), atual="1.3.0", bits=64) is None


def test_so_oferece_quando_o_arquivo_dos_bits_certos_ja_foi_publicado():
    assert gh.interpretar(_release(), atual="1.3.0", bits=64) is not None
    assert gh.interpretar(_release(), atual="1.3.0", bits=32) is None
    assert gh.interpretar({**_release(), "assets": []}, atual="1.3.0", bits=64) is None


@pytest.mark.parametrize("campo", ["draft", "prerelease"])
def test_ignora_rascunho_e_pre_lancamento(campo):
    assert gh.interpretar({**_release(), campo: True}, atual="1.3.0", bits=64) is None


def test_novidades_so_com_os_titulos():
    assert gh.novidades(_release()["body"]) == ["Nova tela"]
    assert gh.novidades(None) == []


def test_sem_internet_vira_erro_amigavel(monkeypatch):
    def falha(*a, **k):
        raise URLError("sem rede")

    monkeypatch.setattr(gh, "urlopen", falha)
    with pytest.raises(gh.ErroDeAtualizacao, match="GitHub"):
        gh.procurar()


# --- API -------------------------------------------------------------------------


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "cfg"))
    monkeypatch.setattr(sistema, "rodando_como_exe", lambda: True)
    monkeypatch.setattr(gh, "procurar", lambda: gh.VersaoNova("99.0.0", ["Nova tela"]))
    return Api()


def test_rodando_pelo_python_nao_oferece_atualizacao(api, monkeypatch):
    monkeypatch.setattr(sistema, "rodando_como_exe", lambda: False)
    assert api.atualizacao_procurar(True) == {"indisponivel": True}


def test_oferece_a_versao_nova(api):
    assert api.atualizacao_procurar() == {"versao": "99.0.0", "novidades": ["Nova tela"]}


def test_agora_nao_so_volta_a_perguntar_em_outro_dia(api):
    api.atualizacao_adiar()
    assert api.atualizacao_procurar() == {}
    assert api.atualizacao_procurar(True)["versao"] == "99.0.0"
    api._cfg["atualizacao_adiada_em"] = "2020-01-01"
    assert api.atualizacao_procurar()["versao"] == "99.0.0"


def test_desligado_nao_consulta_ao_abrir(api, monkeypatch):
    def nao_chamar():
        raise AssertionError("não deveria consultar o GitHub")

    monkeypatch.setattr(gh, "procurar", nao_chamar)
    api._cfg["atualizacao_automatica"] = False
    assert api.atualizacao_procurar() == {}


def test_erro_de_internet_so_aparece_quando_pedido(api, monkeypatch):
    def falha():
        raise gh.ErroDeAtualizacao("sem rede")

    monkeypatch.setattr(gh, "procurar", falha)
    assert api.atualizacao_procurar() == {}
    assert api.atualizacao_procurar(True) == {"erro": "sem rede"}


def test_abrir_a_pagina_de_download(api, monkeypatch):
    abertos = []
    monkeypatch.setattr(sistema, "abrir_link", abertos.append)
    api.atualizacao_abrir_pagina()
    assert abertos == [gh.PAGINA_RELEASES]
