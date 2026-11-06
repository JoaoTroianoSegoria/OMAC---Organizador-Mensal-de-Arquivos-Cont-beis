import json
from datetime import date
from urllib.parse import unquote

import pytest

from omac import config, sistema
from omac.agendamentos import mensagens as msg
from omac.agendamentos import pacientes as pc
from omac.app import Api

TEL = "5561900000000"
NOV = date(2026, 11, 6)


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "cfg"))
    abertos = []
    monkeypatch.setattr(sistema, "abrir_link", abertos.append)
    a = Api()
    a.abertos = abertos
    a._cfg.update(assistente_nome="Exemplo", chave_pix="chave@exemplo.com")
    return a


def _novo(api, **campos):
    dados = {"nome": "Maria Exemplo", "telefone": "(61) 90000-0000", "valor": "250,00", **campos}
    r = api.agendamentos_salvar(dados)
    assert "erro" not in r, r
    return r


# --- Valor ------------------------------------------------------------------------


@pytest.mark.parametrize("digitado, centavos", [
    ("250", 25000), ("250,5", 25050), ("250,00", 25000), ("R$ 250,00", 25000), ("1.250,00", 125000),
    ("1250,99", 125099), ("250.50", 25050), ("1.250", 125000), ("0,29", 29), ("", None), (None, None),
])
def test_valor_em_centavos(digitado, centavos):
    assert pc.valor_em_centavos(digitado) == centavos


@pytest.mark.parametrize("ruim", ["abc", "-50", "12,345", "1,250.00"])
def test_recusa_valor_estranho(ruim):
    with pytest.raises(pc.PacienteInvalido):
        pc.valor_em_centavos(ruim)


# --- Cadastro ---------------------------------------------------------------------


def test_adiciona_paciente(api):
    p = _novo(api)["ativos"][0]
    assert (p["nome"], p["telefone"], p["valor_centavos"], p["agendado"]) == ("Maria Exemplo", TEL, 25000, False)


def test_telefone_e_valor_podem_ficar_para_depois(api):
    p = api.agendamentos_salvar({"nome": "Maria"})["ativos"][0]
    assert p["telefone"] == "" and p["valor_centavos"] is None


@pytest.mark.parametrize("dados, trecho", [
    ({"nome": "  "}, "nome"),
    ({"nome": "Maria", "telefone": "123"}, "telefone"),
    ({"nome": "Maria", "valor": "abc"}, "valor"),
])
def test_recusa_dados_ruins_sem_salvar(api, dados, trecho):
    assert trecho in api.agendamentos_salvar(dados)["erro"]
    assert api.agendamentos_listar()["ativos"] == []


def test_recusa_nome_repetido_ignorando_acento_e_caixa(api):
    _novo(api, nome="Joana Exemplo")
    r = api.agendamentos_salvar({"nome": "JOANÁ  exemplo"})
    assert "Já existe" in r["erro"]
    assert len(api.agendamentos_listar()["ativos"]) == 1


def test_altera_paciente_mantendo_o_confere(api):
    p = _novo(api)["ativos"][0]
    api.agendamentos_marcar(p["id"], True)
    r = api.agendamentos_salvar({"nome": "Maria Nova", "telefone": "61911111111", "valor": "300"}, p["id"])
    novo = r["ativos"][0]
    assert (novo["id"], novo["nome"], novo["valor_centavos"], novo["agendado"]) == (p["id"], "Maria Nova", 30000, True)


def test_alterar_pode_manter_o_proprio_nome(api):
    p = _novo(api)["ativos"][0]
    assert "erro" not in api.agendamentos_salvar({"nome": p["nome"], "valor": "1"}, p["id"])


def test_excluir_e_desfazer(api):
    p = _novo(api)["ativos"][0]
    api.agendamentos_marcar(p["id"], True)
    r = api.agendamentos_apagar(p["id"])
    assert r["ativos"] == []
    volta = api.agendamentos_restaurar(r["apagado"])
    assert volta["ativos"][0]["id"] == p["id"] and volta["ativos"][0]["agendado"]


def test_desfazer_duas_vezes_nao_duplica(api):
    p = _novo(api)["ativos"][0]
    apagado = api.agendamentos_apagar(p["id"])["apagado"]
    api.agendamentos_restaurar(apagado)
    assert len(api.agendamentos_restaurar(apagado)["ativos"]) == 1


# --- Finalizados -------------------------------------------------------------------


def test_finalizar_muda_de_aba_e_volta(api):
    p = _novo(api)["ativos"][0]
    r = api.agendamentos_salvar({"nome": p["nome"], "finalizado": True}, p["id"])
    assert r["ativos"] == [] and r["finalizados"][0]["finalizado_em"] == date.today().isoformat()
    r = api.agendamentos_salvar({"nome": p["nome"], "finalizado": False}, p["id"])
    assert r["finalizados"] == [] and r["ativos"][0]["id"] == p["id"]


def test_alterar_finalizado_mantem_a_data_original():
    p = {"id": "a", "nome": "Maria", "telefone": "", "valor_centavos": None,
         "agendado_em": "", "finalizado_em": "2026-01-15"}
    pc.alterar([p], "a", {"nome": "Maria Nova", "finalizado": True}, NOV)
    assert p["finalizado_em"] == "2026-01-15"


# --- Confere do mês ----------------------------------------------------------------


def test_confere_vale_so_no_mes_marcado():
    p = {"agendado_em": ""}
    pc.marcar_agendado(p, True, date(2026, 11, 30))
    assert pc.agendado_no_mes(p, date(2026, 11, 1))
    assert not pc.agendado_no_mes(p, date(2026, 12, 1))
    assert not pc.agendado_no_mes(p, date(2027, 11, 15))


def test_confere_de_outro_mes_aparece_desmarcado(api):
    _novo(api)
    with api._agenda() as d:
        d["pacientes"][0]["agendado_em"] = "2020-01-31"
    assert api.agendamentos_listar()["ativos"][0]["agendado"] is False


def test_desmarcar_confere(api):
    p = _novo(api)["ativos"][0]
    assert api.agendamentos_marcar(p["id"], True)["ativos"][0]["agendado"] is True
    assert api.agendamentos_marcar(p["id"], False)["ativos"][0]["agendado"] is False


# --- Mensagens ---------------------------------------------------------------------


def test_reais():
    assert msg.reais(125050) == "R$ 1.250,50"
    assert msg.reais(5) == "R$ 0,05"


def test_mensagem_de_agendar():
    t = msg.agendar("Exemplo", "MARIA EXEMPLO", NOV)
    assert t.startswith("*Assistente Exemplo:* Olá, Maria.\n") and "novembro" in t


def test_cobranca_tem_valor_e_chave():
    t = msg.cobrar("", "Maria", NOV, 25000, " chave@exemplo.com ")
    assert "R$ 250,00" in t and "\nchave@exemplo.com\n" in t and "novembro" in t


def test_cobranca_sem_valor_nao_inventa_numero():
    assert "R$" not in msg.cobrar("", "Maria", NOV, None, "chave")


def test_cobranca_sem_chave_fica_vazia():
    assert msg.cobrar("", "Maria", NOV, 25000, "  ") == ""


def test_retorno():
    assert "retorno" in msg.retorno("", "Maria")


def test_prepara_as_tres_mensagens(api):
    p = _novo(api)["ativos"][0]
    m = api.agendamentos_preparar_mensagens(p["id"])["mensagens"]
    assert set(m) == {"agendar", "cobrar", "retorno"}
    assert "chave@exemplo.com" in m["cobrar"] and "R$ 250,00" in m["cobrar"]


def test_enviar_abre_a_conversa_e_guarda_o_telefone(api):
    p = api.agendamentos_salvar({"nome": "Maria"})["ativos"][0]
    r = api.agendamentos_enviar(p["id"], "(61) 90000-0000", "Olá & tudo bem?")
    assert r["ativos"][0]["telefone"] == TEL
    assert len(api.abertos) == 1 and TEL in api.abertos[0]
    assert unquote(api.abertos[0].split("text=")[1]) == "Olá & tudo bem?"


def test_enviar_com_telefone_ruim_nao_abre_nada(api):
    p = _novo(api)["ativos"][0]
    assert "telefone" in api.agendamentos_enviar(p["id"], "123", "oi")["erro"]
    assert api.abertos == []


def test_paciente_finalizado_tambem_recebe_mensagem(api):
    p = _novo(api)["ativos"][0]
    api.agendamentos_salvar({"nome": p["nome"], "telefone": TEL, "finalizado": True}, p["id"])
    assert "erro" not in api.agendamentos_enviar(p["id"], TEL, "retorno")


# --- Dados que sobrevivem a uma versão nova -----------------------------------------


def test_dados_sobrevivem_a_outra_abertura_do_app(api):
    p = _novo(api)["ativos"][0]
    api.agendamentos_marcar(p["id"], True)
    outra = Api()
    assert outra.agendamentos_listar()["ativos"][0]["agendado"] is True


def test_arquivo_estragado_nao_e_sobrescrito(api):
    arquivo = config.caminho_agendamentos()
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text("{ quebrado", encoding="utf-8")
    assert "Os pacientes" in api.agendamentos_salvar({"nome": "Maria"})["erro"]
    assert arquivo.read_text(encoding="utf-8") == "{ quebrado"


def test_nao_deixa_arquivo_temporario(api):
    _novo(api)
    assert [a.name for a in config.pasta_dados().glob("*.tmp")] == []


def test_configuracao_de_versao_antiga_e_mantida(api):
    """Quem tem o config.json da 1.2.0 mantém tudo e ganha os campos novos vazios."""
    arquivo = config.pasta_dados() / "config.json"
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(json.dumps({"pasta_notas": "C:/NFS-e 2026", "assistente_nome": "Exemplo",
                                   "lembrete_fechamento_dia": 5, "tema": "escuro"}), encoding="utf-8")
    cfg = config.carregar()
    assert (cfg["pasta_notas"], cfg["assistente_nome"], cfg["lembrete_fechamento_dia"], cfg["tema"]) == \
        ("C:/NFS-e 2026", "Exemplo", 5, "escuro")
    assert cfg["chave_pix"] == "" and cfg["avisos_recolhidos"] == []
    salva = config.salvar({**cfg, "chave_pix": "abc", "avisos_recolhidos": ["notas"]})
    assert config.carregar()["chave_pix"] == "abc" and salva["avisos_recolhidos"] == ["notas"]


@pytest.mark.parametrize("ruim", ["notas", None, 3])
def test_avisos_recolhidos_estragados_viram_lista_vazia(ruim):
    assert config.normalizar({"avisos_recolhidos": ruim})["avisos_recolhidos"] == []
