"""Migrações dos arquivos de dados, todas num lugar só.

1. `atualizar`: cada arquivo novo tem "versao". Quando o formato mudar, a versão em
   esquema.py sobe e entra aqui um passo `PASSOS[arquivo][n]`, que leva da versão n para
   a n+1. Os passos rodam em cadeia, e cada um tem teste.
2. `migrar_da_1_5`: a mudança grande da 1.6.0. Os três arquivos antigos (whatsapp.json,
   agendamentos.json e pagamentos.json) viram contatos, tratamentos, atendimentos,
   lembretes e notas enviadas. Antes de tudo, cópia dos antigos em `antes-da-1.6.0/`.
   Os antigos ficam onde estão (uma volta para a 1.5.0 continua funcionando).
"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path
from typing import Callable

from . import esquema
from .arquivo import DadosIlegiveis, carregar_json, ler_json, salvar_json

PASSOS: dict[str, dict[int, Callable[[dict], dict]]] = {nome: {} for nome in esquema.ARQUIVOS}


def atualizar(nome: str, dados: dict) -> dict:
    atual = esquema.ARQUIVOS[nome]["versao"]
    try:
        versao = int(dados.get("versao", 1))
    except (TypeError, ValueError):
        versao = 1
    if versao > atual:
        raise DadosIlegiveis(f"“{nome}” foi gravado por uma versão mais nova do OMAC. "
                             "Baixe a versão mais nova para continuar.")
    while versao < atual:
        dados = PASSOS[nome][versao](dados)
        versao += 1
    return {**dados, "versao": atual}


# --- 1.5.0 → 1.6.0 -------------------------------------------------------------------------

ANTIGOS = ["whatsapp.json", "agendamentos.json", "pagamentos.json"]
PASTA_COPIA = "antes-da-1.6.0"

# Cartões do Início da 1.5.0 → widgets da 1.6.0 (o primeiro de cada um decide a posição).
CARTOES_ANTIGOS = {
    "hoje": "hoje", "contas": "lembretes", "notas_enviar": "lembretes", "orto": "tratamentos",
    "ficha": "atendimentos", "fechamento": "relatorio", "resumo": "resumo",
}


def precisa_migrar(pasta: Path) -> bool:
    if (pasta / esquema.CONTATOS).exists():
        return False
    return any((pasta / nome).exists() for nome in [*ANTIGOS, esquema.CONFIG])


def copiar_antigos(pasta: Path) -> Path:
    """Copia todos os .json da pasta de dados. Uma cópia que já existe nunca é trocada."""
    destino = pasta / PASTA_COPIA
    destino.mkdir(parents=True, exist_ok=True)
    for arquivo in sorted(pasta.glob("*.json")):
        alvo = destino / arquivo.name
        if not alvo.exists():
            shutil.copy2(arquivo, alvo)
            if alvo.read_bytes() != arquivo.read_bytes():
                raise OSError(f"A cópia de {arquivo.name} não ficou igual ao original.")
    return destino


class _Agenda:
    """Junta as pessoas pelo nome (igual, sem acento e maiúsculas) enquanto migra."""

    def __init__(self, hoje: date):
        from ..contatos import contatos as ct

        self.ct = ct
        self.hoje = hoje
        self.contatos: list[dict] = []
        self.conflitos: dict[str, set[str]] = {}

    def obter(self, nome, telefone="", criado_em="") -> dict | None:
        nome = " ".join(str(nome or "").split())
        if not nome:
            return None
        contato = self.ct.por_nome(self.contatos, nome)
        if contato is None:
            contato = self.ct.novo(nome, telefone or "", self.hoje)
            self.contatos.append(contato)
        elif telefone:
            if not contato["telefone"]:
                contato["telefone"] = telefone
            elif contato["telefone"] != telefone:
                self.conflitos.setdefault(contato["id"], {contato["telefone"]}).add(telefone)
        if criado_em and criado_em < contato["criado_em"]:
            contato["criado_em"] = criado_em
        return contato

    def a_conferir(self) -> list[dict]:
        itens = [{"tipo": self.ct.PARECIDOS, "ids": par} for par in self.ct.parecidos(self.contatos)]
        itens += [{"tipo": self.ct.TELEFONE, "id": i, "telefones": sorted(t)} for i, t in self.conflitos.items()]
        return itens


def _tratamentos(agenda: _Agenda, pacientes: list[dict]) -> list[dict]:
    tratamentos = []
    for p in pacientes:
        criado = p.get("criado_em") or agenda.hoje.isoformat()
        contato = agenda.obter(p.get("nome"), p.get("telefone", ""), criado)
        if contato is None:
            continue
        responsaveis = p.get("responsaveis") or {}
        for papel in ("mae", "pai"):
            pessoa = responsaveis.get(papel) or {}
            r = agenda.obter(pessoa.get("nome"), pessoa.get("telefone", ""))
            if r is None or r is contato:
                continue
            if not any(x["contato_id"] == r["id"] for x in contato["responsaveis"]):
                contato["responsaveis"].append({"contato_id": r["id"], "papel": papel})
            if responsaveis.get("envia_para") == papel:
                contato["envia_para"] = r["id"]
        tratamentos.append({
            "id": p.get("id") or contato["id"],
            "contato_id": contato["id"],
            "valor_centavos": p.get("valor_centavos"),
            "agendado_em": p.get("agendado_em", ""),
            "finalizado_em": p.get("finalizado_em", ""),
            "alta_inicio": p.get("alta_inicio", ""),
            "alta_fim": p.get("alta_fim", ""),
            "atendidos": p.get("atendidos") or {},
            "altas": p.get("altas") or [],
            "criado_em": criado,
        })
    return tratamentos


def _atendimentos(agenda: _Agenda, antigos: list[dict]) -> list[dict]:
    atendimentos = []
    for a in antigos:
        contato = agenda.obter(a.get("nome"))
        if contato is None:
            continue
        atendimentos.append({
            "id": a["id"],
            "contato_id": contato["id"],
            "tratamento": a.get("tratamento", ""),
            "data": a["data"],
            "valor_centavos": a.get("valor_centavos"),
            "forma": a.get("forma", ""),
            "parcelas": a.get("parcelas", 1),
            "pago_em": a.get("pago_em", ""),
            "nota": "ok" if a.get("nota_manual") else "",
        })
    return atendimentos


def _cartoes(antigos) -> list[dict]:
    novos, vistos = [], set()
    for c in antigos if isinstance(antigos, list) else []:
        novo = CARTOES_ANTIGOS.get(c.get("id")) if isinstance(c, dict) else None
        if novo and novo not in vistos:
            vistos.add(novo)
            novos.append({"id": novo, "visivel": bool(c.get("visivel", True)), "largo": bool(c.get("largo", False))})
    return novos


def migrar_da_1_5(pasta: Path, hoje: date | None = None) -> dict:
    """Devolve um resumo do que foi feito (para o teste e para o registro)."""
    hoje = hoje or date.today()
    copiar_antigos(pasta)
    wa = carregar_json(pasta / "whatsapp.json",
                       {"inicio": "", "ultima_abertura": "", "contatos": {}, "enviadas": {}, "contas": []}, "Os contatos")
    ag = carregar_json(pasta / "agendamentos.json", {"pacientes": []}, "Os pacientes")
    pg = carregar_json(pasta / "pagamentos.json", {"atendimentos": []}, "Os atendimentos da ficha")
    cfg = ler_json(pasta / esquema.CONFIG, "As configurações") or {}

    agenda = _Agenda(hoje)
    tratamentos = _tratamentos(agenda, ag["pacientes"])
    atendimentos = _atendimentos(agenda, pg["atendimentos"])
    for item in (wa["contatos"] or {}).values():
        agenda.obter(item.get("nome"), item.get("telefone", ""))
    destinatario = agenda.obter(cfg.get("lembrete_nome") or ("Lembretes" if cfg.get("lembrete_telefone") else ""),
                                cfg.get("lembrete_telefone", ""))

    def gravar(nome: str, conteudo: dict) -> None:
        salvar_json(pasta / nome, {"versao": esquema.ARQUIVOS[nome]["versao"], **conteudo})

    gravar(esquema.TRATAMENTOS, {"tratamentos": tratamentos})
    gravar(esquema.ATENDIMENTOS, {"atendimentos": atendimentos})
    gravar(esquema.LEMBRETES, {"ultima_abertura": wa["ultima_abertura"],
                               "destinatario": destinatario["id"] if destinatario else "",
                               "contas": wa["contas"], "livres": []})
    gravar(esquema.NOTAS_ENVIADAS, {"inicio": wa["inicio"], "enviadas": wa["enviadas"]})
    # Por último: contatos.json existir quer dizer que a migração terminou.
    a_conferir = agenda.a_conferir()
    gravar(esquema.CONTATOS, {"contatos": agenda.contatos, "a_conferir": a_conferir})
    # O telefone dos lembretes só sai da configuração depois de estar nos contatos.
    if cfg:
        novo_cfg = {k: v for k, v in cfg.items() if k not in ("lembrete_nome", "lembrete_telefone")}
        if "inicio_cartoes" in cfg:
            novo_cfg["inicio_cartoes"] = _cartoes(cfg["inicio_cartoes"])
        salvar_json(pasta / esquema.CONFIG, novo_cfg)
    return {"contatos": len(agenda.contatos), "tratamentos": len(tratamentos),
            "atendimentos": len(atendimentos), "a_conferir": len(a_conferir)}


def preparar(pasta: Path) -> str:
    """Roda ao abrir o app. Devolve "" ou a mensagem de erro (e aí nada é gravado)."""
    if not precisa_migrar(pasta):
        return ""
    try:
        migrar_da_1_5(pasta)
    except (OSError, ValueError, KeyError, TypeError) as e:
        return (f"Não consegui passar os dados para o formato da 1.6.0 ({e}). Nada foi apagado: "
                f"os arquivos antigos estão na pasta dos dados e a cópia em “{PASTA_COPIA}”.")
    return ""
