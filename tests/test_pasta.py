from datetime import date

import pytest

from omac.notas import pasta as modulo_pasta
from omac.notas.pasta import PASTA_CANCELADAS, Cache, varrer
from tests.fabrica import criar_nota, criar_pasta_exemplo, nome_arquivo


@pytest.fixture
def pasta(tmp_path):
    return criar_pasta_exemplo(tmp_path / "NFS-e 2026")


def test_filtra_por_competencia(pasta):
    v = varrer(pasta)
    outubro = v.do_mes(2026, 10)
    # 801–811: a 811 foi emitida em novembro, mas a competência é outubro.
    assert [n.numero for n in outubro] == list(range(801, 812))
    assert [n.numero for n in v.do_mes(2026, 11)] == [812]
    assert v.do_mes(2026, 9) == []
    assert v.competencias() == [(2026, 10, 11), (2026, 11, 1)]


def test_dependente_na_varredura(pasta):
    pacientes = {n.numero: n.paciente for n in varrer(pasta).notas}
    assert pacientes[803] == "LUCAS COSTA RIBEIRO"
    assert pacientes[807] == "SOFIA GOMES PEREIRA"


def test_cancelada_vai_para_subpasta(pasta):
    v = varrer(pasta)
    assert len(v.canceladas_movidas) == 1
    assert 799 not in {n.numero for n in v.notas}
    assert (pasta / PASTA_CANCELADAS / v.canceladas_movidas[0]).is_file()
    assert not (pasta / v.canceladas_movidas[0]).exists()
    # Na próxima leitura não há nada para mover.
    assert varrer(pasta).canceladas_movidas == []


def test_cancelada_com_nome_repetido_nao_sobrescreve(pasta):
    nome = nome_arquivo(799, "NOTA CANCELADA EXEMPLO", date(2026, 9, 29))
    (pasta / PASTA_CANCELADAS).mkdir()
    (pasta / PASTA_CANCELADAS / nome).write_bytes(b"original")
    v = varrer(pasta)
    assert v.canceladas_movidas == []
    assert (pasta / nome).exists()
    assert (pasta / PASTA_CANCELADAS / nome).read_bytes() == b"original"
    assert any("já existe" in a["mensagem"] for a in v.avisos)


def test_nao_entra_em_subpastas(pasta):
    sub = pasta / "Outros"
    sub.mkdir()
    criar_nota(sub / nome_arquivo(900, "NAO DEVE APARECER", date(2026, 10, 2)),
               900, date(2026, 10, 2), date(2026, 10, 2), "10.00")
    assert 900 not in {n.numero for n in varrer(pasta).notas}


def test_pdf_ilegivel_vira_aviso(pasta):
    (pasta / "quebrado.pdf").write_bytes(b"isto nao e um pdf")
    v = varrer(pasta)
    assert len(v.do_mes(2026, 10)) == 11
    assert any(a["arquivo"] == "quebrado.pdf" for a in v.avisos)


def test_numero_repetido_vira_aviso(pasta):
    criar_nota(pasta / "NFS-e Nº 000000801 - COPIA - 01-10 - (1).pdf",
               801, date(2026, 10, 1), date(2026, 10, 1), "350.00")
    v = varrer(pasta)
    assert any("801" in a["mensagem"] and "mais de um" in a["mensagem"] for a in v.avisos)


def test_cache_evita_reler(pasta, tmp_path, monkeypatch):
    arquivo_cache = tmp_path / "cache.json"
    primeira = varrer(pasta, Cache(arquivo_cache))
    assert arquivo_cache.exists()

    def nao_deveria_ler(_):
        raise AssertionError("leu o PDF de novo mesmo com cache")

    monkeypatch.setattr(modulo_pasta, "ler_nota", nao_deveria_ler)
    segunda = varrer(pasta, Cache(arquivo_cache))
    assert [n.para_dict() for n in segunda.notas] == [n.para_dict() for n in primeira.notas]


def test_cache_rele_arquivo_alterado(pasta, tmp_path):
    arquivo_cache = tmp_path / "cache.json"
    varrer(pasta, Cache(arquivo_cache))
    alvo = pasta / nome_arquivo(805, "JULIANA ALVES", date(2026, 10, 14))
    criar_nota(alvo, 805, date(2026, 10, 14), date(2026, 10, 14), "999.00")
    import os
    os.utime(alvo, (alvo.stat().st_atime, alvo.stat().st_mtime + 10))
    v = varrer(pasta, Cache(arquivo_cache))
    assert next(n for n in v.notas if n.numero == 805).valor == 999


def test_progresso(pasta):
    chamadas = []
    varrer(pasta, progresso=lambda f, t: chamadas.append((f, t)))
    assert chamadas[-1] == (13, 13)


def test_pasta_inexistente(tmp_path):
    with pytest.raises(FileNotFoundError):
        varrer(tmp_path / "nao-existe")
