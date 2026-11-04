"""Configurações do usuário, salvas em %APPDATA%\\OMAC (ou ~/.config/omac)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from . import sistema

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
    arquivo = pasta_dados() / "config.json"
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
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
    for chave in ("alto_contraste", "reduzir_movimento"):
        limpo[chave] = bool(limpo[chave])
    for chave in ("pasta_notas", "pasta_extratos", "pasta_saida",
                  "assistente_nome", "lembrete_nome", "lembrete_telefone"):
        limpo[chave] = str(limpo[chave] or "")
    try:
        limpo["lembrete_fechamento_dia"] = min(28, max(0, int(limpo["lembrete_fechamento_dia"])))
    except (TypeError, ValueError):
        limpo["lembrete_fechamento_dia"] = PADRAO["lembrete_fechamento_dia"]
    return limpo
