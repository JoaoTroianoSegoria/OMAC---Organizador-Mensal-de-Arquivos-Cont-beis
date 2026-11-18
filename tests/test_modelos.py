"""Modelos (1.8.0): guardar uma cópia, imprimir, abrir, baixar, apagar e o backup."""

import zipfile
from datetime import date, datetime
from pathlib import Path

import pytest

from omac import config, sistema
from omac.app import Api
from omac.backup import backup as bk
from omac.modelos import modelos as md


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "cfg"))
    monkeypatch.setenv("TMPDIR", str(tmp_path / "tmp"))
    (tmp_path / "tmp").mkdir()
    import tempfile
    monkeypatch.setattr(tempfile, "tempdir", None)
    abertos, impressos = [], []
    monkeypatch.setattr(sistema, "abrir", abertos.append)
    monkeypatch.setattr(sistema, "imprimir", lambda c: impressos.append(c) or True)
    a = Api()
    a.abertos, a.impressos = abertos, impressos
    return a


def _arquivo(tmp_path, nome="Atestado_comparecimento.pdf", conteudo=b"%PDF-1.4 exemplo"):
    caminho = tmp_path / "originais" / nome
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(conteudo)
    return caminho


def _pasta(api):
    return config.pasta_dados() / md.PASTA


# --- Regras ---------------------------------------------------------------------------------


def test_titulo_sugerido_pelo_nome_do_arquivo():
    assert md.titulo_do_arquivo("Atestado_de__comparecimento.docx") == "Atestado de comparecimento"
    assert md.titulo_do_arquivo("Termo - Clareamento.pdf") == "Termo - Clareamento"


def test_nome_para_salvar_tira_o_que_o_windows_nao_aceita():
    assert md.nome_para_salvar({"titulo": 'Receita: "simples" / 2026?', "arquivo": "abc.PDF"}) == \
        "Receita simples 2026.pdf"
    assert md.nome_para_salvar({"titulo": "...", "arquivo": "abc.docx"}) == "Modelo.docx"


@pytest.mark.parametrize("nome", ["planilha.xlsx", "programa.exe", "sem_extensao"])
def test_recusa_tipo_que_nao_e_documento(tmp_path, nome):
    with pytest.raises(md.ModeloInvalido, match="tipo de arquivo"):
        md.conferir_arquivo(_arquivo(tmp_path, nome))


def test_aceita_documentos_e_imagens(tmp_path):
    for nome in ["a.pdf", "b.DOCX", "c.doc", "d.odt", "e.rtf", "f.txt", "g.png", "h.JPG", "i.jpeg"]:
        assert md.conferir_arquivo(_arquivo(tmp_path, nome)) == Path(nome).suffix.lower()


def test_guardado_so_aceita_id_e_extensao_conhecida():
    assert md.RE_GUARDADO.match("0123456789ab.pdf")
    for ruim in ["../config.json", "0123456789ab.exe", "x.pdf", "0123456789ab.pdf/../a"]:
        assert not md.RE_GUARDADO.match(ruim)


# --- API ------------------------------------------------------------------------------------


def test_adicionar_guarda_uma_copia(api, tmp_path):
    original = _arquivo(tmp_path)
    r = api.modelos_salvar({"titulo": "  Atestado   de comparecimento ", "caminho": str(original)})
    [m] = r["modelos"]
    assert (m["titulo"], m["tipo"], m["extensao"], m["nome_original"], m["existe"]) == (
        "Atestado de comparecimento", "PDF", "pdf", "Atestado_comparecimento.pdf", True)
    guardados = list(_pasta(api).iterdir())
    assert len(guardados) == 1 and guardados[0].read_bytes() == b"%PDF-1.4 exemplo"
    # O original pode sumir: o modelo continua.
    original.unlink()
    assert api.modelos_imprimir(m["id"]) == {"impresso": True, "titulo": "Atestado de comparecimento"}
    assert api.impressos[0] == guardados[0]


def test_titulo_vazio_ou_repetido_e_sem_arquivo(api, tmp_path):
    original = _arquivo(tmp_path)
    assert "título" in api.modelos_salvar({"titulo": " ", "caminho": str(original)})["erro"]
    assert "arquivo" in api.modelos_salvar({"titulo": "Receita"})["erro"]
    api.modelos_salvar({"titulo": "Receita", "caminho": str(original)})
    assert "Já existe" in api.modelos_salvar({"titulo": "RECEITA", "caminho": str(original)})["erro"]
    assert len(list(_pasta(api).iterdir())) == 1  # o recusado não deixa arquivo para trás


def test_lista_em_ordem_de_titulo(api, tmp_path):
    for titulo in ["Termo", "atestado", "Receita"]:
        api.modelos_salvar({"titulo": titulo, "caminho": str(_arquivo(tmp_path))})
    assert [m["titulo"] for m in api.modelos_listar()["modelos"]] == ["atestado", "Receita", "Termo"]


def test_alterar_titulo_e_trocar_o_arquivo(api, tmp_path):
    m = api.modelos_salvar({"titulo": "Termo", "caminho": str(_arquivo(tmp_path))})["modelos"][0]
    r = api.modelos_salvar({"id": m["id"], "titulo": "Termo de consentimento"})
    assert r["modelos"][0]["titulo"] == "Termo de consentimento" and r["modelos"][0]["extensao"] == "pdf"
    novo = _arquivo(tmp_path, "termo-novo.docx", b"word")
    r = api.modelos_salvar({"id": m["id"], "titulo": "Termo de consentimento", "caminho": str(novo)})
    assert (r["modelos"][0]["extensao"], r["modelos"][0]["nome_original"]) == ("docx", "termo-novo.docx")
    # O arquivo antigo (outra extensão) sai; fica só o novo.
    assert [p.name for p in _pasta(api).iterdir()] == [f"{m['id']}.docx"]


def test_apagar_desfazer_e_limpar_sobras_na_proxima_vez(api, tmp_path):
    a = api.modelos_salvar({"titulo": "A", "caminho": str(_arquivo(tmp_path))})["modelos"][0]
    api.modelos_salvar({"titulo": "B", "caminho": str(_arquivo(tmp_path))})
    r = api.modelos_apagar(a["id"])
    assert [m["titulo"] for m in r["modelos"]] == ["B"] and r["posicao"] == 0
    assert len(list(_pasta(api).iterdir())) == 2  # o arquivo espera o desfazer
    volta = api.modelos_restaurar(r["apagado"], r["posicao"])
    assert [m["titulo"] for m in volta["modelos"]] == ["A", "B"]
    api.modelos_apagar(a["id"])
    # Outra sessão do app: a sobra sai na primeira lista.
    outra = Api()
    assert [m["titulo"] for m in outra.modelos_listar()["modelos"]] == ["B"]
    assert len(list(_pasta(api).iterdir())) == 1


def test_abrir_mostra_uma_copia_e_nao_o_modelo(api, tmp_path):
    m = api.modelos_salvar({"titulo": "Receita: simples", "caminho": str(_arquivo(tmp_path))})["modelos"][0]
    assert api.modelos_abrir(m["id"]) == {}
    [aberto] = api.abertos
    assert aberto.name == "Receita simples.pdf" and _pasta(api) not in aberto.parents
    aberto.write_bytes(b"preenchido")
    assert next(_pasta(api).iterdir()).read_bytes() == b"%PDF-1.4 exemplo"


def test_baixar_salva_onde_a_pessoa_escolher(api, tmp_path, monkeypatch):
    m = api.modelos_salvar({"titulo": "Termo", "caminho": str(_arquivo(tmp_path))})["modelos"][0]
    destino = tmp_path / "Downloads" / "Termo.pdf"
    destino.parent.mkdir()
    pedidos = []
    monkeypatch.setattr(api, "_dialogo_salvar", lambda *a: pedidos.append(a) or destino)
    assert api.modelos_baixar(m["id"]) == {"caminho": str(destino)}
    assert pedidos[0][:2] == ("Termo.pdf", "pdf") and destino.read_bytes() == b"%PDF-1.4 exemplo"
    monkeypatch.setattr(api, "_dialogo_salvar", lambda *a: None)
    assert api.modelos_baixar(m["id"]) == {"cancelado": True}


def test_arquivo_que_sumiu_avisa(api, tmp_path):
    m = api.modelos_salvar({"titulo": "Termo", "caminho": str(_arquivo(tmp_path))})["modelos"][0]
    next(_pasta(api).iterdir()).unlink()
    assert api.modelos_listar()["modelos"][0]["existe"] is False
    assert "sumiu" in api.modelos_imprimir(m["id"])["erro"]
    assert api.impressos == []


def test_widget_lista_os_modelos(api, tmp_path):
    assert api._widget_modelos(date(2026, 11, 18)) == {"modelos": []}
    api.modelos_salvar({"titulo": "Receita", "caminho": str(_arquivo(tmp_path))})
    [w] = api._widget_modelos(date(2026, 11, 18))["modelos"]
    assert (w["titulo"], w["tipo"]) == ("Receita", "PDF")


# --- Backup ---------------------------------------------------------------------------------


def test_backup_leva_os_arquivos_e_restaurar_devolve(api, tmp_path):
    pasta_dados = config.pasta_dados()
    a = api.modelos_salvar({"titulo": "A", "caminho": str(_arquivo(tmp_path))})["modelos"][0]
    (tmp_path / "pendrive").mkdir()
    zip_ = bk.fazer(pasta_dados, str(tmp_path / "pendrive"), datetime(2026, 11, 18, 9))
    with zipfile.ZipFile(zip_) as z:
        assert f"modelos/{a['id']}.pdf" in z.namelist() and "modelos.json" in z.namelist()
    assert bk.ler_manifesto(zip_)["arquivos"][-1] == f"modelos/{a['id']}.pdf"

    # Depois do backup: apaga o A e cria o B. Restaurar volta ao A e guarda o B.
    api.modelos_apagar(a["id"])
    b = api.modelos_salvar({"titulo": "B", "caminho": str(_arquivo(tmp_path, "b.docx", b"b"))})["modelos"][0]
    (_pasta(api) / f"{a['id']}.pdf").unlink()
    r = bk.restaurar(zip_, pasta_dados, datetime(2026, 11, 18, 10))
    assert sorted(p.name for p in _pasta(api).iterdir()) == [f"{a['id']}.pdf"]
    assert (Path(r["guardados_em"]) / "modelos" / f"{b['id']}.docx").read_bytes() == b"b"
    api._armazem.esquecer()
    assert [m["titulo"] for m in api.modelos_listar()["modelos"]] == ["A"]


def test_restaurar_ignora_caminho_estranho_no_zip(api, tmp_path):
    pasta_dados = config.pasta_dados()
    (tmp_path / "pendrive").mkdir()
    zip_ = bk.fazer(pasta_dados, str(tmp_path / "pendrive"), datetime(2026, 11, 18, 9))
    with zipfile.ZipFile(zip_, "a") as z:
        z.writestr("modelos/../../fora.pdf", b"x")
        z.writestr("modelos/0123456789ab.exe", b"x")
    manifesto = bk.ler_manifesto(zip_)
    assert not any(n.startswith("modelos/") for n in manifesto["arquivos"])
