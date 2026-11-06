/* OMAC — módulo de agendamentos: pacientes de ortodontia, mensagens e confere do mês. */
"use strict";

const agenda = {
  aba: "ativos",
  filtro: "todos",
  ano: 0,
  mes: 0,
  ativos: [],
  finalizados: [],
  editando: null, // paciente aberto na janela de alteração
  mensagem: null, // dados da janela de mensagem
};

modulos.agendamentos = {
  aoMostrar: carregarAgenda,
  carregar: carregarAgenda,
  ligar() {
    $("#form-paciente").addEventListener("submit", salvarPaciente);
    $("#form-ag-mensagem").addEventListener("submit", enviarMensagem);
  },
};

const pacienteAgenda = (alvo) =>
  [...agenda.ativos, ...agenda.finalizados].find((p) => p.id === alvo.dataset.id);

Object.assign(acoes, {
  "ag-aba": (alvo) => { agenda.aba = alvo.dataset.aba; desenharAgenda(); },
  "ag-filtro": (alvo) => { agenda.filtro = alvo.dataset.filtro; desenharAgenda(); },
  "ag-novo": () => abrirPaciente(null),
  "ag-editar": (alvo) => abrirPaciente(pacienteAgenda(alvo)),
  "ag-fechar-paciente": () => $("#ag-paciente").close(),
  "ag-alternar-finalizado": (alvo) => alvo.setAttribute("aria-checked", String(alvo.getAttribute("aria-checked") !== "true")),
  "ag-excluir": excluirPaciente,
  "ag-marcar": marcarAgendado,
  "ag-mensagem": (alvo) => abrirMensagem(alvo.dataset.id),
  "ag-tipo": (alvo) => escolherMensagem(alvo.dataset.tipo),
  "ag-fechar-mensagem": () => $("#ag-mensagem").close(),
  "ag-abrir-config": () => {
    $("#ag-mensagem").close();
    mostrarView("config");
    $("#cfg-pix").focus();
  },
});

/* ---------- Lista ---------- */

async function carregarAgenda() {
  aplicarAgenda(await api().agendamentos_listar());
}

function aplicarAgenda(r) {
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  Object.assign(agenda, { ano: r.ano, mes: r.mes, ativos: r.ativos, finalizados: r.finalizados });
  desenharAgenda();
}

function desenharAgenda() {
  $$("#ag-abas .escolha").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.aba === agenda.aba)));
  $("#ag-ativos").hidden = agenda.aba !== "ativos";
  $("#ag-finalizados").hidden = agenda.aba !== "finalizados";
  $("#ag-mes").textContent = `${MESES[agenda.mes - 1]} de ${agenda.ano}`;
  $("#ag-qtd-ativos").textContent = agenda.ativos.length ? `(${agenda.ativos.length})` : "";
  $("#ag-qtd-finalizados").textContent = agenda.finalizados.length ? `(${agenda.finalizados.length})` : "";
  desenharAtivos();
  desenharFinalizados();
}

function celula(texto, classe = "") {
  return Object.assign(document.createElement("td"), { className: classe, textContent: texto });
}

function celulaTelefone(p) {
  return p.telefone ? celula(telefoneBR(p.telefone), "c-telefone") : celula("Sem telefone", "c-telefone ag-sem-dado");
}

function celulaAcoes(p) {
  const td = document.createElement("td");
  td.className = "c-acoes-regra";
  td.append(botaoIcone("ag-mensagem", "i-whats", `Mandar mensagem para ${p.nome}`, { id: p.id }),
    botaoIcone("ag-editar", "i-lapis", `Alterar ${p.nome}`, { id: p.id }));
  return td;
}

function desenharAtivos() {
  const feitos = agenda.ativos.filter((p) => p.agendado).length;
  const vazio = agenda.ativos.length === 0;
  $("#ag-feitos").textContent = String(feitos);
  $("#ag-faltam").textContent = String(agenda.ativos.length - feitos);
  $("#ag-resumo").hidden = vazio;
  $("#ag-filtros").hidden = vazio;
  $("#ag-ativos-caixa").hidden = vazio;
  $("#ag-dica").hidden = vazio;
  $("#ag-ativos-vazio").hidden = !vazio;
  $$("#ag-filtros .escolha").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.filtro === agenda.filtro)));

  const visiveis = agenda.ativos.filter((p) =>
    agenda.filtro === "todos" || p.agendado === (agenda.filtro === "agendados"));
  if (visiveis.length === 0) {
    const tr = document.createElement("tr");
    const td = celula(agenda.filtro === "pendentes"
      ? "Todos os pacientes já foram conferidos neste mês."
      : "Nenhum paciente marcado como agendado neste mês.", "ag-nada");
    td.colSpan = 5;
    tr.append(td);
    $("#ag-ativos-corpo").replaceChildren(tr);
    return;
  }
  $("#ag-ativos-corpo").replaceChildren(...visiveis.map((p) => {
    const tr = document.createElement("tr");
    const tdConfere = document.createElement("td");
    tdConfere.className = "c-confere";
    const caixa = Object.assign(document.createElement("input"), { type: "checkbox", className: "confere", checked: p.agendado });
    caixa.dataset.acao = "ag-marcar";
    caixa.dataset.id = p.id;
    caixa.setAttribute("aria-label", `${p.nome} já tem a manutenção agendada neste mês`);
    tdConfere.append(caixa);
    tr.append(tdConfere, celula(p.nome), celulaTelefone(p),
      p.valor_centavos == null ? celula("Sem valor", "c-valor ag-sem-dado") : celula(real.format(p.valor_centavos / 100), "c-valor"),
      celulaAcoes(p));
    return tr;
  }));
}

function desenharFinalizados() {
  const vazio = agenda.finalizados.length === 0;
  $("#ag-finalizados-caixa").hidden = vazio;
  $("#ag-finalizados-vazio").hidden = !vazio;
  $("#ag-finalizados-corpo").replaceChildren(...agenda.finalizados.map((p) => {
    const tr = document.createElement("tr");
    tr.append(celula(p.nome), celulaTelefone(p), celula(dataBR(p.finalizado_em), "c-data"), celulaAcoes(p));
    return tr;
  }));
}

async function marcarAgendado(caixa) {
  const r = await api().agendamentos_marcar(caixa.dataset.id, caixa.checked);
  if (r.erro) {
    caixa.checked = !caixa.checked;
    return mostrarToast(r.erro, { erro: true });
  }
  aplicarAgenda(r);
}

/* ---------- Novo paciente / alterar paciente ---------- */

function abrirPaciente(p) {
  agenda.editando = p;
  $("#ag-paciente-titulo").textContent = p ? "Alterar paciente" : "Novo paciente";
  $("#ag-nome").value = p ? p.nome : "";
  $("#ag-telefone").value = p && p.telefone ? telefoneBR(p.telefone) : "";
  $("#ag-valor").value = p && p.valor_centavos != null ? (p.valor_centavos / 100).toFixed(2).replace(".", ",") : "";
  $("#ag-finalizado").setAttribute("aria-checked", String(!!(p && p.finalizado_em)));
  $("#ag-finalizado-linha").hidden = !p;
  $("#ag-excluir").hidden = !p;
  $("#ag-paciente-erro").hidden = true;
  $("#ag-paciente").showModal();
  $("#ag-nome").focus();
}

async function salvarPaciente(e) {
  e.preventDefault();
  const anterior = agenda.editando;
  const finalizado = $("#ag-finalizado").getAttribute("aria-checked") === "true";
  const nome = $("#ag-nome").value;
  const r = await api().agendamentos_salvar({
    nome,
    telefone: $("#ag-telefone").value,
    valor: $("#ag-valor").value,
    finalizado,
  }, anterior ? anterior.id : null);
  if (r.erro) {
    // Um aviso comum ficaria escondido atrás da janela.
    $("#ag-paciente-erro").textContent = r.erro;
    $("#ag-paciente-erro").hidden = false;
    return;
  }
  $("#ag-paciente").close();
  aplicarAgenda(r);
  if (anterior && finalizado && !anterior.finalizado_em) mostrarToast(`${nome.trim()} foi para Finalizados.`);
  if (anterior && !finalizado && anterior.finalizado_em) mostrarToast(`${nome.trim()} voltou para Em tratamento.`);
}

async function excluirPaciente() {
  const r = await api().agendamentos_apagar(agenda.editando.id);
  $("#ag-paciente").close();
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  aplicarAgenda(r);
  mostrarToast(`Paciente excluído: ${r.apagado.nome}`, {
    acoes: [["Desfazer", async () => aplicarAgenda(await api().agendamentos_restaurar(r.apagado))]],
  });
}

/* ---------- Mensagem ---------- */

async function abrirMensagem(id) {
  const r = await api().agendamentos_preparar_mensagens(id);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  agenda.mensagem = r;
  $("#ag-mensagem-titulo").textContent = `Mensagem para ${r.nome}`;
  $("#ag-msg-telefone").value = r.telefone ? telefoneBR(r.telefone) : "";
  $("#ag-mensagem-erro").hidden = true;
  escolherMensagem("agendar");
  $("#ag-mensagem").showModal();
  (r.telefone ? $("#ag-msg-texto") : $("#ag-msg-telefone")).focus();
}

function escolherMensagem(tipo) {
  const texto = agenda.mensagem.mensagens[tipo];
  $$(".ag-tipos .escolha").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.tipo === tipo)));
  $("#ag-msg-texto").value = texto;
  // Sem chave Pix não há cobrança para mandar.
  $("#ag-sem-pix").hidden = texto !== "";
  $("#ag-msg-texto-campo").hidden = texto === "";
  $("#ag-enviar").disabled = texto === "";
}

async function enviarMensagem(e) {
  e.preventDefault();
  const r = await api().agendamentos_enviar(agenda.mensagem.id, $("#ag-msg-telefone").value, $("#ag-msg-texto").value);
  if (r.erro) {
    $("#ag-mensagem-erro").textContent = r.erro;
    $("#ag-mensagem-erro").hidden = false;
    return;
  }
  $("#ag-mensagem").close();
  aplicarAgenda(r);
  mostrarToast("Conversa aberta no WhatsApp. É só conferir e enviar.");
}
