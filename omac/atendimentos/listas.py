"""Listas da ficha de atendimentos (1.14.0): separar, por exemplo, Brasília e São Paulo.

A lista só separa: nome e mais nada. Totais e planilha de Atendimentos são por lista; o resto do
app (notas, extrato, Início, Resumo do ano, Tratamentos) continua vendo todos os atendimentos.

Guardadas em atendimentos.json → "listas": [{"id", "nome"}]; cada atendimento tem "lista_id".
Sem nenhuma lista guardada existe uma só, "Lista 1", de id "" — a dos atendimentos de antes da
1.14.0, que também têm lista_id "". Atendimento com lista que não existe mais (backup antigo
restaurado, por exemplo) aparece na primeira lista.
"""

from __future__ import annotations

import uuid

from .. import texto as tx

NOME_PADRAO = "Lista 1"
NOME_MAX = 30


class ListaInvalida(ValueError):
    """Nome vazio ou repetido, ou lista que não pode ser apagada."""


def todas(dados: dict) -> list[dict]:
    """As listas do atendimentos.json (sempre pelo menos uma)."""
    listas = [{"id": str(item.get("id", "")), "nome": str(item.get("nome") or "")}
              for item in dados.get("listas") or [] if isinstance(item, dict)]
    return listas or [{"id": "", "nome": NOME_PADRAO}]


def da(atendimento: dict, listas: list[dict]) -> str:
    """O id da lista do atendimento (a primeira, se a dele não existe mais)."""
    lista_id = atendimento.get("lista_id", "")
    return lista_id if any(item["id"] == lista_id for item in listas) else listas[0]["id"]


def certa(lista_id, listas: list[dict]) -> str:
    """O id pedido pela tela, ou o da primeira lista se ele não existe (lista apagada em outra janela)."""
    lista_id = str(lista_id or "")
    return lista_id if any(item["id"] == lista_id for item in listas) else listas[0]["id"]


def filtrar(atendimentos: list[dict], listas: list[dict], lista_id: str) -> list[dict]:
    return [a for a in atendimentos if da(a, listas) == lista_id]


def nome_de(listas: list[dict], lista_id: str) -> str:
    return next((item["nome"] for item in listas if item["id"] == lista_id), "")


def _nome_valido(listas: list[dict], nome, ignorar: str | None = None) -> str:
    nome = tx.nome_limpo(nome)[:NOME_MAX].strip()
    if not nome:
        raise ListaInvalida("Dê um nome para a lista.")
    if any(tx.normalizar(item["nome"]) == tx.normalizar(nome) for item in listas if item["id"] != ignorar):
        raise ListaInvalida(f"Já existe uma lista chamada {nome}.")
    return nome


def criar(dados: dict, nome) -> dict:
    listas = todas(dados)
    nova = {"id": uuid.uuid4().hex, "nome": _nome_valido(listas, nome)}
    dados["listas"] = [*listas, nova]
    return nova


def renomear(dados: dict, lista_id: str, nome) -> dict:
    listas = todas(dados)
    lista = next((item for item in listas if item["id"] == lista_id), None)
    if lista is None:
        raise ListaInvalida("Não encontrei essa lista. Ela pode ter sido apagada.")
    lista["nome"] = _nome_valido(listas, nome, ignorar=lista_id)
    dados["listas"] = listas
    return lista


def apagar(dados: dict, lista_id: str) -> None:
    """Só lista vazia (em todos os meses), para nenhum atendimento sumir sem querer."""
    listas = todas(dados)
    if not any(item["id"] == lista_id for item in listas):
        raise ListaInvalida("Não encontrei essa lista. Ela pode ter sido apagada.")
    if len(listas) == 1:
        raise ListaInvalida("A ficha precisa de pelo menos uma lista.")
    qtd = len(filtrar(dados["atendimentos"], listas, lista_id))
    if qtd:
        nome = nome_de(listas, lista_id)
        raise ListaInvalida(f"A lista {nome} tem {qtd} {'atendimento' if qtd == 1 else 'atendimentos'}. "
                            "Mude eles de lista ou apague antes de apagar a lista.")
    restantes = [item for item in listas if item["id"] != lista_id]
    # Os atendimentos sem lista (os de antes da 1.14.0) ficam na primeira: se a "Lista 1" de id ""
    # foi apagada (estava vazia), a primeira passa a ser outra e nada muda para eles.
    dados["listas"] = restantes
