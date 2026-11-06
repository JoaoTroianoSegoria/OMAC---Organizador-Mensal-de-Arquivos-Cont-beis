"""Cadastro dos pacientes de ortodontia e o confere do mês.

O confere não precisa ser apagado todo dia 1: guarda a data em que foi marcado e só
vale no mês dessa data. Assim ele recomeça mesmo se o app estiver fechado no dia 1.
"""

from __future__ import annotations

import re
import uuid
from datetime import date
from decimal import Decimal

from ..texto import normalizar
from ..whatsapp.mensagens import normalizar_telefone


class PacienteInvalido(ValueError):
    """Faltou o nome, o nome já existe ou o valor não dá para entender."""


def valor_em_centavos(texto) -> int | None:
    """Aceita 250 · 250,5 · 250,00 · 1.250,00 · R$ 250. Vazio quer dizer "sem valor"."""
    bruto = re.sub(r"(?i)r\$|\s", "", str(texto or ""))
    if not bruto:
        return None
    if re.fullmatch(r"\d{1,3}(\.\d{3})*(,\d{1,2})?", bruto) or re.fullmatch(r"\d+(,\d{1,2})?", bruto):
        numero = bruto.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d+\.\d{1,2}", bruto):  # 250.50, como vem de uma calculadora
        numero = bruto
    else:
        raise PacienteInvalido("Confira o valor da manutenção: use algo como 250,00.")
    return int(Decimal(numero) * 100)


def _validar(dados: dict) -> dict:
    nome = " ".join(str(dados.get("nome", "")).split())
    if not nome:
        raise PacienteInvalido("Diga o nome do paciente.")
    telefone = str(dados.get("telefone") or "").strip()
    return {
        "nome": nome,
        # O telefone pode ficar para depois: é pedido de novo na hora de mandar a mensagem.
        "telefone": normalizar_telefone(telefone) if telefone else "",
        "valor_centavos": valor_em_centavos(dados.get("valor")),
    }


def _conferir_nome(pacientes: list[dict], nome: str, ignorar: str | None = None) -> None:
    for p in pacientes:
        if p["id"] != ignorar and normalizar(p["nome"]) == normalizar(nome):
            onde = "nos Finalizados" if p["finalizado_em"] else "na lista"
            raise PacienteInvalido(
                f"Já existe “{p['nome']}” {onde}. Se for outra pessoa, coloque o sobrenome para diferenciar."
            )


def buscar(pacientes: list[dict], paciente_id: str) -> dict:
    for p in pacientes:
        if p["id"] == paciente_id:
            return p
    raise PacienteInvalido("Não encontrei esse paciente. Ele pode ter sido excluído.")


def adicionar(pacientes: list[dict], dados: dict) -> dict:
    novo = _validar(dados)
    _conferir_nome(pacientes, novo["nome"])
    novo.update(id=uuid.uuid4().hex, agendado_em="", finalizado_em="")
    pacientes.append(novo)
    return novo


def alterar(pacientes: list[dict], paciente_id: str, dados: dict, hoje: date) -> dict:
    paciente = buscar(pacientes, paciente_id)
    novos = _validar(dados)
    _conferir_nome(pacientes, novos["nome"], ignorar=paciente_id)
    paciente.update(novos)
    if dados.get("finalizado"):
        # Quem já estava finalizado mantém a data original.
        paciente["finalizado_em"] = paciente["finalizado_em"] or hoje.isoformat()
    else:
        paciente["finalizado_em"] = ""
    return paciente


def restaurar(pacientes: list[dict], paciente: dict) -> None:
    """Desfaz uma exclusão: o paciente volta como estava, com o confere do mês."""
    if any(p["id"] == paciente.get("id") for p in pacientes):
        return
    _conferir_nome(pacientes, paciente["nome"])
    pacientes.append(paciente)


def agendado_no_mes(paciente: dict, hoje: date) -> bool:
    return paciente["agendado_em"][:7] == hoje.isoformat()[:7]


def marcar_agendado(paciente: dict, agendado: bool, hoje: date) -> None:
    paciente["agendado_em"] = hoje.isoformat() if agendado else ""
