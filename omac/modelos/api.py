"""Parte da API dos Modelos: guardar, imprimir, abrir uma cópia e baixar."""

from __future__ import annotations

import os
import shutil
import tempfile
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from .. import config, sistema
from ..dados import esquema
from ..inicio.registro import widget
from ..nucleo import ApiBase, caminho_unico, seguro
from . import modelos as md


class ModelosApi(ApiBase):
    def _pasta_modelos(self) -> Path:
        return config.pasta_dados() / md.PASTA

    @contextmanager
    def _modelos(self):
        with self._armazem.editar(esquema.MODELOS) as d:
            yield d["modelos"]

    def _lista_de_modelos(self) -> list[dict]:
        return self._armazem.ler(esquema.MODELOS)["modelos"]

    def _caminho_do_modelo(self, modelo: dict) -> Path:
        caminho = self._pasta_modelos() / modelo["arquivo"]
        if not caminho.is_file():
            raise md.ModeloInvalido(f"O arquivo do modelo “{modelo['titulo']}” sumiu da pasta do OMAC. "
                                    "Use Alterar > Trocar arquivo para escolher de novo.")
        return caminho

    def _vista_modelos(self) -> dict:
        modelos = self._lista_de_modelos()
        pasta = self._pasta_modelos()
        return {"modelos": [{
            "id": m["id"],
            "titulo": m["titulo"],
            "tipo": md.tipo(m),
            "extensao": Path(m["arquivo"]).suffix.lower().lstrip("."),
            "nome_original": m["nome_original"],
            "criado_em": m["criado_em"],
            "existe": (pasta / m["arquivo"]).is_file(),
        } for m in md.em_ordem(modelos)]}

    @seguro
    def modelos_listar(self):
        # Sobras de modelos apagados (o desfazer já passou): só na primeira lista da sessão.
        if not getattr(self, "_modelos_limpos", False):
            self._modelos_limpos = True
            for sobra in md.sem_uso(self._pasta_modelos(), self._lista_de_modelos()):
                sobra.unlink(missing_ok=True)
        return self._vista_modelos()

    @seguro
    def modelos_escolher_arquivo(self):
        import webview

        tipos = ";".join(f"*{e}" for e in md.TIPOS)
        escolha = self._janela.create_file_dialog(
            webview.FileDialog.OPEN, directory=str(Path.home()),
            file_types=(f"Documentos e imagens ({tipos})",),
        )
        if not escolha:
            return {"cancelado": True}
        caminho = Path(caminho_unico(escolha))
        md.conferir_arquivo(caminho)
        return {"caminho": str(caminho), "nome": caminho.name, "titulo": md.titulo_do_arquivo(caminho.name)}

    @seguro
    def modelos_salvar(self, dados: dict):
        """Modelo novo (título + arquivo) ou alterar o título e, se quiser, trocar o arquivo."""
        if self._armazem.bloqueio:
            return {"erro": self._armazem.bloqueio}
        modelo_id = dados.get("id") or None
        origem = Path(dados["caminho"]) if dados.get("caminho") else None
        if modelo_id is None and origem is None:
            return {"erro": "Escolha o arquivo do modelo."}
        extensao = md.conferir_arquivo(origem) if origem else None
        pasta = self._pasta_modelos()
        pasta.mkdir(parents=True, exist_ok=True)

        with self._modelos() as modelos:
            if modelo_id is None:
                modelo = md.novo(modelos, dados.get("titulo", ""), extensao, origem.name, date.today())
            else:
                modelo = md.buscar(modelos, modelo_id)
                modelo["titulo"] = md.conferir_titulo(modelos, dados.get("titulo", ""), ignorar=modelo_id)
            if origem:
                antigo = modelo["arquivo"] if modelo_id else None
                modelo["arquivo"] = f"{modelo['id']}{extensao}"
                modelo["nome_original"] = origem.name
                # Copia antes de gravar a lista: se a cópia falhar, nada muda.
                temporario = pasta / f"{modelo['arquivo']}.tmp"
                shutil.copyfile(origem, temporario)
                os.replace(temporario, pasta / modelo["arquivo"])
                if antigo and antigo != modelo["arquivo"]:
                    (pasta / antigo).unlink(missing_ok=True)
        return {**self._vista_modelos(), "id": modelo["id"]}

    @seguro
    def modelos_apagar(self, modelo_id: str):
        """Tira da lista. O arquivo fica até a próxima vez que o OMAC abrir (para o desfazer)."""
        with self._modelos() as modelos:
            modelo = md.buscar(modelos, modelo_id)
            posicao = modelos.index(modelo)
            modelos.remove(modelo)
        return {**self._vista_modelos(), "apagado": modelo, "posicao": posicao}

    @seguro
    def modelos_restaurar(self, modelo: dict, posicao: int):
        with self._modelos() as modelos:
            if not any(m["id"] == modelo["id"] for m in modelos):
                md.conferir_titulo(modelos, modelo["titulo"])
                modelos.insert(min(int(posicao), len(modelos)), esquema.completar_item(esquema.MODELOS, modelo))
        return self._vista_modelos()

    @seguro
    def modelos_imprimir(self, modelo_id: str):
        modelo = md.buscar(self._lista_de_modelos(), modelo_id)
        return {"impresso": sistema.imprimir(self._caminho_do_modelo(modelo)), "titulo": modelo["titulo"]}

    @seguro
    def modelos_abrir(self, modelo_id: str):
        """Abre uma cópia (na pasta temporária): preencher o documento não muda o modelo."""
        modelo = md.buscar(self._lista_de_modelos(), modelo_id)
        origem = self._caminho_do_modelo(modelo)
        pasta = Path(tempfile.gettempdir()) / "OMAC" / "modelos"
        pasta.mkdir(parents=True, exist_ok=True)
        nome = md.nome_para_salvar(modelo)
        destino = pasta / nome
        n = 2
        while True:
            try:
                shutil.copyfile(origem, destino)
                break
            except PermissionError:  # a cópia anterior ainda está aberta no Word
                destino = pasta / f"{Path(nome).stem} ({n}){Path(nome).suffix}"
                n += 1
                if n > 50:
                    raise
        sistema.abrir(destino)
        return {}

    @seguro
    def modelos_baixar(self, modelo_id: str):
        modelo = md.buscar(self._lista_de_modelos(), modelo_id)
        origem = self._caminho_do_modelo(modelo)
        extensao = origem.suffix.lower().lstrip(".")
        destino = self._dialogo_salvar(md.nome_para_salvar(modelo), extensao, f"Arquivo {md.tipo(modelo)}",
                                       str(Path.home() / "Downloads"))
        if destino is None:
            return {"cancelado": True}
        try:
            shutil.copyfile(origem, destino)
        except PermissionError:
            return {"erro": "Não consegui salvar: o arquivo está aberto em outro programa? Feche e tente de novo."}
        return {"caminho": str(destino)}

    # --- Widget do Início --------------------------------------------------------------------

    @widget("modelos", "Modelos", ordem=80)
    def _widget_modelos(self, hoje: date) -> dict:
        return {"modelos": [{"id": m["id"], "titulo": m["titulo"], "tipo": md.tipo(m)}
                            for m in md.em_ordem(self._lista_de_modelos())]}
