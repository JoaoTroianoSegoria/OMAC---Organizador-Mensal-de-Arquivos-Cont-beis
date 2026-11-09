/* OMAC — módulo de agendamentos: pacientes de ortodontia, responsáveis, altas e confere do mês. */
"use strict";

const agenda = {
  aba: "ativos",
  filtro: "todos",
  ano: 0,
  mes: 0,
  ativos: [],
  altas: [],
  finalizados: [],
  editando: null, // paciente aberto na janela de alteração
  situacao: "ativo", // escolhida na janela de paciente
  enviaPara: "mae", // escolhida na janela de paciente
  mensagem: null, // dados da janela de mensagem
};

const NOMES_DAS_ABAS = { ativo: "Em tratamento", alta: "Alta temporária", finalizado: "Finalizados" };

modulos.agendamentos = {
  aoMostrar: carregarAgenda,
  carregar: carregarAgenda,
  ligar() {
    $("#form-paciente").addEventListener("submit", salvarPaciente);
    $("#form-ag-mensagem").addEventListener("submit", enviarMensagem);
    $("#ag-tem-responsaveis").addEventListener("change", mostrarResponsaveis);
  },
};

const pacienteAgenda = (alvo) =>
  [...agenda.ativos, ...agenda.altas, ...agenda.finalizados].find((p) => p.id === alvo.dataset.id);

Object.assign(acoes, {
  "ag-aba": (alvo) => { agenda.aba = alvo.dataset.aba; desenharAgenda(); },
  "ag-filtro": (alvo) => { agenda.filtro = alvo.dataset.filtro; desenharAgenda(); },
  "ag-novo": () => abrirPaciente(null),
  "ag-editar": (alvo) => abrirPaciente(pacienteAgenda(alvo)),
  "ag-fechar-paciente": () => $("#ag-paciente").close(),
  "ag-situacao": (alvo) => escolherSituacao(alvo.dataset.situacao),
  "ag-envia-para": (alvo) => escolherQuemRecebe(alvo.dataset.papel),
  "ag-voltar": voltarAoTratamento,
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
  Object.assign(agenda, { ano: r.ano, mes: r.mes, ativos: r.ativos, altas: r.altas, finalizados: r.finalizados });
  desenharAgenda();
}

function desenharAgenda() {
  $$("#ag-abas .escolha").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.aba === agenda.aba)));
  $("#ag-ativos").hidden = agenda.aba !== "ativos";
  $("#ag-altas").hidden = agenda.aba !== "altas";
  $("#ag-finalizados").hidden = agenda.aba !== "finalizados";
  $("#ag-mes").textContent = `${MESES[agenda.mes - 1]} de ${agenda.ano}`;
  for (const lista of ["ativos", "altas", "finalizados"]) {
    $(`#ag-qtd-${lista}`).textContent = agenda[lista].length ? `(${agenda[lista].length})` : "";
  }
  desenharAtivos();
  desenharAltas();
  desenharFinalizados();
}

function celula(texto, classe = "") {
  return Object.assign(document.createElement("td"), { className: classe, textContent: texto });
}

function celulaPaciente(p) {
  const td = document.createElement("td");
  const caixa = Object.assign(document.createElement("div"), { className: "paciente" });
  caixa.append(Object.assign(document.createElement("span"), { textContent: p.nome }));
  if (p.destino.papel) {
    caixa.append(Object.assign(document.createElement("span"), {
      className: "etiqueta", textContent: `${p.destino.papel}: ${p.destino.nome}`,
      title: "As mensagens deste paciente vão para este responsável",
    }));
  }
  td.append(caixa);
  return td;
}

function celulaTelefone(p) {
  const telefone = p.destino.telefone;
  return telefone ? celula(telefoneBR(telefone), "c-telefone") : celula("Sem telefone", "c-telefone ag-sem-dado");
}

function celulaAcoes(p, ...extras) {
  const td = document.createElement("td");
  td.className = extras.length ? "c-acoes-alta" : "c-acoes-regra";
  td.append(...extras, botaoIcone("ag-mensagem", "i-whats", `Mandar mensagem sobre ${p.nome}`, { id: p.id }),
    botaoIcone("ag-editar", "i-lapis", `Alterar ${p.nome}`, { id: p.id }));
  return td;
}

function desenharAtivos() {
  const feitos = agenda.ativos.filter((p) => p.agendado).length;
  const vazio = agenda.ativos.length === 0;
  const terminadas = agenda.altas.filter((p) => p.terminou).length;
  $("#ag-altas-terminadas").hidden = terminadas === 0;
  $("#ag-altas-terminadas-texto").textContent = terminadas === 1
    ? "1 alta temporária já terminou."
    : `${terminadas} altas temporárias já terminaram.`;
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
    tr.append(tdConfere, celulaPaciente(p), celulaTelefone(p),
      p.valor_centavos == null ? celula("Sem valor", "c-valor ag-sem-dado") : celula(real.format(p.valor_centavos / 100), "c-valor"),
      celulaAcoes(p));
    return tr;
  }));
}

function desenharAltas() {
  const vazio = agenda.altas.length === 0;
  $("#ag-altas-caixa").hidden = vazio;
  $("#ag-altas-vazio").hidden = !vazio;
  $("#ag-altas-corpo").replaceChildren(...agenda.altas.map((p) => {
    const tr = document.createElement("tr");
    const fim = celula(dataBR(p.alta_fim), "c-data");
    if (p.terminou) {
      const aviso = Object.assign(document.createElement("span"), { className: "etiqueta etiqueta-aviso ag-terminou", textContent: "terminou" });
      fim.append(aviso);
    }
    tr.append(celulaPaciente(p), celulaTelefone(p), celula(dataBR(p.alta_inicio), "c-data"), fim,
      celulaAcoes(p, botaoIcone("ag-voltar", "i-atualizar", `Voltar ${p.nome} para Em tratamento`, { id: p.id })));
    return tr;
  }));
}

function desenharFinalizados() {
  const vazio = agenda.finalizados.length === 0;
  $("#ag-finalizados-caixa").hidden = vazio;
  $("#ag-finalizados-vazio").hidden = !vazio;
  $("#ag-finalizados-corpo").replaceChildren(...agenda.finalizados.map((p) => {
    const tr = document.createElement("tr");
    tr.append(celulaPaciente(p), celulaTelefone(p), celula(dataBR(p.finalizado_em), "c-data"), celulaAcoes(p));
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

async function voltarAoTratamento(alvo) {
  const p = pacienteAgenda(alvo);
  const r = await api().agendamentos_voltar_ao_tratamento(p.id);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  aplicarAgenda(r);
  mostrarToast(`${p.nome} voltou para Em tratamento.`);
}

/* ---------- Novo paciente / alterar paciente ---------- */

function escolherSituacao(situacao) {
  agenda.situacao = situacao;
  $$(".ag-situacoes .escolha").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.situacao === situacao)));
  $("#ag-alta-campos").hidden = situacao !== "alta";
}

function escolherQuemRecebe(papel) {
  agenda.enviaPara = papel;
  $$(".ag-envia-para .escolha").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.papel === papel)));
}

function mostrarResponsaveis() {
  const tem = $("#ag-tem-responsaveis").checked;
  $("#ag-responsaveis").hidden = !tem;
  // Com responsáveis, a mensagem usa o telefone deles.
  $("#ag-telefone-campo").hidden = tem;
}

function preencherResponsavel(papel, pessoa) {
  $(`#ag-${papel}-nome`).value = pessoa ? pessoa.nome : "";
  $(`#ag-${papel}-telefone`).value = pessoa && pessoa.telefone ? telefoneBR(pessoa.telefone) : "";
}

function abrirPaciente(p) {
  agenda.editando = p;
  const responsaveis = p && p.responsaveis;
  $("#ag-paciente-titulo").textContent = p ? "Alterar paciente" : "Novo paciente";
  $("#ag-nome").value = p ? p.nome : "";
  $("#ag-telefone").value = p && p.telefone ? telefoneBR(p.telefone) : "";
  $("#ag-valor").value = p && p.valor_centavos != null ? (p.valor_centavos / 100).toFixed(2).replace(".", ",") : "";
  $("#ag-tem-responsaveis").checked = !!responsaveis;
  preencherResponsavel("pai", responsaveis && responsaveis.pai);
  preencherResponsavel("mae", responsaveis && responsaveis.mae);
  escolherQuemRecebe(responsaveis ? responsaveis.envia_para : "mae");
  mostrarResponsaveis();
  $("#ag-alta-inicio").value = p ? p.alta_inicio : "";
  $("#ag-alta-fim").value = p ? p.alta_fim : "";
  escolherSituacao(p ? p.situacao : "ativo");
  $("#ag-excluir").hidden = !p;
  $("#ag-paciente-erro").hidden = true;
  $("#ag-paciente").showModal();
  $("#ag-nome").focus();
}

function dadosDoResponsavel(papel) {
  return { nome: $(`#ag-${papel}-nome`).value, telefone: $(`#ag-${papel}-telefone`).value };
}

async function salvarPaciente(e) {
  e.preventDefault();
  const anterior = agenda.editando;
  const situacao = agenda.situacao;
  const nome = $("#ag-nome").value;
  const r = await api().agendamentos_salvar({
    nome,
    telefone: $("#ag-telefone").value,
    valor: $("#ag-valor").value,
    situacao,
    alta_inicio: $("#ag-alta-inicio").value,
    alta_fim: $("#ag-alta-fim").value,
    responsaveis: $("#ag-tem-responsaveis").checked
      ? { pai: dadosDoResponsavel("pai"), mae: dadosDoResponsavel("mae"), envia_para: agenda.enviaPara }
      : null,
  }, anterior ? anterior.id : null);
  if (r.erro) {
    // Um aviso comum ficaria escondido atrás da janela.
    $("#ag-paciente-erro").textContent = r.erro;
    $("#ag-paciente-erro").hidden = false;
    return;
  }
  $("#ag-paciente").close();
  aplicarAgenda(r);
  if (situacao !== (anterior ? anterior.situacao : "ativo")) {
    mostrarToast(`${nome.trim()} foi para ${NOMES_DAS_ABAS[situacao]}.`);
  }
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
  const { nome, telefone, papel } = r.destino;
  $("#ag-mensagem-titulo").textContent = papel
    ? `Mensagem para ${nome} (${papel} de ${r.nome})`
    : `Mensagem para ${r.nome}`;
  $("#ag-msg-telefone").value = telefone ? telefoneBR(telefone) : "";
  $("#ag-mensagem-erro").hidden = true;
  escolherMensagem("agendar");
  $("#ag-mensagem").showModal();
  (telefone ? $("#ag-msg-texto") : $("#ag-msg-telefone")).focus();
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
