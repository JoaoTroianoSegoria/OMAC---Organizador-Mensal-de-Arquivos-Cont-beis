"""Ficha do paciente (1.15.0): os dados de um contato, as pessoas ligadas a ele e um resumo.

Abre ao clicar no nome em Atendimentos e Tratamentos. Só lê: para mudar alguma coisa, o botão
Editar abre a janela de contato de sempre. Monta tudo a partir do que já está guardado
(contatos, tratamentos, atendimentos e as notas lidas da pasta), sem guardar nada novo.
"""

from __future__ import annotations

from datetime import date

from ..atendimentos import ficha as fc
from ..atendimentos import listas as lst
from ..notas.leitor import responsavel
from ..texto import mesma_pessoa, normalizar
from ..tratamentos import orto
from . import contatos as ct
from . import cpf as cpfs

ULTIMOS = 5  # quantos atendimentos e notas aparecem no resumo

SITUACAO_DO_TRATAMENTO = {orto.ATIVO: "Em tratamento", orto.ALTA: "De alta", orto.FINALIZADO: "Finalizado"}
SITUACAO_DO_MES = {orto.VEIO: "já veio este mês", orto.FALTA_VIR: "ainda não veio este mês",
                   orto.NAO_VEIO: "não veio", orto.DE_ALTA: "de alta este mês"}
# Do lado de quem é responsável: a pessoa é "mãe" do dependente, então ele é filho ou filha.
RELACAO_DO_DEPENDENTE = {"mae": "filho ou filha", "pai": "filho ou filha", "conjuge": "cônjuge", "outro": "dependente"}
SITUACAO_DO_PAGAMENTO = {fc.PAGO: "Pago", fc.AGUARDANDO: "A receber", fc.NAO_PAGO: "Não pago"}


def idade(nascimento: str, hoje: date) -> int | None:
    if not nascimento:
        return None
    try:
        dia = date.fromisoformat(nascimento)
    except ValueError:
        return None
    return hoje.year - dia.year - ((hoje.month, hoje.day) < (dia.month, dia.day))


def _pessoa(c: dict, hoje: date) -> dict:
    return {"id": c["id"], "nome": c["nome"], "telefone": c["telefone"], "cpf": cpfs.formatar(c["cpf"]) if c["cpf"] else "",
            "nascimento": c["nascimento"], "idade": idade(c["nascimento"], hoje)}


def _vinculos(contatos: list[dict], contato: dict, hoje: date) -> list[dict]:
    """Responsáveis (mãe, pai...) e dependentes, cada um com os dados dele."""
    por_id = {c["id"]: c for c in contatos}
    vinculos = [{**_pessoa(por_id[r["contato_id"]], hoje), "tipo": "responsavel",
                 "relacao": ct.PAPEIS.get(r["papel"], "responsável")}
                for r in contato["responsaveis"] if r["contato_id"] in por_id]
    for d in ct.dependentes(contatos, contato["id"]):
        papel = next(r["papel"] for r in d["responsaveis"] if r["contato_id"] == contato["id"])
        vinculos.append({**_pessoa(d, hoje), "tipo": "dependente", "relacao": RELACAO_DO_DEPENDENTE.get(papel, "dependente")})
    return vinculos


def _tratamento(tratamentos: list[dict], contato_id: str, hoje: date) -> dict | None:
    t = orto.do_contato(tratamentos, contato_id)
    if t is None:
        return None
    situacao = orto.situacao(t)
    mes = orto.situacao_no_mes(t, hoje.year, hoje.month, hoje) if situacao != orto.FINALIZADO else ""
    historico = orto.historico_do_paciente(t, hoje)
    return {
        "situacao": SITUACAO_DO_TRATAMENTO.get(situacao, situacao),
        "mes": SITUACAO_DO_MES.get(mes, ""),
        "valor_centavos": t["valor_centavos"],
        "proxima_consulta": orto.proxima_consulta(t, hoje) if situacao != orto.FINALIZADO else "",
        "veio": historico["veio"], "esperados": historico["esperados"],
        "desde": t["criado_em"][:7],
    }


def _atendimentos(atendimentos: list[dict], listas: list[dict], contato_id: str, hoje: date) -> dict:
    dele = sorted((a for a in atendimentos if a["contato_id"] == contato_id), key=lambda a: a["data"], reverse=True)
    varias_listas = len(listas) > 1
    pago = sum(a["valor_centavos"] or 0 for a in dele if a["pago_em"])
    return {
        "qtd": len(dele),
        "pago_centavos": pago,
        "a_receber_centavos": sum(a["valor_centavos"] or 0 for a in dele if not a["pago_em"]),
        "ultimos": [{
            "data": a["data"], "tratamento": a["tratamento"], "valor_centavos": a["valor_centavos"],
            "forma": fc.forma_por_extenso(a), "pagamento": SITUACAO_DO_PAGAMENTO[fc.situacao(a, hoje)],
            "situacao": fc.situacao(a, hoje),
            "lista": lst.nome_de(listas, lst.da(a, listas)) if varias_listas else "",
        } for a in dele[:ULTIMOS]],
    }


def _notas(notas: list | None, contato: dict) -> dict | None:
    """As notas do paciente (pelo nome, ou pelo CPF quando a nota é dele mesmo) e as que ele recebeu
    como responsável de um dependente. None quando a pasta das notas ainda não foi lida."""
    if notas is None:
        return None
    nome, cpf = contato["nome"], contato["cpf"]
    achadas = []
    for n in notas:
        if mesma_pessoa(n.paciente, nome) or (not n.dependente and cpf and n.cpf_tomador == cpf):
            achadas.append((n, "paciente"))
        elif n.dependente and mesma_pessoa(responsavel(n), nome):
            achadas.append((n, "responsavel"))
    achadas.sort(key=lambda x: (x[0].competencia, x[0].numero), reverse=True)
    valendo = [n for n, _ in achadas if not n.cancelada]
    return {
        "qtd": len(valendo),
        "total_centavos": sum(int(n.valor * 100) for n in valendo),
        "ultimas": [{"numero": n.numero, "competencia": n.competencia.isoformat(), "valor_centavos": int(n.valor * 100),
                     "arquivo": n.arquivo, "cancelada": n.cancelada,
                     "de": n.paciente.title() if como == "responsavel" else ""} for n, como in achadas[:ULTIMOS]],
    }


def montar(contato_id: str, contatos: list[dict], tratamentos: list[dict], dados_atendimentos: dict,
           notas: list | None, hoje: date) -> dict:
    contato = ct.buscar(contatos, contato_id)
    return {
        **_pessoa(contato, hoje),
        "criado_em": contato["criado_em"],
        "vinculos": sorted(_vinculos(contatos, contato, hoje), key=lambda v: (v["tipo"] != "responsavel", normalizar(v["nome"]))),
        "tratamento": _tratamento(tratamentos, contato_id, hoje),
        "atendimentos": _atendimentos(dados_atendimentos["atendimentos"], lst.todas(dados_atendimentos), contato_id, hoje),
        "notas": _notas(notas, contato),
    }
