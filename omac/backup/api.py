"""Parte da API que cuida do backup (Configurações > Backup)."""

from __future__ import annotations

import threading
import traceback
from datetime import datetime
from pathlib import Path

from .. import config
from ..dados import migracoes
from ..nucleo import ApiBase, caminho_unico, seguro
from . import backup as bk


class BackupApi(ApiBase):
    def __init__(self):
        super().__init__()
        self._trava_backup = threading.Lock()

    def _situacao_backup(self) -> dict:
        cfg = self._cfg
        return {
            "pasta": cfg["backup_pasta"],
            "automatico": cfg["backup_automatico"],
            "ultimo": cfg["backup_ultimo"],
            "dias": bk.dias_desde(cfg, datetime.now().date()),
            "erro": cfg["backup_erro"],
        }

    def _fazer_backup(self) -> dict:
        with self._trava_backup:
            agora = datetime.now()
            pasta_dados = config.pasta_dados()
            try:
                zip_feito = bk.fazer(pasta_dados, self._cfg["backup_pasta"], agora)
                copiados = 0
                if self._cfg["backup_arquivos"]:
                    destino = Path(self._cfg["backup_pasta"])
                    copiados += bk.espelhar(self._cfg["pasta_notas"], destino / "Notas")
                    copiados += bk.espelhar(self._cfg["pasta_extratos"], destino / "Extratos")
            except (OSError, bk.BackupInvalido) as e:
                traceback.print_exc()
                self._cfg = config.salvar({**self._cfg, "backup_erro": str(e) or e.__class__.__name__})
                raise
            self._cfg = config.salvar({**self._cfg, "backup_ultimo": agora.isoformat(timespec="seconds"),
                                       "backup_erro": ""})
            return {"arquivo": str(zip_feito), "copiados": copiados}

    @seguro
    def backup_situacao(self):
        return self._situacao_backup()

    @seguro
    def backup_escolher_pasta(self):
        import webview

        inicial = self._cfg["backup_pasta"] or str(Path.home())
        escolha = self._janela.create_file_dialog(webview.FileDialog.FOLDER, directory=inicial)
        if not escolha:
            return {"cancelado": True}
        self._cfg = config.salvar({**self._cfg, "backup_pasta": caminho_unico(escolha), "backup_erro": ""})
        return {"config": self._cfg, **self._situacao_backup()}

    @seguro
    def backup_agora(self):
        feito = self._fazer_backup()
        return {**feito, "config": self._cfg, **self._situacao_backup()}

    @seguro
    def backup_verificar(self):
        """Chamado ao abrir e uma vez por hora: faz o backup automático se passou a data."""
        if not bk.esta_na_hora(self._cfg, datetime.now()):
            return {"feito": False, **self._situacao_backup()}
        try:
            feito = self._fazer_backup()
        except (OSError, bk.BackupInvalido):
            # A falha vira aviso no Início; o app segue normal.
            return {"feito": False, "falhou": True, "config": self._cfg, **self._situacao_backup()}
        return {"feito": True, **feito, "config": self._cfg, **self._situacao_backup()}

    @seguro
    def backup_escolher_para_restaurar(self):
        import webview

        inicial = self._cfg["backup_pasta"] or str(Path.home())
        escolha = self._janela.create_file_dialog(webview.FileDialog.OPEN, directory=inicial,
                                                  file_types=("Backup do OMAC (*.zip)",))
        if not escolha:
            return {"cancelado": True}
        caminho = caminho_unico(escolha)
        manifesto = bk.ler_manifesto(Path(caminho))
        return {"caminho": caminho, "data": manifesto.get("data", ""), "versao": manifesto.get("versao", ""),
                "arquivos": manifesto["arquivos"]}

    @seguro
    def backup_restaurar(self, caminho: str):
        """Troca os dados pelos do backup. A tela recarrega depois (como reabrir o app)."""
        pasta_dados = config.pasta_dados()
        backup_atual = {k: v for k, v in self._cfg.items() if k.startswith("backup_")}
        with self._trava_backup:
            r = bk.restaurar(Path(caminho), pasta_dados, datetime.now())
            # As escolhas de backup são deste computador: não voltam com os dados.
            self._cfg = config.salvar({**config.carregar(), **backup_atual})
            self._armazem.esquecer()
            self._armazem.bloqueio = migracoes.preparar(pasta_dados)
        return {"data": r.get("data", ""), "versao": r.get("versao", ""), "guardados_em": r["guardados_em"]}
