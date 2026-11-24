"""Menu lateral em grupos (config) e notas que chegam na pasta (conferência rápida + notas novas)."""

from datetime import date

import pytest

from omac import config, sistema
from omac.app import Api
from tests.fabrica import criar_nota, criar_pasta_exemplo, nome_arquivo


def test_menu_vazio_e_o_padrao_da_tela():
    assert config.normalizar({})["menu"] == []
    assert config.normalizar({"menu": "bagunça"})["menu"] == []


def test_menu_confere_o_formato_e_nao_repete_tela():
    menu = config.normalizar({"menu": [
        {"nome": "  Financeiro   do mês ", "itens": ["relatorio", "resumo", "relatorio", 3, ""]},
        {"nome": None, "itens": ["resumo", "atendimentos"]},
        "lixo",
        {"nome": "x" * 50, "itens": "não é lista"},
    ]})["menu"]
    assert menu == [
        {"nome": "Financeiro do mês", "itens": ["relatorio", "resumo"]},
        {"nome": "", "itens": ["atendimentos"]},  # sem nome: no menu fica só a linha
        {"nome": "x" * 30, "itens": []},
    ]


def test_config_antiga_ganha_o_automatico_das_notas_ligado():
    assert config.normalizar({})["notas_automatico"] is True
    assert config.normalizar({"notas_automatico": 0})["notas_automatico"] is False


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "cfg"))
    monkeypatch.setattr(sistema, "colar_sozinho_disponivel", lambda: False)
    a = Api()
    a.pasta = criar_pasta_exemplo(tmp_path / "NFS-e 2026")
    a._cfg.update(pasta_notas=str(a.pasta))
    return a


def test_sem_leitura_nao_ha_o_que_conferir(api):
    assert api.notas_conferir() == {"mudou": False}


def test_conferir_so_avisa_quando_a_pasta_muda_e_a_leitura_diz_as_novas(api):
    primeira = api.notas_do_mes(2026, 10)
    assert primeira["novas"] == [] and len(primeira["lida_em"]) == 5  # "14:32"
    assert api.notas_conferir() == {"mudou": False}

    dia = date(2026, 10, 30)
    criar_nota(api.pasta / nome_arquivo(900, "PACIENTE NOVO", dia), 900, dia, dia, "180.00", tomador="PACIENTE NOVO")
    (api.pasta / "anotacao.txt").write_text("não é nota")  # outro tipo de arquivo não conta
    assert api.notas_conferir() == {"mudou": True}

    segunda = api.notas_do_mes(2026, 10)
    assert segunda["novas"] == [{"numero": 900, "paciente": "PACIENTE NOVO", "renomear": None}]
    assert api.notas_conferir() == {"mudou": False}
    assert api.notas_do_mes(2026, 10)["novas"] == []  # só avisa uma vez


def test_nota_apagada_tambem_conta_como_mudanca(api):
    api.notas_do_mes(2026, 10)
    next(api.pasta.glob("*.pdf")).unlink()
    assert api.notas_conferir()["mudou"] is True


def test_trocar_de_pasta_nao_chama_as_notas_da_outra_de_novas(api, tmp_path):
    api.notas_do_mes(2026, 10)
    outra = tmp_path / "outra"
    outra.mkdir()
    dia = date(2026, 10, 2)
    criar_nota(outra / nome_arquivo(1, "ALGUEM", dia), 1, dia, dia, "10.00", tomador="ALGUEM")
    api._cfg.update(pasta_notas=str(outra))
    assert api.notas_conferir()["mudou"] is True
    assert api.notas_do_mes(2026, 10)["novas"] == []
