"""Modelos de documentos para imprimir (atestado, receita, termo…).

O OMAC guarda uma cópia de cada arquivo em <pasta dos dados>/modelos/<id><extensão>, para
o modelo continuar funcionando mesmo que o original seja movido ou apagado. A lista fica em
modelos.json: {"id", "titulo", "arquivo", "nome_original", "criado_em"}.
"""

from __future__ import annotations

import re
import uuid
from datetime import date
from pathlib import Path

from ..texto import normalizar

PASTA = "modelos"
TIPOS = {
    ".pdf": "PDF",
    ".docx": "Word", ".doc": "Word", ".odt": "Documento", ".rtf": "Documento", ".txt": "Texto",
    ".png": "Imagem", ".jpg": "Imagem", ".jpeg": "Imagem",
}
LIMITE_MB = 50
# Nome de um arquivo guardado pelo OMAC: id + extensão conhecida. Nada de pastas no meio.
RE_GUARDADO = re.compile(r"^[0-9a-f]{12}(" + "|".join(re.escape(e) for e in TIPOS) + r")$")


class ModeloInvalido(ValueError):
    """Título vazio ou repetido, ou arquivo que o OMAC não guarda."""


def titulo_limpo(titulo: str) -> str:
    return " ".join(str(titulo or "").split())


def titulo_do_arquivo(nome: str) -> str:
    """Sugestão de título: o nome do arquivo sem a extensão e sem _ ou - sobrando."""
    return titulo_limpo(re.sub(r"[_]+", " ", Path(nome).stem))


def conferir_arquivo(caminho: Path) -> str:
    """A extensão (minúscula) se o arquivo pode virar modelo."""
    extensao = caminho.suffix.lower()
    if extensao not in TIPOS:
        aceitos = "PDF, Word (.docx ou .doc), .odt, .rtf, .txt ou imagem (.png ou .jpg)"
        raise ModeloInvalido(f"Esse tipo de arquivo não dá para usar como modelo. Use {aceitos}.")
    if not caminho.is_file():
        raise ModeloInvalido(f"Não encontrei o arquivo “{caminho.name}”. Ele foi movido ou renomeado?")
    if caminho.stat().st_size > LIMITE_MB * 1024 * 1024:
        raise ModeloInvalido(f"O arquivo tem mais de {LIMITE_MB} MB. Use um arquivo menor.")
    return extensao


def conferir_titulo(modelos: list[dict], titulo: str, ignorar: str | None = None) -> str:
    titulo = titulo_limpo(titulo)
    if not titulo:
        raise ModeloInvalido("Dê um título para o modelo.")
    if any(normalizar(m["titulo"]) == normalizar(titulo) and m["id"] != ignorar for m in modelos):
        raise ModeloInvalido(f"Já existe um modelo chamado “{titulo}”.")
    return titulo


def novo(modelos: list[dict], titulo: str, extensao: str, nome_original: str, hoje: date) -> dict:
    titulo = conferir_titulo(modelos, titulo)
    ident = uuid.uuid4().hex[:12]
    modelo = {"id": ident, "titulo": titulo, "arquivo": f"{ident}{extensao}",
              "nome_original": nome_original, "criado_em": hoje.isoformat()}
    modelos.append(modelo)
    return modelo


def buscar(modelos: list[dict], modelo_id: str) -> dict:
    for m in modelos:
        if m["id"] == modelo_id:
            return m
    raise ModeloInvalido("Esse modelo não existe mais.")


def em_ordem(modelos: list[dict]) -> list[dict]:
    return sorted(modelos, key=lambda m: normalizar(m["titulo"]))


def tipo(modelo: dict) -> str:
    return TIPOS.get(Path(modelo["arquivo"]).suffix.lower(), "Arquivo")


def nome_para_salvar(modelo: dict) -> str:
    """O título vira o nome do arquivo (sem os caracteres que o Windows não aceita)."""
    base = re.sub(r'[\\/:*?"<>|]+', " ", modelo["titulo"]).strip(" .") or "Modelo"
    return titulo_limpo(base) + Path(modelo["arquivo"]).suffix.lower()


def sem_uso(pasta: Path, modelos: list[dict]) -> list[Path]:
    """Arquivos guardados que nenhum modelo usa mais (sobras de modelos apagados)."""
    if not pasta.is_dir():
        return []
    usados = {m["arquivo"] for m in modelos}
    return [p for p in pasta.iterdir() if p.is_file() and RE_GUARDADO.match(p.name) and p.name not in usados]
