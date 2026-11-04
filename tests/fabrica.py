"""Gera PDFs de NFS-e de mentira no mesmo layout do DANFSe v2.0.

Serve para os testes e para o autoteste do .exe no GitHub Actions: nenhum dado
real de paciente entra no repositório.

    python -m tests.fabrica <pasta>   # cria uma pasta de exemplo
"""

from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

_COLUNAS = (12, 156, 300, 444)
_FONTE = None


def _fonte() -> str:
    """Fonte com acentos (as fontes padrão do PDF não têm Ç, Ã etc. no pdfium)."""
    global _FONTE
    if _FONTE:
        return _FONTE
    import reportlab

    candidata = Path(reportlab.__file__).parent / "fonts" / "Vera.ttf"
    pdfmetrics.registerFont(TTFont("Vera", str(candidata)))
    _FONTE = "Vera"
    return _FONTE


def _br(v: Decimal) -> str:
    inteiro, centavos = f"{v:.2f}".split(".")
    return f"R$ {int(inteiro):,}".replace(",", ".") + f",{centavos}"


def criar_nota(
    caminho: Path,
    numero: int,
    competencia: date,
    emissao: date,
    valor: Decimal | str,
    descricao: str = "TRATAMENTO ODONTOLÓGICO",
    tomador: str = "FULANO DE TAL",
    situacao: str = "NFS-e gerada",
    marca_dagua: str | None = None,
) -> Path:
    valor = Decimal(str(valor))
    caminho = Path(caminho)
    c = canvas.Canvas(str(caminho), pagesize=A4)
    f = _fonte()
    altura = A4[1]

    def linha_de_celulas(y: float, celulas: list[tuple[str, str]]) -> None:
        # Cada célula: rótulo em cima, valor embaixo (como no DANFSe).
        for x, (rotulo, valor_celula) in zip(_COLUNAS, celulas):
            c.setFont(f, 7)
            c.drawString(x, altura - y, rotulo)
            if valor_celula:
                c.setFont(f, 8)
                c.drawString(x, altura - y - 12, valor_celula)

    c.setFont(f, 9)
    c.drawString(250, altura - 30, "DANFSe v2.0")
    c.drawString(250, altura - 40, "Documento Auxiliar da NFS-e")
    linha_de_celulas(70, [
        ("NÚMERO DA NFS-E", str(numero)),
        ("COMPETÊNCIA DA NFS-E", competencia.strftime("%d/%m/%Y")),
        ("DATA E HORA DA EMISSÃO DA NFS-E", emissao.strftime("%d/%m/%Y") + " 10:00:00"),
    ])
    linha_de_celulas(110, [
        ("EMITENTE DA NFS-E", "Prestador"),
        ("SITUAÇÃO DA NFS-E", situacao),
        ("FINALIDADE", "NFS-e regular"),
    ])
    linha_de_celulas(150, [("PRESTADOR / FORNECEDOR", ""), ("CNPJ / CPF / NIF", "00.000.000/0001-00")])
    linha_de_celulas(175, [("Nome / Nome Empresarial", "CLINICA EXEMPLO LTDA")])
    linha_de_celulas(210, [("TOMADOR / ADQUIRENTE", ""), ("CNPJ / CPF / NIF", "000.000.000-00")])
    linha_de_celulas(235, [("Nome / Nome Empresarial", tomador)])

    c.setFont(f, 7)
    c.drawString(12, altura - 280, "SERVIÇO PRESTADO")
    c.drawString(12, altura - 300, "Descrição do Serviço")
    c.setFont(f, 8)
    y = 312
    for parte in descricao.split("\n"):
        c.drawString(12, altura - y, parte)
        y += 11
    c.setFont(f, 7)
    c.drawString(12, altura - 350, "TRIBUTAÇÃO MUNICIPAL (ISSQN)")
    c.drawString(156, altura - 350, "Tipo de Tributação do ISSQN")

    linha_de_celulas(420, [("VALOR TOTAL DA NFS-E", ""), ("VALOR DA OPERAÇÃO / SERVIÇO", _br(valor)),
                           ("Desconto Incondicionado", "-"), ("Desconto Condicionado", "-")])
    linha_de_celulas(450, [("Total das Retenções (ISSQN / Federais)", "-"),
                           ("VALOR LÍQUIDO DA NFS-e", _br(valor))])

    if marca_dagua:
        c.saveState()
        c.setFont(f, 60)
        c.translate(300, 400)
        c.rotate(35)
        c.drawCentredString(0, 0, marca_dagua)
        c.restoreState()

    c.showPage()
    c.save()
    return caminho


def nome_arquivo(numero: int, paciente: str, emissao: date, competencia: date | None = None) -> str:
    fim = f" - {competencia:%d-%m}" if competencia and competencia != emissao else " -"
    return f"NFS-e Nº {numero:09d} - {paciente} - {emissao:%d-%m}{fim}.pdf"


EXEMPLOS = [
    # número, paciente (arquivo), emissão, competência, valor, descrição
    (801, "ANA BEATRIZ MOREIRA", date(2026, 10, 1), date(2026, 10, 1), "350.00", None),
    (802, "CARLOS EDUARDO LIMA", date(2026, 10, 3), date(2026, 10, 3), "1200.00", None),
    (803, "FERNANDA COSTA", date(2026, 10, 6), date(2026, 10, 6), "180.00",
     "TRATAMENTO ODONTOLÓGICO REFERENTE AO DEPENDENTE LUCAS COSTA RIBEIRO"),
    (804, "MARCOS PAULO SANTOS", date(2026, 10, 9), date(2026, 10, 9), "2450.00", None),
    (805, "JULIANA ALVES", date(2026, 10, 14), date(2026, 10, 14), "90.00", None),
    (806, "ROBERTO NUNES", date(2026, 10, 17), date(2026, 10, 17), "640.00", None),
    (807, "PATRÍCIA GOMES", date(2026, 10, 21), date(2026, 10, 21), "300.00",
     "TRATAMENTO ODONTOLÓGICO REFERENTE A(AO) DEPENDENTE SOFIA GOMES PEREIRA"),
    (808, "LUIZ HENRIQUE ROCHA", date(2026, 10, 24), date(2026, 10, 24), "1580.00", None),
    (809, "CAMILA FERREIRA", date(2026, 10, 28), date(2026, 10, 28), "220.00", "CONSULTA DE AVALIAÇÃO"),
    (810, "BRUNO CARVALHO", date(2026, 10, 30), date(2026, 10, 30), "475.00", None),
    (811, "TATIANE MENDES", date(2026, 11, 3), date(2026, 10, 31), "380.00", None),
    (812, "RAFAEL MARTINS", date(2026, 11, 4), date(2026, 11, 4), "150.00", None),
]


def criar_pasta_exemplo(pasta: Path) -> Path:
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    for numero, paciente, emissao, comp, valor, desc in EXEMPLOS:
        criar_nota(
            pasta / nome_arquivo(numero, paciente, emissao, comp),
            numero, comp, emissao, valor,
            descricao=desc or "TRATAMENTO ODONTOLÓGICO",
            tomador=paciente,
        )
    # Uma cancelada, para testar a mudança de pasta
    criar_nota(
        pasta / nome_arquivo(799, "NOTA CANCELADA EXEMPLO", date(2026, 9, 29)),
        799, date(2026, 9, 29), date(2026, 9, 29), "100.00",
        situacao="NFS-e cancelada", tomador="NOTA CANCELADA EXEMPLO",
    )
    return pasta


if __name__ == "__main__":
    destino = Path(sys.argv[1] if len(sys.argv) > 1 else "exemplo-notas")
    criar_pasta_exemplo(destino)
    print(f"Pasta de exemplo criada em {destino.resolve()}")
