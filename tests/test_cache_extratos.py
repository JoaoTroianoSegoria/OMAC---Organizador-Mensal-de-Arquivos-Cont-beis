"""1.11.0: a leitura dos extratos fica num arquivo, para a primeira abertura do dia ser rápida."""

import json

import pytest

from omac.extrato import pasta as px
from tests.fabrica import criar_pasta_extratos


@pytest.fixture(autouse=True)
def memoria_limpa(monkeypatch):
    monkeypatch.setattr(px, "_MEMORIA", {})
    monkeypatch.setattr(px, "_CACHE_LIDO", set())
    monkeypatch.setattr(px, "_CHAVES_SALVAS", {})


def _esquecer():
    """Como abrir o app de novo: a memória começa vazia."""
    px._MEMORIA.clear()
    px._CACHE_LIDO.clear()
    px._CHAVES_SALVAS.clear()


def test_segunda_abertura_nao_abre_os_pdfs(tmp_path, monkeypatch):
    pasta = criar_pasta_extratos(tmp_path / "Extratos")
    cache = tmp_path / "cfg" / "cache-extratos.json"
    primeira = px.varrer(pasta, cache)
    assert cache.is_file() and primeira.lancamentos

    _esquecer()
    monkeypatch.setattr(px, "ler_extrato", lambda arquivo: pytest.fail(f"abriu o PDF {arquivo}"))
    segunda = px.varrer(pasta, cache)
    assert segunda.lancamentos == primeira.lancamentos
    assert [e.solicitado_em for e in segunda.extratos] == [e.solicitado_em for e in primeira.extratos]
    assert segunda.avisos_do_mes(2026, 10) == primeira.avisos_do_mes(2026, 10)


def test_pdf_mudado_e_lido_de_novo_e_o_que_sai_da_pasta_sai_do_cache(tmp_path):
    pasta = criar_pasta_extratos(tmp_path / "Extratos")
    cache = tmp_path / "cache-extratos.json"
    px.varrer(pasta, cache)
    pdfs = sorted(pasta.glob("*.pdf"))
    pdfs[0].unlink()
    _esquecer()
    px.varrer(pasta, cache)
    itens = json.loads(cache.read_text(encoding="utf-8"))["itens"]
    assert sorted(itens) == sorted(str(p.resolve()) for p in pdfs[1:])


@pytest.mark.parametrize("conteudo", ["estragado{", json.dumps({"versao": 999, "itens": {"x": 1}}),
                                      json.dumps({"versao": px.VERSAO_CACHE, "itens": {"x": {"marca": 1}}})])
def test_cache_estragado_ou_de_outra_versao_le_os_pdfs(tmp_path, conteudo):
    pasta = criar_pasta_extratos(tmp_path / "Extratos")
    cache = tmp_path / "cache-extratos.json"
    cache.write_text(conteudo, encoding="utf-8")
    assert px.varrer(pasta, cache).lancamentos
    assert json.loads(cache.read_text(encoding="utf-8"))["versao"] == px.VERSAO_CACHE


def test_leitura_ao_abrir_deixa_tudo_pronto_sem_avisar_nota_nova(tmp_path, monkeypatch):
    from omac import config, sistema
    from omac.app import Api
    from tests.fabrica import criar_pasta_exemplo

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "cfg"))
    monkeypatch.setattr(sistema, "colar_sozinho_disponivel", lambda: False)
    api = Api()
    notas = criar_pasta_exemplo(tmp_path / "NFS-e 2026")
    api._cfg.update(pasta_notas=str(notas), pasta_extratos=str(notas / "Extratos"))
    progresso = []
    monkeypatch.setattr(api, "_progresso", lambda feitos, total: progresso.append(feitos))
    api._ler_ao_abrir()
    assert not progresso  # em segundo plano não mexe na barra da tela
    assert config.caminho_cache().is_file() and config.caminho_cache_extratos().is_file()
    r = api.notas_do_mes(2026, 10)
    assert r["novas"] == [] and len(r["notas"]) == 11


def test_leitura_ao_abrir_sem_pastas_nao_quebra(tmp_path, monkeypatch):
    from omac.app import Api

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "cfg"))
    api = Api()
    api._cfg.update(pasta_notas="", pasta_extratos=str(tmp_path / "não existe"))
    api._ler_ao_abrir()
