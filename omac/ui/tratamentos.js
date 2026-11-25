/* OMAC — Tratamentos (ortodontia): agendado do mês, atendido, altas, histórico e mensagens.
 *
 * Nome, telefone e responsáveis são do contato: criar e alterar o paciente é pela janela
 * de contato (contatos.js), com a chave "Em tratamento de orto" ligada. */
"use strict";

const agenda = {
  aba: "ativos",
  filtro: "todos",
  ano: 0,
  mes: 0,
  ativos: [],
  altas: [],
  finalizados: [],
  proximoMes: "", // "AAAA-MM" do mês seguinte (o "agendar o próximo mês")
  agendando: null, // {id, qual} da janela de agendar
  histFim: null, // [ano, mês] da última coluna do histórico (null = mês atual)
  historico: null,
};

const HIST_MESES = 6;
const SITUACAO_NO_MES = {
  veio: "veio", nao_veio: "não veio", falta_vir: "ainda não veio", alta: "de alta", "": "não era paciente",
};
const MESES_CURTOS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

modulos.tratamentos = {
  aoMostrar: carregarAgenda,
  carregar: carregarAgenda,
  antesDeMostrar(aba) { agenda.aba = aba; }, // a aba vale já no carregamento, que vem ao mostrar a tela
  ligar() {
    $("#form-ag-agendar").addEventListener("submit", (e) => { e.preventDefault(); salvarAgendar(true); });
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
  "ag-ver-historico": () => { $("#ct-contato").close(); abrirHistoricoDoPaciente(contatos.editando.tratamento.id); },
  "ag-fechar-hist": () => $("#ag-hist-paciente").close(),
  "ag-filtro": (alvo) => { agenda.filtro = alvo.dataset.filtro; desenharAgenda(); },
  "ag-novo": () => abrirContato(null, { orto: true }),
  "ag-editar": (alvo) => abrirContatoPorId(pacienteAgenda(alvo).contato_id),
  "ag-voltar": voltarAoTratamento,
  "ag-marcar": marcarAgendado,
  "ag-agendar-proximo": (alvo) => { const p = pacienteAgenda(alvo); if (p) abrirAgendar(p, "proximo"); },
  "ag-agendar-fechar": () => $("#ag-agendar").close(),
  "ag-agendar-tirar": () => salvarAgendar(false),
  "ag-mensagem": (alvo) => abrirMensagem(alvo.dataset.id),
});

/* ---------- Lista ---------- */

async function carregarAgenda() {
  aplicarAgenda(await api().tratamentos_listar());
}

function aplicarAgenda(r) {
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  Object.assign(agenda, { ano: r.ano, mes: r.mes, ativos: r.ativos, altas: r.altas, finalizados: r.finalizados,
    proximoMes: r.proximo_mes });
  // A aba entra na conta: o "ir para a aba" (antesDeMostrar) troca a aba antes de carregar.
  if (!desenharSeMudou("agenda", [r, agenda.aba], desenharAgenda) && agenda.aba === "historico") carregarHistorico();
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
  // Todos os responsáveis; quem recebe as mensagens ganha o ícone do WhatsApp.
  for (const r of p.responsaveis || []) {
    const recebe = r.contato_id === p.destino.contato_id;
    const et = Object.assign(document.createElement("span"), {
      className: `etiqueta ag-resp${recebe ? " etiqueta-acento ag-recebe" : ""}`,
      title: recebe ? "As mensagens deste paciente vão para este responsável" : "Responsável",
    });
    if (recebe) et.innerHTML = '<svg class="ic"><use href="#i-whats"/></svg>';
    et.append(`${r.papel}: ${r.nome}`);
    caixa.append(et);
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

const nomeDoMes = (chave) => MESES[Number(chave.slice(5, 7)) - 1].toLowerCase();
const diaMes = (iso) => dataBR(iso).slice(0, 5);
// Agendado e atendido no mês: vai para a parte de baixo ("Feitos em novembro").
const feitoNoMes = (p) => p.agendado && p.atendido;

function caixaDaAgenda(acao, p, marcada, rotulo) {
  const td = Object.assign(document.createElement("td"), { className: "c-confere" });
  const caixa = Object.assign(document.createElement("input"), { type: "checkbox", className: "confere", checked: marcada });
  caixa.dataset.acao = acao;
  caixa.dataset.id = p.id;
  caixa.setAttribute("aria-label", rotulo);
  td.append(caixa);
  return td;
}

/* O paciente com o que vale para o mês: a consulta marcada e se o agendado veio do mês anterior. */
function celulaPacienteDoMes(p) {
  const td = celulaPaciente(p);
  const caixa = td.querySelector(".paciente");
  if (p.consulta) caixa.append(texto("span", `consulta ${diaMes(p.consulta)}`, "etiqueta etiqueta-acento ag-consulta"));
  if (p.agendado_antes) {
    const anterior = MESES[(agenda.mes + 10) % 12].toLowerCase();
    caixa.append(texto("span", `agendado em ${anterior}`, "etiqueta ag-veio-antes"));
  }
  return td;
}

/* `comTelefone`: a lista de cima mostra; a de "feitos" não (lá a coluna é o próximo mês). */
function linhaAtiva(p, comTelefone = true) {
  const tr = document.createElement("tr");
  tr.append(
    caixaDaAgenda("ag-marcar", p, p.agendado, `${p.nome} já tem a manutenção agendada neste mês`),
    caixaDaAgenda("ag-atendido", p, p.atendido, `${p.nome} já foi atendido neste mês`),
    celulaPacienteDoMes(p),
  );
  if (comTelefone) tr.append(celulaTelefone(p));
  tr.append(p.valor_centavos == null ? celula("Sem valor", "c-valor ag-sem-dado") : celula(dinheiro(p.valor_centavos), "c-valor"));
  return tr;
}

function botaoProximoMes(p) {
  const nome = nomeDoMes(agenda.proximoMes);
  const b = Object.assign(document.createElement("button"), { type: "button", className: "btn btn-peq ag-proximo" });
  b.dataset.acao = "ag-agendar-proximo";
  b.dataset.id = p.id;
  if (p.proximo.agendado) {
    b.classList.add("ag-proximo-feito");
    b.innerHTML = '<svg class="ic"><use href="#i-ok"/></svg>';
    // A coluna já diz o mês: o botão fica curto ("Agendado · 04/12").
    b.append(`Agendado${p.proximo.consulta ? ` · ${diaMes(p.proximo.consulta)}` : ""}`);
    b.title = `Mudar o dia ou tirar o agendado de ${nome}`;
    b.setAttribute("aria-label", `${p.nome}: ${nome} agendado. Mudar o dia ou tirar`);
  } else {
    b.textContent = "Agendar";
    b.title = `Deixar ${nome} já agendado para ${p.nome}`;
    b.setAttribute("aria-label", `Agendar ${nome} para ${p.nome}`);
  }
  return b;
}

function desenharAtivos() {
  const agendados = agenda.ativos.filter((p) => p.agendado).length;
  const vazio = agenda.ativos.length === 0;
  const terminadas = agenda.altas.filter((p) => p.terminou).length;
  $("#ag-altas-terminadas").hidden = terminadas === 0;
  $("#ag-altas-terminadas-texto").textContent = terminadas === 1
    ? "1 alta temporária já terminou."
    : `${terminadas} altas temporárias já terminaram.`;
  $("#ag-feitos").textContent = String(agendados);
  $("#ag-faltam").textContent = String(agenda.ativos.length - agendados);
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
  const pendentes = agenda.ativos.filter((p) => !feitoNoMes(p));
  const visiveis = pendentes.filter(filtros[agenda.filtro] || filtros.todos);
  if (visiveis.length === 0) {
    const tr = document.createElement("tr");
    const td = celula(pendentes.length === 0 && agenda.ativos.length
      ? "Todos já foram agendados e atendidos neste mês. Eles estão logo abaixo."
      : {
        pendentes: "Todos os pacientes já estão agendados neste mês.",
        agendados: "Nenhum paciente marcado como agendado neste mês.",
        nao_atendidos: "Todos os pacientes já foram atendidos neste mês.",
        todos: "Nenhum paciente.",
      }[agenda.filtro], "ag-nada");
    td.colSpan = 6;
    tr.append(td);
    $("#ag-ativos-corpo").replaceChildren(tr);
  } else {
    $("#ag-ativos-corpo").replaceChildren(...visiveis.map((p) => {
      const tr = linhaAtiva(p);
      tr.append(celulaAcoes(p));
      return tr;
    }));
  }

  // Feitos no mês: com o botão de já deixar o próximo mês agendado.
  const feitos = agenda.ativos.filter(feitoNoMes);
  $("#ag-concluidos").hidden = feitos.length === 0;
  $("#ag-concluidos-titulo").textContent = `Feitos em ${MESES[agenda.mes - 1].toLowerCase()} (${feitos.length})`;
  $("#ag-th-proximo").textContent = `${nomeDoMes(agenda.proximoMes)[0].toUpperCase()}${nomeDoMes(agenda.proximoMes).slice(1)}`;
  $("#ag-concluidos-corpo").replaceChildren(...feitos.map((p) => {
    const tr = linhaAtiva(p, false);
    const td = Object.assign(document.createElement("td"), { className: "ag-c-proximo" });
    td.append(botaoProximoMes(p));
    tr.append(td, celulaAcoes(p));
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
    tr.append(celulaPaciente(p), celulaTelefone(p),
      p.valor_centavos == null ? celula("Sem valor", "c-valor ag-sem-dado") : celula(dinheiro(p.valor_centavos), "c-valor"),
      celula(dataBR(p.finalizado_em), "c-data"), celulaAcoes(p));
    return tr;
  }));
}

const mesAtualDaAgenda = () => `${agenda.ano}-${String(agenda.mes).padStart(2, "0")}`;

/* Agendado e Atendido perguntam antes de marcar e de desmarcar (a mesma janela do Pago). */
function marcarNaAgenda(caixa, perguntas, gravar) {
  return marcarComConfirmacao(caixa, perguntas, async (marcar) => {
    const r = await gravar(marcar);
    if (r.erro) {
      caixa.checked = !marcar;
      return mostrarToast(r.erro, { erro: true });
    }
    aplicarAgenda(r);
  });
}

function marcarAgendado(caixa) {
  const p = pacienteAgenda(caixa);
  if (!p) return;
  const mes = MESES[agenda.mes - 1].toLowerCase();
  if (caixa.checked) {
    // Marcar abre a janela com o dia da consulta (opcional); a caixa só fica marcada se salvar.
    caixa.checked = false;
    return abrirAgendar(p, "mes");
  }
  return marcarNaAgenda(caixa, {
    marcar: ["", ""],
    desmarcar: [`Tirar o agendado de ${p.nome} em ${mes}?`, "Tirar o agendado"],
  }, (marcar) => api().tratamentos_marcar(p.id, marcar));
}

/* ---------- Janela "agendar" (este mês ou o próximo), com o dia da consulta ---------- */

function limitesDoMes(chave) {
  const [a, m] = chave.split("-").map(Number);
  const ultimo = new Date(a, m, 0).getDate();
  return [`${chave}-01`, `${chave}-${String(ultimo).padStart(2, "0")}`];
}

/* `qual`: "mes" (o Agendado deste mês) ou "proximo" (deixar o mês seguinte agendado). */
function abrirAgendar(p, qual) {
  const chave = qual === "mes" ? mesAtualDaAgenda() : agenda.proximoMes;
  const nome = nomeDoMes(chave);
  const jaTem = qual === "proximo" && p.proximo.agendado;
  agenda.agendando = { id: p.id, qual };
  $("#ag-agendar-titulo").textContent = qual === "mes" ? `Agendado em ${nome}` : `Agendar ${nome}`;
  $("#ag-agendar-texto").textContent = qual === "mes"
    ? `${p.nome} já tem a manutenção de ${nome} agendada?`
    : jaTem ? `A manutenção de ${p.nome} em ${nome} já está agendada.`
      : `A manutenção de ${p.nome} em ${nome} já está agendada? Quando ${nome} chegar, ele já aparece como agendado.`;
  const dia = $("#ag-agendar-dia");
  [dia.min, dia.max] = limitesDoMes(chave);
  dia.value = (qual === "mes" ? p.consulta : p.proximo.consulta) || "";
  $("#ag-agendar-sim").textContent = jaTem ? "Salvar o dia" : qual === "mes" ? "Marcar como agendado" : `Marcar ${nome} como agendado`;
  $("#ag-agendar-tirar").hidden = !jaTem;
  $("#ag-agendar-erro").hidden = true;
  $("#ag-agendar").showModal();
  dia.focus();
}

async function salvarAgendar(agendado) {
  const { id, qual } = agenda.agendando || {};
  if (!id) return;
  const dia = agendado ? $("#ag-agendar-dia").value : "";
  const r = qual === "mes"
    ? await api().tratamentos_marcar(id, agendado, dia)
    : await api().tratamentos_agendar_proximo(id, agendado, dia);
  if (r.erro) {
    $("#ag-agendar-erro").textContent = r.erro;
    $("#ag-agendar-erro").hidden = false;
    return;
  }
  $("#ag-agendar").close();
  aplicarAgenda(r);
}

function marcarAtendido(caixa) {
  const p = pacienteAgenda(caixa);
  if (!p) return;
  const mes = MESES[agenda.mes - 1].toLowerCase();
  return marcarNaAgenda(caixa, {
    marcar: [`Marcar ${p.nome} como atendido em ${mes}?`, "Marcar como atendido"],
    desmarcar: [`Tirar o atendido de ${p.nome} em ${mes}?`, "Tirar o atendido"],
  }, (marcar) => api().tratamentos_marcar_atendido(p.id, mesAtualDaAgenda(), marcar));
}

/* ---------- Histórico ---------- */

function fimDoHistorico() {
  return agenda.histFim || [agenda.ano, agenda.mes];
}

async function carregarHistorico() {
  const [ano, mes] = fimDoHistorico();
  const r = await api().tratamentos_historico(ano, mes, HIST_MESES);
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
  const r = await api().tratamentos_marcar_atendido(botao.dataset.id, botao.dataset.mes, veio);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  aplicarAgenda(r); // já recarrega o histórico, que está aberto
  // O foco volta para a mesma célula, para seguir marcando pelo teclado.
  const [id, mes] = [botao.dataset.id, botao.dataset.mes];
  setTimeout(() => $(`.ag-hist-botao[data-id="${id}"][data-mes="${mes}"]`)?.focus(), 150);
}

async function abrirHistoricoDoPaciente(id) {
  const r = await api().tratamentos_historico_paciente(id);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  $("#ag-hist-titulo").textContent = `Histórico de ${r.nome}`;
  $("#ag-hist-conta").textContent = r.esperados
    ? `Veio em ${r.veio} de ${r.esperados} ${r.esperados === 1 ? "mês" : "meses"}.`
    : "Ainda não há meses completos no histórico.";
  $("#ag-hist-lista").replaceChildren(...r.meses.map((m) => {
    const li = document.createElement("li");
    li.append(marcaDoMes(m.situacao),
      Object.assign(document.createElement("span"), { textContent: `${MESES[m.mes - 1]} de ${m.ano}` }),
      Object.assign(document.createElement("span"), {
        className: "ag-hist-texto",
        // Quem veio mostra o dia (quando se sabe: um mês marcado depois fica só "veio").
        textContent: m.situacao === "veio" && m.dia ? `veio em ${dataBR(m.dia)}` : SITUACAO_NO_MES[m.situacao],
      }));
    return li;
  }));
  $("#ag-hist-paciente").showModal();
}

async function voltarAoTratamento(alvo) {
  const p = pacienteAgenda(alvo);
  const r = await api().tratamentos_voltar_ao_tratamento(p.id);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  aplicarAgenda(r);
  mostrarToast(`${p.nome} voltou para Em tratamento.`);
}

/* ---------- Mensagem ---------- */

async function abrirMensagem(id) {
  const r = await api().tratamentos_preparar_mensagens(id);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  // Para quem vai: o próprio paciente ou um responsável. Começa na última escolha.
  abrirJanelaMensagem({
    titulo: (d) => (d.papel ? `Mensagem para ${d.nome} (${d.papel} de ${r.nome})` : `Mensagem para ${r.nome}`),
    destinos: r.destinos,
    escolhido: r.escolhido,
    rotuloDestino: (d) => (d.papel ? `${d.nome} (${d.papel})` : `${d.nome} (paciente)`),
    tipos: [
      { id: "agendar", rotulo: "Agendar manutenção" },
      { id: "cobrar", rotulo: "Cobrar manutenção" },
      { id: "retorno", rotulo: "Agendar retorno" },
    ],
    texto: (d, tipo) => d.mensagens[tipo],
    // Sem chave Pix não há cobrança para mandar.
    falta: (d, tipo) => (d && d.mensagens[tipo] === ""
      ? { texto: "Para cobrar, preencha a chave Pix nas Configurações.", botao: "Abrir Configurações", acao: abrirChavePix }
      : null),
    enviar: ({ destino, telefone, texto }) => api().tratamentos_enviar(r.id, destino.contato_id, telefone, texto),
    aoEnviar: aplicarAgenda,
  });
}

function abrirChavePix() {
  mostrarView("config");
  $("#cfg-pix").focus();
}

/* ---------- Widget do Início ---------- */

registrarWidget("tratamentos", {
  icone: "i-agenda",
  desenhar(corpo, o) {
    if (!o.ativos) {
      corpo.append(texto("p", "Nenhum paciente em tratamento.", "dica"), rodape(botaoIr("Abrir tratamentos", "tratamentos")));
      return;
    }
    corpo.append(numeros([
      ["Agendados no mês", `${o.agendados} de ${o.ativos}`],
      ["Atendidos no mês", `${o.atendidos} de ${o.ativos}`],
    ]));
    const linhas = [];
    if (o.altas_terminadas) linhas.push(plural(o.altas_terminadas, "alta temporária já terminou", "altas temporárias já terminaram"));
    for (const a of o.altas_acabando) linhas.push(`Alta de ${a.nome} acaba em ${dataBR(a.alta_fim).slice(0, 5)}`);
    if (linhas.length) {
      const ul = Object.assign(document.createElement("ul"), { className: "ini-lista ini-lista-aviso" });
      ul.append(...linhas.map((l) => texto("li", l)));
      corpo.append(ul);
    }
    corpo.append(rodape(botaoIr("Abrir tratamentos", "tratamentos", "ativos"), botaoIr("Histórico", "tratamentos", "historico")));
  },
});
