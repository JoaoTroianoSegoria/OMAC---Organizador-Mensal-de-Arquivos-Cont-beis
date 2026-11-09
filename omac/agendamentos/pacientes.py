"""Cadastro dos pacientes de ortodontia, a situação de cada um e o confere do mês.

O confere não precisa ser apagado todo dia 1: guarda a data em que foi marcado e só
vale no mês dessa data. Assim ele recomeça mesmo se o app estiver fechado no dia 1.
"""

from __future__ import annotations

import re
import uuid
from datetime import date
from decimal import Decimal

from ..texto import normalizar
from ..whatsapp.mensagens import TelefoneInvalido, normalizar_telefone

ATIVO = "ativo"
ALTA = "alta"
FINALIZADO = "finalizado"

PAPEIS = {"pai": "pai", "mae": "mãe"}

# Quem foi cadastrado numa versão anterior ganha os campos novos ao abrir.
_CAMPOS_PADRAO = {
    "telefone": "",
    "valor_centavos": None,
    "agendado_em": "",
    "finalizado_em": "",
    "alta_inicio": "",
    "alta_fim": "",
    "responsaveis": None,  # {"pai": {"nome", "telefone"}, "mae": {...}, "envia_para": "pai" | "mae"}
}


class PacienteInvalido(ValueError):
    """Faltou o nome, o nome já existe, ou um valor, data ou telefone não dá para entender."""


def completar(paciente: dict) -> dict:
    return {**_CAMPOS_PADRAO, **paciente}


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


def _nome_limpo(texto) -> str:
    return " ".join(str(texto or "").split())


def _telefone(texto) -> str:
    # O telefone pode ficar para depois: é pedido de novo na hora de mandar a mensagem.
    texto = str(texto or "").strip()
    return normalizar_telefone(texto) if texto else ""


def _validar_responsaveis(dados: dict | None) -> dict | None:
    if not dados:
        return None
    limpo = {}
    for papel, rotulo in PAPEIS.items():
        pessoa = dados.get(papel) or {}
        try:
            limpo[papel] = {"nome": _nome_limpo(pessoa.get("nome")), "telefone": _telefone(pessoa.get("telefone"))}
        except TelefoneInvalido as e:
            raise PacienteInvalido(f"Telefone do(a) {rotulo}: {e}") from e
    envia_para = dados.get("envia_para")
    if envia_para not in PAPEIS:
        raise PacienteInvalido("Escolha para quem vão as mensagens: pai ou mãe.")
    if not limpo[envia_para]["nome"]:
        raise PacienteInvalido(f"As mensagens vão para o(a) {PAPEIS[envia_para]}: preencha o nome dele(a).")
    return {**limpo, "envia_para": envia_para}


def _validar(dados: dict) -> dict:
    nome = _nome_limpo(dados.get("nome"))
    if not nome:
        raise PacienteInvalido("Diga o nome do paciente.")
    return {
        "nome": nome,
        "telefone": _telefone(dados.get("telefone")),
        "valor_centavos": valor_em_centavos(dados.get("valor")),
        "responsaveis": _validar_responsaveis(dados.get("responsaveis")),
    }


# --- Situação ------------------------------------------------------------------------


def situacao(paciente: dict) -> str:
    if paciente["finalizado_em"]:
        return FINALIZADO
    return ALTA if paciente["alta_inicio"] else ATIVO


def _data(texto, falta: str) -> date:
    if not texto:
        raise PacienteInvalido(falta)
    try:
        return date.fromisoformat(str(texto))
    except ValueError as e:
        raise PacienteInvalido(f"{falta} A data informada não existe.") from e


def _campos_de_situacao(dados: dict, atual: dict, hoje: date) -> dict:
    nova = dados.get("situacao", ATIVO)
    if nova == ALTA:
        inicio = _data(dados.get("alta_inicio"), "Preencha o dia em que a alta foi dada.")
        fim = _data(dados.get("alta_fim"), "Preencha o dia em que a alta acaba.")
        if fim < inicio:
            raise PacienteInvalido("O fim da alta não pode ser antes do dia em que ela foi dada.")
        return {"alta_inicio": inicio.isoformat(), "alta_fim": fim.isoformat(), "finalizado_em": ""}
    if nova == FINALIZADO:
        # Quem já estava finalizado mantém a data original.
        return {"alta_inicio": "", "alta_fim": "", "finalizado_em": atual.get("finalizado_em") or hoje.isoformat()}
    if nova == ATIVO:
        return {"alta_inicio": "", "alta_fim": "", "finalizado_em": ""}
    raise PacienteInvalido("Escolha a situação do paciente.")


def alta_terminou(paciente: dict, hoje: date) -> bool:
    return situacao(paciente) == ALTA and paciente["alta_fim"] < hoje.isoformat()


def voltar_ao_tratamento(paciente: dict) -> None:
    paciente.update(alta_inicio="", alta_fim="", finalizado_em="")


# --- Para quem vai a mensagem --------------------------------------------------------


def destino(paciente: dict) -> dict:
    """{"nome", "telefone", "papel"}: o responsável escolhido ou o próprio paciente."""
    responsaveis = paciente["responsaveis"]
    if not responsaveis:
        return {"nome": paciente["nome"], "telefone": paciente["telefone"], "papel": ""}
    papel = responsaveis["envia_para"]
    return {**responsaveis[papel], "papel": PAPEIS[papel]}


def guardar_telefone(paciente: dict, telefone: str) -> None:
    responsaveis = paciente["responsaveis"]
    if responsaveis:
        responsaveis[responsaveis["envia_para"]]["telefone"] = telefone
    else:
        paciente["telefone"] = telefone


# --- Lista ---------------------------------------------------------------------------


def _conferir_nome(pacientes: list[dict], nome: str, ignorar: str | None = None) -> None:
    onde = {ATIVO: "na lista", ALTA: "em Alta temporária", FINALIZADO: "nos Finalizados"}
    for p in pacientes:
        if p["id"] != ignorar and normalizar(p["nome"]) == normalizar(nome):
            raise PacienteInvalido(
                f"Já existe “{p['nome']}” {onde[situacao(p)]}. Se for outra pessoa, coloque o sobrenome para diferenciar."
            )


def buscar(pacientes: list[dict], paciente_id: str) -> dict:
    for p in pacientes:
        if p["id"] == paciente_id:
            return p
    raise PacienteInvalido("Não encontrei esse paciente. Ele pode ter sido excluído.")


def adicionar(pacientes: list[dict], dados: dict, hoje: date | None = None) -> dict:
    novo = _validar(dados)
    _conferir_nome(pacientes, novo["nome"])
    novo.update(_campos_de_situacao(dados, {}, hoje or date.today()))
    novo = completar({**novo, "id": uuid.uuid4().hex})
    pacientes.append(novo)
    return novo


def alterar(pacientes: list[dict], paciente_id: str, dados: dict, hoje: date) -> dict:
    paciente = buscar(pacientes, paciente_id)
    # Valida tudo antes: um erro na alta não pode deixar o nome já trocado.
    novos = _validar(dados)
    _conferir_nome(pacientes, novos["nome"], ignorar=paciente_id)
    novos.update(_campos_de_situacao(dados, paciente, hoje))
    paciente.update(novos)
    return paciente


def restaurar(pacientes: list[dict], paciente: dict) -> None:
    """Desfaz uma exclusão: o paciente volta como estava, com o confere do mês."""
    if any(p["id"] == paciente.get("id") for p in pacientes):
        return
    _conferir_nome(pacientes, paciente["nome"])
    pacientes.append(completar(paciente))


def agendado_no_mes(paciente: dict, hoje: date) -> bool:
    return paciente["agendado_em"][:7] == hoje.isoformat()[:7]


def marcar_agendado(paciente: dict, agendado: bool, hoje: date) -> None:
    paciente["agendado_em"] = hoje.isoformat() if agendado else ""
