/* OMAC — módulo de agendamentos: pacientes de ortodontia, responsáveis, altas, confere,
 * atendido do mês e histórico (quem veio em cada mês). */
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
  histFim: null, // [ano, mês] da última coluna do histórico (null = mês atual)
  historico: null,
};

const HIST_MESES = 6;
const SITUACAO_NO_MES = {
  veio: "veio", nao_veio: "não veio", falta_vir: "ainda não veio", alta: "de alta", "": "não era paciente",
};
const MESES_CURTOS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

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
  "ag-atendido": marcarAtendido,
  "ag-hist-mover": (alvo) => moverHistorico(Number(alvo.dataset.passo)),
  "ag-hist-marcar": marcarNoHistorico,
  "ag-hist-paciente": (alvo) => abrirHistoricoDoPaciente(alvo.dataset.id),
  "ag-ver-historico": () => { $("#ag-paciente").close(); abrirHistoricoDoPaciente(agenda.editando.id); },
  "ag-fechar-hist": () => $("#ag-hist-paciente").close(),
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
  $("#ag-historico").hidden = agenda.aba !== "historico";
  if (agenda.aba === "historico") carregarHistorico();
  $("#ag-mes").textContent = `${MESES[agenda.mes - 1]} de ${agenda.ano}`;
  for (const lista of ["ativos", "altas", "finalizados"]) {
    $(`#ag-qtd-${lista}`).textContent = agenda[lista].length ? `(${agenda[lista].length})` : "";
  }
  desenharAtivos();
  desenharAltas();
  desenharFinalizados();
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
  $("#ag-atendidos").textContent = `${agenda.ativos.filter((p) => p.atendido).length} de ${agenda.ativos.length}`;
  $("#ag-resumo").hidden = vazio;
  $("#ag-filtros").hidden = vazio;
  $("#ag-ativos-caixa").hidden = vazio;
  $("#ag-dica").hidden = vazio;
  $("#ag-ativos-vazio").hidden = !vazio;
  $$("#ag-filtros .escolha").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.filtro === agenda.filtro)));

  const filtros = {
    todos: () => true,
    pendentes: (p) => !p.agendado,
    agendados: (p) => p.agendado,
    nao_atendidos: (p) => !p.atendido,
  };
  const visiveis = agenda.ativos.filter(filtros[agenda.filtro] || filtros.todos);
  if (visiveis.length === 0) {
    const tr = document.createElement("tr");
    const td = celula({
      pendentes: "Todos os pacientes já foram conferidos neste mês.",
      agendados: "Nenhum paciente marcado como agendado neste mês.",
      nao_atendidos: "Todos os pacientes já foram atendidos neste mês.",
    }[agenda.filtro], "ag-nada");
    td.colSpan = 6;
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
    const tdAtendido = document.createElement("td");
    tdAtendido.className = "c-confere";
    const atendido = Object.assign(document.createElement("input"), { type: "checkbox", className: "confere", checked: p.atendido });
    atendido.dataset.acao = "ag-atendido";
    atendido.dataset.id = p.id;
    atendido.setAttribute("aria-label", `${p.nome} já foi atendido neste mês`);
    tdAtendido.append(atendido);
    tr.append(tdConfere, tdAtendido, celulaPaciente(p), celulaTelefone(p),
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

const mesAtualDaAgenda = () => `${agenda.ano}-${String(agenda.mes).padStart(2, "0")}`;

async function marcarAtendido(caixa) {
  const r = await api().agendamentos_marcar_atendido(caixa.dataset.id, mesAtualDaAgenda(), caixa.checked);
  if (r.erro) {
    caixa.checked = !caixa.checked;
    return mostrarToast(r.erro, { erro: true });
  }
  aplicarAgenda(r);
}

/* ---------- Histórico ---------- */

function fimDoHistorico() {
  return agenda.histFim || [agenda.ano, agenda.mes];
}

async function carregarHistorico() {
  const [ano, mes] = fimDoHistorico();
  const r = await api().agendamentos_historico(ano, mes, HIST_MESES);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  agenda.historico = r;
  desenharHistorico();
}

function moverHistorico(passo) {
  const [ano, mes] = fimDoHistorico();
  const total = ano * 12 + (mes - 1) + passo;
  const atual = agenda.ano * 12 + (agenda.mes - 1);
  const fim = Math.min(total, atual); // não passa do mês atual
  agenda.histFim = [Math.floor(fim / 12), (fim % 12) + 1];
  carregarHistorico();
}

function marcaDoMes(situacao) {
  const span = Object.assign(document.createElement("span"), { className: `ag-marca ag-${situacao || "fora"}` });
  if (situacao === "veio") span.innerHTML = '<svg class="ic"><use href="#i-ok"/></svg>';
  else if (situacao === "nao_veio") span.innerHTML = '<svg class="ic"><use href="#i-x"/></svg>';
  else span.textContent = { falta_vir: "…", alta: "alta" }[situacao] || "—";
  return span;
}

function desenharHistorico() {
  const h = agenda.historico;
  const vazio = h.pacientes.length === 0;
  const primeiro = h.meses[0];
  const ultimo = h.meses[h.meses.length - 1];
  $("#ag-hist-periodo").textContent = `${MESES[primeiro.mes - 1]} de ${primeiro.ano} a ${MESES[ultimo.mes - 1]} de ${ultimo.ano}`;
  $("#ag-hist-avancar").disabled = ultimo.chave >= h.hoje;
  $("#ag-hist-caixa").hidden = vazio;
  $("#ag-hist-vazio").hidden = !vazio;

  const thNome = Object.assign(document.createElement("th"), { scope: "col", textContent: "Paciente" });
  $("#ag-hist-cab").replaceChildren(thNome, ...h.meses.map((m) => {
    const th = Object.assign(document.createElement("th"), { scope: "col", className: "ag-hist-mes" });
    th.append(Object.assign(document.createElement("span"), { textContent: `${MESES_CURTOS[m.mes - 1]}/${String(m.ano).slice(2)}` }));
    if (m.esperados) {
      th.append(Object.assign(document.createElement("small"), {
        textContent: `${m.veio} de ${m.esperados}`, title: `${m.veio} de ${m.esperados} pacientes vieram`,
      }));
    }
    return th;
  }));

  $("#ag-hist-corpo").replaceChildren(...h.pacientes.map((p) => {
    const tr = document.createElement("tr");
    const th = Object.assign(document.createElement("th"), { scope: "row" });
    const nome = Object.assign(document.createElement("button"), { type: "button", className: "ag-hist-nome", textContent: p.nome });
    nome.dataset.acao = "ag-hist-paciente";
    nome.dataset.id = p.id;
    nome.title = `Ver todos os meses de ${p.nome}`;
    th.append(nome);
    if (p.situacao !== "ativo") {
      th.append(Object.assign(document.createElement("span"), {
        className: "etiqueta", textContent: p.situacao === "alta" ? "alta" : "finalizado",
      }));
    }
    tr.append(th, ...p.meses.map((situacao, i) => {
      const m = h.meses[i];
      const td = document.createElement("td");
      td.className = "ag-hist-celula";
      const rotulo = `${p.nome}, ${MESES[m.mes - 1]} de ${m.ano}: ${SITUACAO_NO_MES[situacao]}`;
      if (m.chave > h.hoje) {
        td.append(marcaDoMes(""));
        td.title = rotulo;
        return td;
      }
      // Qualquer mês que já chegou pode ser marcado ou desmarcado, se esqueceu na hora.
      const b = Object.assign(document.createElement("button"), { type: "button", className: "ag-hist-botao" });
      b.dataset.acao = "ag-hist-marcar";
      b.dataset.id = p.id;
      b.dataset.mes = m.chave;
      b.setAttribute("aria-pressed", String(situacao === "veio"));
      b.setAttribute("aria-label", `${rotulo}. Clique para ${situacao === "veio" ? "desmarcar" : "marcar que veio"}.`);
      b.title = rotulo;
      b.append(marcaDoMes(situacao));
      td.append(b);
      return td;
    }));
    return tr;
  }));
}

async function marcarNoHistorico(botao) {
  const veio = botao.getAttribute("aria-pressed") !== "true";
  const r = await api().agendamentos_marcar_atendido(botao.dataset.id, botao.dataset.mes, veio);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  aplicarAgenda(r); // já recarrega o histórico, que está aberto
  // O foco volta para a mesma célula, para seguir marcando pelo teclado.
  const [id, mes] = [botao.dataset.id, botao.dataset.mes];
  setTimeout(() => $(`.ag-hist-botao[data-id="${id}"][data-mes="${mes}"]`)?.focus(), 150);
}

async function abrirHistoricoDoPaciente(id) {
  const r = await api().agendamentos_historico_paciente(id);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  $("#ag-hist-titulo").textContent = `Histórico de ${r.nome}`;
  $("#ag-hist-conta").textContent = r.esperados
    ? `Veio em ${r.veio} de ${r.esperados} ${r.esperados === 1 ? "mês" : "meses"}.`
    : "Ainda não há meses completos no histórico.";
  $("#ag-hist-lista").replaceChildren(...r.meses.map((m) => {
    const li = document.createElement("li");
    li.append(marcaDoMes(m.situacao),
      Object.assign(document.createElement("span"), { textContent: `${MESES[m.mes - 1]} de ${m.ano}` }),
      Object.assign(document.createElement("span"), { className: "ag-hist-texto", textContent: SITUACAO_NO_MES[m.situacao] }));
    return li;
  }));
  $("#ag-hist-paciente").showModal();
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
  $("#ag-ver-historico").hidden = !p;
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
