"""Backup dos dados do OMAC: só copia, nunca apaga nada do que é da pessoa.

- O zip `OMAC-backup-AAAA-MM-DD.zip` leva os arquivos de dados (esquema.DO_BACKUP), os arquivos
  dos modelos (modelos/<id>.<extensão>) e um manifesto.json (versão do app, data e lista de
  arquivos). Ficam os 12 mais novos.
- Opcional: espelho das notas e dos extratos em <pasta>/Notas e <pasta>/Extratos, copiando
  só arquivo novo ou alterado. Nada é apagado do espelho.
- Restaurar guarda os dados atuais em `antes-de-restaurar/` antes de trocar, e recusa um
  backup feito por uma versão mais nova do app.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import zipfile
from calendar import monthrange
from datetime import date, datetime, timedelta
from pathlib import Path

from .. import __version__
from ..dados import esquema
from ..modelos import modelos as md

GUARDAR = 12
MANIFESTO = "manifesto.json"
PADRAO_NOME = re.compile(r"^OMAC-backup-(\d{4}-\d{2}-\d{2})\.zip$")
PASTA_ANTES = "antes-de-restaurar"


class BackupInvalido(ValueError):
    """Pasta que não dá para usar, ou zip que não é um backup do OMAC."""


def versao_em_numeros(versao: str) -> tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", str(versao))[:3]) or (0,)


# --- Quando fazer -----------------------------------------------------------------------


def ultima_data_marcada(cfg: dict, hoje: date) -> date:
    """O dia mais recente (até hoje) em que um backup estava marcado para acontecer."""
    if cfg["backup_frequencia"] == "dia":
        return hoje
    if cfg["backup_frequencia"] == "semana":
        return hoje - timedelta(days=(hoje.weekday() - cfg["backup_dia_semana"]) % 7)
    dia = cfg["backup_dia_mes"]
    neste = date(hoje.year, hoje.month, min(dia, monthrange(hoje.year, hoje.month)[1]))
    if neste <= hoje:
        return neste
    anterior = hoje.replace(day=1) - timedelta(days=1)
    return date(anterior.year, anterior.month, min(dia, monthrange(anterior.year, anterior.month)[1]))


def esta_na_hora(cfg: dict, agora: datetime) -> bool:
    """Se o dia marcado caiu com o computador desligado, faz na próxima abertura."""
    if not cfg["backup_automatico"] or not cfg["backup_pasta"]:
        return False
    if not cfg["backup_ultimo"]:
        return True
    try:
        ultimo = datetime.fromisoformat(cfg["backup_ultimo"]).date()
    except ValueError:
        return True
    return ultimo < ultima_data_marcada(cfg, agora.date())


def dias_desde(cfg: dict, hoje: date) -> int | None:
    if not cfg["backup_ultimo"]:
        return None
    try:
        return (hoje - datetime.fromisoformat(cfg["backup_ultimo"]).date()).days
    except ValueError:
        return None


# --- Fazer ----------------------------------------------------------------------------------


def _pasta_de_backup(pasta: str) -> Path:
    if not pasta:
        raise BackupInvalido("Escolha a pasta do backup primeiro.")
    destino = Path(pasta)
    if not destino.is_dir():
        raise BackupInvalido(f"Não encontrei a pasta do backup “{pasta}”. O pendrive ou o HD está conectado?")
    return destino


def _arquivos_de_modelos(pasta_dados: Path) -> list[str]:
    pasta = pasta_dados / md.PASTA
    if not pasta.is_dir():
        return []
    return sorted(f"{md.PASTA}/{p.name}" for p in pasta.iterdir() if p.is_file() and md.RE_GUARDADO.match(p.name))


def _e_de_modelo(nome: str) -> bool:
    pasta, _, arquivo = nome.partition("/")
    return pasta == md.PASTA and bool(md.RE_GUARDADO.match(arquivo))


def fazer(pasta_dados: Path, pasta_backup: str, agora: datetime) -> Path:
    destino = _pasta_de_backup(pasta_backup)
    arquivos = [n for n in esquema.DO_BACKUP if (pasta_dados / n).is_file()] + _arquivos_de_modelos(pasta_dados)
    manifesto = {"app": "OMAC", "versao": __version__, "data": agora.isoformat(timespec="seconds"),
                 "arquivos": arquivos}
    final = destino / f"OMAC-backup-{agora:%Y-%m-%d}.zip"
    temporario = final.with_name(final.name + ".tmp")
    with zipfile.ZipFile(temporario, "w", zipfile.ZIP_DEFLATED) as z:
        for nome in arquivos:
            z.write(pasta_dados / nome, nome)
        z.writestr(MANIFESTO, json.dumps(manifesto, ensure_ascii=False, indent=2))
    # Confere antes de trocar: um zip estragado não pode tomar o lugar de um bom.
    with zipfile.ZipFile(temporario) as z:
        if z.testzip() is not None:
            raise OSError("O backup ficou com defeito. Tente de novo.")
    os.replace(temporario, final)
    limpar_antigos(destino)
    return final


def backups(pasta: Path) -> list[Path]:
    """Os zips de backup da pasta, do mais novo para o mais velho."""
    return sorted((p for p in pasta.iterdir() if p.is_file() and PADRAO_NOME.match(p.name)),
                  key=lambda p: p.name, reverse=True)


def limpar_antigos(pasta: Path, guardar: int = GUARDAR) -> list[str]:
    apagados = []
    for velho in backups(pasta)[guardar:]:
        velho.unlink()
        apagados.append(velho.name)
    return apagados


def espelhar(origem: str, destino: Path) -> int:
    """Copia para `destino` o que é novo ou mudou em `origem` (com as subpastas). Nunca apaga."""
    if not origem or not Path(origem).is_dir():
        return 0
    copiados = 0
    raiz = Path(origem)
    for arquivo in raiz.rglob("*"):
        if not arquivo.is_file():
            continue
        alvo = destino / arquivo.relative_to(raiz)
        st = arquivo.stat()
        if alvo.exists():
            at = alvo.stat()
            if at.st_size == st.st_size and int(at.st_mtime) == int(st.st_mtime):
                continue
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(arquivo, alvo)
        copiados += 1
    return copiados


# --- Restaurar ----------------------------------------------------------------------------


def ler_manifesto(zip_caminho: Path) -> dict:
    try:
        with zipfile.ZipFile(zip_caminho) as z:
            manifesto = json.loads(z.read(MANIFESTO).decode("utf-8"))
            nomes = set(z.namelist())
    except (OSError, KeyError, ValueError, zipfile.BadZipFile) as e:
        raise BackupInvalido("Esse arquivo não é um backup do OMAC.") from e
    if manifesto.get("app") != "OMAC" or not isinstance(manifesto.get("arquivos"), list):
        raise BackupInvalido("Esse arquivo não é um backup do OMAC.")
    # Só os arquivos de dados conhecidos: um zip nunca escreve fora da pasta dos dados.
    arquivos = [n for n in manifesto["arquivos"] if (n in esquema.DO_BACKUP or _e_de_modelo(n)) and n in nomes]
    return {**manifesto, "arquivos": arquivos}


def restaurar(zip_caminho: Path, pasta_dados: Path, agora: datetime) -> dict:
    manifesto = ler_manifesto(zip_caminho)
    if versao_em_numeros(manifesto.get("versao", "")) > versao_em_numeros(__version__):
        raise BackupInvalido(f"Esse backup foi feito na versão {manifesto['versao']}, mais nova que esta "
                             f"({__version__}). Baixe a versão nova do OMAC para restaurar.")
    if not any(n in esquema.DO_BACKUP for n in manifesto["arquivos"]):
        raise BackupInvalido("Esse backup não tem nenhum arquivo de dados.")
    guarda = pasta_dados / PASTA_ANTES / f"{agora:%Y-%m-%d_%H-%M-%S}"
    guarda.mkdir(parents=True, exist_ok=True)
    atuais_de_modelos = _arquivos_de_modelos(pasta_dados)
    for nome in [*esquema.DO_BACKUP, *atuais_de_modelos]:
        if (pasta_dados / nome).is_file():
            (guarda / nome).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pasta_dados / nome, guarda / nome)
    with zipfile.ZipFile(zip_caminho) as z:
        for nome in manifesto["arquivos"]:
            (pasta_dados / nome).parent.mkdir(parents=True, exist_ok=True)
            temporario = pasta_dados / f"{nome}.tmp"
            temporario.write_bytes(z.read(nome))
            os.replace(temporario, pasta_dados / nome)
    # Arquivo de modelo que não estava no backup: já foi guardado acima, sai da pasta.
    for nome in atuais_de_modelos:
        if nome not in manifesto["arquivos"]:
            (pasta_dados / nome).unlink(missing_ok=True)
    # Arquivo que existe agora mas não estava no backup (ex.: comandos.json novo): fica guardado e sai.
    for nome in esquema.ARQUIVOS:
        if nome not in manifesto["arquivos"] and (pasta_dados / nome).is_file():
            (pasta_dados / nome).unlink()
    return {**manifesto, "guardados_em": str(guarda)}
