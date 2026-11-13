/* OMAC — núcleo da interface: configurações, navegação, avisos e ações.
 *
 * Fala com o Python por window.pywebview.api.<método>(), que devolve uma
 * Promise. Erros do Python chegam como { erro: "mensagem" }.
 *
 * Cada módulo (notas.js, extrato.js…) se registra assim:
 *   modulos.nome = { aoMostrar() {}, carregar() {}, ligar() {}, aoIniciar() {} };   // nome = data-view do menu
 *   Object.assign(acoes, { "minha-acao": (alvo) => {} }); // data-acao dos botões
 */
"use strict";

const MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
  "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];
const PASSOS_FONTE = [1, 1.15, 1.3, 1.5, 1.75, 2];

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));
const real = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

const estado = {
  cfg: null,
  ano: 0,
  mes: 0,
  view: "",
};

const modulos = {};
const acoes = {};

const api = () => window.pywebview.api;

/* ---------- Início ---------- */

/* Um script vazio ou cortado não gera erro nenhum: sem esta conferência, a tela fica muda. */
const MODULOS_ESPERADOS = ["inicio", "notas", "extrato", "whatsapp", "agendamentos", "pagamentos", "resumo", "atualizacao"];

async function conferirModulos() {
  for (const nome of MODULOS_ESPERADOS.filter((m) => !modulos[m])) {
    let detalhe = "";
    try {
      const resposta = await fetch(`${nome}.js`);
      detalhe = `HTTP ${resposta.status}, ${(await resposta.text()).length} letras`;
    } catch (e) {
      detalhe = `não abriu (${e.message})`;
    }
    omacMostrarErroDeTela(`Módulo ${nome} não rodou: ${detalhe}`);
  }
}

async function iniciar() {
  conferirModulos();
  const r = await api().estado();
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  estado.cfg = r.config;
  $("#versao").textContent = `versão ${r.versao}`;
  $("#sobre-versao").textContent = r.versao;

  // No começo do mês o relatório costuma ser do mês anterior.
  const hoje = new Date();
  const base = hoje.getDate() <= 15 ? new Date(hoje.getFullYear(), hoje.getMonth() - 1, 1) : hoje;
  estado.ano = base.getFullYear();
  estado.mes = base.getMonth() + 1;

  aplicarConfig();
  ligarEventos();
  mostrarView(estado.cfg.abrir_em === "notas" ? "notas" : "inicio");
  carregarInicioAutomatico();
  Object.values(modulos).forEach((m) => m.aoIniciar?.());
}

// DOMContentLoaded: espera os scripts dos módulos, que vêm depois deste.
document.addEventListener("DOMContentLoaded", () => {
  if (window.pywebview && window.pywebview.api) iniciar();
  else window.addEventListener("pywebviewready", iniciar, { once: true });
});

/* ---------- Configurações ---------- */

const temaEscuroSistema = window.matchMedia("(prefers-color-scheme: dark)");
temaEscuroSistema.addEventListener("change", () => { if (estado.cfg) aplicarConfig(); });

function aplicarConfig() {
  const c = estado.cfg;
  const html = document.documentElement;
  const escuro = c.tema === "escuro" || (c.tema === "sistema" && temaEscuroSistema.matches);
  html.dataset.tema = escuro ? "escuro" : "claro";
  html.dataset.visual = c.visual;
  html.style.setProperty("--escala", c.escala_fonte);
  if (c.alto_contraste) html.dataset.contraste = "alto"; else delete html.dataset.contraste;
  if (c.reduzir_movimento) html.dataset.movimento = "reduzido"; else delete html.dataset.movimento;

  $$(".escolhas[data-config]").forEach((grupo) => {
    grupo.querySelectorAll(".escolha").forEach((b) => {
      b.setAttribute("aria-pressed", String(b.dataset.valor === c[grupo.dataset.config]));
    });
  });
  $$("[data-config-bool]").forEach((b) => b.setAttribute("aria-checked", String(!!c[b.dataset.configBool])));
  $$("[data-config-campo]").forEach((el) => {
    // Não mexe no campo em que a pessoa está digitando.
    if (el !== document.activeElement) el.value = c[el.dataset.configCampo];
  });
  $("#escala").value = c.escala_fonte;
  $("#escala-valor").textContent = `${Math.round(c.escala_fonte * 100)}%`;
  mostrarPastas();
  desenharFaixasRecolhiveis();
  ajustarTrilho();
}

let salvarTimer = null;
let configPendente = {};
function mudarConfig(parcial) {
  Object.assign(estado.cfg, parcial);
  Object.assign(configPendente, parcial);
  aplicarConfig();
  clearTimeout(salvarTimer);
  salvarTimer = setTimeout(async () => {
    // Só o que mudou aqui: o Python também salva coisas, como a última pasta de exportação.
    const mudancas = configPendente;
    configPendente = {};
    const r = await api().salvar_config(mudancas);
    if (r && r.erro) mostrarToast(`Não consegui salvar as configurações: ${r.erro}`, { erro: true });
  }, 300);
}

function mudarFonte(direcao) {
  const atual = estado.cfg.escala_fonte;
  let novo;
  if (direcao === 0) novo = 1;
  else if (direcao > 0) novo = PASSOS_FONTE.find((p) => p > atual + 0.001) ?? 2;
  else novo = [...PASSOS_FONTE].reverse().find((p) => p < atual - 0.001) ?? 1;
  mudarConfig({ escala_fonte: novo });
}

async function carregarInicioAutomatico() {
  const r = await api().inicio_automatico();
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  desenharInicioAutomatico(r);
}

function desenharInicioAutomatico({ disponivel, ligado }) {
  const chave = $("#chave-inicio");
  chave.disabled = !disponivel;
  chave.setAttribute("aria-checked", String(ligado));
  $("#inicio-indisponivel").hidden = disponivel;
}

async function alternarInicioAutomatico(chave) {
  const r = await api().definir_inicio_automatico(chave.getAttribute("aria-checked") !== "true");
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  desenharInicioAutomatico(r);
}

/* Menu lateral só com ícones quando não cabe (janela estreita ou letra grande),
 * e com os itens mais juntos quando a janela é baixa, para não precisar rolar. */
function ajustarTrilho() {
  const rem = 16 * (estado.cfg ? estado.cfg.escala_fonte : 1);
  const html = document.documentElement;
  if (window.innerWidth / rem < 58) html.dataset.trilho = "1";
  else delete html.dataset.trilho;
  if (window.innerHeight / rem < 30) html.dataset.menuCompacto = "1";
  else delete html.dataset.menuCompacto;
}
window.addEventListener("resize", ajustarTrilho);

function mostrarPastas() {
  $$("[data-pasta]").forEach((el) => {
    const pasta = estado.cfg[el.dataset.pasta];
    // O <bdi> evita que o direction:rtl (que corta o começo do caminho) embaralhe as barras.
    el.replaceChildren(Object.assign(document.createElement("bdi"), {
      textContent: pasta || "Nenhuma pasta escolhida",
    }));
    el.title = pasta || "";
  });
}

async function escolherPasta(chave) {
  const r = await api().escolher_pasta(chave);
  if (!r || r.cancelado) return;
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  estado.cfg = r.config;
  aplicarConfig();
  const destino = chave === "pasta_extratos" ? "extrato" : "notas";
  mostrarView(destino);
  await modulos[destino].carregar();
}

/* ---------- Navegação ---------- */

function mostrarView(nome) {
  estado.view = nome;
  $$(".view").forEach((v) => {
    const ativa = v.id === `view-${nome}`;
    v.hidden = !ativa;
    if (ativa) {
      v.classList.remove("view-entrando");
      void v.offsetWidth; // reinicia a animação
      v.classList.add("view-entrando");
    }
  });
  $$(".menu-item").forEach((b) => {
    if (b.dataset.view === nome) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  });
  $("#conteudo").scrollTop = 0;
  modulos[nome]?.aoMostrar?.();
}

/* ---------- Mês e ano (são os mesmos em todos os módulos) ---------- */

function preencherSeletores(selMes, selAno, contagens) {
  const qtd = new Map(contagens.map(([a, m, n]) => [`${a}-${m}`, n]));
  const anos = new Set(contagens.map(([a]) => a));
  anos.add(estado.ano);
  anos.add(new Date().getFullYear());

  selAno.replaceChildren(...[...anos].sort().map((a) => new Option(String(a), String(a))));
  selAno.value = String(estado.ano);

  selMes.replaceChildren(...MESES.map((nome, i) => {
    const n = qtd.get(`${estado.ano}-${i + 1}`);
    return new Option(n ? `${nome} (${n})` : nome, String(i + 1));
  }));
  selMes.value = String(estado.mes);
}

function mudarMes(ano, mes) {
  estado.ano = ano;
  estado.mes = mes;
  modulos[estado.view]?.carregar?.();
}

/* Botões para ir direto aos meses que têm dados, os mais recentes primeiro. */
function botoesDeMeses(contagens, singular, plural) {
  return [...contagens].reverse().slice(0, 8).map(([a, m, n]) => {
    const b = document.createElement("button");
    b.className = "btn btn-peq";
    b.dataset.acao = "ir-mes";
    b.dataset.ano = a;
    b.dataset.mes = m;
    b.textContent = `${MESES[m - 1]} ${a} · ${n} ${n === 1 ? singular : plural}`;
    return b;
  });
}

function dataBR(iso) {
  const [a, m, d] = iso.split("-");
  return `${d}/${m}/${a}`;
}

function listaDeAvisos(itens) {
  return itens.map(([titulo, msg]) => {
    const li = document.createElement("li");
    if (titulo) li.append(Object.assign(document.createElement("b"), { textContent: `${titulo}: ` }));
    li.append(msg);
    return li;
  });
}

/* ---------- Peças usadas por vários módulos ---------- */

function botaoIcone(acao, icone, rotulo, dados) {
  const b = document.createElement("button");
  b.type = "button";
  b.className = "btn-linha";
  b.dataset.acao = acao;
  Object.assign(b.dataset, dados);
  b.title = rotulo;
  b.setAttribute("aria-label", rotulo);
  b.innerHTML = `<svg class="ic"><use href="#${icone}"/></svg>`;
  return b;
}

function celula(texto, classe = "") {
  return Object.assign(document.createElement("td"), { className: classe, textContent: texto });
}

function telefoneBR(digitos) {
  const m = /^55(\d{2})(\d{4,5})(\d{4})$/.exec(digitos);
  return m ? `(${m[1]}) ${m[2]}-${m[3]}` : digitos;
}

/* Faixas de aviso que dá para minimizar: seguem visíveis, mostrando só a quantidade. */
function desenharFaixasRecolhiveis() {
  $$("[data-recolhivel]").forEach((faixa) => {
    const recolhida = estado.cfg.avisos_recolhidos.includes(faixa.dataset.recolhivel);
    faixa.classList.toggle("recolhida", recolhida);
    faixa.querySelector(".lista-simples").hidden = recolhida;
    const cabecalho = faixa.querySelector(".faixa-cab");
    cabecalho.setAttribute("aria-expanded", String(!recolhida));
    cabecalho.querySelector(".faixa-acao").textContent = recolhida ? "Ver avisos" : "Minimizar";
  });
}

function recolherFaixa(faixa, recolher) {
  const id = faixa.dataset.recolhivel;
  const outras = estado.cfg.avisos_recolhidos.filter((r) => r !== id);
  mudarConfig({ avisos_recolhidos: recolher ? [...outras, id] : outras });
}

function mostrarQtdAvisos(faixa, qtd) {
  faixa.hidden = qtd === 0;
  faixa.querySelector(".faixa-qtd").textContent = `${qtd} ${qtd === 1 ? "aviso" : "avisos"}`;
}

/* ---------- Notificações ---------- */

function mostrarToast(texto, { erro = false, acoes: botoes = [] } = {}) {
  const t = document.createElement("div");
  t.className = `toast vidro${erro ? " erro" : ""}`;
  t.setAttribute("role", erro ? "alert" : "status");
  t.innerHTML = `<svg class="ic"><use href="#${erro ? "i-alerta" : "i-ok"}"/></svg>`;
  t.append(Object.assign(document.createElement("span"), { className: "toast-texto", textContent: texto }));

  const caixa = document.createElement("div");
  caixa.className = "toast-acoes";
  for (const [rotulo, fn] of botoes) {
    const b = Object.assign(document.createElement("button"), { className: "btn btn-peq", textContent: rotulo });
    b.addEventListener("click", fn);
    caixa.append(b);
  }
  const fechar = Object.assign(document.createElement("button"), { className: "btn btn-peq btn-icone" });
  fechar.setAttribute("aria-label", "Fechar aviso");
  fechar.innerHTML = '<svg class="ic"><use href="#i-fechar"/></svg>';
  fechar.addEventListener("click", () => t.remove());
  caixa.append(fechar);
  t.append(caixa);

  $("#toasts").append(t);
  // Erro fica até fechar; o resto some sozinho (com tempo de sobra para ler).
  if (!erro) setTimeout(() => t.remove(), 12000);
}

function toastDeArquivo(texto, caminho) {
  mostrarToast(texto, {
    acoes: [
      ["Abrir", () => api().abrir(caminho)],
      ["Mostrar na pasta", () => api().mostrar_na_pasta(caminho)],
    ],
  });
}

/* ---------- Eventos ---------- */

Object.assign(acoes, {
  "escolher-pasta": (alvo) => escolherPasta(alvo.dataset.chave),
  "abrir-pasta": (alvo) => api().abrir_pasta(alvo.dataset.chave),
  "ir-mes": (alvo) => mudarMes(Number(alvo.dataset.ano), Number(alvo.dataset.mes)),
  "fonte-mais": () => mudarFonte(1),
  "fonte-menos": () => mudarFonte(-1),
  "alternar-inicio": alternarInicioAutomatico,
  "alternar-avisos": (alvo) => {
    const faixa = alvo.closest("[data-recolhivel]");
    recolherFaixa(faixa, !faixa.classList.contains("recolhida"));
  },
  "abrir-pasta-dados": () => api().abrir_pasta_dados(),
});

function ligarEventos() {
  $$(".menu-item").forEach((b) => {
    b.title = b.querySelector(".rotulo").firstChild.textContent.trim(); // aparece quando o menu mostra só ícones
    b.addEventListener("click", () => mostrarView(b.dataset.view));
  });

  $$(".escolhas[data-config] .escolha").forEach((b) => b.addEventListener("click", () => {
    mudarConfig({ [b.closest(".escolhas").dataset.config]: b.dataset.valor });
  }));
  $$("[data-config-bool]").forEach((b) => b.addEventListener("click", () => {
    mudarConfig({ [b.dataset.configBool]: !estado.cfg[b.dataset.configBool] });
  }));
  $$("[data-config-campo]").forEach((el) => {
    const evento = el.tagName === "SELECT" ? "change" : "input";
    el.addEventListener(evento, () => {
      const valor = el.dataset.tipo === "numero" ? Number(el.value) : el.value;
      mudarConfig({ [el.dataset.configCampo]: valor });
    });
  });
  $("#escala").addEventListener("input", (e) => mudarConfig({ escala_fonte: Number(e.target.value) }));

  $$("[data-sel-mes]").forEach((s) => s.addEventListener("change", (e) => mudarMes(estado.ano, Number(e.target.value))));
  $$("[data-sel-ano]").forEach((s) => s.addEventListener("change", (e) => mudarMes(Number(e.target.value), estado.mes)));

  document.addEventListener("click", (e) => {
    const alvo = e.target.closest("[data-acao]");
    if (!alvo || alvo.disabled) return;
    acoes[alvo.dataset.acao]?.(alvo);
  });

  document.addEventListener("keydown", (e) => {
    if (!e.ctrlKey || e.altKey) return;
    if (e.key === "+" || e.key === "=") { e.preventDefault(); mudarFonte(1); }
    else if (e.key === "-" || e.key === "_") { e.preventDefault(); mudarFonte(-1); }
    else if (e.key === "0") { e.preventDefault(); mudarFonte(0); }
  });

  Object.values(modulos).forEach((m) => m.ligar?.());
}
