"""Ficha de atendimentos: a versão do papel impresso todo mês.

Colunas: paciente | tratamento | data | valor | forma de pagamento | dividido | pago | nota.
O paciente é um contato (`contato_id`); o nome fica só em contatos.json.

"Pago" nunca é apagado nem reescrito na virada do mês: a situação sai das datas.
Marcado é "sim"; em branco é "aguardando" enquanto o mês do atendimento não acabou;
depois disso vira "não". Se pagar depois, é só marcar.
"""

from __future__ import annotations

import uuid
from datetime import date

from .. import texto as tx
from ..dados import esquema

FORMAS = {
    "pix_pj": "Pix PJ",
    "pix_pf": "Pix PF",
    "dinheiro": "Dinheiro",
    "debito": "Débito",
    "credito": "Crédito",
}
PARCELAS_MAX = 12
TRATAMENTOS_PADRAO = ["Limpeza", "Manutenção", "Botox"]

# Nota: "" = falta (ou achada sozinha na pasta), "ok" = emitida (marcada à mão), "nao_precisa".
NOTA_OK = "ok"
NOTA_NAO_PRECISA = "nao_precisa"
NOTA_FALTA = "falta"  # marcada à mão: falta, mesmo que o automático ache uma nota
NOTAS = {"", NOTA_OK, NOTA_NAO_PRECISA, NOTA_FALTA}  # "" = automático
# Formas em que a nota costuma não ser emitida: já sugerem "não precisa" (dá para trocar).
SEM_NOTA_POR_PADRAO = {"dinheiro", "pix_pf"}

PAGO = "pago"
AGUARDANDO = "aguardando"
NAO_PAGO = "nao_pago"

class AtendimentoInvalido(ValueError):
    """Faltou a data, ou um valor, forma ou parcela não dá para entender."""


def completar(atendimento: dict) -> dict:
    return esquema.completar_item(esquema.ATENDIMENTOS, atendimento)


def _data(texto) -> str:
    if not texto:
        raise AtendimentoInvalido("Preencha a data do atendimento.")
    try:
        return date.fromisoformat(str(texto)).isoformat()
    except ValueError as e:
        raise AtendimentoInvalido("A data do atendimento não existe.") from e


def validar(dados: dict) -> dict:
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
    nota = dados.get("nota") or ""
    if nota not in NOTAS:
        raise AtendimentoInvalido("Escolha a situação da nota.")
    return {
        "tratamento": tx.nome_limpo(dados.get("tratamento")),
        "data": _data(dados.get("data")),
        "valor_centavos": valor,
        "forma": forma,
        "parcelas": parcelas,
        "nota": nota,
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


mesmo_paciente = tx.mesma_pessoa


def nota_do_atendimento(atendimento: dict, nome: str, notas: list) -> int | None:
    """Número da nota de um atendimento sozinho (o mesmo de `ligar_notas` com uma lista de um)."""
    return ligar_notas([atendimento], {atendimento["id"]: nome}, notas).get(atendimento["id"])


def ligar_notas(atendimentos: list[dict], nomes: dict[str, str], notas: list) -> dict[str, int]:
    """Qual nota é de qual atendimento: {atendimento_id: número}. Cada nota vale para um só.

    Mesmo paciente e mesmo mês da competência, e então, nesta ordem (cada etapa para todas as
    notas antes da próxima, para uma reserva não roubar o atendimento de um valor exato):
    1. o atendimento com o mesmo valor da nota (o pago antes, e o mais antigo);
    2. dois a quatro atendimentos cuja soma é o valor da nota (a nota do valor total);
    3. valor diferente (desconto...): o primeiro atendimento pago sem nota, senão o primeiro sem nota.
    Marcado à mão como "não precisa" ou "falta" não recebe nota.
    """
    from itertools import combinations

    def candidatos(nota, livres):
        mes = nota.competencia.isoformat()[:7]
        lista = [a for a in livres if a["data"][:7] == mes and a["nota"] not in (NOTA_NAO_PRECISA, NOTA_FALTA)
                 and mesmo_paciente(nomes.get(a["id"], ""), nota.paciente)]
        return sorted(lista, key=lambda a: (not a["pago_em"], a["data"], a["id"]))

    ligados: dict[str, int] = {}
    livres = list(atendimentos)
    sobra = sorted(notas, key=lambda n: n.numero)

    def ligar(nota, escolhidos):
        for a in escolhidos:
            ligados[a["id"]] = nota.numero
            livres.remove(a)
        sobra.remove(nota)

    centavos = lambda n: int(round(n.valor * 100))
    for nota in list(sobra):
        iguais = [a for a in candidatos(nota, livres) if a["valor_centavos"] == centavos(nota)]
        if iguais:
            ligar(nota, iguais[:1])
    for nota in list(sobra):
        com_valor = [a for a in candidatos(nota, livres) if a["valor_centavos"]][:8]
        achou = next((grupo for k in range(2, min(4, len(com_valor)) + 1) for grupo in combinations(com_valor, k)
                      if sum(a["valor_centavos"] for a in grupo) == centavos(nota)), None)
        if achou:
            ligar(nota, list(achou))
    for nota in list(sobra):
        resto = candidatos(nota, livres)
        if resto:
            ligar(nota, resto[:1])
    return ligados


FALTA = "falta"


def situacao_da_nota(atendimento: dict, numero_achado: int | None) -> str:
    """"ok", "nao_precisa" ou "falta". A marcação à mão vale mais; "" (automático) segue a pasta."""
    marcada = atendimento["nota"]
    if marcada == NOTA_OK:
        return NOTA_OK
    if marcada == NOTA_NAO_PRECISA:
        return NOTA_NAO_PRECISA
    if marcada == NOTA_FALTA:
        return FALTA
    return NOTA_OK if numero_achado else FALTA


# --- Lista ---------------------------------------------------------------------------


def buscar(atendimentos: list[dict], atendimento_id: str) -> dict:
    for a in atendimentos:
        if a["id"] == atendimento_id:
            return a
    raise AtendimentoInvalido("Não encontrei esse atendimento. Ele pode ter sido excluído.")


def adicionar(atendimentos: list[dict], contato_id: str, dados: dict, hoje: date) -> dict:
    novo = completar({**validar(dados), "id": uuid.uuid4().hex, "contato_id": contato_id})
    marcar_pago(novo, bool(dados.get("pago")), hoje)
    atendimentos.append(novo)
    return novo


def alterar(atendimentos: list[dict], atendimento_id: str, contato_id: str, dados: dict, hoje: date) -> dict:
    atendimento = buscar(atendimentos, atendimento_id)
    atendimento.update(validar(dados), contato_id=contato_id)
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
    return sorted((a for a in atendimentos if a["data"][:7] == prefixo), key=lambda a: a["data"])


def meses(atendimentos: list[dict]) -> list[tuple[int, int, int]]:
    """[(ano, mês, quantidade)] dos meses com atendimento, do mais antigo ao mais novo."""
    contagem: dict[tuple[int, int], int] = {}
    for a in atendimentos:
        chave = (int(a["data"][:4]), int(a["data"][5:7]))
        contagem[chave] = contagem.get(chave, 0) + 1
    return [(a, m, n) for (a, m), n in sorted(contagem.items())]


def totais(lista: list[dict]) -> dict:
    """Soma por situação. `lista` já vem com "situacao" e "nota_situacao" de cada atendimento."""
    soma = {PAGO: 0, AGUARDANDO: 0, NAO_PAGO: 0}
    for a in lista:
        soma[a["situacao"]] += a["valor_centavos"] or 0
    return {
        "recebido_centavos": soma[PAGO],
        "a_receber_centavos": soma[AGUARDANDO],
        "nao_pago_centavos": soma[NAO_PAGO],
        "nao_pagos": sum(a["situacao"] == NAO_PAGO for a in lista),
        "sem_nota": sum(a["nota_situacao"] == FALTA for a in lista),
    }
