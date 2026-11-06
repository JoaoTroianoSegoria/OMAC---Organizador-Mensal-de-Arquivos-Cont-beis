"""Varredura da pasta de notas do ano (ex.: "NFS-e 2026").

- Lê só os PDFs que estão direto na pasta (não entra em subpastas).
- Guarda o resultado num cache, então cada nota só é lida uma vez.
- Nota cancelada fica fora do relatório. Nenhum arquivo da pasta é movido ou alterado.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .leitor import VERSAO_LEITOR, Nota, NotaIlegivel, ler_nota


@dataclass
class Varredura:
    notas: list[Nota] = field(default_factory=list)
    # Avisos que não são de uma nota específica: PDF ilegível, número repetido…
    avisos: list[dict] = field(default_factory=list)
    canceladas: list[Nota] = field(default_factory=list)

    def do_mes(self, ano: int, mes: int) -> list[Nota]:
        """Notas cuja competência cai no mês/ano pedido, em ordem de número."""
        return sorted(
            (n for n in self.notas if n.competencia.year == ano and n.competencia.month == mes),
            key=lambda n: n.numero,
        )

    def canceladas_do_mes(self, ano: int, mes: int) -> list[Nota]:
        return [n for n in self.canceladas if n.competencia.year == ano and n.competencia.month == mes]

    def competencias(self) -> list[tuple[int, int, int]]:
        """(ano, mês, quantidade de notas) de cada competência encontrada."""
        qtd = Counter((n.competencia.year, n.competencia.month) for n in self.notas)
        return [(ano, mes, q) for (ano, mes), q in sorted(qtd.items())]


class Cache:
    """Resultado da leitura de cada PDF, por nome + tamanho + data de modificação."""

    def __init__(self, caminho: Path | None):
        self.caminho = caminho
        self.itens: dict[str, dict] = {}
        self._alterado = False
        if caminho and caminho.exists():
            try:
                dados = json.loads(caminho.read_text(encoding="utf-8"))
                if dados.get("versao") == VERSAO_LEITOR:
                    self.itens = dados.get("itens", {})
            except (OSError, ValueError):
                pass  # cache corrompido: começa do zero

    @staticmethod
    def _chave(arquivo: Path) -> str:
        return str(arquivo.resolve())

    @staticmethod
    def _assinatura(arquivo: Path) -> list:
        st = arquivo.stat()
        return [st.st_size, int(st.st_mtime)]

    def obter(self, arquivo: Path) -> Nota | None:
        item = self.itens.get(self._chave(arquivo))
        if item and item.get("assinatura") == self._assinatura(arquivo):
            return Nota.de_dict(item["nota"])
        return None

    def guardar(self, arquivo: Path, nota: Nota) -> None:
        self.itens[self._chave(arquivo)] = {
            "assinatura": self._assinatura(arquivo),
            "nota": nota.para_dict(),
        }
        self._alterado = True

    def limpar_ausentes(self, presentes: set[str]) -> None:
        for chave in list(self.itens):
            if chave not in presentes:
                del self.itens[chave]
                self._alterado = True

    def salvar(self) -> None:
        if not (self.caminho and self._alterado):
            return
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.caminho.with_suffix(".tmp")
        tmp.write_text(json.dumps({"versao": VERSAO_LEITOR, "itens": self.itens}), encoding="utf-8")
        tmp.replace(self.caminho)
        self._alterado = False


def varrer(
    pasta: Path,
    cache: Cache | None = None,
    progresso: Callable[[int, int], None] | None = None,
) -> Varredura:
    pasta = Path(pasta)
    if not pasta.is_dir():
        raise FileNotFoundError(f"A pasta não existe: {pasta}")
    cache = cache or Cache(None)

    arquivos = sorted(p for p in pasta.iterdir() if p.is_file() and p.suffix.lower() == ".pdf")
    total = len(arquivos)
    resultado = Varredura()
    presentes: set[str] = set()
    ultimo_aviso = 0.0

    for i, arquivo in enumerate(arquivos, 1):
        nota = cache.obter(arquivo)
        if nota is None:
            try:
                nota = ler_nota(arquivo)
            except NotaIlegivel as e:
                resultado.avisos.append({"arquivo": arquivo.name, "mensagem": f"Nota ignorada: {e}."})
                nota = None
            except OSError as e:
                resultado.avisos.append(
                    {"arquivo": arquivo.name, "mensagem": f"Não consegui ler o arquivo ({e.strerror or e})."}
                )
                nota = None
            if nota:
                cache.guardar(arquivo, nota)

        if nota:
            presentes.add(Cache._chave(arquivo))
            (resultado.canceladas if nota.cancelada else resultado.notas).append(nota)

        agora = time.monotonic()
        if progresso and (agora - ultimo_aviso > 0.1 or i == total):
            progresso(i, total)
            ultimo_aviso = agora

    cache.limpar_ausentes(presentes)
    cache.salvar()

    repetidos = [num for num, qtd in Counter(n.numero for n in resultado.notas).items() if qtd > 1]
    for num in sorted(repetidos):
        nomes = ", ".join(n.arquivo for n in resultado.notas if n.numero == num)
        resultado.avisos.append(
            {"arquivo": None, "mensagem": f"A nota nº {num} aparece em mais de um arquivo: {nomes}."}
        )
    return resultado
