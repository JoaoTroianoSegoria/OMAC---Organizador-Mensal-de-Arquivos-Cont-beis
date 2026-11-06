"""Baixa e troca o .exe.

O Windows não deixa sobrescrever um programa aberto, mas deixa renomear. Por isso:
o .exe atual vira "OMAC.exe.antigo", o novo assume o nome e abre, e é ele quem apaga
o antigo depois. Se algo falhar no meio, o nome original volta para o programa atual.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable
from urllib.error import URLError
from urllib.request import Request, urlopen

from .. import config
from .github import AGENTE, ErroDeAtualizacao, VersaoNova

PEDACO = 64 * 1024
TEMPO_LIMITE = 30  # segundos sem receber nada
PASTA_BACKUP = "backup-antes-de-atualizar"


def caminho_novo(executavel: Path) -> Path:
    return executavel.with_name(f"{executavel.name}.novo")


def caminho_antigo(executavel: Path) -> Path:
    return executavel.with_name(f"{executavel.name}.antigo")


def baixar(versao: VersaoNova, destino: Path, progresso: Callable[[int, int], None] | None = None) -> None:
    """Grava o arquivo em `destino` só se o tamanho e o hash baterem com o publicado."""
    pedido = Request(versao.url, headers={"User-Agent": AGENTE})
    soma = hashlib.sha256()
    recebidos = 0
    try:
        with urlopen(pedido, timeout=TEMPO_LIMITE) as resposta, destino.open("wb") as saida:  # noqa: S310
            while pedaco := resposta.read(PEDACO):
                saida.write(pedaco)
                soma.update(pedaco)
                recebidos += len(pedaco)
                if progresso:
                    progresso(recebidos, versao.tamanho)
        if recebidos != versao.tamanho or soma.hexdigest() != versao.sha256:
            raise ErroDeAtualizacao("O arquivo baixado veio diferente do publicado. Nada foi trocado: tente de novo.")
    except ErroDeAtualizacao:
        destino.unlink(missing_ok=True)
        raise
    except PermissionError as e:
        raise ErroDeAtualizacao(
            f"Não tenho permissão para gravar em “{destino.parent}”. Mova o OMAC para outra pasta "
            "ou baixe a versão nova pela página."
        ) from e
    except (URLError, OSError) as e:
        destino.unlink(missing_ok=True)
        raise ErroDeAtualizacao("O download foi interrompido. Nada foi trocado: tente de novo.") from e


def trocar_executavel(executavel: Path, novo: Path) -> Path:
    """Devolve onde o programa atual ficou guardado."""
    antigo = caminho_antigo(executavel)
    try:
        antigo.unlink(missing_ok=True)
        os.replace(executavel, antigo)
        try:
            os.replace(novo, executavel)
        except OSError:
            os.replace(antigo, executavel)
            raise
    except OSError as e:
        raise ErroDeAtualizacao(
            "O Windows não deixou trocar o programa. Nada foi alterado: baixe a versão nova pela página."
        ) from e
    return antigo


def desfazer_troca(executavel: Path, antigo: Path) -> None:
    os.replace(antigo, executavel)


def abrir_programa(executavel: Path, *argumentos: str) -> None:
    # Sem isto, o .exe novo herdaria a pasta temporária deste, que some quando ele fechar.
    ambiente = {**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"}
    opcoes = {}
    if sys.platform == "win32":
        opcoes["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([str(executavel), *argumentos], cwd=executavel.parent, env=ambiente, close_fds=True, **opcoes)  # noqa: S603


def copiar_dados() -> None:
    """Cópia de segurança dos dados do usuário antes de trocar de versão (sem o cache)."""
    pasta = config.pasta_dados()
    destino = pasta / PASTA_BACKUP
    destino.mkdir(parents=True, exist_ok=True)
    for arquivo in pasta.glob("*.json"):
        if arquivo != config.caminho_cache():
            shutil.copy2(arquivo, destino / arquivo.name)


def limpar_restos(executavel: Path, tentativas: int = 30, espera: float = 1.0) -> bool:
    """Apaga o programa antigo e downloads pela metade. O antigo pode demorar a fechar."""
    caminho_novo(executavel).unlink(missing_ok=True)
    antigo = caminho_antigo(executavel)
    for tentativa in range(tentativas):
        try:
            antigo.unlink(missing_ok=True)
            return True
        except OSError:
            if tentativa < tentativas - 1:
                time.sleep(espera)
    return False


def limpar_restos_em_segundo_plano(executavel: Path) -> None:
    def tarefa():
        try:
            limpar_restos(executavel)
        except OSError:
            pass  # na próxima abertura tenta de novo

    threading.Thread(target=tarefa, daemon=True).start()
