"""Extração de texto de PDF com o pdfium (usada pelos módulos que leem PDFs)."""

from __future__ import annotations

import threading
from pathlib import Path

# O pdfium não aguenta duas chamadas ao mesmo tempo, nem em arquivos diferentes: o programa
# inteiro cai sem mensagem de erro. A tela chama a API em várias threads (notas e extrato podem
# estar sendo lidos juntos), então todo uso do pdfium passa por esta trava.
_TRAVA_PDFIUM = threading.Lock()


class PdfIlegivel(Exception):
    """O arquivo não pôde ser aberto como PDF, ou não tem páginas."""


def extrair_paginas(caminho: Path, limite: int | None = None) -> list[str]:
    """Texto de cada página. `limite` evita ler páginas que não serão usadas."""
    import pypdfium2 as pdfium

    try:
        # Lê os bytes antes: assim o arquivo não fica preso por este programa.
        dados = Path(caminho).read_bytes()
    except OSError as e:
        raise PdfIlegivel(f"não foi possível abrir o PDF ({e})") from e

    with _TRAVA_PDFIUM:
        try:
            pdf = pdfium.PdfDocument(dados)
        except Exception as e:  # pdfium levanta PdfiumError, etc.
            raise PdfIlegivel(f"não foi possível abrir o PDF ({e})") from e
        try:
            if len(pdf) == 0:
                raise PdfIlegivel("o PDF está vazio")
            qtd = len(pdf) if limite is None else min(limite, len(pdf))
            try:
                return [_texto_da_pagina(pdf, i) for i in range(qtd)]
            except Exception as e:  # noqa: BLE001 — pdfium levanta PdfiumError, etc.
                raise PdfIlegivel(f"não foi possível ler o texto do PDF ({e})") from e
        finally:
            pdf.close()


def _texto_da_pagina(pdf, indice: int) -> str:
    # Fecha aqui, dentro da trava: deixar para o coletor de lixo faria a limpeza
    # acontecer depois, em qualquer thread, fora da proteção.
    pagina = pdf[indice]
    try:
        texto = pagina.get_textpage()
        try:
            return texto.get_text_range().replace("\r\n", "\n").replace("\r", "\n")
        finally:
            texto.close()
    finally:
        pagina.close()
