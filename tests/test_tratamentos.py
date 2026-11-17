import json
from datetime import date
from urllib.parse import unquote

import pytest

from omac import config, sistema
from omac.app import Api
from omac.dados import esquema
from omac.tratamentos import mensagens as msg
from omac.tratamentos import orto as pc

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


def _contato_do(api, tratamento_id):
    return next(t["contato_id"] for t in api._armazem.ler(esquema.TRATAMENTOS)["tratamentos"]
                if t["id"] == tratamento_id)


def _salvar(api, dados, tratamento_id=None):
    """A janela de contato com a chave "Em tratamento de orto" ligada."""
    contato_id = _contato_do(api, tratamento_id) if tratamento_id else None
    r = api.contatos_salvar({"orto": True, **dados}, contato_id)
    return r if "erro" in r else api.tratamentos_listar()


def _novo(api, **campos):
    dados = {"nome": "Maria Exemplo", "telefone": "(61) 90000-0000", "valor": "250,00", **campos}
    r = _salvar(api, dados)
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
    p = _salvar(api, {"nome": "Maria"})["ativos"][0]
    assert p["telefone"] == "" and p["valor_centavos"] is None


@pytest.mark.parametrize("dados, trecho", [
    ({"nome": "  "}, "nome"),
    ({"nome": "Maria", "telefone": "123"}, "telefone"),
    ({"nome": "Maria", "valor": "abc"}, "valor"),
])
def test_recusa_dados_ruins_sem_salvar(api, dados, trecho):
    assert trecho in _salvar(api, dados)["erro"]
    assert api.tratamentos_listar()["ativos"] == []


def test_recusa_nome_repetido_ignorando_acento_e_caixa(api):
    _novo(api, nome="Joana Exemplo")
    r = _salvar(api, {"nome": "JOANÁ  exemplo"})
    assert "Já existe" in r["erro"]
    assert len(api.tratamentos_listar()["ativos"]) == 1


def test_altera_paciente_mantendo_o_confere(api):
    p = _novo(api)["ativos"][0]
    api.tratamentos_marcar(p["id"], True)
    r = _salvar(api, {"nome": "Maria Nova", "telefone": "61911111111", "valor": "300"}, p["id"])
    novo = r["ativos"][0]
    assert (novo["id"], novo["nome"], novo["valor_centavos"], novo["agendado"]) == (p["id"], "Maria Nova", 30000, True)


def test_alterar_pode_manter_o_proprio_nome(api):
    p = _novo(api)["ativos"][0]
    assert "erro" not in _salvar(api, {"nome": p["nome"], "valor": "1"}, p["id"])


def _excluir(api, p):
    """Desligar a ortodontia na janela de contato tira o paciente de Tratamentos."""
    return api.contatos_salvar({"nome": p["nome"], "telefone": p["telefone"], "orto": False}, p["contato_id"])


def test_excluir_e_desfazer(api):
    p = _novo(api)["ativos"][0]
    api.tratamentos_marcar(p["id"], True)
    r = _excluir(api, p)
    assert api.tratamentos_listar()["ativos"] == []
    api.contatos_restaurar_tratamento(r["tratamento_apagado"])
    volta = api.tratamentos_listar()
    assert volta["ativos"][0]["id"] == p["id"] and volta["ativos"][0]["agendado"]


def test_excluir_tira_so_da_ortodontia_e_o_contato_fica(api):
    p = _novo(api)["ativos"][0]
    r = _excluir(api, p)
    assert [c["nome"] for c in r["contatos"]] == ["Maria Exemplo"]


def test_desfazer_duas_vezes_nao_duplica(api):
    p = _novo(api)["ativos"][0]
    apagado = _excluir(api, p)["tratamento_apagado"]
    api.contatos_restaurar_tratamento(apagado)
    api.contatos_restaurar_tratamento(apagado)
    assert len(api.tratamentos_listar()["ativos"]) == 1


# --- Finalizados -------------------------------------------------------------------


def test_finalizar_muda_de_aba_e_volta(api):
    p = _novo(api)["ativos"][0]
    r = _salvar(api, {"nome": p["nome"], "situacao": "finalizado"}, p["id"])
    assert r["ativos"] == [] and r["finalizados"][0]["finalizado_em"] == date.today().isoformat()
    r = _salvar(api, {"nome": p["nome"], "situacao": "ativo"}, p["id"])
    assert r["finalizados"] == [] and r["ativos"][0]["id"] == p["id"]


def test_alterar_finalizado_mantem_a_data_original():
    p = pc.completar({"id": "a", "contato_id": "c", "finalizado_em": "2026-01-15"})
    pc.salvar([p], "c", {"situacao": "finalizado"}, NOV)
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
    with api._armazem.editar(esquema.TRATAMENTOS) as d:
        d["tratamentos"][0]["agendado_em"] = "2020-01-31"
    assert api.tratamentos_listar()["ativos"][0]["agendado"] is False


def test_desmarcar_confere(api):
    p = _novo(api)["ativos"][0]
    assert api.tratamentos_marcar(p["id"], True)["ativos"][0]["agendado"] is True
    assert api.tratamentos_marcar(p["id"], False)["ativos"][0]["agendado"] is False


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


def _mensagens(api, tratamento_id, papel=""):
    r = api.tratamentos_preparar_mensagens(tratamento_id)
    return next(d for d in r["destinos"] if d["papel"] == papel)["mensagens"]


def test_prepara_as_tres_mensagens(api):
    p = _novo(api)["ativos"][0]
    m = _mensagens(api, p["id"])
    assert set(m) == {"agendar", "cobrar", "retorno"}
    assert "chave@exemplo.com" in m["cobrar"] and "R$ 250,00" in m["cobrar"]


def test_enviar_abre_a_conversa_e_guarda_o_telefone(api):
    p = _salvar(api, {"nome": "Maria"})["ativos"][0]
    r = api.tratamentos_enviar(p["id"], p["contato_id"], "(61) 90000-0000", "Olá & tudo bem?")
    assert r["ativos"][0]["telefone"] == TEL
    assert len(api.abertos) == 1 and TEL in api.abertos[0]
    assert unquote(api.abertos[0].split("text=")[1]) == "Olá & tudo bem?"


def test_enviar_com_telefone_ruim_nao_abre_nada(api):
    p = _novo(api)["ativos"][0]
    assert "telefone" in api.tratamentos_enviar(p["id"], p["contato_id"], "123", "oi")["erro"]
    assert api.abertos == []


def test_paciente_finalizado_tambem_recebe_mensagem(api):
    p = _novo(api)["ativos"][0]
    _salvar(api, {"nome": p["nome"], "telefone": TEL, "situacao": "finalizado"}, p["id"])
    assert "erro" not in api.tratamentos_enviar(p["id"], p["contato_id"], TEL, "retorno")


# --- Dados que sobrevivem a uma versão nova -----------------------------------------


def test_dados_sobrevivem_a_outra_abertura_do_app(api):
    p = _novo(api)["ativos"][0]
    api.tratamentos_marcar(p["id"], True)
    outra = Api()
    assert outra.tratamentos_listar()["ativos"][0]["agendado"] is True


def test_arquivo_estragado_nao_e_sobrescrito(api):
    arquivo = config.pasta_dados() / esquema.TRATAMENTOS
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text("{ quebrado", encoding="utf-8")
    assert "pacientes de ortodontia" in _salvar(api, {"nome": "Maria"})["erro"]
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


# --- Alta temporária -----------------------------------------------------------------

ALTA = {"situacao": "alta", "alta_inicio": "2026-10-01", "alta_fim": "2026-12-31"}


def test_alta_muda_de_aba_e_sai_do_confere(api):
    p = _novo(api)["ativos"][0]
    r = _salvar(api, {"nome": p["nome"], **ALTA}, p["id"])
    assert r["ativos"] == [] and r["finalizados"] == []
    assert (r["altas"][0]["alta_inicio"], r["altas"][0]["alta_fim"]) == ("2026-10-01", "2026-12-31")


def test_novo_paciente_ja_pode_entrar_de_alta(api):
    assert _salvar(api, {"nome": "Maria", **ALTA})["altas"][0]["nome"] == "Maria"


@pytest.mark.parametrize("campos, trecho", [
    ({"alta_inicio": "", "alta_fim": "2026-12-31"}, "foi dada"),
    ({"alta_inicio": "2026-10-01", "alta_fim": ""}, "acaba"),
    ({"alta_inicio": "2026-12-31", "alta_fim": "2026-10-01"}, "antes"),
    ({"alta_inicio": "2026-02-31", "alta_fim": "2026-12-31"}, "não existe"),
])
def test_alta_precisa_de_duas_datas_validas(api, campos, trecho):
    assert trecho in _salvar(api, {"nome": "Maria", "situacao": "alta", **campos})["erro"]
    assert api.tratamentos_listar()["altas"] == []


def test_erro_na_alta_nao_troca_o_nome(api):
    p = _novo(api)["ativos"][0]
    assert "erro" in _salvar(api, {"nome": "Outro Nome", "situacao": "alta", "alta_inicio": ""}, p["id"])
    assert api.tratamentos_listar()["ativos"][0]["nome"] == p["nome"]


def test_alta_que_termina_hoje_ainda_vale():
    p = pc.completar({"contato_id": "c", "alta_inicio": "2026-10-01", "alta_fim": "2026-11-06"})
    assert not pc.alta_terminou(p, NOV)
    assert pc.alta_terminou(p, date(2026, 11, 7))


def test_altas_em_ordem_de_quem_acaba_primeiro(api):
    _salvar(api, {"nome": "Ana", "situacao": "alta", "alta_inicio": "2020-01-01", "alta_fim": "2099-01-01"})
    _salvar(api, {"nome": "Bia", "situacao": "alta", "alta_inicio": "2020-01-01", "alta_fim": "2020-02-01"})
    altas = api.tratamentos_listar()["altas"]
    assert [(a["nome"], a["terminou"]) for a in altas] == [("Bia", True), ("Ana", False)]


def test_voltar_ao_tratamento_limpa_as_datas(api):
    p = _salvar(api, {"nome": "Maria", **ALTA})["altas"][0]
    r = api.tratamentos_voltar_ao_tratamento(p["id"])
    assert r["altas"] == [] and r["ativos"][0]["alta_inicio"] == ""


def test_finalizar_quem_estava_de_alta_limpa_as_datas(api):
    p = _salvar(api, {"nome": "Maria", **ALTA})["altas"][0]
    r = _salvar(api, {"nome": "Maria", "situacao": "finalizado"}, p["id"])
    assert r["altas"] == [] and r["finalizados"][0]["alta_fim"] == ""


def test_situacao_desconhecida(api):
    assert "situação" in _salvar(api, {"nome": "Maria", "situacao": "x"})["erro"]


# --- Responsáveis --------------------------------------------------------------------

MAE = {"nome": "Helena Exemplo", "telefone": "(61) 91111-1111", "papel": "mae"}
PAI = {"nome": "Carlos Exemplo", "telefone": "(61) 92222-2222", "papel": "pai"}
TEL_MAE, TEL_PAI = "5561911111111", "5561922222222"


def _crianca(api, **campos):
    dados = {"nome": "Pedro Exemplo", "responsaveis": [MAE, PAI], **campos}
    r = _salvar(api, dados)
    assert "erro" not in r, r
    return r["ativos"][0]


def _destino(p):
    return {k: p["destino"][k] for k in ("nome", "telefone", "papel")}


def test_sem_escolha_o_destino_e_o_proprio_paciente(api):
    assert _destino(_novo(api)["ativos"][0]) == {"nome": "Maria Exemplo", "telefone": TEL, "papel": ""}
    assert _destino(_crianca(api, nome="Ana Exemplo"))["nome"] == "Ana Exemplo"


@pytest.mark.parametrize("papel, nome, tel", [("mãe", "Helena Exemplo", TEL_MAE), ("pai", "Carlos Exemplo", TEL_PAI)])
def test_envio_lembra_para_quem_foi(api, papel, nome, tel):
    p = _crianca(api)
    destino = next(d for d in api.tratamentos_preparar_mensagens(p["id"])["destinos"] if d["papel"] == papel)
    r = api.tratamentos_enviar(p["id"], destino["contato_id"], tel, "oi")
    assert _destino(r["ativos"][0]) == {"nome": nome, "telefone": tel, "papel": papel}
    assert api.tratamentos_preparar_mensagens(p["id"])["escolhido"] == destino["contato_id"]


def test_responsavel_vira_contato(api):
    _crianca(api)
    contatos = {c["nome"]: c for c in api.contatos_listar()["contatos"]}
    assert set(contatos) == {"Pedro Exemplo", "Helena Exemplo", "Carlos Exemplo"}
    assert contatos["Helena Exemplo"]["telefone"] == TEL_MAE
    assert contatos["Helena Exemplo"]["dependentes"] == ["Pedro Exemplo"]
    assert [r["papel"] for r in contatos["Pedro Exemplo"]["responsaveis"]] == ["mae", "pai"]


def test_telefone_ruim_diz_de_quem_e(api):
    r = _salvar(api, {"nome": "Pedro", "responsaveis": [{"nome": "Ana", "telefone": "123", "papel": "mae"}]})
    assert "Ana" in r["erro"]
    assert api.contatos_listar()["contatos"] == []


def test_mensagem_fala_com_o_responsavel_sobre_o_paciente(api):
    p = _crianca(api, valor="250,00")
    m = _mensagens(api, p["id"], "mãe")
    for tipo in ("agendar", "cobrar", "retorno"):
        assert "Olá, Helena." in m[tipo] and "Pedro" in m[tipo]
    assert "R$ 250,00" in m["cobrar"] and "chave@exemplo.com" in m["cobrar"]


def test_mensagem_sem_responsavel_nao_cita_ninguem_mais(api):
    m = _mensagens(api, _novo(api)["ativos"][0]["id"])["agendar"]
    assert "Olá, Maria." in m and "a sua manutenção" in m


def test_enviar_abre_o_telefone_do_responsavel_e_guarda_nele(api):
    p = _salvar(api, {"nome": "Pedro", "responsaveis": [{"nome": "Helena", "papel": "mae"}]})["ativos"][0]
    mae = api.tratamentos_preparar_mensagens(p["id"])["destinos"][1]
    r = api.tratamentos_enviar(p["id"], mae["contato_id"], "(61) 91111-1111", "oi")
    assert TEL_MAE in api.abertos[0]
    assert r["ativos"][0]["destino"]["telefone"] == TEL_MAE
    assert r["ativos"][0]["telefone"] == ""


def test_nao_envia_para_quem_nao_e_responsavel(api):
    p = _crianca(api)
    outro = api.contatos_salvar({"nome": "Fulano"})["salvo"]
    assert "erro" in api.tratamentos_enviar(p["id"], outro["id"], TEL, "oi")
    assert api.abertos == []


def test_tirar_os_responsaveis_volta_para_o_paciente(api):
    p = _crianca(api, telefone="(61) 90000-0000")
    mae = api.tratamentos_preparar_mensagens(p["id"])["destinos"][1]
    api.tratamentos_enviar(p["id"], mae["contato_id"], TEL_MAE, "oi")
    r = _salvar(api, {"nome": p["nome"], "telefone": "(61) 90000-0000", "responsaveis": []}, p["id"])
    assert r["ativos"][0]["destino"]["telefone"] == TEL
    # Os responsáveis continuam como contatos.
    assert len(api.contatos_listar()["contatos"]) == 3


# --- Quem já estava cadastrado antes destes campos ------------------------------------


def test_so_abrir_a_lista_nao_regrava_o_arquivo(api):
    _novo(api)
    arquivo = config.pasta_dados() / esquema.TRATAMENTOS
    gravado = arquivo.read_text(encoding="utf-8")
    api.tratamentos_listar()
    api.tratamentos_historico(2026, 11)
    assert arquivo.read_text(encoding="utf-8") == gravado


def test_desfazer_exclusao_de_quem_esta_de_alta(api):
    p = _salvar(api, {"nome": "Maria", **ALTA})["altas"][0]
    api.contatos_restaurar_tratamento(_excluir(api, p)["tratamento_apagado"])
    assert api.tratamentos_listar()["altas"][0]["alta_fim"] == "2026-12-31"
