"""Cadastro dos pacientes de ortodontia, a situação de cada um, o confere e o histórico.

O confere não precisa ser apagado todo dia 1: guarda a data em que foi marcado e só
vale no mês dessa data. Assim ele recomeça mesmo se o app estiver fechado no dia 1.

"Atendido" fica guardado mês a mês ({"AAAA-MM": dia em que foi marcado}), e é isso
que monta o histórico: em cada mês o paciente veio, não veio, estava de alta, ou
ainda não era (ou não é mais) paciente.
"""

from __future__ import annotations

import uuid
from datetime import date

from .. import texto as tx
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
    "atendidos": {},  # "AAAA-MM" → dia em que foi marcado como atendido
    "altas": [],  # altas que já acabaram: [{"inicio", "fim"}], para o histórico
    "criado_em": "",  # primeiro mês do histórico
}

VEIO = "veio"
NAO_VEIO = "nao_veio"
FALTA_VIR = "falta_vir"  # mês atual, ainda sem marcar
DE_ALTA = "alta"
FORA = ""  # antes de virar paciente, depois de finalizar, ou mês que ainda não chegou


class PacienteInvalido(ValueError):
    """Faltou o nome, o nome já existe, ou um valor, data ou telefone não dá para entender."""


def completar(paciente: dict) -> dict:
    # Cópia das listas e dicionários: o padrão não pode ser alterado por um paciente.
    return {**_CAMPOS_PADRAO, "atendidos": {}, "altas": [], **paciente}


def registrar_inicio(paciente: dict, hoje: date) -> None:
    """Paciente de uma versão anterior começa o histórico no dia em que esta abriu."""
    if not paciente["criado_em"]:
        paciente["criado_em"] = hoje.isoformat()


def valor_em_centavos(texto) -> int | None:
    try:
        return tx.valor_em_centavos(texto)
    except tx.ValorInvalido as e:
        raise PacienteInvalido("Confira o valor da manutenção: use algo como 250,00.") from e


_nome_limpo = tx.nome_limpo


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


def _guardar_alta(paciente: dict) -> None:
    """A alta que acaba vai para o histórico, senão aqueles meses viram "não veio"."""
    if paciente["alta_inicio"]:
        paciente["altas"] = [*paciente["altas"], {"inicio": paciente["alta_inicio"], "fim": paciente["alta_fim"]}]


def voltar_ao_tratamento(paciente: dict) -> None:
    _guardar_alta(paciente)
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
    hoje = hoje or date.today()
    novo.update(_campos_de_situacao(dados, {}, hoje))
    novo = completar({**novo, "id": uuid.uuid4().hex, "criado_em": hoje.isoformat()})
    pacientes.append(novo)
    return novo


def alterar(pacientes: list[dict], paciente_id: str, dados: dict, hoje: date) -> dict:
    paciente = buscar(pacientes, paciente_id)
    # Valida tudo antes: um erro na alta não pode deixar o nome já trocado.
    novos = _validar(dados)
    _conferir_nome(pacientes, novos["nome"], ignorar=paciente_id)
    novos.update(_campos_de_situacao(dados, paciente, hoje))
    if paciente["alta_inicio"] and novos["alta_inicio"] != paciente["alta_inicio"]:
        _guardar_alta(paciente)
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


# --- Atendido e histórico ----------------------------------------------------------------


def chave_do_mes(ano: int, mes: int) -> str:
    return f"{ano:04d}-{mes:02d}"


def meses_ate(ano: int, mes: int, quantos: int) -> list[tuple[int, int]]:
    """Os `quantos` meses que terminam em (ano, mês), do mais antigo ao mais novo."""
    total = ano * 12 + mes - 1
    return [((t // 12), t % 12 + 1) for t in range(total - quantos + 1, total + 1)]


def atendido_no_mes(paciente: dict, hoje: date) -> bool:
    return chave_do_mes(hoje.year, hoje.month) in paciente["atendidos"]


def marcar_atendido(paciente: dict, mes: str, atendido: bool, hoje: date) -> None:
    """`mes` é "AAAA-MM". Dá para marcar um mês que passou, se esqueceu na hora."""
    if mes > hoje.isoformat()[:7]:
        raise PacienteInvalido("Esse mês ainda não chegou.")
    atendidos = {**paciente["atendidos"]}
    if atendido:
        atendidos[mes] = hoje.isoformat()
    else:
        atendidos.pop(mes, None)
    paciente["atendidos"] = atendidos


def _inicio_do_historico(paciente: dict) -> str:
    """Primeiro mês do histórico: o do cadastro, ou um atendimento marcado antes dele."""
    meses = [paciente["criado_em"][:7], *paciente["atendidos"]]
    meses = [m for m in meses if m]
    return min(meses) if meses else ""


def _de_alta(paciente: dict, mes: str) -> bool:
    altas = [*paciente["altas"]]
    if paciente["alta_inicio"]:
        altas.append({"inicio": paciente["alta_inicio"], "fim": paciente["alta_fim"]})
    # Quem veio no mês da alta já aparece como "veio": isso é conferido antes.
    return any(a["inicio"][:7] <= mes <= a["fim"][:7] for a in altas)


def situacao_no_mes(paciente: dict, ano: int, mes: int, hoje: date) -> str:
    chave = chave_do_mes(ano, mes)
    if chave in paciente["atendidos"]:
        return VEIO
    atual = hoje.isoformat()[:7]
    inicio = _inicio_do_historico(paciente)
    if chave > atual or not inicio or chave < inicio:
        return FORA
    if paciente["finalizado_em"] and chave > paciente["finalizado_em"][:7]:
        return FORA
    if _de_alta(paciente, chave):
        return DE_ALTA
    return FALTA_VIR if chave == atual else NAO_VEIO


def historico_do_paciente(paciente: dict, hoje: date) -> dict:
    """Todos os meses desde o começo do histórico até hoje, do mais novo ao mais antigo."""
    inicio = _inicio_do_historico(paciente) or hoje.isoformat()[:7]
    ano, mes = int(inicio[:4]), int(inicio[5:7])
    quantos = (hoje.year * 12 + hoje.month) - (ano * 12 + mes) + 1
    meses = [{"ano": a, "mes": m, "situacao": situacao_no_mes(paciente, a, m, hoje)}
             for a, m in meses_ate(hoje.year, hoje.month, max(quantos, 1))]
    meses = [m for m in meses if m["situacao"] != FORA or m["mes"] == hoje.month and m["ano"] == hoje.year]
    contados = [m for m in meses if m["situacao"] in (VEIO, NAO_VEIO)]
    return {
        "meses": list(reversed(meses)),
        "veio": sum(m["situacao"] == VEIO for m in contados),
        # O mês atual só entra na conta depois de marcado: ele ainda não acabou.
        "esperados": len(contados),
    }
