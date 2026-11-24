"""Registro dos widgets do Início.

Cada módulo marca o método que monta os dados do seu widget com `@widget(...)`, e o
desenho fica no .js do módulo (`registrarWidget`). O Início só percorre o registro:
widget novo aparece no fim da tela de quem já personalizou, e widget removido some.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Widget:
    id: str
    titulo: str
    metodo: str
    ordem: int
    largo: bool
    no_hoje: bool  # o "Hoje" junta as pendências deste widget, mesmo quando ele está escondido


WIDGETS: dict[str, Widget] = {}


def widget(id: str, titulo: str, ordem: int, largo: bool = False, no_hoje: bool = True):
    """Marca um método `(self, hoje) -> dict` da API como os dados de um widget.

    `no_hoje=False`: o "Hoje" não usa os dados dele, então escondido ele nem é calculado.
    """

    def marcar(funcao):
        if id in WIDGETS and WIDGETS[id].metodo != funcao.__name__:
            raise ValueError(f"Dois widgets com o id “{id}”.")
        WIDGETS[id] = Widget(id, titulo, funcao.__name__, ordem, largo, no_hoje)
        return funcao

    return marcar


def em_ordem() -> list[Widget]:
    return sorted(WIDGETS.values(), key=lambda w: w.ordem)


def cartoes(escolhas: list[dict]) -> list[dict]:
    """A ordem e as escolhas da pessoa, só com os widgets que existem, e os novos no fim."""
    vistos, lista = set(), []
    for c in escolhas:
        if c["id"] in WIDGETS and c["id"] not in vistos:
            vistos.add(c["id"])
            lista.append({"id": c["id"], "visivel": c["visivel"], "largo": c["largo"]})
    return lista + [{"id": w.id, "visivel": True, "largo": w.largo} for w in em_ordem() if w.id not in vistos]
