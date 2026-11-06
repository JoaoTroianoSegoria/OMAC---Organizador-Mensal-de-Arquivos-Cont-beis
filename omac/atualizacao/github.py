"""Consulta a última versão publicada na aba Releases do GitHub."""

from __future__ import annotations

import json
import re
import struct
from dataclasses import dataclass, field
from urllib.error import URLError
from urllib.request import Request, urlopen

from .. import REPOSITORIO, __version__

URL_ULTIMA = f"https://api.github.com/repos/{REPOSITORIO}/releases/latest"
# Só baixa daqui, mesmo que a resposta aponte para outro lugar.
PREFIXO_DOWNLOAD = f"https://github.com/{REPOSITORIO}/releases/download/"
PAGINA_RELEASES = f"https://github.com/{REPOSITORIO}/releases/latest"
AGENTE = "OMAC-atualizador"
TEMPO_LIMITE = 10  # segundos
MAX_NOVIDADES = 8


class ErroDeAtualizacao(Exception):
    """Algo deu errado. A mensagem é para mostrar na tela, e o programa atual segue intacto."""


@dataclass(frozen=True)
class VersaoNova:
    numero: str
    url: str
    tamanho: int
    sha256: str
    novidades: list[str] = field(default_factory=list)


def numero_da_versao(texto: str) -> tuple[int, ...] | None:
    """"v1.3.0" vira (1, 3, 0). Devolve None para o que não for uma versão simples."""
    m = re.fullmatch(r"v?(\d+(?:\.\d+)*)", str(texto).strip())
    return tuple(int(p) for p in m[1].split(".")) if m else None


def nome_do_arquivo(bits: int | None = None) -> str:
    return f"OMAC-{bits or struct.calcsize('P') * 8}bits.exe"


def novidades(corpo: str | None) -> list[str]:
    """Só os títulos das mudanças, sem autor e link, que não dizem nada a quem usa o app."""
    itens = []
    for linha in (corpo or "").splitlines():
        m = re.match(r"\s*[*-]\s+(.+)", linha)
        if m:
            itens.append(re.sub(r"\s+by\s+@\S+.*$", "", m[1]).strip())
    return itens[:MAX_NOVIDADES]


def interpretar(release: dict, atual: str = __version__, bits: int | None = None) -> VersaoNova | None:
    """A versão para instalar, ou None se não houver nada mais novo e confiável."""
    numero = numero_da_versao(release.get("tag_name", ""))
    if numero is None or numero <= (numero_da_versao(atual) or ()):
        return None
    if release.get("draft") or release.get("prerelease"):
        return None

    nome = nome_do_arquivo(bits)
    for arquivo in release.get("assets", []):
        if arquivo.get("name") != nome:
            continue
        url = str(arquivo.get("browser_download_url", ""))
        digest = str(arquivo.get("digest") or "")
        # A publicação ainda pode estar em andamento: sem hash ou sem tamanho, não instala.
        if not url.startswith(PREFIXO_DOWNLOAD) or not digest.startswith("sha256:") or not arquivo.get("size"):
            return None
        return VersaoNova(".".join(map(str, numero)), url, int(arquivo["size"]),
                          digest.removeprefix("sha256:").lower(), novidades(release.get("body")))
    return None


def procurar() -> VersaoNova | None:
    pedido = Request(URL_ULTIMA, headers={"User-Agent": AGENTE, "Accept": "application/vnd.github+json"})
    try:
        with urlopen(pedido, timeout=TEMPO_LIMITE) as resposta:  # noqa: S310 — endereço fixo, https
            return interpretar(json.loads(resposta.read().decode("utf-8")))
    except (URLError, OSError, ValueError) as e:
        raise ErroDeAtualizacao("Não consegui falar com o GitHub. Confira a internet e tente de novo.") from e
