"""Quais lembretes mostrar ao abrir o app, e quais contas já foram pagas.

Cada conta avisa no dia anterior ao vencimento e no próprio dia. Quem ficou com o
app fechado nesses dias recebe o aviso na próxima vez que abrir. Conta marcada como
paga naquele mês não avisa mais.

Como na ficha de pagamentos, nada é reescrito na virada do mês: conta sem marcar
fica "em aberto" até o mês acabar e depois aparece como "não paga".
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta

from ..planilha import MESES
from ..texto import normalizar

JANELA_MAXIMA = timedelta(days=31)  # depois de muito tempo fechado, não lista o ano inteiro


class ContaInvalida(ValueError):
    """Conta sem nome, ou com um dia que não existe."""


def validar_conta(conta: dict) -> dict:
    nome = " ".join(str(conta.get("nome", "")).split())
    if not nome:
        raise ContaInvalida("Diga o nome da conta.")
    try:
        dia = int(conta.get("dia"))
    except (TypeError, ValueError):
        dia = 0
    if not 1 <= dia <= 31:
        raise ContaInvalida("O dia do vencimento precisa ser de 1 a 31.")
    return {"nome": nome, "dia": dia}


PAGA = "paga"
EM_ABERTO = "em_aberto"
NAO_PAGA = "nao_paga"


def completar_conta(conta: dict, hoje: date) -> dict:
    """Conta de uma versão anterior começa a ser acompanhada no dia em que esta abriu."""
    return {"pagas": {}, "criada_em": hoje.isoformat(), **conta}


def _mes(ano: int, mes: int) -> str:
    return f"{ano:04d}-{mes:02d}"


def _historico(conta: dict | None) -> dict:
    """O que já foi pago e desde quando a conta é acompanhada."""
    return {k: conta[k] for k in ("pagas", "criada_em") if conta and conta.get(k)}


def adicionar_conta(contas: list[dict], nova: dict, antiga: dict | None = None,
                    hoje: date | None = None) -> list[dict]:
    """`nova` pode trazer o histórico (desfazer uma exclusão); alterar mantém o da `antiga`."""
    historico = _historico(nova)
    validada = validar_conta(nova)
    fora = {normalizar(validada["nome"])}
    if antiga:
        fora.add(normalizar(antiga["nome"]))
    # A conta substituída (a alterada, ou uma com o mesmo nome) passa o histórico adiante.
    guardada = next((c for c in contas if normalizar(c["nome"]) in fora), None)
    if guardada and (antiga or not historico):
        historico = _historico(guardada)
    validada = completar_conta({**validada, **historico}, hoje or date.today())
    return [*(c for c in contas if normalizar(c["nome"]) not in fora), validada]


def buscar_conta(contas: list[dict], nome: str) -> dict:
    for c in contas:
        if normalizar(c["nome"]) == normalizar(nome):
            return c
    raise ContaInvalida(f"Não encontrei a conta “{nome}”. Ela pode ter sido apagada.")


def marcar_paga(conta: dict, mes: str, paga: bool, hoje: date) -> None:
    """`mes` é "AAAA-MM", o mês do vencimento."""
    pagas = {**conta.get("pagas", {})}
    if paga:
        pagas[mes] = hoje.isoformat()
    else:
        pagas.pop(mes, None)
    conta["pagas"] = pagas


def situacao_no_mes(conta: dict, ano: int, mes: int, hoje: date) -> str:
    """"" para um mês antes de a conta começar a ser acompanhada."""
    chave = _mes(ano, mes)
    if chave in conta.get("pagas", {}):
        return PAGA
    if chave < conta.get("criada_em", "")[:7]:
        return ""
    return NAO_PAGA if chave < hoje.isoformat()[:7] else EM_ABERTO


def vencimento_no_mes(conta: dict, ano: int, mes: int) -> date:
    return _dia_no_mes(ano, mes, conta["dia"])


def remover_conta(contas: list[dict], nome: str) -> list[dict]:
    return [c for c in contas if normalizar(c["nome"]) != normalizar(nome)]


def _dia_no_mes(ano: int, mes: int, dia: int) -> date:
    """Conta do dia 31 vence no último dia em meses mais curtos."""
    return date(ano, mes, min(dia, monthrange(ano, mes)[1]))


def _meses_em_volta(hoje: date) -> list[tuple[int, int]]:
    meses = []
    for desloca in (-1, 0, 1):
        total = hoje.year * 12 + hoje.month - 1 + desloca
        meses.append((total // 12, total % 12 + 1))
    return meses


def _desde(ultima_abertura: date | None, hoje: date) -> date:
    """Último dia já avisado. Na primeira vez, só o dia de hoje conta."""
    if ultima_abertura is None:
        return hoje - timedelta(days=1)
    return max(ultima_abertura, hoje - JANELA_MAXIMA)


def _situacao(vencimento: date, hoje: date) -> str:
    if vencimento == hoje:
        return f"vence hoje ({vencimento:%d/%m})"
    if vencimento > hoje:
        return f"vence amanhã ({vencimento:%d/%m})"
    return f"venceu dia {vencimento:%d/%m}"


def contas_a_avisar(contas: list[dict], hoje: date, ultima_abertura: date | None = None) -> list[dict]:
    desde = _desde(ultima_abertura, hoje)
    itens = []
    for conta in contas:
        for ano, mes in _meses_em_volta(hoje):
            vencimento = _dia_no_mes(ano, mes, conta["dia"])
            if _mes(ano, mes) in conta.get("pagas", {}):
                continue
            if any(desde < aviso <= hoje for aviso in (vencimento - timedelta(days=1), vencimento)):
                itens.append({
                    "nome": conta["nome"],
                    "mes": _mes(ano, mes),
                    "vencimento": vencimento,
                    "situacao": _situacao(vencimento, hoje),
                })
    itens.sort(key=lambda i: i["vencimento"])
    return [{**i, "vencimento": i["vencimento"].isoformat()} for i in itens]


def aviso_de_fechamento(dia: int, hoje: date, ultima_abertura: date | None = None) -> str:
    """Texto do lembrete de gerar o fechamento do mês anterior, ou "" se não for a hora."""
    if not dia:
        return ""
    desde = _desde(ultima_abertura, hoje)
    for ano, mes in _meses_em_volta(hoje):
        data = _dia_no_mes(ano, mes, dia)
        if desde < data <= hoje:
            anterior = (data.replace(day=1) - timedelta(days=1))
            return f"Hora de gerar o fechamento de {MESES[anterior.month - 1]} de {anterior.year}."
    return ""
