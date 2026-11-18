"""Contatos: o único lugar com nome e telefone de uma pessoa.

Tratamentos, atendimentos e lembretes guardam só o `contato_id`. Um contato pode ter
responsáveis, que também são contatos (pai, mãe, cônjuge ou outro). Para quem vai a
mensagem é escolhido na hora do envio; a última escolha fica em `envia_para`.
"""

from __future__ import annotations

import uuid
from datetime import date

from ..dados import esquema
from ..texto import mesma_pessoa, nome_limpo, normalizar
from ..whatsapp.mensagens import TelefoneInvalido, normalizar_telefone

PAPEIS = {"mae": "mãe", "pai": "pai", "conjuge": "cônjuge", "outro": "responsável"}

PARECIDOS = "parecidos"
TELEFONE = "telefone"

class ContatoInvalido(ValueError):
    """Faltou o nome, o nome já existe, ou um telefone não dá para entender."""


def completar(contato: dict) -> dict:
    return esquema.completar_item(esquema.CONTATOS, contato)


def telefone(texto, de_quem: str = "") -> str:
    """O telefone pode ficar para depois: é pedido de novo na hora de mandar a mensagem."""
    texto = str(texto or "").strip()
    if not texto:
        return ""
    try:
        return normalizar_telefone(texto)
    except TelefoneInvalido as e:
        raise ContatoInvalido(f"Telefone {de_quem}: {e}" if de_quem else str(e)) from e


def novo(nome: str, telefone_: str = "", hoje: date | None = None) -> dict:
    return completar({"id": uuid.uuid4().hex, "nome": nome_limpo(nome), "telefone": telefone_,
                      "criado_em": (hoje or date.today()).isoformat()})


def buscar(contatos: list[dict], contato_id: str) -> dict:
    for c in contatos:
        if c["id"] == contato_id:
            return c
    raise ContatoInvalido("Não encontrei esse contato. Ele pode ter sido apagado.")


def por_nome(contatos: list[dict], nome: str) -> dict | None:
    chave = normalizar(nome_limpo(nome))
    return next((c for c in contatos if normalizar(c["nome"]) == chave), None) if chave else None


def nomes(contatos: list[dict]) -> dict[str, str]:
    return {c["id"]: c["nome"] for c in contatos}


def conferir_nome(contatos: list[dict], nome: str, ignorar: str | None = None) -> None:
    igual = por_nome(contatos, nome)
    if igual and igual["id"] != ignorar:
        raise ContatoInvalido(
            f"Já existe o contato “{igual['nome']}”. Se for outra pessoa, coloque o sobrenome para diferenciar.")


def obter(contatos: list[dict], nome: str, telefone_: str = "", hoje: date | None = None) -> dict:
    """O contato com esse nome, ou um novo. Telefone novo só preenche quem não tinha."""
    nome = nome_limpo(nome)
    if not nome:
        raise ContatoInvalido("Diga o nome do contato.")
    contato = por_nome(contatos, nome)
    if contato is None:
        contato = novo(nome, telefone_, hoje)
        contatos.append(contato)
    elif telefone_ and not contato["telefone"]:
        contato["telefone"] = telefone_
    return contato


# --- Salvar pela janela de contato ----------------------------------------------------


def _responsaveis(contatos: list[dict], linhas: list[dict] | None, proprio_id: str | None,
                  nome_proprio: str, hoje: date) -> list[dict]:
    """Cada linha é {"contato_id"?, "nome", "telefone", "papel"}: escolhido da lista ou criado na hora."""
    escolhidos, vistos = [], set()
    for linha in linhas or []:
        nome = nome_limpo(linha.get("nome"))
        if not nome and not linha.get("contato_id"):
            continue
        papel = linha.get("papel")
        if papel not in PAPEIS:
            raise ContatoInvalido(f"Escolha quem é {nome or 'o responsável'}: mãe, pai, cônjuge ou outro.")
        fone = telefone(linha.get("telefone"), f"de {nome}" if nome else "do responsável")
        if linha.get("contato_id"):
            pessoa = buscar(contatos, linha["contato_id"])
        elif normalizar(nome) == normalizar(nome_proprio):
            raise ContatoInvalido("O responsável precisa ser outra pessoa.")
        else:
            pessoa = obter(contatos, nome, "", hoje)
        if pessoa["id"] == proprio_id:
            raise ContatoInvalido("O responsável precisa ser outra pessoa.")
        if fone:
            pessoa["telefone"] = fone  # o telefone digitado ali é o do responsável
        if pessoa["id"] not in vistos:
            vistos.add(pessoa["id"])
            escolhidos.append({"contato_id": pessoa["id"], "papel": papel})
    return escolhidos


def salvar(contatos: list[dict], dados: dict, contato_id: str | None, hoje: date) -> dict:
    """Cria ou altera. Valida tudo antes de mexer: um erro não deixa nada pela metade."""
    nome = nome_limpo(dados.get("nome"))
    if not nome:
        raise ContatoInvalido("Diga o nome do contato.")
    conferir_nome(contatos, nome, ignorar=contato_id)
    fone = telefone(dados.get("telefone"))
    atual = buscar(contatos, contato_id) if contato_id else None
    # Os responsáveis podem criar contatos: trabalha numa cópia e só troca no fim.
    copia = [dict(c) for c in contatos]
    responsaveis = _responsaveis(copia, dados.get("responsaveis"), contato_id, nome, hoje)
    contatos[:] = copia
    if atual is None:
        atual = novo(nome, fone, hoje)
        contatos.append(atual)
    else:
        atual = buscar(contatos, contato_id)
    atual.update(nome=nome, telefone=fone, responsaveis=responsaveis)
    if atual["envia_para"] and atual["envia_para"] not in {r["contato_id"] for r in responsaveis}:
        atual["envia_para"] = ""
    return atual


# --- Para quem vai a mensagem -----------------------------------------------------------


def destinos(contatos: list[dict], contato: dict) -> list[dict]:
    """O próprio contato e cada responsável: [{"contato_id", "nome", "telefone", "papel"}]."""
    lista = [{"contato_id": contato["id"], "nome": contato["nome"], "telefone": contato["telefone"], "papel": ""}]
    for r in contato["responsaveis"]:
        try:
            pessoa = buscar(contatos, r["contato_id"])
        except ContatoInvalido:
            continue
        lista.append({"contato_id": pessoa["id"], "nome": pessoa["nome"], "telefone": pessoa["telefone"],
                      "papel": PAPEIS.get(r["papel"], "responsável")})
    return lista


def destino_escolhido(contatos: list[dict], contato: dict) -> dict:
    """A última escolha. Sem escolha: o próprio contato, ou, se ele não tem telefone (criança),
    o primeiro responsável que tem."""
    lista = destinos(contatos, contato)
    escolhido = next((d for d in lista if d["contato_id"] == contato["envia_para"]), None)
    if escolhido:
        return escolhido
    if not lista[0]["telefone"]:
        return next((d for d in lista[1:] if d["telefone"]), lista[0])
    return lista[0]


# --- Apagar e desfazer ----------------------------------------------------------------------


def dependentes(contatos: list[dict], contato_id: str) -> list[dict]:
    return [c for c in contatos if any(r["contato_id"] == contato_id for r in c["responsaveis"])]


def tirar_vinculos(contatos: list[dict], contato_id: str) -> list[dict]:
    """Tira o contato da lista de responsáveis dos outros. Devolve o que tirou, para desfazer."""
    tirados = []
    for c in contatos:
        for r in c["responsaveis"]:
            if r["contato_id"] == contato_id:
                tirados.append({"dependente_id": c["id"], **r, "envia_para": c["envia_para"] == contato_id})
        c["responsaveis"] = [r for r in c["responsaveis"] if r["contato_id"] != contato_id]
        if c["envia_para"] == contato_id:
            c["envia_para"] = ""
    return tirados


def devolver_vinculos(contatos: list[dict], tirados: list[dict]) -> None:
    for t in tirados:
        c = next((c for c in contatos if c["id"] == t["dependente_id"]), None)
        if c is None:
            continue
        if not any(r["contato_id"] == t["contato_id"] for r in c["responsaveis"]):
            c["responsaveis"].append({"contato_id": t["contato_id"], "papel": t["papel"]})
        if t["envia_para"]:
            c["envia_para"] = t["contato_id"]


# --- Conferir contatos (o que a migração não juntou sozinha) ------------------------------


def parecidos(contatos: list[dict]) -> list[list[str]]:
    """Pares de nomes que podem ser a mesma pessoa (um sobrenome a mais ou a menos)."""
    pares = []
    for i, a in enumerate(contatos):
        for b in contatos[i + 1:]:
            if normalizar(a["nome"]) != normalizar(b["nome"]) and mesma_pessoa(a["nome"], b["nome"]):
                pares.append([a["id"], b["id"]])
    return pares


def a_conferir_validos(itens: list[dict], contatos: list[dict]) -> list[dict]:
    """Some sozinho o que perdeu o sentido (contato apagado, telefone já igual)."""
    ids = {c["id"]: c for c in contatos}
    validos = []
    for item in itens:
        if item.get("tipo") == PARECIDOS and all(i in ids for i in item.get("ids", [])):
            validos.append(item)
        elif item.get("tipo") == TELEFONE and item.get("id") in ids:
            if len(set(item.get("telefones", []))) > 1:
                validos.append(item)
    return validos


def juntar(manter: dict, tirar: dict) -> None:
    """`tirar` some e `manter` fica com o que faltava nele (telefone e responsáveis)."""
    if not manter["telefone"]:
        manter["telefone"] = tirar["telefone"]
    ids = {r["contato_id"] for r in manter["responsaveis"]}
    manter["responsaveis"] += [r for r in tirar["responsaveis"] if r["contato_id"] not in ids | {manter["id"]}]
    if not manter["envia_para"]:
        manter["envia_para"] = tirar["envia_para"]
    manter["criado_em"] = min(x for x in (manter["criado_em"], tirar["criado_em"]) if x) \
        if manter["criado_em"] or tirar["criado_em"] else ""


def trocar_id(contatos: list[dict], de: str, para: str) -> None:
    """Quem tinha `de` como responsável passa a ter `para`."""
    for c in contatos:
        vistos, novos = set(), []
        for r in c["responsaveis"]:
            r = {**r, "contato_id": para if r["contato_id"] == de else r["contato_id"]}
            if r["contato_id"] not in vistos and r["contato_id"] != c["id"]:
                vistos.add(r["contato_id"])
                novos.append(r)
        c["responsaveis"] = novos
        if c["envia_para"] == de:
            c["envia_para"] = para
