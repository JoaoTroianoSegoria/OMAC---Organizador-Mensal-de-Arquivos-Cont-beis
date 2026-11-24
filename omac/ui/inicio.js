/* OMAC — Início: o que importa hoje, em widgets que a pessoa escolhe e organiza.
 *
 * O Início não conhece os módulos. Os dados vêm de uma chamada só (inicio_painel), que
 * percorre o registro do Python; o desenho de cada widget fica no .js do módulo dele
 * (registrarWidget). A ordem, quais aparecem e quais são largos ficam em
 * estado.cfg.inicio_cartoes; o Python devolve a lista já completa em painel.cartoes.
 */
"use strict";

const inicio = { painel: null, editando: false, arrastando: null };

modulos.inicio = {
  aoMostrar: carregarInicio,
  carregar: carregarInicio,
  // O gráfico do resumo tem a dica em texto: desenha de novo para ela esconder ou mostrar o valor.
  // Só se estiver na tela: fora dela, a volta já redesenha (o olho entra no desenharSeMudou).
  aoMudarValores: () => { if (inicio.painel && estado.view === "inicio") desenharInicio(); },
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
  "ini-personalizar": async () => {
    inicio.editando = !inicio.editando;
    if (inicio.editando) {
      // Fora do Personalizar os escondidos nem são calculados: agora eles vêm também.
      const r = await api().inicio_painel(true);
      if (!r.erro) inicio.painel = r;
    }
    desenharInicio();
  },
  "ini-restaurar": restaurarCartoes,
  "ini-subir": (alvo) => moverCartao(alvo.dataset.id, -1),
  "ini-descer": (alvo) => moverCartao(alvo.dataset.id, 1),
  "ini-visivel": (alvo) => trocarCartao(alvo.dataset.id, "visivel"),
  "ini-largo": (alvo) => trocarCartao(alvo.dataset.id, "largo"),
});

async function carregarInicio() {
  // Fora do Personalizar, o Python só calcula os cartões que aparecem.
  const r = await api().inicio_painel(inicio.editando);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  inicio.painel = r;
  desenharSeMudou("inicio", r, desenharInicio);
}

/* Recarrega o Início se ele estiver na tela (depois de mudar algo em outro lugar). */
function atualizarInicioSeAberto() {
  if (estado.view === "inicio") carregarInicio();
}

/* A lista vazia volta ao padrão: quem sabe a ordem padrão é o registro do Python. */
async function restaurarCartoes() {
  const r = await api().salvar_config({ inicio_cartoes: [] });
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  estado.cfg.inicio_cartoes = r.inicio_cartoes;
  carregarInicio();
}

/* ---------- Ordem e escolhas ---------- */

function salvarCartoes(lista) {
  inicio.painel.cartoes = lista;
  mudarConfig({ inicio_cartoes: lista });
  desenharInicio();
}

function moverCartao(id, passo) {
  const lista = [...inicio.painel.cartoes];
  const i = lista.findIndex((c) => c.id === id);
  const j = i + passo;
  if (j < 0 || j >= lista.length) return;
  [lista[i], lista[j]] = [lista[j], lista[i]];
  salvarCartoes(lista);
  // O botão clicado foi redesenhado: o foco volta para ele, no cartão que mudou de lugar.
  $(`.ini-cartao[data-id="${id}"] [data-acao="${passo < 0 ? "ini-subir" : "ini-descer"}"]`)?.focus();
}

function moverCartaoPara(id, alvoId) {
  const lista = inicio.painel.cartoes.filter((c) => c.id !== id);
  const cartao = inicio.painel.cartoes.find((c) => c.id === id);
  lista.splice(lista.findIndex((c) => c.id === alvoId), 0, cartao);
  salvarCartoes(lista);
}

function trocarCartao(id, campo) {
  salvarCartoes(inicio.painel.cartoes.map((c) => (c.id === id ? { ...c, [campo]: !c[campo] } : c)));
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

  // Widget sem desenho nesta tela (de uma versão mais nova do Python) fica de fora.
  const lista = inicio.painel.cartoes.filter((c) => widgets[c.id]);
  const visiveis = lista.filter((c) => inicio.editando || c.visivel);
  $("#ini-grade").replaceChildren(...visiveis.map((c) => montarCartao(c, lista.indexOf(c), lista.length)));
  if (!visiveis.length) {
    $("#ini-grade").replaceChildren(texto("p", "Todos os widgets estão escondidos. Clique em Personalizar para mostrar algum.", "dica"));
  }
}

function montarCartao(c, posicao, total) {
  const def = widgets[c.id];
  const titulo = inicio.painel.titulos[c.id] || c.id;
  const sec = Object.assign(document.createElement("section"), { className: "ini-cartao vidro" });
  sec.dataset.id = c.id;
  sec.classList.toggle("ini-largo", c.largo);
  sec.classList.toggle("ini-escondido", !c.visivel);
  sec.setAttribute("aria-labelledby", `ini-t-${c.id}`);
  sec.draggable = inicio.editando;

  const cab = Object.assign(document.createElement("header"), { className: "ini-cab" });
  const h2 = Object.assign(document.createElement("h2"), { id: `ini-t-${c.id}` });
  h2.innerHTML = `<svg class="ic"><use href="#${def.icone}"/></svg>`;
  h2.append(titulo);
  cab.append(h2);
  if (inicio.editando) {
    const barra = Object.assign(document.createElement("div"), { className: "ini-ferramentas" });
    const subir = botaoIcone("ini-subir", "i-cima", `Subir ${titulo}`, { id: c.id });
    subir.disabled = posicao === 0;
    const descer = botaoIcone("ini-descer", "i-seta", `Descer ${titulo}`, { id: c.id });
    descer.disabled = posicao === total - 1;
    const largo = botaoIcone("ini-largo", "i-largura", c.largo ? `Deixar ${titulo} normal` : `Deixar ${titulo} largo`, { id: c.id });
    largo.setAttribute("aria-pressed", String(c.largo));
    const olho = botaoIcone("ini-visivel", c.visivel ? "i-olho" : "i-olho-fechado",
      c.visivel ? `Esconder ${titulo}` : `Mostrar ${titulo}`, { id: c.id });
    olho.setAttribute("aria-pressed", String(!c.visivel));
    barra.append(subir, descer, largo, olho);
    cab.append(barra);
  }
  sec.append(cab);

  const corpo = Object.assign(document.createElement("div"), { className: "ini-corpo" });
  const dados = inicio.painel.widgets[c.id];
  if (dados && dados.erro) {
    corpo.append(texto("p", dados.erro, "modal-erro"));
  } else {
    try {
      def.desenhar(corpo, dados, inicio.painel.widgets);
    } catch (e) {
      // Um widget com defeito de desenho não apaga os outros.
      corpo.replaceChildren(texto("p", `Não consegui mostrar: ${e.message}`, "modal-erro"));
    }
  }
  sec.append(corpo);
  return sec;
}

/* ---------- Hoje (o único widget do próprio Início) ---------- */

function avisoDoBackup(b) {
  if (b.erro) return [`O backup automático não deu certo: ${b.erro}`, "config", "backup"];
  if (!b.pasta) return b.atrasado ? ["Você ainda não tem backup. Escolha uma pasta em Configurações", "config", "backup"] : null;
  if (b.dias == null) return ["Ainda não foi feito nenhum backup", "config", "backup"];
  if (b.atrasado) return [`Último backup há ${b.dias} dias`, "config", "backup"];
  return null;
}

/* O "Hoje" junta o que está para hoje em todos os widgets (mesmo nos escondidos). */
function pendenciasDeHoje(w) {
  const itens = [];
  const ok = (x) => x && !x.erro;
  if (ok(w.hoje)) {
    const backup = avisoDoBackup(w.hoje.backup);
    if (backup) itens.push(backup);
  }
  if (ok(w.lembretes)) {
    const contas = w.lembretes.abertas.filter((c) => c.perto);
    if (contas.length) itens.push([`${plural(contas.length, "conta vence", "contas vencem")} até amanhã ou já venceu`, "lembretes", "contas"]);
    const notas = w.lembretes.notas_enviar;
    if (notas && notas.qtd) itens.push([`${plural(notas.qtd, "nota", "notas")} para enviar no WhatsApp`, "lembretes", "enviar"]);
    const livres = w.lembretes.livres || [];
    if (livres.length) itens.push([`${plural(livres.length, "lembrete em aberto", "lembretes em aberto")}`, "lembretes", "livres"]);
  }
  if (ok(w.tratamentos)) {
    const faltam = w.tratamentos.ativos - w.tratamentos.agendados;
    if (faltam > 0) itens.push([`${plural(faltam, "paciente de orto", "pacientes de orto")} para agendar no mês`, "tratamentos", "ativos"]);
  }
  if (ok(w.atendimentos) && w.atendimentos.sem_nota) {
    itens.push([`${plural(w.atendimentos.sem_nota, "atendimento", "atendimentos")} do mês sem nota`, "atendimentos"]);
  }
  const f = w.relatorio;
  if (ok(f) && f.dia_lembrete && new Date().getDate() >= f.dia_lembrete && f.lancamentos === 0) {
    itens.push([`Falta o extrato de ${f.nome_mes.toLowerCase()} para o fechamento`, "relatorio", "extrato"]);
  }
  if (ok(w.contatos) && w.contatos.a_conferir) {
    itens.push([`${plural(w.contatos.a_conferir, "contato para conferir", "contatos para conferir")}`, "contatos"]);
  }
  return itens;
}

function pendenciasAnteriores(w) {
  const itens = [];
  const ok = (x) => x && !x.erro;
  if (ok(w.lembretes) && w.lembretes.nao_pagas_mes_passado.length) {
    itens.push([`Contas do mês passado sem marcar como pagas: ${w.lembretes.nao_pagas_mes_passado.join(", ")}`, "lembretes", "contas"]);
  }
  if (ok(w.atendimentos) && w.atendimentos.nao_pagos_mes_passado) {
    itens.push([`${plural(w.atendimentos.nao_pagos_mes_passado, "atendimento do mês passado ficou", "atendimentos do mês passado ficaram")} sem pagar`, "atendimentos"]);
  }
  if (ok(w.tratamentos) && w.tratamentos.nao_vieram_mes_passado) {
    itens.push([`${plural(w.tratamentos.nao_vieram_mes_passado, "paciente de orto não veio", "pacientes de orto não vieram")} no mês passado`, "tratamentos", "historico"]);
  }
  if (ok(w.tratamentos) && w.tratamentos.altas_terminadas) {
    itens.push([plural(w.tratamentos.altas_terminadas, "alta temporária terminou", "altas temporárias terminaram"), "tratamentos", "altas"]);
  }
  return itens;
}

registrarWidget("hoje", {
  icone: "i-casa",
  desenhar(corpo, _dados, w) {
    const hora = new Date().getHours();
    const saudacao = hora < 12 ? "Bom dia" : hora < 18 ? "Boa tarde" : "Boa noite";
    const nome = (estado.cfg.assistente_nome || "").trim().split(" ")[0];
    corpo.append(texto("p", nome ? `${saudacao}, ${nome}!` : `${saudacao}!`, "ini-saudacao"));
    const hoje = pendenciasDeHoje(w);
    corpo.append(hoje.length ? listaDeLinks(hoje) : texto("p", "Nada urgente para hoje.", "ini-tudo-certo"));
    const antes = pendenciasAnteriores(w);
    if (antes.length) corpo.append(texto("p", "Dos meses anteriores", "ini-subtitulo"), listaDeLinks(antes));
  },
});
