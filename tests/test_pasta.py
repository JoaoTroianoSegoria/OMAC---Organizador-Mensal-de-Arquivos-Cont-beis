from datetime import date

import pytest

from omac.notas import pasta as modulo_pasta
from omac.notas.pasta import Cache, varrer
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


def test_cancelada_fica_fora_do_relatorio_sem_mover_o_arquivo(pasta):
    antes = sorted(p.name for p in pasta.iterdir())
    v = varrer(pasta)
    assert [n.numero for n in v.canceladas] == [799]
    assert 799 not in {n.numero for n in v.notas}
    assert all(n.numero != 799 for n in v.do_mes(2026, 9))
    assert sorted(p.name for p in pasta.iterdir()) == antes
    assert not (pasta / "Canceladas").exists()


def test_cancelada_aparece_so_no_mes_dela(pasta):
    v = varrer(pasta)
    assert [n.numero for n in v.canceladas_do_mes(2026, 9)] == [799]
    assert v.canceladas_do_mes(2026, 10) == []


def test_cancelada_fica_no_cache_para_nao_ser_lida_de_novo(pasta, tmp_path):
    arquivo_cache = tmp_path / "cache.json"
    varrer(pasta, Cache(arquivo_cache))
    cache = Cache(arquivo_cache)
    v = varrer(pasta, cache)
    assert [n.numero for n in v.canceladas] == [799]
    assert sum(1 for item in cache.itens.values() if item["nota"]["cancelada"]) == 1


def test_ler_a_pasta_nunca_altera_os_arquivos(pasta, tmp_path):
    def foto():
        return {p.name: (p.stat().st_size, p.stat().st_mtime_ns) for p in pasta.iterdir() if p.is_file()}

    antes = foto()
    varrer(pasta, Cache(tmp_path / "cache.json"))
    assert foto() == antes


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
