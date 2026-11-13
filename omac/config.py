"""Configurações do usuário, salvas em %APPDATA%\\OMAC (ou ~/.config/omac)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from . import sistema
from .armazem import salvar_json

PADRAO = {
    "pasta_notas": "",
    "pasta_extratos": "",
    "visual": "bonito",  # "bonito" (liquid glass) | "otimizado"
    "tema": "sistema",  # "sistema" | "claro" | "escuro"
    "escala_fonte": 1.0,  # 1.0 a 2.0
    "alto_contraste": False,
    "reduzir_movimento": False,
    "formato": "xlsx",  # "xlsx" | "csv"
    "pasta_saida": "",
    "assistente_nome": "",  # assina as mensagens: "*Assistente Fulano:*"
    "whatsapp_destino": "app",  # "app" (instalado) | "web" (navegador)
    "lembrete_nome": "",  # quem recebe os lembretes de contas
    "lembrete_telefone": "",
    "lembrete_fechamento_dia": 1,  # dia do mês para lembrar do fechamento; 0 = desligado
    "chave_pix": "",  # vai na mensagem de cobrança da manutenção
    "tratamentos": ["Limpeza", "Manutenção", "Botox"],  # sugestões da ficha de pagamentos
    "avisos_recolhidos": [],  # faixas minimizadas: "notas", "extrato"
    "atualizacao_automatica": True,  # procura versão nova ao abrir (instalar é sempre opcional)
    "atualizacao_adiada_em": "",  # dia em que a pessoa clicou em "Agora não"
}

_VALIDOS = {
    "visual": {"bonito", "otimizado"},
    "tema": {"sistema", "claro", "escuro"},
    "formato": {"xlsx", "csv"},
    "whatsapp_destino": {"app", "web"},
}


def pasta_dados() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        return base / "OMAC"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "omac"


def caminho_cache() -> Path:
    return pasta_dados() / "cache-notas.json"


def caminho_whatsapp() -> Path:
    return pasta_dados() / "whatsapp.json"


def caminho_regras() -> Path:
    return pasta_dados() / "regras-extrato.json"


def caminho_agendamentos() -> Path:
    return pasta_dados() / "agendamentos.json"


def caminho_pagamentos() -> Path:
    return pasta_dados() / "pagamentos.json"


def carregar() -> dict:
    cfg = dict(PADRAO)
    arquivo = pasta_dados() / "config.json"
    try:
        cfg.update(json.loads(arquivo.read_text(encoding="utf-8")))
    except FileNotFoundError:
        # Primeira vez: em PC fraco já começa no modo otimizado.
        if sistema.pc_modesto():
            cfg["visual"] = "otimizado"
    except (OSError, ValueError):
        pass
    return normalizar(cfg)


def salvar(cfg: dict) -> dict:
    cfg = normalizar(cfg)
    salvar_json(pasta_dados() / "config.json", cfg)
    return cfg


def normalizar(cfg: dict) -> dict:
    limpo = {k: cfg.get(k, v) for k, v in PADRAO.items()}
    for chave, opcoes in _VALIDOS.items():
        if limpo[chave] not in opcoes:
            limpo[chave] = PADRAO[chave]
    try:
        limpo["escala_fonte"] = min(2.0, max(1.0, float(limpo["escala_fonte"])))
    except (TypeError, ValueError):
        limpo["escala_fonte"] = 1.0
    for chave in ("alto_contraste", "reduzir_movimento", "atualizacao_automatica"):
        limpo[chave] = bool(limpo[chave])
    for chave in ("pasta_notas", "pasta_extratos", "pasta_saida",
                  "assistente_nome", "lembrete_nome", "lembrete_telefone", "chave_pix",
                  "atualizacao_adiada_em"):
        limpo[chave] = str(limpo[chave] or "")
    try:
        limpo["lembrete_fechamento_dia"] = min(28, max(0, int(limpo["lembrete_fechamento_dia"])))
    except (TypeError, ValueError):
        limpo["lembrete_fechamento_dia"] = PADRAO["lembrete_fechamento_dia"]
    limpo["tratamentos"] = _lista_de_nomes(limpo["tratamentos"], PADRAO["tratamentos"])
    recolhidos = limpo["avisos_recolhidos"]
    limpo["avisos_recolhidos"] = [str(r) for r in recolhidos] if isinstance(recolhidos, list) else []
    return limpo


def _lista_de_nomes(valor, padrao: list[str]) -> list[str]:
    """Sem nomes vazios nem repetidos (ignorando maiúsculas e acentos). Lista vazia é escolha da pessoa."""
    from .texto import nome_limpo, normalizar

    if not isinstance(valor, list):
        return list(padrao)
    vistos, limpos = set(), []
    for item in valor:
        nome = nome_limpo(item)
        if nome and normalizar(nome) not in vistos:
            vistos.add(normalizar(nome))
            limpos.append(nome)
    return limpos
