"""Leitura de uma NFS-e (DANFSe v2.0, padrão nacional) a partir do PDF.

O texto do PDF é extraído pelo pdfium, que entrega cada rótulo seguido do seu
valor na linha de baixo, por exemplo:

    NÚMERO DA NFS-E
    836
    COMPETÊNCIA DA NFS-E
    30/10/2026

O nome do paciente vem do nome do arquivo, salvo quando a descrição do
serviço indica um dependente ("... referente ao dependente FULANO"): nesse
caso o nome do dependente tem prioridade.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from ..pdf import PdfIlegivel, extrair_paginas

# Mude quando a forma de ler as notas mudar: invalida o cache antigo.
VERSAO_LEITOR = 1


class NotaIlegivel(Exception):
    """O PDF não pôde ser aberto ou não tem os campos de uma NFS-e."""


@dataclass
class Nota:
    numero: int
    paciente: str
    valor: Decimal
    emissao: date
    competencia: date
    arquivo: str
    dependente: bool = False
    cancelada: bool = False
    avisos: list[str] = field(default_factory=list)

    def para_dict(self) -> dict:
        return {
            "numero": self.numero,
            "paciente": self.paciente,
            "valor": str(self.valor),
            "emissao": self.emissao.isoformat(),
            "competencia": self.competencia.isoformat(),
            "arquivo": self.arquivo,
            "dependente": self.dependente,
            "cancelada": self.cancelada,
            "avisos": list(self.avisos),
        }

    @classmethod
    def de_dict(cls, d: dict) -> "Nota":
        return cls(
            numero=d["numero"],
            paciente=d["paciente"],
            valor=Decimal(d["valor"]),
            emissao=date.fromisoformat(d["emissao"]),
            competencia=date.fromisoformat(d["competencia"]),
            arquivo=d["arquivo"],
            dependente=d.get("dependente", False),
            cancelada=d.get("cancelada", False),
            avisos=list(d.get("avisos", [])),
        )


# --- Nome do arquivo -------------------------------------------------------

# "NFS-e Nº 000000835 - NOME DO PACIENTE - 30-10 -" (competência opcional no fim)
_RE_ARQUIVO = re.compile(
    r"^NFS-?e\s*N\S*\s*0*(?P<numero>\d+)\s*-\s*(?P<nome>.+?)\s*-\s*\d{1,2}-\d{1,2}\b",
    re.IGNORECASE,
)


def ler_nome_arquivo(nome: str) -> tuple[int, str] | None:
    """Devolve (número, paciente) do nome do arquivo, ou None fora do padrão."""
    m = _RE_ARQUIVO.match(Path(nome).stem.strip())
    if not m:
        return None
    paciente = _limpar_nome(m.group("nome"))
    if not paciente:
        return None
    return int(m.group("numero")), paciente


# --- Conteúdo do PDF -------------------------------------------------------

_RE_NUMERO = re.compile(r"N[ÚU]MERO DA NFS-E\s*\n\s*(\d+)", re.IGNORECASE)
_RE_COMPETENCIA = re.compile(r"COMPET[ÊE]NCIA DA NFS-E\s*\n\s*(\d{2}/\d{2}/\d{4})", re.IGNORECASE)
_RE_EMISSAO = re.compile(
    r"DATA E HORA DA EMISS[ÃA]O DA NFS-E\s*\n\s*(\d{2}/\d{2}/\d{4})", re.IGNORECASE
)
_RE_SITUACAO = re.compile(r"SITUA[ÇC][ÃA]O DA NFS-E\s*\n\s*([^\n]+)", re.IGNORECASE)
# O valor pode não vir na linha logo abaixo (a coluna "VALOR TOTAL" ao lado
# costuma estar vazia e o pdfium junta os rótulos), então pega o primeiro R$.
_RE_VALOR_SERVICO = re.compile(
    r"VALOR DA OPERA[ÇC][ÃA]O\s*/\s*SERVI[ÇC]O.*?R\$\s*([\d.]+,\d{2})", re.IGNORECASE | re.DOTALL
)
_RE_VALOR_LIQUIDO = re.compile(
    r"VALOR L[ÍI]QUIDO DA NFS-E\s*\n\s*R\$\s*([\d.]+,\d{2})", re.IGNORECASE
)
_RE_DESCRICAO = re.compile(
    r"Descri[çc][ãa]o do Servi[çc]o\s*\n(.*?)\n\s*TRIBUTA[ÇC][ÃA]O MUNICIPAL",
    re.IGNORECASE | re.DOTALL,
)
_RE_TOMADOR = re.compile(
    r"TOMADOR\s*/\s*ADQUIRENTE.*?Nome\s*/\s*Nome Empresarial\s*\n\s*([^\n]+)",
    re.IGNORECASE | re.DOTALL,
)
_RE_DEPENDENTE = re.compile(r"\bdependente\b\s*[:\-]?\s*(.+)", re.IGNORECASE | re.DOTALL)
_RE_CANCELADA = re.compile(r"\bcancelad[ao]\b", re.IGNORECASE)


def extrair_texto(caminho: Path) -> str:
    """Texto da primeira página do PDF (o DANFSe tem uma página só)."""
    try:
        return extrair_paginas(caminho, limite=1)[0]
    except PdfIlegivel as e:
        raise NotaIlegivel(str(e)) from e


def interpretar_texto(texto: str, nome_arquivo: str) -> Nota:
    """Monta a Nota a partir do texto do PDF e do nome do arquivo."""
    avisos: list[str] = []

    numero = _buscar(_RE_NUMERO, texto)
    competencia = _buscar(_RE_COMPETENCIA, texto)
    emissao = _buscar(_RE_EMISSAO, texto)
    valor = _buscar(_RE_VALOR_SERVICO, texto) or _buscar(_RE_VALOR_LIQUIDO, texto)

    faltando = [
        rotulo
        for rotulo, v in (
            ("número", numero),
            ("competência", competencia),
            ("data de emissão", emissao),
            ("valor", valor),
        )
        if v is None
    ]
    if faltando:
        if not texto.strip():
            raise NotaIlegivel("o PDF não tem texto (é uma imagem escaneada?)")
        raise NotaIlegivel("não encontrei " + ", ".join(faltando) + " no PDF")

    situacao = _buscar(_RE_SITUACAO, texto) or ""
    cancelada = bool(_RE_CANCELADA.search(situacao) or _RE_CANCELADA.search(texto))

    descricao = " ".join((_buscar(_RE_DESCRICAO, texto) or "").split())
    if "tratamento odontol" not in _sem_acentos(descricao).lower():
        avisos.append("A descrição do serviço não contém “tratamento odontológico”.")

    do_arquivo = ler_nome_arquivo(nome_arquivo)
    dependente = _nome_dependente(descricao)

    if dependente:
        paciente = dependente
    elif do_arquivo:
        paciente = do_arquivo[1]
    else:
        paciente = _limpar_nome(_buscar(_RE_TOMADOR, texto) or "")
        avisos.append(
            "O nome do arquivo está fora do padrão; usei o nome do tomador que está na nota."
        )
        if not paciente:
            paciente = "(sem nome)"

    numero_int = int(numero)
    if do_arquivo and do_arquivo[0] != numero_int:
        avisos.append(
            f"O número no nome do arquivo ({do_arquivo[0]}) é diferente do número da nota ({numero_int})."
        )

    return Nota(
        numero=numero_int,
        paciente=paciente,
        valor=_valor(valor),
        emissao=_data(emissao),
        competencia=_data(competencia),
        arquivo=nome_arquivo,
        dependente=bool(dependente),
        cancelada=cancelada,
        avisos=avisos,
    )


def ler_nota(caminho: Path) -> Nota:
    caminho = Path(caminho)
    return interpretar_texto(extrair_texto(caminho), caminho.name)


# --- Auxiliares ------------------------------------------------------------


def _buscar(regex: re.Pattern, texto: str) -> str | None:
    m = regex.search(texto)
    return m.group(1).strip() if m else None


def _nome_dependente(descricao: str) -> str | None:
    m = _RE_DEPENDENTE.search(descricao)
    if not m:
        return None
    # Corta o que vier depois do nome: CPF, números, parênteses, pontuação.
    nome = re.split(r"[,;:()\[\]\d]|\s[-–]\s|\bCPF\b", m.group(1), maxsplit=1, flags=re.IGNORECASE)[0]
    return _limpar_nome(nome) or None


def _limpar_nome(nome: str) -> str:
    return " ".join(nome.split()).strip(" .-–").upper()


def _sem_acentos(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _valor(s: str) -> Decimal:
    return Decimal(s.replace(".", "").replace(",", "."))


def _data(s: str) -> date:
    return datetime.strptime(s, "%d/%m/%Y").date()
