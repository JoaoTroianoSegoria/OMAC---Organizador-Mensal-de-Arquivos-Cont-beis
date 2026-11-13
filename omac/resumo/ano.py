"""Resumo do ano: faturamento das notas, entradas e saídas do extrato e a ficha, mês a mês.

Tudo sai do que o OMAC já lê; nada novo é guardado. Mês sem dado fica em branco
(None), nunca zero: "não tem nota lida" é diferente de "faturou R$ 0".
"""

from __future__ import annotations

from datetime import date

from ..planilha import MESES


def _centavos(valor) -> int:
    return int(round(valor * 100))


def montar(ano: int, hoje: date, notas: list | None, extrato_por_mes: dict | None,
           ficha_por_mes: dict) -> dict:
    """`notas`: todas as notas lidas (ou None sem pasta).
    `extrato_por_mes`: {mês: (entradas, saídas)} em centavos, só dos meses que têm extrato (ou None).
    `ficha_por_mes`: {mês: {"recebido_centavos", "pendente_centavos", "qtd"}}.
    """
    # Último mês que já acabou: o atual ainda pode ganhar notas, então não entra no aviso.
    ultimo = 12 if ano < hoje.year else (hoje.month - 1 if ano == hoje.year else 0)
    meses = []
    for mes in range(1, 13):
        do_mes = [n for n in notas or [] if n.competencia.year == ano and n.competencia.month == mes]
        extrato = (extrato_por_mes or {}).get(mes)
        ficha = ficha_por_mes.get(mes)
        meses.append({
            "mes": mes,
            "nome": MESES[mes - 1],
            "notas": len(do_mes),
            "faturamento_centavos": sum(_centavos(n.valor) for n in do_mes) if do_mes else None,
            "entradas_centavos": extrato[0] if extrato else None,
            "saidas_centavos": extrato[1] if extrato else None,
            "recebido_centavos": ficha["recebido_centavos"] if ficha else None,
            "pendente_centavos": ficha["pendente_centavos"] if ficha else None,
            "passou": mes <= ultimo,
        })

    com_notas = [m for m in meses if m["faturamento_centavos"] is not None]
    total = sum(m["faturamento_centavos"] for m in com_notas)
    # Média, melhor e pior só com meses que já acabaram: o mês atual ainda está pela metade.
    fechados = [m for m in com_notas if ano < hoje.year or m["mes"] < hoje.month]
    resumo = {
        "ano": ano,
        "meses": meses,
        "faturamento_centavos": total if com_notas else None,
        "media_centavos": sum(m["faturamento_centavos"] for m in fechados) // len(fechados) if fechados else None,
        "meses_na_media": len(fechados),
        "melhor": max(fechados, key=lambda m: m["faturamento_centavos"])["mes"] if fechados else None,
        "pior": min(fechados, key=lambda m: m["faturamento_centavos"])["mes"] if len(fechados) > 1 else None,
        # Meses que já passaram e não têm nenhuma nota lida: o aviso diz quais são.
        "sem_notas": [m["mes"] for m in meses if m["passou"] and m["faturamento_centavos"] is None]
        if notas is not None else [],
        "notas_lidas": notas is not None,
        "extrato_lido": extrato_por_mes is not None,
    }
    resumo["comparacao"] = _comparacao(meses, hoje, ano)
    return resumo


def _comparacao(meses: list[dict], hoje: date, ano: int) -> dict | None:
    """O último mês fechado contra o anterior. Só quando os dois têm notas."""
    if ano != hoje.year or hoje.month < 3:
        return None
    atual, anterior = meses[hoje.month - 2], meses[hoje.month - 3]
    if atual["faturamento_centavos"] is None or not anterior["faturamento_centavos"]:
        return None
    variacao = (atual["faturamento_centavos"] - anterior["faturamento_centavos"]) / anterior["faturamento_centavos"]
    return {"mes": atual["mes"], "anterior": anterior["mes"], "variacao": round(variacao * 100, 1)}
