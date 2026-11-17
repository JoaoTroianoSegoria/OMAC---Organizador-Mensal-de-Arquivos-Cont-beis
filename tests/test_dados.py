"""Camada de dados (armazém, versões) e a migração dos arquivos da 1.5.0 para a 1.6.0."""

import json
import os
from datetime import date

import pytest

from omac import config, sistema
from omac.app import Api
from omac.dados import Armazem, DadosIlegiveis, esquema, migracoes

HOJE = date(2026, 11, 17)
TEL_A, TEL_B, TEL_MAE = "5561900000001", "5561900000002", "5561911111111"


def _gravar(pasta, nome, dados):
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / nome).write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")


def _ler(pasta, nome):
    return json.loads((pasta / nome).read_text(encoding="utf-8"))


# --- Armazém ----------------------------------------------------------------------------


def test_arquivo_novo_vem_com_o_padrao_e_a_versao(tmp_path):
    a = Armazem(tmp_path)
    assert a.ler(esquema.CONTATOS) == {"contatos": [], "a_conferir": [], "versao": 1}
    assert not (tmp_path / esquema.CONTATOS).exists()  # só ler não cria arquivo


def test_editar_grava_so_quando_muda(tmp_path):
    a = Armazem(tmp_path)
    with a.editar(esquema.COMANDOS):
        pass
    assert not (tmp_path / esquema.COMANDOS).exists()
    with a.editar(esquema.COMANDOS) as d:
        d["categorias"].append({"nome": "Geral"})
    assert _ler(tmp_path, esquema.COMANDOS) == {"categorias": [{"nome": "Geral"}], "versao": 1}


def test_ler_devolve_copia(tmp_path):
    a = Armazem(tmp_path)
    a.ler(esquema.CONTATOS)["contatos"].append("lixo")
    assert a.ler(esquema.CONTATOS)["contatos"] == []


def test_erro_no_meio_da_edicao_nao_grava(tmp_path):
    a = Armazem(tmp_path)
    with pytest.raises(ZeroDivisionError):
        with a.editar(esquema.COMANDOS) as d:
            d["categorias"].append("x")
            1 / 0
    assert not (tmp_path / esquema.COMANDOS).exists()
    assert a.ler(esquema.COMANDOS)["categorias"] == []


def test_arquivo_mudado_por_fora_e_lido_de_novo(tmp_path):
    a = Armazem(tmp_path)
    with a.editar(esquema.COMANDOS) as d:
        d["categorias"] = [{"id": "1", "nome": "um"}]
    _gravar(tmp_path, esquema.COMANDOS, {"versao": 1, "categorias": [{"id": "2", "nome": "dois"}]})
    assert a.ler(esquema.COMANDOS)["categorias"] == [{"id": "2", "nome": "dois", "comandos": []}]


def test_arquivo_estragado_nunca_e_sobrescrito(tmp_path):
    (tmp_path / esquema.CONTATOS).write_text("{ quebrado", encoding="utf-8")
    a = Armazem(tmp_path)
    with pytest.raises(DadosIlegiveis, match="Os contatos"):
        with a.editar(esquema.CONTATOS) as d:
            d["contatos"] = []
    assert (tmp_path / esquema.CONTATOS).read_text(encoding="utf-8") == "{ quebrado"


def test_bloqueio_impede_gravar(tmp_path):
    a = Armazem(tmp_path)
    a.bloqueio = "A migração falhou."
    with pytest.raises(DadosIlegiveis, match="migração"):
        with a.editar(esquema.CONTATOS):
            pass


# --- Versões e passos de migração ---------------------------------------------------------


def test_arquivo_de_versao_mais_nova_e_recusado(tmp_path):
    _gravar(tmp_path, esquema.CONTATOS, {"versao": 99, "contatos": []})
    with pytest.raises(DadosIlegiveis, match="versão mais nova"):
        Armazem(tmp_path).ler(esquema.CONTATOS)


def test_passos_rodam_em_cadeia(monkeypatch, tmp_path):
    """Simula uma versão futura: contatos.json na versão 3, com dois passos."""
    monkeypatch.setitem(esquema.ARQUIVOS, esquema.CONTATOS, {**esquema.ARQUIVOS[esquema.CONTATOS], "versao": 3})
    monkeypatch.setitem(migracoes.PASSOS, esquema.CONTATOS, {
        1: lambda d: {**d, "contatos": [{**c, "apelido": ""} for c in d["contatos"]]},
        2: lambda d: {**d, "contatos": [{**c, "apelido": c["nome"].split()[0]} for c in d["contatos"]]},
    })
    _gravar(tmp_path, esquema.CONTATOS, {"versao": 1, "contatos": [{"id": "a", "nome": "Ana Souza"}]})
    dados = Armazem(tmp_path).ler(esquema.CONTATOS)
    assert dados["versao"] == 3 and dados["contatos"][0]["apelido"] == "Ana"
    _gravar(tmp_path, esquema.CONTATOS, {"versao": 2, "contatos": [{"id": "a", "nome": "Bia Lima"}]})
    assert Armazem(tmp_path).ler(esquema.CONTATOS)["contatos"][0]["apelido"] == "Bia"


def test_todo_arquivo_tem_versao_e_passos_completos():
    for nome, info in esquema.ARQUIVOS.items():
        assert info["versao"] >= 1 and "versao" not in info["padrao"]
        assert sorted(migracoes.PASSOS[nome]) == list(range(1, info["versao"])), nome


# --- Migração da 1.5.0 ------------------------------------------------------------------------


def _pasta_1_5(tmp_path):
    """Dados como a 1.5.0 deixava: nomes em três arquivos, ligados só pelo nome."""
    pasta = tmp_path / "OMAC"
    _gravar(pasta, "whatsapp.json", {
        "inicio": "2026-11-04", "ultima_abertura": "2026-11-16",
        "contatos": {
            "FERNANDA COSTA": {"nome": "FERNANDA COSTA", "telefone": TEL_A},
            "MARIA EXEMPLO": {"nome": "MARIA EXEMPLO", "telefone": TEL_B},  # mesma pessoa da orto
            "PEDRO SOUZA LIMA": {"nome": "PEDRO SOUZA LIMA", "telefone": ""},  # parecido com Pedro Lima
        },
        "enviadas": {"801": "2026-11-05"},
        "contas": [{"nome": "Aluguel", "dia": 10, "pagas": {"2026-11": "2026-11-09"}, "criada_em": "2026-11-04"}],
    })
    _gravar(pasta, "agendamentos.json", {"pacientes": [
        {"id": "p1", "nome": "Maria Exemplo", "telefone": TEL_A, "valor_centavos": 25000, "agendado_em": "2026-11-02",
         "finalizado_em": "", "alta_inicio": "", "alta_fim": "", "responsaveis": None,
         "atendidos": {"2026-10": "2026-10-10"}, "altas": [], "criado_em": "2026-09-01"},
        {"id": "p2", "nome": "Pedro Lima", "telefone": "", "valor_centavos": None, "agendado_em": "",
         "finalizado_em": "", "alta_inicio": "2026-11-01", "alta_fim": "2026-12-01",
         "responsaveis": {"pai": {"nome": "", "telefone": ""}, "mae": {"nome": "Helena Lima", "telefone": TEL_MAE},
                          "envia_para": "mae"},
         "atendidos": {}, "altas": [], "criado_em": "2026-10-01"},
    ]})
    _gravar(pasta, "pagamentos.json", {"atendimentos": [
        {"id": "a1", "nome": "maria  exemplo", "tratamento": "Manutenção", "data": "2026-11-03",
         "valor_centavos": 25000, "forma": "pix_pj", "parcelas": 1, "pago_em": "2026-11-03", "nota_manual": True},
        {"id": "a2", "nome": "Joana Nova", "tratamento": "Limpeza", "data": "2026-11-05",
         "valor_centavos": 15000, "forma": "dinheiro", "parcelas": 1, "pago_em": "", "nota_manual": False},
    ]})
    _gravar(pasta, "config.json", {
        "pasta_notas": "C:/NFS-e 2026", "assistente_nome": "João", "lembrete_nome": "Dra. Exemplo",
        "lembrete_telefone": "5561933333333", "tema": "escuro",
        "inicio_cartoes": [{"id": "resumo", "visivel": True, "largo": True}, {"id": "contas", "visivel": False},
                           {"id": "notas_enviar", "visivel": True}, {"id": "avisos", "visivel": True},
                           {"id": "orto", "visivel": True, "largo": True}],
    })
    _gravar(pasta, "regras-extrato.json", {"regras": []})
    return pasta


def test_migracao_completa(tmp_path):
    pasta = _pasta_1_5(tmp_path)
    originais = {p.name: p.read_bytes() for p in pasta.glob("*.json")}
    assert migracoes.precisa_migrar(pasta)
    resumo = migracoes.migrar_da_1_5(pasta, HOJE)
    assert not migracoes.precisa_migrar(pasta)

    # 1. Cópia de tudo, byte a byte, e os antigos continuam no lugar.
    copia = pasta / "antes-da-1.6.0"
    assert {p.name: p.read_bytes() for p in copia.glob("*.json")} == originais
    for nome in ("whatsapp.json", "agendamentos.json", "pagamentos.json"):
        assert (pasta / nome).read_bytes() == originais[nome]

    # 2. Contatos: nome igual junta (acento, caixa, espaço); a ordem decide o nome que fica.
    contatos = _ler(pasta, esquema.CONTATOS)
    assert contatos["versao"] == 1
    por_nome = {c["nome"]: c for c in contatos["contatos"]}
    assert set(por_nome) == {"Maria Exemplo", "Pedro Lima", "Helena Lima", "Joana Nova", "FERNANDA COSTA",
                             "PEDRO SOUZA LIMA", "Dra. Exemplo"}
    assert resumo == {"contatos": 7, "tratamentos": 2, "atendimentos": 2, "a_conferir": 2}
    maria, pedro, helena = por_nome["Maria Exemplo"], por_nome["Pedro Lima"], por_nome["Helena Lima"]
    assert maria["telefone"] == TEL_A and maria["criado_em"] == "2026-09-01"
    assert pedro["responsaveis"] == [{"contato_id": helena["id"], "papel": "mae"}]
    assert pedro["envia_para"] == helena["id"] and helena["telefone"] == TEL_MAE
    # O que não dá para decidir sozinho vai para "Conferir contatos".
    tipos = {i["tipo"]: i for i in contatos["a_conferir"]}
    assert sorted(tipos["parecidos"]["ids"]) == sorted([pedro["id"], por_nome["PEDRO SOUZA LIMA"]["id"]])
    assert tipos["telefone"] == {"tipo": "telefone", "id": maria["id"], "telefones": [TEL_A, TEL_B]}

    # 3. Tratamentos e atendimentos só com o id do contato.
    trat = {t["id"]: t for t in _ler(pasta, esquema.TRATAMENTOS)["tratamentos"]}
    assert trat["p1"]["contato_id"] == maria["id"] and trat["p1"]["atendidos"] == {"2026-10": "2026-10-10"}
    assert trat["p2"]["alta_fim"] == "2026-12-01" and "nome" not in trat["p2"]
    atend = {a["id"]: a for a in _ler(pasta, esquema.ATENDIMENTOS)["atendimentos"]}
    assert atend["a1"]["contato_id"] == maria["id"] and atend["a1"]["nota"] == "ok"
    assert atend["a2"]["contato_id"] == por_nome["Joana Nova"]["id"] and atend["a2"]["nota"] == ""
    assert "nome" not in atend["a1"] and "nota_manual" not in atend["a1"]

    # 4. Lembretes, notas enviadas e configuração.
    lembretes = _ler(pasta, esquema.LEMBRETES)
    assert lembretes["destinatario"] == por_nome["Dra. Exemplo"]["id"]
    assert por_nome["Dra. Exemplo"]["telefone"] == "5561933333333"
    assert lembretes["contas"][0]["pagas"] == {"2026-11": "2026-11-09"} and lembretes["ultima_abertura"] == "2026-11-16"
    assert _ler(pasta, esquema.NOTAS_ENVIADAS) == {"versao": 1, "inicio": "2026-11-04", "enviadas": {"801": "2026-11-05"}}
    cfg = _ler(pasta, "config.json")
    assert "lembrete_telefone" not in cfg and cfg["assistente_nome"] == "João" and cfg["tema"] == "escuro"
    assert cfg["inicio_cartoes"] == [{"id": "resumo", "visivel": True, "largo": True},
                                     {"id": "lembretes", "visivel": False, "largo": False},
                                     {"id": "tratamentos", "visivel": True, "largo": True}]
    assert _ler(pasta, "regras-extrato.json") == {"regras": []}


def test_migracao_roda_uma_vez_so(tmp_path):
    pasta = _pasta_1_5(tmp_path)
    migracoes.migrar_da_1_5(pasta, HOJE)
    contatos = (pasta / esquema.CONTATOS).read_bytes()
    assert migracoes.preparar(pasta) == ""
    assert (pasta / esquema.CONTATOS).read_bytes() == contatos


def test_copia_que_ja_existe_nunca_e_trocada(tmp_path):
    pasta = _pasta_1_5(tmp_path)
    _gravar(pasta / "antes-da-1.6.0", "whatsapp.json", {"primeira": "cópia"})
    migracoes.migrar_da_1_5(pasta, HOJE)
    assert _ler(pasta / "antes-da-1.6.0", "whatsapp.json") == {"primeira": "cópia"}


def test_instalacao_nova_nao_migra_nada(tmp_path):
    assert not migracoes.precisa_migrar(tmp_path)
    assert migracoes.preparar(tmp_path) == ""
    assert list(tmp_path.iterdir()) == []


def test_so_com_a_configuracao_tambem_migra(tmp_path):
    _gravar(tmp_path, "config.json", {"lembrete_nome": "Dra.", "lembrete_telefone": "5561933333333"})
    migracoes.migrar_da_1_5(tmp_path, HOJE)
    [dra] = _ler(tmp_path, esquema.CONTATOS)["contatos"]
    assert (dra["nome"], dra["telefone"]) == ("Dra.", "5561933333333")
    assert _ler(tmp_path, esquema.LEMBRETES)["destinatario"] == dra["id"]


def test_arquivo_antigo_estragado_bloqueia_sem_apagar_nada(tmp_path):
    pasta = tmp_path / "OMAC"
    pasta.mkdir()
    (pasta / "agendamentos.json").write_text("{ quebrado", encoding="utf-8")
    erro = migracoes.preparar(pasta)
    assert "Nada foi apagado" in erro
    assert (pasta / "agendamentos.json").read_text(encoding="utf-8") == "{ quebrado"
    assert (pasta / "antes-da-1.6.0" / "agendamentos.json").exists()
    assert not (pasta / esquema.CONTATOS).exists()  # tenta de novo na próxima abertura


# --- Abrindo a 1.6.0 por cima dos dados da 1.5.0 ------------------------------------------------


@pytest.fixture
def pasta_dados(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "cfg"))
    monkeypatch.setattr(sistema, "abrir_link", lambda u: None)
    return config.pasta_dados()


def test_app_abre_com_os_dados_da_1_5(pasta_dados, tmp_path):
    origem = _pasta_1_5(tmp_path)
    pasta_dados.parent.mkdir(parents=True, exist_ok=True)
    os.rename(origem, pasta_dados)
    api = Api()
    assert api.estado()["erro_dados"] == ""
    t = api.tratamentos_listar()
    assert [p["nome"] for p in t["ativos"]] == ["Maria Exemplo"] and t["ativos"][0]["agendado"] is (date.today().isoformat()[:7] == "2026-11")
    assert t["altas"][0]["destino"]["nome"] == "Helena Lima"
    f = api.atendimentos_listar(2026, 11)
    assert [a["nome"] for a in f["atendimentos"]] == ["Maria Exemplo", "Joana Nova"]
    assert f["atendimentos"][0]["nota_situacao"] == "ok"
    assert api.lembretes_destinatario()["contato"]["nome"] == "Dra. Exemplo"
    assert len(api.contatos_listar()["a_conferir"]) == 2
    assert api._cfg["inicio_cartoes"][0]["id"] == "resumo"


def test_app_com_migracao_falha_mostra_o_erro_e_nao_grava(pasta_dados):
    _gravar(pasta_dados, "pagamentos.json", {"atendimentos": [{"nome": "Ana", "sem": "id nem data"}]})
    api = Api()
    assert "Nada foi apagado" in api.estado()["erro_dados"]
    assert "erro" in api.contatos_salvar({"nome": "Ana"})
    assert not (pasta_dados / esquema.CONTATOS).exists()


def test_item_antigo_ganha_os_campos_novos_sem_regravar(tmp_path):
    _gravar(tmp_path, esquema.TRATAMENTOS, {"versao": 1, "tratamentos": [{"id": "t", "contato_id": "c"}]})
    antes = (tmp_path / esquema.TRATAMENTOS).read_bytes()
    a = Armazem(tmp_path)
    [t] = a.ler(esquema.TRATAMENTOS)["tratamentos"]
    assert t["atendidos"] == {} and t["altas"] == [] and t["valor_centavos"] is None
    with a.editar(esquema.TRATAMENTOS) as d:
        d["tratamentos"][0]["atendidos"]["2026-11"] = "x"  # mexer num não pode mudar o padrão dos outros
    assert esquema.ITENS[esquema.TRATAMENTOS]["tratamentos"]["atendidos"] == {}
    with a.editar(esquema.TRATAMENTOS):
        pass
    assert (tmp_path / esquema.TRATAMENTOS).read_bytes() != antes  # só gravou pela mudança acima
    assert a.ler(esquema.TRATAMENTOS)["tratamentos"][0]["atendidos"] == {"2026-11": "x"}
