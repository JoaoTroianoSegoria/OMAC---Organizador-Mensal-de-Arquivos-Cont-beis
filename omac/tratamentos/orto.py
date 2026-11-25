"""Cadastro dos pacientes de ortodontia, a situação de cada um, o confere e o histórico.

O confere não precisa ser apagado todo dia 1: guarda a data em que foi marcado e só
vale no mês dessa data. Assim ele recomeça mesmo se o app estiver fechado no dia 1.

"Atendido" fica guardado mês a mês ({"AAAA-MM": dia em que foi marcado}), e é isso
que monta o histórico: em cada mês o paciente veio, não veio, estava de alta, ou
ainda não era (ou não é mais) paciente.
"""

from __future__ import annotations

import uuid
from datetime import date

from .. import texto as tx
from ..dados import esquema
from ..planilha import MESES

ATIVO = "ativo"
ALTA = "alta"
FINALIZADO = "finalizado"

VEIO = "veio"
NAO_VEIO = "nao_veio"
FALTA_VIR = "falta_vir"  # mês atual, ainda sem marcar
DE_ALTA = "alta"
FORA = ""  # antes de virar paciente, depois de finalizar, ou mês que ainda não chegou


class PacienteInvalido(ValueError):
    """Um valor ou uma data não dá para entender, ou o paciente não existe mais."""


def completar(tratamento: dict) -> dict:
    return esquema.completar_item(esquema.TRATAMENTOS, tratamento)


def valor_em_centavos(texto) -> int | None:
    try:
        return tx.valor_em_centavos(texto)
    except tx.ValorInvalido as e:
        raise PacienteInvalido("Confira o valor da manutenção: use algo como 250,00.") from e


# --- Situação ------------------------------------------------------------------------


def situacao(paciente: dict) -> str:
    if paciente["finalizado_em"]:
        return FINALIZADO
    return ALTA if paciente["alta_inicio"] else ATIVO


def _data(texto, falta: str) -> date:
    if not texto:
        raise PacienteInvalido(falta)
    try:
        return date.fromisoformat(str(texto))
    except ValueError as e:
        raise PacienteInvalido(f"{falta} A data informada não existe.") from e


def _campos_de_situacao(dados: dict, atual: dict, hoje: date) -> dict:
    nova = dados.get("situacao", ATIVO)
    if nova == ALTA:
        inicio = _data(dados.get("alta_inicio"), "Preencha o dia em que a alta foi dada.")
        fim = _data(dados.get("alta_fim"), "Preencha o dia em que a alta acaba.")
        if fim < inicio:
            raise PacienteInvalido("O fim da alta não pode ser antes do dia em que ela foi dada.")
        return {"alta_inicio": inicio.isoformat(), "alta_fim": fim.isoformat(), "finalizado_em": ""}
    if nova == FINALIZADO:
        # Quem já estava finalizado mantém a data original.
        return {"alta_inicio": "", "alta_fim": "", "finalizado_em": atual.get("finalizado_em") or hoje.isoformat()}
    if nova == ATIVO:
        return {"alta_inicio": "", "alta_fim": "", "finalizado_em": ""}
    raise PacienteInvalido("Escolha a situação do paciente.")


def validar(dados: dict, atual: dict | None, hoje: date) -> dict:
    """Valor e situação já conferidos: {"valor_centavos", "alta_inicio", "alta_fim", "finalizado_em"}."""
    return {"valor_centavos": valor_em_centavos(dados.get("valor")), **_campos_de_situacao(dados, atual or {}, hoje)}


def alta_terminou(paciente: dict, hoje: date) -> bool:
    return situacao(paciente) == ALTA and paciente["alta_fim"] < hoje.isoformat()


def _guardar_alta(paciente: dict) -> None:
    """A alta que acaba vai para o histórico, senão aqueles meses viram "não veio"."""
    if paciente["alta_inicio"]:
        paciente["altas"] = [*paciente["altas"], {"inicio": paciente["alta_inicio"], "fim": paciente["alta_fim"]}]


def voltar_ao_tratamento(paciente: dict) -> None:
    _guardar_alta(paciente)
    paciente.update(alta_inicio="", alta_fim="", finalizado_em="")


# --- Lista ---------------------------------------------------------------------------


def buscar(tratamentos: list[dict], tratamento_id: str) -> dict:
    for t in tratamentos:
        if t["id"] == tratamento_id:
            return t
    raise PacienteInvalido("Não encontrei esse paciente. Ele pode ter sido excluído.")


def do_contato(tratamentos: list[dict], contato_id: str) -> dict | None:
    return next((t for t in tratamentos if t["contato_id"] == contato_id), None)


def salvar(tratamentos: list[dict], contato_id: str, dados: dict, hoje: date) -> dict:
    """Cria o tratamento do contato ou altera o que ele já tem (um por contato)."""
    atual = do_contato(tratamentos, contato_id)
    # Valida tudo antes: um erro na alta não pode deixar o valor já trocado.
    campos = validar(dados, atual, hoje)
    if atual is None:
        atual = completar({"id": uuid.uuid4().hex, "contato_id": contato_id, "criado_em": hoje.isoformat()})
        tratamentos.append(atual)
    elif atual["alta_inicio"] and campos["alta_inicio"] != atual["alta_inicio"]:
        _guardar_alta(atual)
    atual.update(campos)
    return atual


def restaurar(tratamentos: list[dict], tratamento: dict) -> None:
    """Desfaz uma exclusão: o tratamento volta como estava, com o confere e o histórico."""
    if not any(t["id"] == tratamento.get("id") or t["contato_id"] == tratamento.get("contato_id")
               for t in tratamentos):
        tratamentos.append(completar(tratamento))


def agendado_no_mes(paciente: dict, hoje: date) -> bool:
    """Marcado neste mês, ou agendado no mês anterior para este (o "agendar o próximo mês")."""
    mes = hoje.isoformat()[:7]
    return paciente["agendado_em"][:7] == mes or paciente["agendado_para"] == mes


def agendado_antes(paciente: dict, hoje: date) -> bool:
    """Este mês veio agendado do mês anterior (a tela diz "agendado em outubro")."""
    return paciente["agendado_para"] == hoje.isoformat()[:7] and paciente["agendado_em"][:7] != hoje.isoformat()[:7]


def proximo_mes(hoje: date) -> str:
    return chave_do_mes(hoje.year + (hoje.month == 12), hoje.month % 12 + 1)


def _dia_da_consulta(texto, mes: str) -> str:
    """O dia da consulta é opcional; se vier, precisa cair no mês que está sendo agendado."""
    texto = str(texto or "").strip()
    if not texto:
        return ""
    try:
        dia = date.fromisoformat(texto)
    except ValueError as e:
        raise PacienteInvalido("Confira o dia da consulta: essa data não existe.") from e
    if dia.isoformat()[:7] != mes:
        nome = MESES[int(mes[5:7]) - 1].lower()
        raise PacienteInvalido(f"O dia da consulta precisa ser em {nome}.")
    return dia.isoformat()


def proxima_consulta(paciente: dict, hoje: date) -> str:
    """O dia da consulta marcada, se ainda não passou ("" se não tem)."""
    return paciente["consulta_em"] if paciente["consulta_em"] >= hoje.isoformat() else ""


def consulta_no_mes(paciente: dict, mes: str) -> str:
    return paciente["consulta_em"] if paciente["consulta_em"][:7] == mes else ""


def marcar_agendado(paciente: dict, agendado: bool, hoje: date, dia: str = "") -> None:
    """O Agendado deste mês. Desmarcar também desfaz o que veio agendado do mês anterior."""
    mes = hoje.isoformat()[:7]
    if agendado:
        consulta = _dia_da_consulta(dia, mes)
        paciente["agendado_em"] = hoje.isoformat()
        if consulta:
            paciente["consulta_em"] = consulta
        return
    paciente["agendado_em"] = ""
    if paciente["agendado_para"] == mes:
        paciente["agendado_para"] = ""
    if consulta_no_mes(paciente, mes):
        paciente["consulta_em"] = ""


def agendar_proximo(paciente: dict, agendado: bool, hoje: date, dia: str = "") -> None:
    """Já deixa o mês seguinte agendado (com o dia da consulta, se souber)."""
    mes = proximo_mes(hoje)
    if agendado:
        consulta = _dia_da_consulta(dia, mes)
        paciente["agendado_para"] = mes
        paciente["consulta_em"] = consulta
        return
    if paciente["agendado_para"] == mes:
        paciente["agendado_para"] = ""
    if consulta_no_mes(paciente, mes):
        paciente["consulta_em"] = ""


# --- Atendido e histórico ----------------------------------------------------------------


def chave_do_mes(ano: int, mes: int) -> str:
    return f"{ano:04d}-{mes:02d}"


def meses_ate(ano: int, mes: int, quantos: int) -> list[tuple[int, int]]:
    """Os `quantos` meses que terminam em (ano, mês), do mais antigo ao mais novo."""
    total = ano * 12 + mes - 1
    return [((t // 12), t % 12 + 1) for t in range(total - quantos + 1, total + 1)]


def atendido_no_mes(paciente: dict, hoje: date) -> bool:
    return chave_do_mes(hoje.year, hoje.month) in paciente["atendidos"]


def marcar_atendido(paciente: dict, mes: str, atendido: bool, hoje: date) -> None:
    """`mes` é "AAAA-MM". Dá para marcar um mês que passou, se esqueceu na hora."""
    if mes > hoje.isoformat()[:7]:
        raise PacienteInvalido("Esse mês ainda não chegou.")
    atendidos = {**paciente["atendidos"]}
    if atendido:
        # Marcou depois do dia da consulta (no mesmo mês): o dia que ele veio é o da consulta.
        consulta = consulta_no_mes(paciente, mes)
        atendidos[mes] = consulta if consulta and consulta <= hoje.isoformat() else hoje.isoformat()
    else:
        atendidos.pop(mes, None)
    paciente["atendidos"] = atendidos


def dia_que_veio(paciente: dict, mes: str) -> str:
    """O dia guardado quando o Atendido foi marcado, se ele cai no próprio mês ("" se não veio,
    ou se o mês foi marcado depois, quando esqueceram na hora: aí não se sabe o dia)."""
    dia = paciente["atendidos"].get(mes, "")
    return dia if dia[:7] == mes else ""


def _inicio_do_historico(paciente: dict) -> str:
    """Primeiro mês do histórico: o do cadastro, ou um atendimento marcado antes dele."""
    meses = [paciente["criado_em"][:7], *paciente["atendidos"]]
    meses = [m for m in meses if m]
    return min(meses) if meses else ""


def _de_alta(paciente: dict, mes: str) -> bool:
    altas = [*paciente["altas"]]
    if paciente["alta_inicio"]:
        altas.append({"inicio": paciente["alta_inicio"], "fim": paciente["alta_fim"]})
    # Quem veio no mês da alta já aparece como "veio": isso é conferido antes.
    return any(a["inicio"][:7] <= mes <= a["fim"][:7] for a in altas)


def situacao_no_mes(paciente: dict, ano: int, mes: int, hoje: date) -> str:
    chave = chave_do_mes(ano, mes)
    if chave in paciente["atendidos"]:
        return VEIO
    atual = hoje.isoformat()[:7]
    inicio = _inicio_do_historico(paciente)
    if chave > atual or not inicio or chave < inicio:
        return FORA
    if paciente["finalizado_em"] and chave > paciente["finalizado_em"][:7]:
        return FORA
    if _de_alta(paciente, chave):
        return DE_ALTA
    return FALTA_VIR if chave == atual else NAO_VEIO


def historico_do_paciente(paciente: dict, hoje: date) -> dict:
    """Todos os meses desde o começo do histórico até hoje, do mais novo ao mais antigo."""
    inicio = _inicio_do_historico(paciente) or hoje.isoformat()[:7]
    ano, mes = int(inicio[:4]), int(inicio[5:7])
    quantos = (hoje.year * 12 + hoje.month) - (ano * 12 + mes) + 1
    meses = [{"ano": a, "mes": m, "situacao": situacao_no_mes(paciente, a, m, hoje),
              "dia": dia_que_veio(paciente, chave_do_mes(a, m))}
             for a, m in meses_ate(hoje.year, hoje.month, max(quantos, 1))]
    meses = [m for m in meses if m["situacao"] != FORA or m["mes"] == hoje.month and m["ano"] == hoje.year]
    contados = [m for m in meses if m["situacao"] in (VEIO, NAO_VEIO)]
    return {
        "meses": list(reversed(meses)),
        "veio": sum(m["situacao"] == VEIO for m in contados),
        # O mês atual só entra na conta depois de marcado: ele ainda não acabou.
        "esperados": len(contados),
    }
