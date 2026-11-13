"""Ficha de atendimentos pagos: a versão do papel impresso todo mês.

Colunas: paciente | tratamento | data | valor | forma de pagamento | dividido | pago | nota.

"Pago" nunca é apagado nem reescrito na virada do mês: a situação sai das datas.
Marcado é "sim"; em branco é "aguardando" enquanto o mês do atendimento não acabou;
depois disso vira "não". Se pagar depois, é só marcar.
"""

from __future__ import annotations

import uuid
from datetime import date

from .. import texto as tx
from ..texto import normalizar

FORMAS = {
    "pix_pj": "Pix PJ",
    "pix_pf": "Pix PF",
    "dinheiro": "Dinheiro",
    "debito": "Débito",
    "credito": "Crédito",
}
PARCELAS_MAX = 12
TRATAMENTOS_PADRAO = ["Limpeza", "Manutenção", "Botox"]

PAGO = "pago"
AGUARDANDO = "aguardando"
NAO_PAGO = "nao_pago"

# Quem foi salvo numa versão anterior ganha os campos novos ao abrir.
_CAMPOS_PADRAO = {
    "tratamento": "",
    "valor_centavos": None,
    "forma": "",
    "parcelas": 1,
    "pago_em": "",
    "nota_manual": False,  # nota emitida com outro nome: marcada à mão
}


class AtendimentoInvalido(ValueError):
    """Faltou o nome ou a data, ou um valor, forma ou parcela não dá para entender."""


def completar(atendimento: dict) -> dict:
    return {**_CAMPOS_PADRAO, **atendimento}


def _data(texto) -> str:
    if not texto:
        raise AtendimentoInvalido("Preencha a data do atendimento.")
    try:
        return date.fromisoformat(str(texto)).isoformat()
    except ValueError as e:
        raise AtendimentoInvalido("A data do atendimento não existe.") from e


def _validar(dados: dict) -> dict:
    nome = tx.nome_limpo(dados.get("nome"))
    if not nome:
        raise AtendimentoInvalido("Diga o nome do paciente.")
    try:
        valor = tx.valor_em_centavos(dados.get("valor"))
    except tx.ValorInvalido as e:
        raise AtendimentoInvalido(str(e)) from e
    forma = dados.get("forma") or ""
    if forma and forma not in FORMAS:
        raise AtendimentoInvalido("Escolha a forma de pagamento.")
    parcelas = 1
    if forma == "credito":
        try:
            parcelas = int(dados.get("parcelas") or 1)
        except (TypeError, ValueError):
            parcelas = 0
        if not 1 <= parcelas <= PARCELAS_MAX:
            raise AtendimentoInvalido(f"No crédito, divida de 1 a {PARCELAS_MAX} vezes.")
    return {
        "nome": nome,
        "tratamento": tx.nome_limpo(dados.get("tratamento")),
        "data": _data(dados.get("data")),
        "valor_centavos": valor,
        "forma": forma,
        "parcelas": parcelas,
        "nota_manual": bool(dados.get("nota_manual")),
    }


# --- Situação ------------------------------------------------------------------------


def situacao(atendimento: dict, hoje: date) -> str:
    if atendimento["pago_em"]:
        return PAGO
    return NAO_PAGO if atendimento["data"][:7] < hoje.isoformat()[:7] else AGUARDANDO


def marcar_pago(atendimento: dict, pago: bool, hoje: date) -> None:
    atendimento["pago_em"] = hoje.isoformat() if pago else ""


def forma_por_extenso(atendimento: dict) -> str:
    forma = FORMAS.get(atendimento["forma"], "")
    if atendimento["forma"] == "credito":
        parcelas = atendimento["parcelas"]
        return f"{forma} {parcelas}x" if parcelas > 1 else f"{forma} à vista"
    return forma


# --- Nota emitida ----------------------------------------------------------------------


def mesmo_paciente(nome_ficha: str, nome_nota: str) -> bool:
    """O nome da nota pode ter um sobrenome a mais ou a menos que o da ficha.

    Com uma palavra só, precisa ser igual: "Pedro" não pode achar a nota de qualquer Pedro.
    """
    ficha, nota = normalizar(nome_ficha).split(), normalizar(nome_nota).split()
    if not ficha or not nota:
        return False
    if ficha == nota:
        return True
    menor, maior = sorted((ficha, nota), key=len)
    return len(menor) >= 2 and menor[0] == maior[0] and set(menor) <= set(maior)


def nota_do_atendimento(atendimento: dict, notas: list) -> int | None:
    """Número da nota do mesmo paciente com competência no mês do atendimento."""
    mes = atendimento["data"][:7]
    for nota in notas:
        if nota.competencia.isoformat()[:7] == mes and mesmo_paciente(atendimento["nome"], nota.paciente):
            return nota.numero
    return None


# --- Lista ---------------------------------------------------------------------------


def buscar(atendimentos: list[dict], atendimento_id: str) -> dict:
    for a in atendimentos:
        if a["id"] == atendimento_id:
            return a
    raise AtendimentoInvalido("Não encontrei esse atendimento. Ele pode ter sido excluído.")


def adicionar(atendimentos: list[dict], dados: dict, hoje: date) -> dict:
    novo = completar({**_validar(dados), "id": uuid.uuid4().hex})
    marcar_pago(novo, bool(dados.get("pago")), hoje)
    atendimentos.append(novo)
    return novo


def alterar(atendimentos: list[dict], atendimento_id: str, dados: dict, hoje: date) -> dict:
    atendimento = buscar(atendimentos, atendimento_id)
    atendimento.update(_validar(dados))
    # Quem já estava pago mantém a data em que foi marcado.
    if bool(dados.get("pago")) != bool(atendimento["pago_em"]):
        marcar_pago(atendimento, bool(dados.get("pago")), hoje)
    return atendimento


def restaurar(atendimentos: list[dict], atendimento: dict) -> None:
    """Desfaz uma exclusão."""
    if not any(a["id"] == atendimento.get("id") for a in atendimentos):
        atendimentos.append(completar(atendimento))


def do_mes(atendimentos: list[dict], ano: int, mes: int) -> list[dict]:
    prefixo = f"{ano:04d}-{mes:02d}"
    return sorted((a for a in atendimentos if a["data"][:7] == prefixo),
                  key=lambda a: (a["data"], normalizar(a["nome"])))


def meses(atendimentos: list[dict]) -> list[tuple[int, int, int]]:
    """[(ano, mês, quantidade)] dos meses com atendimento, do mais antigo ao mais novo."""
    contagem: dict[tuple[int, int], int] = {}
    for a in atendimentos:
        chave = (int(a["data"][:4]), int(a["data"][5:7]))
        contagem[chave] = contagem.get(chave, 0) + 1
    return [(a, m, n) for (a, m), n in sorted(contagem.items())]


def nomes_salvos(atendimentos: list[dict], pacientes_orto: list[dict]) -> list[str]:
    """Nomes para completar o campo de paciente: os da ficha e os da ortodontia.

    Se o mesmo nome foi escrito de jeitos diferentes, fica o mais recente.
    """
    nomes: dict[str, str] = {}
    for p in pacientes_orto:
        nomes[normalizar(p["nome"])] = p["nome"]
    for a in sorted(atendimentos, key=lambda a: a["data"]):
        nomes[normalizar(a["nome"])] = a["nome"]
    return sorted(nomes.values(), key=normalizar)


def totais(lista: list[dict]) -> dict:
    """Soma por situação. `lista` já vem com "situacao" e "nota" de cada atendimento."""
    soma = {PAGO: 0, AGUARDANDO: 0, NAO_PAGO: 0}
    for a in lista:
        soma[a["situacao"]] += a["valor_centavos"] or 0
    return {
        "recebido_centavos": soma[PAGO],
        "a_receber_centavos": soma[AGUARDANDO],
        "nao_pago_centavos": soma[NAO_PAGO],
        "nao_pagos": sum(a["situacao"] == NAO_PAGO for a in lista),
        "sem_nota": sum(not a["nota"] for a in lista),
    }
