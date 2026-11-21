"""Configurações do usuário, salvas em %APPDATA%\\OMAC (ou ~/.config/omac)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from . import sistema
from .dados.arquivo import DadosIlegiveis, ler_json, salvar_json

VERSAO = 2  # 2 = 1.6.0 (sem o telefone dos lembretes, que virou contato)

PADRAO = {
    "versao": VERSAO,
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
    "colar_sozinho": False,  # experimental: o OMAC aperta Ctrl+V na conversa (só o app do WhatsApp)
    "lembrete_fechamento_dia": 1,  # dia do mês para lembrar do fechamento; 0 = desligado
    "chave_pix": "",  # vai na mensagem de cobrança da manutenção
    "tratamentos": ["Limpeza", "Manutenção", "Botox"],  # sugestões da ficha de atendimentos
    "avisos_recolhidos": [],  # faixas minimizadas: "notas", "extrato"
    "atualizacao_automatica": True,  # procura versão nova ao abrir (instalar é sempre opcional)
    "atualizacao_adiada_em": "",  # dia em que a pessoa clicou em "Agora não"
    "site_nota": "",  # site onde a nota é emitida (botão na janela "Emitir nota")
    "ocultar_valores_minutos": 5,  # esconde os valores de novo depois de X minutos parado; 0 = não
    "abrir_em": "inicio",  # tela ao abrir: "inicio" | "notas"
    "inicio_cartoes": [],  # ordem e escolhas dos widgets do Início (vazio = padrão)
    # Backup
    "backup_pasta": "",
    "backup_automatico": False,
    "backup_frequencia": "semana",  # "dia" | "semana" | "mes"
    "backup_dia_semana": 0,  # 0 = segunda ... 6 = domingo
    "backup_dia_mes": 1,  # 1 a 28
    "backup_arquivos": False,  # guardar também as notas e os extratos
    "backup_ultimo": "",  # data e hora do último backup que deu certo
    "backup_erro": "",  # o que deu errado na última tentativa automática
}

_VALIDOS = {
    "visual": {"bonito", "otimizado"},
    "tema": {"sistema", "claro", "escuro"},
    "formato": {"xlsx", "csv"},
    "whatsapp_destino": {"app", "web"},
    "abrir_em": {"inicio", "notas"},
    "backup_frequencia": {"dia", "semana", "mes"},
}


def pasta_dados() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        return base / "OMAC"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "omac"


def caminho_cache() -> Path:
    return pasta_dados() / "cache-notas.json"


def caminho_regras() -> Path:
    return pasta_dados() / "regras-extrato.json"


def carregar() -> dict:
    cfg = dict(PADRAO)
    try:
        lidos = ler_json(pasta_dados() / "config.json", "As configurações")
    except DadosIlegiveis:
        lidos = {}  # configuração estragada: volta ao padrão (os dados ficam em outros arquivos)
    if lidos is None and sistema.pc_modesto():
        cfg["visual"] = "otimizado"  # primeira vez num PC fraco: já começa no modo otimizado
    cfg.update(lidos or {})
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
    limpo["versao"] = VERSAO
    for chave in ("alto_contraste", "reduzir_movimento", "atualizacao_automatica",
                  "backup_automatico", "backup_arquivos", "colar_sozinho"):
        limpo[chave] = bool(limpo[chave])
    for chave in ("pasta_notas", "pasta_extratos", "pasta_saida",
                  "assistente_nome", "chave_pix", "atualizacao_adiada_em", "site_nota",
                  "backup_pasta", "backup_ultimo", "backup_erro"):
        limpo[chave] = str(limpo[chave] or "")
    try:
        limpo["lembrete_fechamento_dia"] = min(28, max(0, int(limpo["lembrete_fechamento_dia"])))
    except (TypeError, ValueError):
        limpo["lembrete_fechamento_dia"] = PADRAO["lembrete_fechamento_dia"]
    limpo["ocultar_valores_minutos"] = _inteiro(limpo["ocultar_valores_minutos"], 0, 60, 5)
    limpo["backup_dia_semana"] = _inteiro(limpo["backup_dia_semana"], 0, 6, 0)
    limpo["backup_dia_mes"] = _inteiro(limpo["backup_dia_mes"], 1, 28, 1)
    limpo["tratamentos"] = _lista_de_nomes(limpo["tratamentos"], PADRAO["tratamentos"])
    limpo["inicio_cartoes"] = _cartoes(limpo["inicio_cartoes"])
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


def _inteiro(valor, menor: int, maior: int, padrao: int) -> int:
    try:
        return min(maior, max(menor, int(valor)))
    except (TypeError, ValueError):
        return padrao


def _cartoes(valor) -> list[dict]:
    """Só confere o formato. Quais widgets existem quem sabe é o Início (inicio/registro.py)."""
    escolhidos, vistos = [], set()
    for item in valor if isinstance(valor, list) else []:
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"] not in vistos:
            vistos.add(item["id"])
            escolhidos.append({"id": item["id"], "visivel": bool(item.get("visivel", True)),
                               "largo": bool(item.get("largo", False))})
    return escolhidos
