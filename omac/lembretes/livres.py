"""Lembretes livres: um título e uma observação, sem data.

Ficam "em aberto" até serem marcados como feitos. O feito vai para uma lista à parte
(riscado) e pode voltar. Os em aberto aparecem no widget de Lembretes do Início.
"""

from __future__ import annotations

import uuid
from datetime import date

from ..dados import esquema
from ..texto import nome_limpo


class LembreteInvalido(ValueError):
    """Faltou o título, ou o lembrete não existe mais."""


def completar(lembrete: dict) -> dict:
    return esquema.completar_item(esquema.LEMBRETES, lembrete, "livres")


def _validar(dados: dict) -> dict:
    titulo = nome_limpo(dados.get("titulo"))
    if not titulo:
        raise LembreteInvalido("Diga o que é para lembrar.")
    # A observação pode ter mais de uma linha: só tira o espaço das pontas.
    return {"titulo": titulo, "observacao": str(dados.get("observacao") or "").strip()}


def buscar(livres: list[dict], lembrete_id: str) -> dict:
    for item in livres:
        if item["id"] == lembrete_id:
            return item
    raise LembreteInvalido("Não encontrei esse lembrete. Ele pode ter sido apagado.")


def salvar(livres: list[dict], dados: dict, lembrete_id: str | None, hoje: date) -> dict:
    novos = _validar(dados)
    if lembrete_id:
        item = buscar(livres, lembrete_id)
        item.update(novos)
        return item
    item = completar({"id": uuid.uuid4().hex, **novos, "criado_em": hoje.isoformat()})
    livres.append(item)
    return item


def marcar_feito(item: dict, feito: bool, hoje: date) -> None:
    item["feito_em"] = hoje.isoformat() if feito else ""


def restaurar(livres: list[dict], item: dict, posicao: int | None = None) -> None:
    """Desfaz uma exclusão, de volta ao mesmo lugar da lista."""
    if any(x["id"] == item.get("id") for x in livres):
        return
    livres.insert(len(livres) if posicao is None else max(0, min(int(posicao), len(livres))), completar(item))


def em_aberto(livres: list[dict]) -> list[dict]:
    """Na ordem em que foram criados."""
    return [x for x in livres if not x["feito_em"]]


def feitos(livres: list[dict]) -> list[dict]:
    """O feito mais recente primeiro."""
    return sorted((x for x in livres if x["feito_em"]), key=lambda x: x["feito_em"], reverse=True)
