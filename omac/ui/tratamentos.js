/* OMAC — Tratamentos (ortodontia): confere do mês, atendido, altas, histórico e mensagens.
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
  mensagem: null, // dados da janela de mensagem
  destino: "", // contato que vai receber a mensagem aberta
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
    $("#form-ag-mensagem").addEventListener("submit", enviarMensagem);
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
  "ag-mensagem": (alvo) => abrirMensagem(alvo.dataset.id),
  "ag-tipo": (alvo) => escolherMensagem(alvo.dataset.tipo),
  "ag-destino": (alvo) => escolherDestino(alvo.dataset.id),
  "ag-fechar-mensagem": () => $("#ag-mensagem").close(),
  "ag-abrir-config": () => {
    $("#ag-mensagem").close();
    mostrarView("config");
    $("#cfg-pix").focus();
  },
});

/* ---------- Lista ---------- */

async function carregarAgenda() {
  aplicarAgenda(await api().tratamentos_listar());
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
  const r = await api().tratamentos_marcar(caixa.dataset.id, caixa.checked);
  if (r.erro) {
    caixa.checked = !caixa.checked;
    return mostrarToast(r.erro, { erro: true });
  }
  aplicarAgenda(r);
}

const mesAtualDaAgenda = () => `${agenda.ano}-${String(agenda.mes).padStart(2, "0")}`;

async function marcarAtendido(caixa) {
  const r = await api().tratamentos_marcar_atendido(caixa.dataset.id, mesAtualDaAgenda(), caixa.checked);
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
      Object.assign(document.createElement("span"), { className: "ag-hist-texto", textContent: SITUACAO_NO_MES[m.situacao] }));
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
  agenda.mensagem = r;
  agenda.tipo = "agendar";
  // Para quem vai: o próprio paciente ou um responsável. Começa na última escolha.
  $("#ag-destinos").replaceChildren(...r.destinos.map((d) => {
    const b = Object.assign(document.createElement("button"), { type: "button", className: "escolha" });
    b.dataset.acao = "ag-destino";
    b.dataset.id = d.contato_id;
    b.textContent = d.papel ? `${d.nome} (${d.papel})` : `${d.nome} (paciente)`;
    return b;
  }));
  $("#ag-destinos-campo").hidden = r.destinos.length < 2;
  $("#ag-mensagem-erro").hidden = true;
  escolherDestino(r.escolhido);
  $("#ag-mensagem").showModal();
  ($("#ag-msg-telefone").value ? $("#ag-msg-texto") : $("#ag-msg-telefone")).focus();
}

function destinoAtual() {
  return agenda.mensagem.destinos.find((d) => d.contato_id === agenda.destino) || agenda.mensagem.destinos[0];
}

function escolherDestino(id) {
  agenda.destino = id;
  const d = destinoAtual();
  $$("#ag-destinos .escolha").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.id === d.contato_id)));
  $("#ag-mensagem-titulo").textContent = d.papel
    ? `Mensagem para ${d.nome} (${d.papel} de ${agenda.mensagem.nome})`
    : `Mensagem para ${agenda.mensagem.nome}`;
  $("#ag-msg-telefone").value = d.telefone ? telefoneBR(d.telefone) : "";
  escolherMensagem(agenda.tipo);
}

function escolherMensagem(tipo) {
  agenda.tipo = tipo;
  const textoDela = destinoAtual().mensagens[tipo];
  $$(".ag-tipos .escolha").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.tipo === tipo)));
  $("#ag-msg-texto").value = textoDela;
  // Sem chave Pix não há cobrança para mandar.
  $("#ag-sem-pix").hidden = textoDela !== "";
  $("#ag-msg-texto-campo").hidden = textoDela === "";
  $("#ag-enviar").disabled = textoDela === "";
}

async function enviarMensagem(e) {
  e.preventDefault();
  const r = await api().tratamentos_enviar(agenda.mensagem.id, destinoAtual().contato_id,
    $("#ag-msg-telefone").value, $("#ag-msg-texto").value);
  if (r.erro) {
    $("#ag-mensagem-erro").textContent = r.erro;
    $("#ag-mensagem-erro").hidden = false;
    return;
  }
  $("#ag-mensagem").close();
  aplicarAgenda(r);
  mostrarToast("Conversa aberta no WhatsApp. É só conferir e enviar.");
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
