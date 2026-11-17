"""Backup: quando fazer, o zip, o espelho das notas e a restauração."""

import json
import os
import zipfile
from datetime import date, datetime

import pytest

from omac import __version__, config, sistema
from omac.app import Api
from omac.backup import backup as bk
from omac.dados import esquema


def _cfg(**campos):
    return config.normalizar({"backup_pasta": "X", "backup_automatico": True, **campos})


# --- Quando fazer --------------------------------------------------------------------------


@pytest.mark.parametrize("campos, hoje, esperado", [
    ({"backup_frequencia": "dia"}, date(2026, 11, 17), date(2026, 11, 17)),
    # 17/11/2026 é terça; toda segunda (0) → 16/11; todo domingo (6) → 15/11; toda terça (1) → hoje.
    ({"backup_frequencia": "semana", "backup_dia_semana": 0}, date(2026, 11, 17), date(2026, 11, 16)),
    ({"backup_frequencia": "semana", "backup_dia_semana": 6}, date(2026, 11, 17), date(2026, 11, 15)),
    ({"backup_frequencia": "semana", "backup_dia_semana": 1}, date(2026, 11, 17), date(2026, 11, 17)),
    ({"backup_frequencia": "mes", "backup_dia_mes": 1}, date(2026, 11, 17), date(2026, 11, 1)),
    ({"backup_frequencia": "mes", "backup_dia_mes": 20}, date(2026, 11, 17), date(2026, 10, 20)),
    ({"backup_frequencia": "mes", "backup_dia_mes": 20}, date(2026, 1, 5), date(2025, 12, 20)),
])
def test_ultima_data_marcada(campos, hoje, esperado):
    assert bk.ultima_data_marcada(_cfg(**campos), hoje) == esperado


def test_esta_na_hora():
    agora = datetime(2026, 11, 17, 9, 0)
    semanal = _cfg(backup_frequencia="semana", backup_dia_semana=0)
    assert bk.esta_na_hora(semanal, agora)  # nunca fez
    assert not bk.esta_na_hora({**semanal, "backup_ultimo": "2026-11-16T18:00:00"}, agora)
    # Na segunda o computador ficou desligado: faz na próxima abertura.
    assert bk.esta_na_hora({**semanal, "backup_ultimo": "2026-11-09T18:00:00"}, agora)
    assert not bk.esta_na_hora({**semanal, "backup_automatico": False}, agora)
    assert not bk.esta_na_hora({**semanal, "backup_pasta": ""}, agora)
    diario = _cfg(backup_frequencia="dia", backup_ultimo="2026-11-17T08:00:00")
    assert not bk.esta_na_hora(diario, agora)  # uma vez por dia, mesmo abrindo de hora em hora
    assert bk.esta_na_hora(diario, datetime(2026, 11, 18, 0, 5))


def test_configuracoes_do_backup_sao_validadas():
    c = config.normalizar({"backup_frequencia": "ano", "backup_dia_semana": 9, "backup_dia_mes": 31,
                           "backup_automatico": 1})
    assert (c["backup_frequencia"], c["backup_dia_semana"], c["backup_dia_mes"], c["backup_automatico"]) == \
        ("semana", 6, 28, True)
    assert config.normalizar({})["backup_dia_mes"] == 1


# --- Fazer -------------------------------------------------------------------------------------


@pytest.fixture
def dados(tmp_path):
    pasta = tmp_path / "OMAC"
    pasta.mkdir()
    for nome in (esquema.CONFIG, esquema.CONTATOS, esquema.ATENDIMENTOS, esquema.REGRAS, esquema.CACHE_NOTAS):
        (pasta / nome).write_text(json.dumps({"versao": 1, "de": nome}), encoding="utf-8")
    return pasta


def test_zip_com_os_dados_e_o_manifesto(dados, tmp_path):
    destino = tmp_path / "pendrive"
    destino.mkdir()
    feito = bk.fazer(dados, str(destino), datetime(2026, 11, 17, 10, 30))
    assert feito.name == "OMAC-backup-2026-11-17.zip"
    with zipfile.ZipFile(feito) as z:
        nomes = set(z.namelist())
        manifesto = json.loads(z.read("manifesto.json"))
    assert nomes == {"config.json", "contatos.json", "atendimentos.json", "regras-extrato.json", "manifesto.json"}
    assert "cache-notas.json" not in nomes  # é refeito lendo os PDFs
    assert manifesto["versao"] == __version__ and manifesto["data"] == "2026-11-17T10:30:00"
    assert list(destino.iterdir()) == [feito]  # sem .tmp sobrando


def test_guarda_os_12_mais_novos(dados, tmp_path):
    destino = tmp_path / "pendrive"
    destino.mkdir()
    (destino / "outro arquivo.zip").write_text("da pessoa")
    for dia in range(1, 16):
        bk.fazer(dados, str(destino), datetime(2026, 10, dia))
    zips = bk.backups(destino)
    assert len(zips) == 12 and zips[0].name == "OMAC-backup-2026-10-15.zip"
    assert zips[-1].name == "OMAC-backup-2026-10-04.zip"
    assert (destino / "outro arquivo.zip").exists()  # o que não é backup do OMAC nunca é apagado


def test_pasta_que_sumiu_vira_erro_claro(dados, tmp_path):
    with pytest.raises(bk.BackupInvalido, match="pendrive"):
        bk.fazer(dados, str(tmp_path / "pendrive fora"), datetime(2026, 11, 17))
    with pytest.raises(bk.BackupInvalido, match="Escolha"):
        bk.fazer(dados, "", datetime(2026, 11, 17))


def test_espelho_copia_so_o_novo_e_nunca_apaga(tmp_path):
    notas = tmp_path / "NFS-e 2026"
    (notas / "Canceladas").mkdir(parents=True)
    (notas / "a.pdf").write_bytes(b"a")
    (notas / "Canceladas" / "b.pdf").write_bytes(b"b")
    espelho = tmp_path / "pendrive" / "Notas"
    assert bk.espelhar(str(notas), espelho) == 2
    assert (espelho / "Canceladas" / "b.pdf").read_bytes() == b"b"
    assert bk.espelhar(str(notas), espelho) == 0  # nada mudou
    (notas / "a.pdf").write_bytes(b"a mudou")
    os.utime(notas / "a.pdf", (1, 1))
    (notas / "Canceladas" / "b.pdf").unlink()
    assert bk.espelhar(str(notas), espelho) == 1
    assert (espelho / "a.pdf").read_bytes() == b"a mudou" and (espelho / "Canceladas" / "b.pdf").exists()
    assert bk.espelhar("", espelho) == 0


# --- Restaurar ------------------------------------------------------------------------------------


def _zip(caminho, arquivos, versao=__version__, extra=None):
    with zipfile.ZipFile(caminho, "w") as z:
        for nome, conteudo in arquivos.items():
            z.writestr(nome, json.dumps(conteudo))
        for nome, conteudo in (extra or {}).items():
            z.writestr(nome, conteudo)
        z.writestr("manifesto.json", json.dumps({"app": "OMAC", "versao": versao, "data": "2026-11-01T10:00:00",
                                                 "arquivos": [*arquivos, *(extra or {})]}))
    return caminho


def test_restaurar_guarda_os_atuais_e_troca(dados, tmp_path):
    backup = _zip(tmp_path / "b.zip", {"contatos.json": {"versao": 1, "de": "backup"}})
    (dados / esquema.COMANDOS).write_text("{}", encoding="utf-8")  # existe agora, não existia no backup
    r = bk.restaurar(backup, dados, datetime(2026, 11, 17, 15, 0, 0))
    assert json.loads((dados / "contatos.json").read_text())["de"] == "backup"
    guardados = dados / "antes-de-restaurar" / "2026-11-17_15-00-00"
    assert r["guardados_em"] == str(guardados)
    assert json.loads((guardados / "contatos.json").read_text())["de"] == "contatos.json"
    assert (guardados / esquema.COMANDOS).exists() and not (dados / esquema.COMANDOS).exists()
    assert json.loads((dados / "config.json").read_text())["de"] == "config.json"  # fora do backup: fica


def test_restaurar_recusa_versao_mais_nova(dados, tmp_path):
    backup = _zip(tmp_path / "b.zip", {"contatos.json": {}}, versao="9.0.0")
    with pytest.raises(bk.BackupInvalido, match="mais nova"):
        bk.restaurar(backup, dados, datetime(2026, 11, 17))
    assert json.loads((dados / "contatos.json").read_text())["de"] == "contatos.json"


def test_zip_que_nao_e_backup(tmp_path):
    (tmp_path / "x.zip").write_bytes(b"nada")
    with pytest.raises(bk.BackupInvalido):
        bk.ler_manifesto(tmp_path / "x.zip")
    with zipfile.ZipFile(tmp_path / "y.zip", "w") as z:
        z.writestr("foto.jpg", "x")
    with pytest.raises(bk.BackupInvalido):
        bk.ler_manifesto(tmp_path / "y.zip")


def test_zip_nunca_escreve_fora_da_pasta_dos_dados(dados, tmp_path):
    backup = _zip(tmp_path / "b.zip", {"contatos.json": {"versao": 1}},
                  extra={"../fora.json": "{}", "programa.exe": "x", "sub/config.json": "{}"})
    assert bk.ler_manifesto(backup)["arquivos"] == ["contatos.json"]
    bk.restaurar(backup, dados, datetime(2026, 11, 17))
    assert not (tmp_path / "fora.json").exists() and not (dados / "programa.exe").exists()


# --- Pela API -------------------------------------------------------------------------------------


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "cfg"))
    monkeypatch.setattr(sistema, "abrir_link", lambda u: None)
    a = Api()
    a.pendrive = tmp_path / "pendrive"
    a.pendrive.mkdir()
    return a


def test_api_backup_agora_e_restaurar(api, tmp_path):
    api.contatos_salvar({"nome": "Ana"})
    api._cfg = config.salvar({**api._cfg, "backup_pasta": str(api.pendrive)})
    r = api.backup_agora()
    assert r["dias"] == 0 and r["erro"] == "" and r["config"]["backup_ultimo"]
    [zip_feito] = bk.backups(api.pendrive)

    api.contatos_salvar({"nome": "Bia"})
    api._cfg = config.salvar({**api._cfg, "backup_frequencia": "dia"})
    r = api.backup_restaurar(str(zip_feito))
    assert r["versao"] == __version__
    assert [c["nome"] for c in api.contatos_listar()["contatos"]] == ["Ana"]
    # As escolhas de backup deste computador não voltam com os dados.
    assert api._cfg["backup_frequencia"] == "dia" and api._cfg["backup_pasta"] == str(api.pendrive)


def test_api_automatico_falha_sem_travar_e_avisa(api, tmp_path):
    api._cfg = config.salvar({**api._cfg, "backup_pasta": str(tmp_path / "pendrive fora"),
                              "backup_automatico": True})
    r = api.backup_verificar()
    assert r["falhou"] and "pendrive" in r["erro"]
    assert api.inicio_painel()["widgets"]["hoje"]["backup"]["erro"]
    api._cfg = config.salvar({**api._cfg, "backup_pasta": str(api.pendrive)})
    r = api.backup_verificar()
    assert r["feito"] and r["erro"] == "" and len(bk.backups(api.pendrive)) == 1
    assert api.backup_verificar()["feito"] is False  # já fez hoje


def test_api_espelho_das_notas(api, tmp_path):
    notas = tmp_path / "NFS-e 2026"
    notas.mkdir()
    (notas / "n.pdf").write_bytes(b"pdf")
    api._cfg = config.salvar({**api._cfg, "backup_pasta": str(api.pendrive), "backup_arquivos": True,
                              "pasta_notas": str(notas)})
    assert api.backup_agora()["copiados"] == 1
    assert (api.pendrive / "Notas" / "n.pdf").exists() and not (api.pendrive / "Extratos").exists()
