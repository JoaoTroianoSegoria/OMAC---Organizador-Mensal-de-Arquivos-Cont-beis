"""Comandos: textos prontos, separados por categoria, para copiar com um clique.

O texto é guardado como foi escrito, com as quebras de linha do meio. Só o espaço e as
linhas em branco das pontas saem, para o que for colado não ter nada a mais.
"""

from __future__ import annotations

import uuid

from ..dados import esquema
from ..texto import nome_limpo, normalizar


class ComandoInvalido(ValueError):
    """Faltou o nome ou o texto, o nome já existe, ou o item não existe mais."""


def completar(categoria: dict) -> dict:
    return esquema.completar_item(esquema.COMANDOS, categoria)


def texto_limpo(texto) -> str:
    """Tira só o espaço das pontas (inclusive linhas em branco); o meio fica igual."""
    return str(texto or "").replace("\r\n", "\n").strip()


def buscar_categoria(categorias: list[dict], categoria_id: str) -> dict:
    for c in categorias:
        if c["id"] == categoria_id:
            return c
    raise ComandoInvalido("Não encontrei essa categoria. Ela pode ter sido apagada.")


def buscar_comando(categoria: dict, comando_id: str) -> dict:
    for c in categoria["comandos"]:
        if c["id"] == comando_id:
            return c
    raise ComandoInvalido("Não encontrei esse comando. Ele pode ter sido apagado.")


def _nome_livre(lista: list[dict], nome: str, ignorar: str | None, o_que: str) -> None:
    if any(x["id"] != ignorar and normalizar(x["nome"]) == normalizar(nome) for x in lista):
        raise ComandoInvalido(f"Já existe {o_que} “{nome}”.")


def salvar_categoria(categorias: list[dict], nome, categoria_id: str | None = None) -> dict:
    nome = nome_limpo(nome)
    if not nome:
        raise ComandoInvalido("Diga o nome da categoria.")
    _nome_livre(categorias, nome, categoria_id, "a categoria")
    if categoria_id:
        categoria = buscar_categoria(categorias, categoria_id)
        categoria["nome"] = nome
        return categoria
    categoria = completar({"id": uuid.uuid4().hex, "nome": nome})
    categorias.append(categoria)
    return categoria


def salvar_comando(categoria: dict, dados: dict, comando_id: str | None = None) -> dict:
    nome = nome_limpo(dados.get("nome"))
    texto = texto_limpo(dados.get("texto"))
    if not nome:
        raise ComandoInvalido("Diga o nome do comando.")
    if not texto:
        raise ComandoInvalido("Escreva o texto que vai ser copiado.")
    _nome_livre(categoria["comandos"], nome, comando_id, "o comando")
    if comando_id:
        comando = buscar_comando(categoria, comando_id)
        comando.update(nome=nome, texto=texto)
        return comando
    comando = {"id": uuid.uuid4().hex, "nome": nome, "texto": texto}
    categoria["comandos"].append(comando)
    return comando


def inserir(lista: list[dict], item: dict, posicao: int | None) -> None:
    """Desfaz uma exclusão, de volta ao mesmo lugar. Desfazer duas vezes não duplica."""
    if any(x["id"] == item.get("id") for x in lista):
        return
    lista.insert(len(lista) if posicao is None else max(0, min(int(posicao), len(lista))), item)


def mover(lista: list[dict], item_id: str, passo: int) -> None:
    """Sobe (-1) ou desce (+1) um item na lista."""
    i = next((n for n, x in enumerate(lista) if x["id"] == item_id), None)
    if i is None:
        raise ComandoInvalido("Não encontrei esse item. Ele pode ter sido apagado.")
    j = i + passo
    if 0 <= j < len(lista):
        lista[i], lista[j] = lista[j], lista[i]
