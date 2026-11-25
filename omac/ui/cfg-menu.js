/* OMAC — menu das Configurações: a "cortina" no menu lateral, as categorias e a procura.
 *
 * Clicar em Configurações faz o botão subir até o topo do menu lateral trazendo as categorias por
 * baixo, como uma cortina que cobre o menu normal; embaixo fica o Voltar, que desce a cortina e
 * volta para a tela de antes. Sem animação no Otimizado e com "Reduzir animações".
 * Sempre abre em Geral (o João achou que lembrar a última categoria confunde).
 * O lado direito mostra a categoria inteira; em Mensagens, os itens embaixo dela são atalhos.
 * A procura aceita erro de digitação: "pixi", "piix" e "pxi" acham "Pix".
 */
"use strict";

const cfgMenu = { voltarPara: "inicio", categoria: "geral", indice: null, animacao: null, quadro: 0 };

/* As Configurações não são um módulo: o que elas precisam carregar ao aparecer fica aqui. */
modulos.config = {
  aoMostrar() {
    const anterior = estado.viewAnterior;
    if (anterior && anterior !== "config") cfgMenu.voltarPara = anterior;
    abrirCortina();
    mostrarCategoria("geral");
    carregarBackup();
    carregarDestinatario();
    carregarConfiguracoes(); // configuracoes.js: formato das notas e mensagens
  },
  aoSair() {
    fecharCortina();
    limparProcura();
  },
  // irPara("config", "backup") abre a categoria do grupo #g-backup; também aceita o id de um campo.
  irParaAba(alvo) { irParaConfiguracao(alvo); },
};

modulos.cfgMenu = {
  ligar() {
    const busca = $("#cfg-busca");
    busca.addEventListener("input", () => procurarNasConfiguracoes(busca.value));
    busca.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && busca.value) {
        e.preventDefault();
        e.stopPropagation();
        limparProcura();
      } else if (e.key === "Enter") {
        e.preventDefault();
        $("#cfg-resultados .cfg-resultado")?.click();
      }
    });
    $("#conteudo").addEventListener("scroll", () => {
      if (cfgMenu.categoria !== "mensagens" || cfgMenu.quadro) return;
      cfgMenu.quadro = requestAnimationFrame(() => { cfgMenu.quadro = 0; marcarMensagemVisivel(); });
    }, { passive: true });
  },
};

Object.assign(acoes, {
  "cfg-categoria": (alvo) => {
    limparProcura();
    mostrarCategoria(alvo.dataset.categoria);
  },
  "cfg-voltar": () => mostrarView(cfgMenu.voltarPara || "inicio"),
  "cfg-atalho": (alvo) => rolarAteConfiguracao(document.getElementById(alvo.dataset.alvo)),
  "cfg-resultado": (alvo) => {
    const item = cfgMenu.indice?.[Number(alvo.dataset.indice)];
    limparProcura();
    if (item) irParaElemento(item.alvo);
  },
});

/* ---------- Cortina ---------- */

function semAnimacao() {
  const html = document.documentElement;
  return html.dataset.visual === "otimizado" || html.dataset.movimento === "reduzido"
    || window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function botaoDasConfiguracoes() {
  return $('.lateral-rodape .menu-item[data-view="config"]');
}

/* A distância entre o botão Configurações (embaixo) e o título da cortina (em cima). */
function distanciaDaCortina() {
  return botaoDasConfiguracoes().getBoundingClientRect().top - $(".cfg-cortina-titulo").getBoundingClientRect().top;
}

function travarMenuNormal(travar) {
  $("#cfg-cortina").inert = !travar;
  $("#menu").inert = travar;
  $(".lateral-rodape").inert = travar;
}

function abrirCortina() {
  const html = document.documentElement;
  if (html.dataset.configAberta === "1") return;
  cfgMenu.animacao?.cancel();
  html.dataset.configAberta = "1";
  travarMenuNormal(true);
  if (semAnimacao()) return;
  // O título começa onde está o botão e sobe, trazendo as categorias por baixo.
  cfgMenu.animacao = $("#cfg-cortina").animate(
    [{ transform: `translateY(${distanciaDaCortina()}px)` }, { transform: "none" }],
    { duration: 420, easing: "cubic-bezier(.2, .8, .2, 1)" });
}

function fecharCortina() {
  const html = document.documentElement;
  if (html.dataset.configAberta !== "1") return;
  cfgMenu.animacao?.cancel();
  travarMenuNormal(false);
  const fim = () => {
    delete html.dataset.configAberta;
    cfgMenu.animacao = null;
  };
  if (semAnimacao()) return fim();
  html.dataset.configAberta = "fechando"; // o menu normal reaparece enquanto a cortina desce
  cfgMenu.animacao = $("#cfg-cortina").animate(
    [{ transform: "none" }, { transform: `translateY(${distanciaDaCortina()}px)` }],
    { duration: 340, easing: "cubic-bezier(.4, 0, .7, .2)" });
  cfgMenu.animacao.onfinish = fim;
  cfgMenu.animacao.oncancel = fim;
}

/* ---------- Categorias ---------- */

function mostrarCategoria(nome) {
  const atual = $(`.cfg-categoria[data-categoria="${nome}"]`);
  if (!atual) return;
  cfgMenu.categoria = nome;
  for (const c of $$(".cfg-categoria")) c.hidden = c !== atual;
  $("#t-config").textContent = atual.dataset.titulo;
  $("#cfg-sub").textContent = atual.dataset.sub;
  for (const b of $$("#cfg-categorias .cfg-cat")) {
    if (b.dataset.categoria === nome) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  }
  $("#cfg-sub-mensagens").hidden = nome !== "mensagens" || !$("#cfg-sub-mensagens").childElementCount;
  $("#conteudo").scrollTop = 0;
  marcarMensagemVisivel();
}

function irParaConfiguracao(alvo) {
  if ($(`.cfg-categoria[data-categoria="${alvo}"]`)) return mostrarCategoria(alvo);
  const el = document.getElementById(`g-${alvo}`) || document.getElementById(alvo);
  if (el) irParaElemento(el);
}

/* Abre a categoria do elemento, rola até ele e dá um destaque rápido. Campo de texto (ou o
 * rótulo dele, como "Chave Pix" achado na procura) põe o cursor no campo. */
function irParaElemento(el) {
  const categoria = el.closest(".cfg-categoria");
  if (!categoria) return;
  if (cfgMenu.categoria !== categoria.dataset.categoria) mostrarCategoria(categoria.dataset.categoria);
  const bloco = el.matches("h2, h3") ? el.closest(".grupo") : el.closest(".opcao, .campo, fieldset, .cfg-msg, .grupo") || el;
  rolarAteConfiguracao(bloco);
  const campo = el.matches("label") ? el.control : el;
  if (campo?.matches("input:not([type=range]), textarea, select")) campo.focus({ preventScroll: true });
}

function rolarAteConfiguracao(el) {
  if (!el) return;
  el.scrollIntoView({ block: "start", behavior: semAnimacao() ? "auto" : "smooth" });
  el.classList.remove("cfg-destaque");
  void el.offsetWidth; // reinicia o destaque
  el.classList.add("cfg-destaque");
  setTimeout(() => el.classList.remove("cfg-destaque"), 1600);
}

/* ---------- Mensagens: atalhos no menu ---------- */

/* `grupos`: [{nome, mensagens: [{tipo, titulo}]}] (vem de configuracoes.js). */
function desenharAtalhosDasMensagens(grupos) {
  const caixa = $("#cfg-sub-mensagens");
  caixa.replaceChildren(...grupos.flatMap((g) => [
    texto("span", g.nome, "cfg-sub-grupo"),
    ...g.mensagens.map((m) => {
      const b = Object.assign(document.createElement("button"), { type: "button", className: "cfg-atalho", textContent: m.titulo });
      b.dataset.acao = "cfg-atalho";
      b.dataset.alvo = `cfg-msg-${m.tipo}`;
      return b;
    }),
  ]));
  caixa.hidden = cfgMenu.categoria !== "mensagens";
  cfgMenu.indice = null; // a procura passa a achar as mensagens novas
  marcarMensagemVisivel();
}

/* O atalho da mensagem que está no alto da tela fica marcado enquanto rola. */
function marcarMensagemVisivel() {
  if (cfgMenu.categoria !== "mensagens") return;
  const cartoes = $$("#cfg-msg-lista .cfg-msg");
  if (!cartoes.length) return;
  const conteudo = $("#conteudo");
  const linha = conteudo.getBoundingClientRect().top + 120;
  let atual = cartoes[0];
  for (const c of cartoes) if (c.getBoundingClientRect().top <= linha) atual = c;
  if (conteudo.scrollTop + conteudo.clientHeight >= conteudo.scrollHeight - 2) atual = cartoes[cartoes.length - 1];
  for (const b of $$("#cfg-sub-mensagens .cfg-atalho")) {
    if (b.dataset.alvo === atual.id) b.setAttribute("aria-current", "true");
    else b.removeAttribute("aria-current");
  }
}

/* ---------- Procura aproximada ---------- */

const PECAS_DA_PROCURA = "h2, h3, legend, label, .rotulo-campo, .opcao-texto strong, .opcao-texto small, .escolha, .dica, .cfg-variaveis .btn";

function semAcento(s) {
  return String(s).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

function palavrasDe(s) {
  return semAcento(s).split(/[^a-z0-9]+/).filter(Boolean);
}

/* Cada pedaço de texto das Configurações (títulos, rótulos, explicações), com onde ele fica. */
function indiceDaProcura() {
  if (cfgMenu.indice) return cfgMenu.indice;
  const itens = [];
  for (const el of $$(`#view-config :is(${PECAS_DA_PROCURA})`)) {
    const oculto = el.closest("[hidden]");
    if (oculto && !oculto.classList.contains("cfg-categoria")) continue; // ex.: "Disponível só no .exe"
    const frase = el.textContent.replace(/\s+/g, " ").trim();
    const categoria = el.closest(".cfg-categoria");
    if (!frase || !categoria) continue;
    const grupo = el.closest(".grupo");
    itens.push({
      frase, alvo: el, palavras: palavrasDe(frase),
      titulo: el.matches("h2, h3, legend, label, .rotulo-campo, .opcao-texto strong"),
      onde: grupo, categoria: categoria.dataset.titulo,
      nomeDoGrupo: grupo?.querySelector("h2, h3")?.textContent.trim() || "",
    });
  }
  cfgMenu.indice = itens;
  return itens;
}

/* Distância entre duas palavras (letra trocada, sobrando, faltando ou duas invertidas), parando em `max`. */
function distanciaEntre(a, b, max) {
  if (Math.abs(a.length - b.length) > max) return max + 1;
  let anterior2 = null;
  let anterior = Array.from({ length: b.length + 1 }, (_, j) => j);
  for (let i = 1; i <= a.length; i++) {
    const linha = [i];
    let menor = i;
    for (let j = 1; j <= b.length; j++) {
      const custo = a[i - 1] === b[j - 1] ? 0 : 1;
      let d = Math.min(anterior[j] + 1, linha[j - 1] + 1, anterior[j - 1] + custo);
      if (anterior2 && i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) d = Math.min(d, anterior2[j - 2] + 1);
      linha.push(d);
      menor = Math.min(menor, d);
    }
    if (menor > max) return max + 1;
    anterior2 = anterior;
    anterior = linha;
  }
  return anterior[b.length];
}

/* Quanto a palavra procurada casa com uma palavra do texto: 0 = não casa.
 * Aceita 1 erro em palavra de 3 a 5 letras e 2 nas maiores; com 1 ou 2 letras, só o começo.
 * Com erro, a primeira letra tem de bater: quase ninguém erra a primeira, e sem isso
 * palavras curtas casam com muita coisa ("país" com "mais"). */
function casamento(procurada, palavra) {
  if (palavra === procurada) return 3;
  if (palavra.startsWith(procurada)) return 2.5;
  const tolerancia = procurada.length <= 2 ? 0 : procurada.length <= 5 ? 1 : 2;
  if (!tolerancia || palavra[0] !== procurada[0]) return 0;
  if (distanciaEntre(procurada, palavra, tolerancia) <= tolerancia) return 2;
  // Ainda digitando: compara com o começo da palavra ("confgu" acha "configurações").
  if (procurada.length >= 4 && palavra.length > procurada.length
    && distanciaEntre(procurada, palavra.slice(0, procurada.length), tolerancia) <= tolerancia) return 1.5;
  return 0;
}

function pontosDoItem(item, procuradas) {
  let total = 0;
  for (const p of procuradas) {
    let melhor = 0;
    for (const w of item.palavras) melhor = Math.max(melhor, casamento(p, w));
    if (!melhor) return 0; // todas as palavras procuradas precisam aparecer
    total += melhor;
  }
  return total + (item.titulo ? 0.5 : 0);
}

function procurarNasConfiguracoes(consulta) {
  const procuradas = palavrasDe(consulta);
  const lista = $("#cfg-resultados");
  const procurando = procuradas.length > 0;
  $("#cfg-categorias").hidden = procurando;
  lista.hidden = !procurando;
  if (!procurando) return lista.replaceChildren();

  // O melhor pedaço de cada bloco, para o mesmo bloco não aparecer várias vezes.
  const indice = indiceDaProcura();
  const melhores = new Map();
  indice.forEach((item, i) => {
    const pontos = pontosDoItem(item, procuradas);
    const chave = item.onde || item.alvo;
    if (pontos && (!melhores.has(chave) || pontos > melhores.get(chave).pontos)) melhores.set(chave, { item, i, pontos });
  });
  const achados = [...melhores.values()].sort((a, b) => b.pontos - a.pontos).slice(0, 8);
  if (!achados.length) {
    return lista.replaceChildren(texto("p", `Nada encontrado para “${consulta.trim()}”.`, "cfg-nada"));
  }
  lista.replaceChildren(...achados.map(({ item, i }) => {
    const b = Object.assign(document.createElement("button"), { type: "button", className: "cfg-resultado" });
    b.dataset.acao = "cfg-resultado";
    b.dataset.indice = i;
    const frase = item.frase.length > 70 ? `${item.frase.slice(0, 68)}…` : item.frase;
    const grupo = item.nomeDoGrupo;
    const onde = grupo && grupo !== item.frase && grupo !== item.categoria ? `${item.categoria} › ${grupo}` : item.categoria;
    b.append(texto("strong", frase), texto("small", onde));
    return b;
  }));
}

function limparProcura() {
  const busca = $("#cfg-busca");
  if (!busca.value && $("#cfg-resultados").hidden) return;
  busca.value = "";
  procurarNasConfiguracoes("");
}
