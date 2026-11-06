import hashlib
import io
import sys
from urllib.error import URLError

import pytest

from omac import __version__, config, sistema
from omac.app import Api
from omac.atualizacao import github as gh
from omac.atualizacao import instalar as inst

CONTEUDO = b"programa novo" * 1000


def _release(tag="v99.0.0", **arquivo):
    url = f"{gh.PREFIXO_DOWNLOAD}{tag}/OMAC-64bits.exe"
    return {
        "tag_name": tag,
        "body": "## What's Changed\n* Nova tela by @alguem in https://exemplo/1\n\n**Full Changelog**: https://exemplo",
        "assets": [
            {"name": "OMAC-32bits.exe", "size": 1, "digest": "sha256:aa", "browser_download_url": url + "32"},
            {"name": "OMAC-64bits.exe", "size": 10, "digest": "sha256:ABC", "browser_download_url": url, **arquivo},
        ],
    }


def _versao(conteudo=CONTEUDO, sha=None, tamanho=None):
    return gh.VersaoNova("99.0.0", f"{gh.PREFIXO_DOWNLOAD}v99/OMAC-64bits.exe", tamanho or len(conteudo),
                         sha or hashlib.sha256(conteudo).hexdigest())


class _Resposta(io.BytesIO):
    pass


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


def test_escolhe_o_arquivo_dos_bits_certos_e_guarda_o_hash():
    v = gh.interpretar(_release(), atual="1.3.0", bits=64)
    assert v.url.endswith("OMAC-64bits.exe") and v.sha256 == "abc" and v.tamanho == 10


@pytest.mark.parametrize("arquivo", [
    {"digest": None},
    {"digest": "md5:abc"},
    {"size": 0},
    {"browser_download_url": "https://exemplo.com/OMAC-64bits.exe"},
    {"browser_download_url": "http://github.com/x/releases/download/v9/OMAC-64bits.exe"},
    {"name": "outro.exe"},
])
def test_recusa_publicacao_sem_garantia(arquivo):
    assert gh.interpretar(_release(**arquivo), atual="1.3.0", bits=64) is None


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


# --- Download ----------------------------------------------------------------------


def test_baixa_e_mostra_o_progresso(tmp_path, monkeypatch):
    monkeypatch.setattr(inst, "urlopen", lambda *a, **k: _Resposta(CONTEUDO))
    destino, chamadas = tmp_path / "OMAC.exe.novo", []
    inst.baixar(_versao(), destino, lambda r, t: chamadas.append((r, t)))
    assert destino.read_bytes() == CONTEUDO
    assert chamadas[-1] == (len(CONTEUDO), len(CONTEUDO))


@pytest.mark.parametrize("versao", [_versao(sha="0" * 64), _versao(tamanho=5)])
def test_arquivo_diferente_do_publicado_e_descartado(tmp_path, monkeypatch, versao):
    monkeypatch.setattr(inst, "urlopen", lambda *a, **k: _Resposta(CONTEUDO))
    destino = tmp_path / "OMAC.exe.novo"
    with pytest.raises(gh.ErroDeAtualizacao, match="diferente"):
        inst.baixar(versao, destino)
    assert not destino.exists()


def test_download_interrompido_e_descartado(tmp_path, monkeypatch):
    class Queda(_Resposta):
        def read(self, *_):
            raise OSError("caiu")

    monkeypatch.setattr(inst, "urlopen", lambda *a, **k: Queda())
    destino = tmp_path / "OMAC.exe.novo"
    with pytest.raises(gh.ErroDeAtualizacao, match="interrompido"):
        inst.baixar(_versao(), destino)
    assert not destino.exists()


# --- Troca do programa --------------------------------------------------------------


@pytest.fixture
def programa(tmp_path):
    exe = tmp_path / "OMAC.exe"
    exe.write_bytes(b"antigo")
    inst.caminho_novo(exe).write_bytes(b"novo")
    return exe


def test_troca_guarda_o_antigo(programa):
    antigo = inst.trocar_executavel(programa, inst.caminho_novo(programa))
    assert programa.read_bytes() == b"novo" and antigo.read_bytes() == b"antigo"
    assert not inst.caminho_novo(programa).exists()


def test_falha_no_meio_devolve_o_nome_ao_programa_atual(programa, monkeypatch):
    real = inst.os.replace

    def falha_na_segunda(origem, destino):
        if str(origem).endswith(".novo"):
            raise PermissionError("bloqueado")
        real(origem, destino)

    monkeypatch.setattr(inst.os, "replace", falha_na_segunda)
    with pytest.raises(gh.ErroDeAtualizacao, match="Nada foi alterado"):
        inst.trocar_executavel(programa, inst.caminho_novo(programa))
    assert programa.read_bytes() == b"antigo"


def test_limpar_restos(programa):
    inst.trocar_executavel(programa, inst.caminho_novo(programa))
    inst.caminho_novo(programa).write_bytes(b"pela metade")
    assert inst.limpar_restos(programa)
    assert [p.name for p in programa.parent.iterdir()] == ["OMAC.exe"]


def test_limpar_restos_nao_trava_se_o_antigo_ainda_estiver_aberto(programa, monkeypatch):
    inst.caminho_antigo(programa).write_bytes(b"aberto")
    real = inst.Path.unlink

    def bloqueado(self, missing_ok=False):
        if self.name.endswith(".antigo"):
            raise PermissionError("em uso")
        real(self, missing_ok=missing_ok)

    monkeypatch.setattr(inst.Path, "unlink", bloqueado)
    assert inst.limpar_restos(programa, tentativas=2, espera=0) is False


# --- API -------------------------------------------------------------------------


@pytest.fixture
def api(tmp_path, monkeypatch, programa):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "cfg"))
    monkeypatch.setattr(sistema, "rodando_como_exe", lambda: True)
    monkeypatch.setattr(sys, "executable", str(programa))
    monkeypatch.setattr(gh, "procurar", lambda: _versao())
    monkeypatch.setattr(inst, "urlopen", lambda *a, **k: _Resposta(CONTEUDO))
    abertos = []
    monkeypatch.setattr(inst, "abrir_programa", lambda exe, *a: abertos.append(exe))
    a = Api()
    a.abertos = abertos
    return a


def test_rodando_pelo_python_nao_oferece_atualizacao(api, monkeypatch):
    monkeypatch.setattr(sistema, "rodando_como_exe", lambda: False)
    assert api.atualizacao_procurar(True) == {"indisponivel": True}


def test_oferece_a_versao_nova(api):
    assert api.atualizacao_procurar()["versao"] == "99.0.0"


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


def test_instalar_troca_abre_a_nova_e_preserva_os_dados(api, programa):
    api.agendamentos_salvar({"nome": "Maria Exemplo"})
    config.salvar({**api._cfg, "chave_pix": "abc"})
    antes = config.caminho_agendamentos().read_bytes()

    api.atualizacao_procurar()
    assert api.atualizacao_instalar() == {"reiniciando": True}

    assert programa.read_bytes() == CONTEUDO
    assert inst.caminho_antigo(programa).read_bytes() == b"antigo"
    assert api.abertos == [programa]
    assert config.caminho_agendamentos().read_bytes() == antes
    assert config.carregar()["chave_pix"] == "abc"
    backup = config.pasta_dados() / inst.PASTA_BACKUP
    assert (backup / "agendamentos.json").read_bytes() == antes
    assert not (backup / "cache-notas.json").exists()


def test_download_ruim_nao_mexe_em_nada(api, programa, monkeypatch):
    api.atualizacao_procurar()
    api._versao_nova = _versao(sha="0" * 64)
    assert "diferente" in api.atualizacao_instalar()["erro"]
    assert programa.read_bytes() == b"antigo" and api.abertos == []


def test_se_a_nova_nao_abre_o_programa_volta(api, programa, monkeypatch):
    def nao_abre(exe, *a):
        raise OSError("bloqueado pelo antivírus")

    monkeypatch.setattr(inst, "abrir_programa", nao_abre)
    api.atualizacao_procurar()
    assert "continua como estava" in api.atualizacao_instalar()["erro"]
    assert programa.read_bytes() == b"antigo"
    assert not inst.caminho_antigo(programa).exists()


def test_instalar_sem_ter_procurado(api):
    assert "erro" in api.atualizacao_instalar()


def test_pode_tentar_de_novo_depois_de_uma_falha(api, programa, monkeypatch):
    api.atualizacao_procurar()
    api._versao_nova = _versao(sha="0" * 64)
    api.atualizacao_instalar()
    api._versao_nova = _versao()
    assert api.atualizacao_instalar() == {"reiniciando": True}
