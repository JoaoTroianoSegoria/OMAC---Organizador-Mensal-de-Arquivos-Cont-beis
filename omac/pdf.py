"""Extração de texto de PDF com o pdfium (usada pelos módulos que leem PDFs)."""

from __future__ import annotations

from pathlib import Path


class PdfIlegivel(Exception):
    """O arquivo não pôde ser aberto como PDF, ou não tem páginas."""


def extrair_paginas(caminho: Path, limite: int | None = None) -> list[str]:
    """Texto de cada página. `limite` evita ler páginas que não serão usadas."""
    import pypdfium2 as pdfium

    try:
        # Lê os bytes antes: assim o arquivo não fica preso por este programa.
        dados = Path(caminho).read_bytes()
        pdf = pdfium.PdfDocument(dados)
    except Exception as e:  # pdfium levanta PdfiumError, OSError, etc.
        raise PdfIlegivel(f"não foi possível abrir o PDF ({e})") from e
    try:
        if len(pdf) == 0:
            raise PdfIlegivel("o PDF está vazio")
        qtd = len(pdf) if limite is None else min(limite, len(pdf))
        return [
            pdf[i].get_textpage().get_text_range().replace("\r\n", "\n").replace("\r", "\n")
            for i in range(qtd)
        ]
    finally:
        pdf.close()
