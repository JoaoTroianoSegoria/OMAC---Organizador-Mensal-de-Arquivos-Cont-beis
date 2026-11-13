/* OMAC — tela inicial: o que importa hoje, em cartões que a pessoa escolhe e organiza.
 *
 * Os dados vêm de uma chamada só (inicio_painel). A ordem, quais aparecem e quais são
 * largos ficam em estado.cfg.inicio_cartoes. No modo Personalizar dá para arrastar,
 * usar as setas (teclado), esconder e mudar a largura; nada some de vez.
 */
"use strict";

const inicio = { painel: null, editando: false, arrastando: null };

const CARTOES = {
  hoje: { titulo: "Hoje", icone: "i-casa", desenhar: cartaoHoje },
  contas: { titulo: "Contas a pagar", icone: "i-whats", desenhar: cartaoContas },
  orto: { titulo: "Ortodontia", icone: "i-agenda", desenhar: cartaoOrto },
  ficha: { titulo: "Ficha do mês", icone: "i-dinheiro", desenhar: cartaoFicha },
  notas_enviar: { titulo: "Notas a enviar", icone: "i-notas", desenhar: cartaoNotasEnviar },
  fechamento: { titulo: "Fechamento", icone: "i-banco", desenhar: cartaoFechamento },
  avisos: { titulo: "Pendências", icone: "i-alerta", desenhar: cartaoAvisos },
  resumo: { titulo: "Resumo do ano", icone: "i-grafico", desenhar: cartaoResumo },
};

modulos.inicio = {
  aoMostrar: carregarInicio,
  carregar: carregarInicio,
  ligar() {
    const grade = $("#ini-grade");
    grade.addEventListener("dragstart", (e) => {
      const cartao = e.target.closest(".ini-cartao");
      if (!inicio.editando || !cartao) return;
      inicio.arrastando = cartao.dataset.id;
      cartao.classList.add("ini-arrastando");
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", cartao.dataset.id);
    });
    grade.addEventListener("dragover", (e) => {
      if (inicio.arrastando) e.preventDefault();
    });
    grade.addEventListener("drop", (e) => {
      const alvo = e.target.closest(".ini-cartao");
      e.preventDefault();
      if (alvo && inicio.arrastando && alvo.dataset.id !== inicio.arrastando) {
        moverCartaoPara(inicio.arrastando, alvo.dataset.id);
      }
    });
    grade.addEventListener("dragend", () => {
      inicio.arrastando = null;
      $$(".ini-arrastando").forEach((c) => c.classList.remove("ini-arrastando"));
    });
  },
};

Object.assign(acoes, {
  "ini-atualizar": carregarInicio,
  "ini-personalizar": () => { inicio.editando = !inicio.editando; desenharInicio(); },
  "ini-restaurar": restaurarCartoes,
  "ini-subir": (alvo) => moverCartao(alvo.dataset.id, -1),
  "ini-descer": (alvo) => moverCartao(alvo.dataset.id, 1),
  "ini-visivel": (alvo) => trocarCartao(alvo.dataset.id, "visivel"),
  "ini-largo": (alvo) => trocarCartao(alvo.dataset.id, "largo"),
  "ini-ir": (alvo) => irPara(alvo.dataset.view, alvo.dataset.aba),
  "ini-conta-paga": marcarContaPagaNoInicio,
});

async function carregarInicio() {
  const r = await api().inicio_painel();
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  inicio.painel = r;
  desenharInicio();
}

/* A lista vazia volta ao padrão: quem sabe a ordem padrão é o Python (config.CARTOES_INICIO). */
async function restaurarCartoes() {
  const r = await api().salvar_config({ inicio_cartoes: [] });
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  estado.cfg.inicio_cartoes = r.inicio_cartoes;
  desenharInicio();
}

function irPara(view, aba) {
  // A aba dos agendamentos vale já no carregamento, que acontece ao mostrar a tela.
  if (view === "agendamentos" && aba) agenda.aba = aba;
  mostrarView(view);
  if (view === "whatsapp" && aba) mostrarAbaWhats(aba);
}

/* ---------- Ordem e escolhas ---------- */

function salvarCartoes(lista) {
  mudarConfig({ inicio_cartoes: lista });
  desenharInicio();
}

function moverCartao(id, passo) {
  const lista = [...estado.cfg.inicio_cartoes];
  const i = lista.findIndex((c) => c.id === id);
  const j = i + passo;
  if (j < 0 || j >= lista.length) return;
  [lista[i], lista[j]] = [lista[j], lista[i]];
  salvarCartoes(lista);
  // O botão clicado foi redesenhado: o foco volta para ele, no cartão que mudou de lugar.
  $(`.ini-cartao[data-id="${id}"] [data-acao="${passo < 0 ? "ini-subir" : "ini-descer"}"]`)?.focus();
}

function moverCartaoPara(id, alvoId) {
  const lista = estado.cfg.inicio_cartoes.filter((c) => c.id !== id);
  const cartao = estado.cfg.inicio_cartoes.find((c) => c.id === id);
  lista.splice(lista.findIndex((c) => c.id === alvoId), 0, cartao);
  salvarCartoes(lista);
}

function trocarCartao(id, campo) {
  salvarCartoes(estado.cfg.inicio_cartoes.map((c) => (c.id === id ? { ...c, [campo]: !c[campo] } : c)));
  $(`.ini-cartao[data-id="${id}"] [data-acao="ini-${campo}"]`)?.focus();
}

/* ---------- Desenho ---------- */

function desenharInicio() {
  const hoje = new Date();
  $("#ini-data").textContent = hoje.toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  $("#ini-personalizar").setAttribute("aria-pressed", String(inicio.editando));
  $("#ini-editando").hidden = !inicio.editando;
  $("#ini-grade").classList.toggle("ini-editando", inicio.editando);
  if (!inicio.painel) return;

  const lista = estado.cfg.inicio_cartoes;
  const visiveis = lista.filter((c) => inicio.editando || c.visivel);
  $("#ini-grade").replaceChildren(...visiveis.map((c) => montarCartao(c, lista.indexOf(c), lista.length)));
  if (!visiveis.length) {
    $("#ini-grade").replaceChildren(Object.assign(document.createElement("p"), {
      className: "dica", textContent: "Todos os cartões estão escondidos. Clique em Personalizar para mostrar algum.",
    }));
  }
}

function montarCartao(c, posicao, total) {
  const def = CARTOES[c.id];
  const sec = Object.assign(document.createElement("section"), { className: "ini-cartao vidro" });
  sec.dataset.id = c.id;
  sec.classList.toggle("ini-largo", c.largo);
  sec.classList.toggle("ini-escondido", !c.visivel);
  sec.setAttribute("aria-labelledby", `ini-t-${c.id}`);
  sec.draggable = inicio.editando;

  const cab = Object.assign(document.createElement("header"), { className: "ini-cab" });
  const h2 = Object.assign(document.createElement("h2"), { id: `ini-t-${c.id}` });
  h2.innerHTML = `<svg class="ic"><use href="#${def.icone}"/></svg>`;
  h2.append(def.titulo);
  cab.append(h2);
  if (inicio.editando) {
    const barra = Object.assign(document.createElement("div"), { className: "ini-ferramentas" });
    const subir = botaoIcone("ini-subir", "i-cima", `Subir ${def.titulo}`, { id: c.id });
    subir.disabled = posicao === 0;
    const descer = botaoIcone("ini-descer", "i-seta", `Descer ${def.titulo}`, { id: c.id });
    descer.disabled = posicao === total - 1;
    const largo = botaoIcone("ini-largo", "i-largura", c.largo ? `Deixar ${def.titulo} normal` : `Deixar ${def.titulo} largo`, { id: c.id });
    largo.setAttribute("aria-pressed", String(c.largo));
    const olho = botaoIcone("ini-visivel", c.visivel ? "i-olho" : "i-olho-fechado",
      c.visivel ? `Esconder ${def.titulo}` : `Mostrar ${def.titulo}`, { id: c.id });
    olho.setAttribute("aria-pressed", String(!c.visivel));
    barra.append(subir, descer, largo, olho);
    cab.append(barra);
  }
  sec.append(cab);

  const corpo = Object.assign(document.createElement("div"), { className: "ini-corpo" });
  const dados = c.id === "hoje" || c.id === "avisos" ? inicio.painel : inicio.painel[c.id];
  if (dados && dados.erro) {
    corpo.append(Object.assign(document.createElement("p"), { className: "modal-erro", textContent: dados.erro }));
  } else {
    def.desenhar(corpo, dados);
  }
  sec.append(corpo);
  return sec;
}

/* ---------- Peças dos cartões ---------- */

function texto(tag, conteudo, classe = "") {
  return Object.assign(document.createElement(tag), { className: classe, textContent: conteudo });
}

function botaoIr(rotulo, view, aba = "") {
  const b = Object.assign(document.createElement("button"), { type: "button", className: "btn btn-peq", textContent: rotulo });
  b.dataset.acao = "ini-ir";
  b.dataset.view = view;
  if (aba) b.dataset.aba = aba;
  return b;
}

function numeros(pares) {
  const dl = Object.assign(document.createElement("dl"), { className: "ini-numeros" });
  for (const [rotulo, valor, classe] of pares) {
    const div = document.createElement("div");
    div.append(texto("dt", rotulo), texto("dd", valor, classe || ""));
    dl.append(div);
  }
  return dl;
}

function rodape(...botoes) {
  const div = Object.assign(document.createElement("div"), { className: "ini-rodape" });
  div.append(...botoes);
  return div;
}

const plural = (n, um, varios) => `${n} ${n === 1 ? um : varios}`;

/* ---------- Cartões ---------- */

function pendenciasDeHoje(p) {
  const itens = [];
  const contas = p.contas && !p.contas.erro ? p.contas.abertas.filter((c) => c.perto) : [];
  if (contas.length) itens.push([`${plural(contas.length, "conta vence", "contas vencem")} até amanhã ou já venceu`, "whatsapp", "contas"]);
  if (p.orto && !p.orto.erro) {
    const faltam = p.orto.ativos - p.orto.agendados;
    if (faltam > 0) itens.push([`${plural(faltam, "paciente de orto", "pacientes de orto")} para agendar no mês`, "agendamentos", "ativos"]);
  }
  if (p.notas_enviar && p.notas_enviar.qtd) itens.push([`${plural(p.notas_enviar.qtd, "nota", "notas")} para enviar no WhatsApp`, "whatsapp", "enviar"]);
  if (p.ficha && !p.ficha.erro && p.ficha.sem_nota) itens.push([`${plural(p.ficha.sem_nota, "atendimento", "atendimentos")} da ficha sem nota`, "pagamentos"]);
  const f = p.fechamento;
  if (f && !f.erro && f.dia_lembrete && new Date().getDate() >= f.dia_lembrete && f.lancamentos === 0) {
    itens.push([`Falta o extrato de ${f.nome_mes.toLowerCase()} para o fechamento`, "extrato"]);
  }
  return itens;
}

function cartaoHoje(corpo, p) {
  const hora = new Date().getHours();
  const saudacao = hora < 12 ? "Bom dia" : hora < 18 ? "Boa tarde" : "Boa noite";
  const nome = (estado.cfg.assistente_nome || "").trim().split(" ")[0];
  corpo.append(texto("p", nome ? `${saudacao}, ${nome}!` : `${saudacao}!`, "ini-saudacao"));
  const itens = pendenciasDeHoje(p);
  if (!itens.length) {
    corpo.append(texto("p", "Nada urgente para hoje.", "ini-tudo-certo"));
    return;
  }
  const ul = Object.assign(document.createElement("ul"), { className: "ini-lista ini-lista-links" });
  for (const [frase, view, aba] of itens) {
    const li = document.createElement("li");
    const b = Object.assign(document.createElement("button"), { type: "button", className: "ini-link", textContent: frase });
    b.dataset.acao = "ini-ir";
    b.dataset.view = view;
    if (aba) b.dataset.aba = aba;
    li.append(b);
    ul.append(li);
  }
  corpo.append(ul);
}

function cartaoContas(corpo, c) {
  const perto = c.abertas.filter((x) => x.perto);
  if (!c.total) {
    corpo.append(texto("p", "Nenhuma conta com lembrete.", "dica"));
  } else if (!perto.length) {
    corpo.append(texto("p", c.abertas.length
      ? `Nada vence até amanhã. ${plural(c.abertas.length, "conta ainda em aberto", "contas ainda em aberto")} no mês.`
      : "Todas as contas do mês estão pagas.", "ini-tudo-certo"));
  } else {
    const ul = Object.assign(document.createElement("ul"), { className: "ini-lista" });
    for (const conta of perto) {
      const li = Object.assign(document.createElement("li"), { className: "ini-conta" });
      const [, mes, dia] = conta.vencimento.split("-");
      const quando = conta.venceu ? `venceu ${dia}/${mes}` : conta.vencimento === inicio.painel.hoje ? "vence hoje" : "vence amanhã";
      li.append(Object.assign(document.createElement("span"), { textContent: conta.nome }),
        texto("span", quando, conta.venceu ? "etiqueta etiqueta-erro" : "etiqueta etiqueta-aviso"));
      const b = Object.assign(document.createElement("button"), { type: "button", className: "btn btn-peq" });
      b.dataset.acao = "ini-conta-paga";
      b.dataset.nome = conta.nome;
      b.dataset.mes = conta.mes;
      b.setAttribute("aria-label", `${conta.nome} já foi paga`);
      b.innerHTML = '<svg class="ic"><use href="#i-ok"/></svg><span>Paga</span>';
      li.append(b);
      ul.append(li);
    }
    corpo.append(ul);
  }
  corpo.append(rodape(botaoIr("Ver contas", "whatsapp", "contas")));
}

async function marcarContaPagaNoInicio(botao) {
  const r = await api().whatsapp_marcar_paga(botao.dataset.nome, botao.dataset.mes, true);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  mostrarToast(`${botao.dataset.nome} marcada como paga.`, {
    acoes: [["Desfazer", async () => {
      await api().whatsapp_marcar_paga(botao.dataset.nome, botao.dataset.mes, false);
      carregarInicio();
    }]],
  });
  carregarInicio();
}

function cartaoOrto(corpo, o) {
  if (!o.ativos) {
    corpo.append(texto("p", "Nenhum paciente em tratamento.", "dica"), rodape(botaoIr("Abrir agendamentos", "agendamentos")));
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
  corpo.append(rodape(botaoIr("Abrir agendamentos", "agendamentos", "ativos"), botaoIr("Histórico", "agendamentos", "historico")));
}

function cartaoFicha(corpo, f) {
  if (!f.qtd) {
    corpo.append(texto("p", "Nenhum atendimento na ficha deste mês.", "dica"), rodape(botaoIr("Abrir ficha", "pagamentos")));
    return;
  }
  corpo.append(numeros([
    ["Recebido", real.format(f.recebido_centavos / 100)],
    ["A receber", real.format(f.a_receber_centavos / 100)],
    ["Sem nota", String(f.sem_nota), f.sem_nota ? "ini-alerta" : ""],
  ]));
  corpo.append(rodape(botaoIr("Abrir ficha", "pagamentos")));
}

function cartaoNotasEnviar(corpo, n) {
  if (n.sem_pasta) {
    corpo.append(texto("p", "Escolha a pasta das notas para ver o que falta enviar.", "dica"), rodape(botaoIr("Abrir notas", "notas")));
    return;
  }
  corpo.append(texto("p", String(n.qtd), "ini-grande"),
    texto("p", n.qtd === 1 ? "nota esperando para ser enviada" : n.qtd ? "notas esperando para serem enviadas" : "Todas as notas foram enviadas.", "dica"),
    rodape(botaoIr("Enviar notas", "whatsapp", "enviar")));
}

function cartaoFechamento(corpo, f) {
  const linhas = [
    ["Notas fiscais", f.notas == null ? "sem pasta" : plural(f.notas, "nota", "notas"), f.notas ? "" : "ini-alerta"],
    ["Extrato", f.lancamentos == null ? "sem pasta" : f.lancamentos ? plural(f.lancamentos, "lançamento", "lançamentos") : "falta o extrato",
      f.lancamentos ? "" : "ini-alerta"],
  ];
  corpo.append(texto("p", `${f.nome_mes} de ${f.ano}`, "ini-subtitulo"), numeros(linhas),
    rodape(botaoIr("Abrir extrato", "extrato")));
}

function cartaoAvisos(corpo, p) {
  const itens = [];
  if (p.contas && !p.contas.erro && p.contas.nao_pagas_mes_passado.length) {
    itens.push([`Contas do mês passado sem marcar como pagas: ${p.contas.nao_pagas_mes_passado.join(", ")}`, "whatsapp", "contas"]);
  }
  if (p.ficha && !p.ficha.erro && p.ficha.nao_pagos_mes_passado) {
    itens.push([`${plural(p.ficha.nao_pagos_mes_passado, "atendimento do mês passado ficou", "atendimentos do mês passado ficaram")} sem pagar`, "pagamentos"]);
  }
  if (p.orto && !p.orto.erro && p.orto.nao_vieram_mes_passado) {
    itens.push([`${plural(p.orto.nao_vieram_mes_passado, "paciente de orto não veio", "pacientes de orto não vieram")} no mês passado`, "agendamentos", "historico"]);
  }
  if (p.orto && !p.orto.erro && p.orto.altas_terminadas) {
    itens.push([plural(p.orto.altas_terminadas, "alta temporária terminou", "altas temporárias terminaram"), "agendamentos", "altas"]);
  }
  if (!itens.length) {
    corpo.append(texto("p", "Nada pendente dos meses anteriores.", "ini-tudo-certo"));
    return;
  }
  const ul = Object.assign(document.createElement("ul"), { className: "ini-lista ini-lista-links" });
  for (const [frase, view, aba] of itens) {
    const li = document.createElement("li");
    const b = Object.assign(document.createElement("button"), { type: "button", className: "ini-link", textContent: frase });
    b.dataset.acao = "ini-ir";
    b.dataset.view = view;
    if (aba) b.dataset.aba = aba;
    li.append(b);
    ul.append(li);
  }
  corpo.append(ul);
}

function cartaoResumo(corpo, r) {
  if (!r.notas_lidas) {
    corpo.append(texto("p", "Escolha a pasta das notas para ver o faturamento.", "dica"), rodape(botaoIr("Ver resumo do ano", "resumo")));
    return;
  }
  corpo.append(numeros([
    [`Faturamento em ${r.ano}`, r.faturamento_centavos == null ? "—" : real.format(r.faturamento_centavos / 100)],
    ["Média por mês", r.media_centavos == null ? "—" : real.format(r.media_centavos / 100)],
    ["Melhor mês", r.melhor ? MESES[r.melhor - 1] : "—"],
  ]));
  const grafico = Object.assign(document.createElement("div"), { className: "rs-grafico" });
  desenharBarras(grafico, r.meses, { ano: r.ano, compacto: true });
  corpo.append(grafico, rodape(botaoIr("Ver resumo do ano", "resumo")));
}
