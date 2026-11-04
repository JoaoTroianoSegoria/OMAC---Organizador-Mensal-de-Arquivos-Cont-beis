/* OMAC — interface
 *
 * Fala com o Python por window.pywebview.api.<método>(), que devolve uma
 * Promise. Erros do Python chegam como { erro: "mensagem" }.
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
  dados: null,
  carregando: false,
};

const api = () => window.pywebview.api;

/* ---------- Início ---------- */

async function iniciar() {
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
  preencherSeletores([]);
  await carregar();
}

if (window.pywebview && window.pywebview.api) iniciar();
else window.addEventListener("pywebviewready", iniciar, { once: true });

/* ---------- Configurações ---------- */

const temaEscuroSistema = window.matchMedia("(prefers-color-scheme: dark)");
temaEscuroSistema.addEventListener("change", () => aplicarConfig());

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
  $("#escala").value = c.escala_fonte;
  $("#escala-valor").textContent = `${Math.round(c.escala_fonte * 100)}%`;
  mostrarPasta(c.pasta_notas);
  ajustarTrilho();
}

let salvarTimer = null;
function mudarConfig(parcial) {
  Object.assign(estado.cfg, parcial);
  aplicarConfig();
  clearTimeout(salvarTimer);
  salvarTimer = setTimeout(async () => {
    const r = await api().salvar_config(estado.cfg);
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

/* Menu lateral só com ícones quando não cabe (janela estreita ou letra grande). */
function ajustarTrilho() {
  const larguraEmRem = window.innerWidth / (16 * (estado.cfg ? estado.cfg.escala_fonte : 1));
  if (larguraEmRem < 58) document.documentElement.dataset.trilho = "1";
  else delete document.documentElement.dataset.trilho;
}
window.addEventListener("resize", ajustarTrilho);

function mostrarPasta(pasta) {
  const texto = pasta || "Nenhuma pasta escolhida";
  for (const el of [$("#pasta-texto"), $("#cfg-pasta-texto")]) {
    // O <bdi> evita que o direction:rtl (que corta o começo do caminho) embaralhe as barras.
    el.replaceChildren(Object.assign(document.createElement("bdi"), { textContent: texto }));
    el.title = pasta || "";
  }
}

/* ---------- Navegação ---------- */

function mostrarView(nome) {
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
}

/* ---------- Notas ---------- */

function preencherSeletores(competencias) {
  const qtd = new Map(competencias.map(([a, m, n]) => [`${a}-${m}`, n]));
  const anos = new Set(competencias.map(([a]) => a));
  anos.add(estado.ano);
  anos.add(new Date().getFullYear());

  const selAno = $("#sel-ano");
  selAno.replaceChildren(...[...anos].sort().map((a) => new Option(String(a), String(a))));
  selAno.value = String(estado.ano);

  const selMes = $("#sel-mes");
  selMes.replaceChildren(...MESES.map((nome, i) => {
    const n = qtd.get(`${estado.ano}-${i + 1}`);
    return new Option(n ? `${nome} (${n})` : nome, String(i + 1));
  }));
  selMes.value = String(estado.mes);
}

let progressoTimer = null;
window.omacProgresso = (feitos, total) => {
  const pct = total ? Math.round((feitos / total) * 100) : 100;
  $("#progresso-texto").textContent = `Lendo as notas… ${feitos} de ${total}`;
  $("#progresso-cheio").style.width = `${pct}%`;
  $("#progresso-barra").setAttribute("aria-valuenow", String(pct));
};

async function carregar() {
  if (estado.carregando) return;
  if (!estado.cfg.pasta_notas) {
    $("#sem-pasta").hidden = false;
    $("#painel-notas").hidden = true;
    return;
  }
  estado.carregando = true;
  const btn = $("#btn-atualizar");
  btn.disabled = true;
  btn.classList.add("girando");
  // Só mostra a barra se demorar (com o cache, normalmente é instantâneo).
  progressoTimer = setTimeout(() => { $("#progresso").hidden = false; }, 250);

  try {
    const r = await api().notas_do_mes(estado.ano, estado.mes);
    if (r.sem_pasta) {
      $("#sem-pasta").hidden = false;
      $("#painel-notas").hidden = true;
      return;
    }
    if (r.erro) {
      mostrarToast(r.erro, { erro: true });
      return;
    }
    estado.dados = r;
    preencherSeletores(r.competencias);
    desenharNotas();
  } finally {
    clearTimeout(progressoTimer);
    $("#progresso").hidden = true;
    btn.disabled = false;
    btn.classList.remove("girando");
    estado.carregando = false;
  }
}

function dataBR(iso) {
  const [a, m, d] = iso.split("-");
  return `${d}/${m}/${a}`;
}

function desenharNotas() {
  const { notas, total_centavos, avisos, canceladas_movidas } = estado.dados;
  $("#sem-pasta").hidden = true;
  $("#painel-notas").hidden = false;

  const nomeMes = `${MESES[estado.mes - 1]} de ${estado.ano}`;
  const total = real.format(total_centavos / 100);
  $("#res-qtd").textContent = String(notas.length);
  $("#res-total").textContent = total;
  $("#rod-qtd").textContent = `Total (${notas.length} ${notas.length === 1 ? "nota" : "notas"})`;
  $("#rod-total").textContent = total;
  $("#tabela-legenda").textContent = `Notas fiscais com competência em ${nomeMes}`;

  // Tabela
  const corpo = document.createDocumentFragment();
  for (const n of notas) {
    const tr = document.createElement("tr");

    const tdNum = document.createElement("td");
    tdNum.className = "c-num";
    tdNum.textContent = n.numero;

    const tdPac = document.createElement("td");
    const caixa = document.createElement("div");
    caixa.className = "paciente";
    caixa.append(Object.assign(document.createElement("span"), { textContent: n.paciente }));
    if (n.dependente) {
      caixa.append(Object.assign(document.createElement("span"), {
        className: "etiqueta", textContent: "dependente",
        title: "Nome do dependente que está na descrição do serviço",
      }));
    }
    if (n.avisos.length) {
      const et = document.createElement("span");
      et.className = "etiqueta etiqueta-aviso";
      et.title = n.avisos.join("\n");
      et.innerHTML = '<svg class="ic"><use href="#i-alerta"/></svg>';
      et.append("aviso");
      caixa.append(et);
    }
    tdPac.append(caixa);

    const tdValor = document.createElement("td");
    tdValor.className = "c-valor";
    tdValor.textContent = real.format(n.valor_centavos / 100);

    const tdEm = document.createElement("td");
    tdEm.className = "c-data";
    tdEm.textContent = dataBR(n.emissao);

    const tdComp = document.createElement("td");
    tdComp.className = "c-data";
    tdComp.textContent = dataBR(n.competencia);

    const tdAcao = document.createElement("td");
    tdAcao.className = "c-acao";
    const abrir = document.createElement("button");
    abrir.className = "btn-linha";
    abrir.dataset.acao = "abrir-nota";
    abrir.dataset.arquivo = n.arquivo;
    abrir.title = "Abrir o PDF da nota";
    abrir.setAttribute("aria-label", `Abrir o PDF da nota ${n.numero}`);
    abrir.innerHTML = '<svg class="ic"><use href="#i-abrir"/></svg>';
    tdAcao.append(abrir);

    tr.append(tdNum, tdPac, tdValor, tdEm, tdComp, tdAcao);
    corpo.append(tr);
  }
  $("#tabela-corpo").replaceChildren(corpo);
  desenharVazio(nomeMes);

  // Avisos: os de cada nota do mês + os gerais da pasta
  const itens = [];
  for (const n of notas) for (const a of n.avisos) itens.push([`Nota nº ${n.numero}`, a]);
  for (const a of avisos) itens.push([a.arquivo || "", a.mensagem]);
  $("#avisos-lista").replaceChildren(...itens.map(([titulo, msg]) => {
    const li = document.createElement("li");
    if (titulo) li.append(Object.assign(document.createElement("b"), { textContent: `${titulo}: ` }));
    li.append(msg);
    return li;
  }));
  $("#faixa-avisos").hidden = itens.length === 0;
  $("#res-avisos").textContent = String(itens.length);
  $("#res-avisos-cartao").classList.toggle("tem", itens.length > 0);

  // Canceladas movidas nesta leitura
  $("#faixa-canceladas").hidden = canceladas_movidas.length === 0;
  if (canceladas_movidas.length) {
    const n = canceladas_movidas.length;
    $("#canceladas-titulo").textContent = n === 1
      ? "1 nota cancelada foi movida para a pasta “Canceladas”:"
      : `${n} notas canceladas foram movidas para a pasta “Canceladas”:`;
    $("#canceladas-lista").replaceChildren(...canceladas_movidas.map((a) =>
      Object.assign(document.createElement("li"), { textContent: a })));
  }

  $$('[data-acao="exportar"]').forEach((b) => { b.disabled = notas.length === 0; });
}

/* Sem notas: no lugar dos cartões e da tabela, explica o porquê e o que fazer. */
function desenharVazio(nomeMes) {
  const { notas, qtd_pasta, competencias } = estado.dados;
  const vazio = notas.length === 0;
  $("#resumo").hidden = vazio;
  $("#tabela-caixa").hidden = vazio;
  $("#notas-vazio").hidden = !vazio;
  if (!vazio) return;

  const pastaVazia = qtd_pasta === 0;
  $("#notas-vazio-ic").setAttribute("href", pastaVazia ? "#i-pasta" : "#i-notas");
  $("#notas-vazio-acoes").hidden = !pastaVazia;
  if (pastaVazia) {
    $("#notas-vazio-titulo").textContent = "Nenhuma nota nesta pasta";
    $("#notas-vazio-texto").textContent =
      "Não encontrei PDFs de notas direto na pasta escolhida. O OMAC não olha dentro de subpastas: " +
      "confira se é a pasta onde as notas do ano ficam (por exemplo, NFS‑e\u00a02026).";
    $("#notas-vazio-meses").replaceChildren();
    return;
  }

  $("#notas-vazio-titulo").textContent = `Nenhuma nota em ${nomeMes}`;
  $("#notas-vazio-texto").textContent =
    `A pasta tem ${qtd_pasta} ${qtd_pasta === 1 ? "nota" : "notas"}, mas nenhuma com competência neste mês. ` +
    "Meses com notas:";
  // Os meses mais recentes primeiro
  $("#notas-vazio-meses").replaceChildren(...[...competencias].reverse().slice(0, 8).map(([a, m, n]) => {
    const b = document.createElement("button");
    b.className = "btn btn-peq";
    b.dataset.acao = "ir-mes";
    b.dataset.ano = a;
    b.dataset.mes = m;
    b.textContent = `${MESES[m - 1]} ${a} · ${n} ${n === 1 ? "nota" : "notas"}`;
    return b;
  }));
}

async function exportar(formato) {
  const r = await api().exportar(estado.ano, estado.mes, formato);
  if (!r || r.cancelado) return;
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  estado.cfg.formato = formato;
  aplicarConfig();
  const nome = r.caminho.split(/[\\/]/).pop();
  mostrarToast(`Planilha salva: ${nome}`, {
    acoes: [
      ["Abrir", () => api().abrir(r.caminho)],
      ["Mostrar na pasta", () => api().mostrar_na_pasta(r.caminho)],
    ],
  });
}

async function escolherPasta() {
  const r = await api().escolher_pasta();
  if (!r || r.cancelado) return;
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  estado.cfg = r.config;
  aplicarConfig();
  mostrarView("notas");
  await carregar();
}

async function abrirNota(arquivo) {
  const r = await api().abrir_nota(arquivo);
  if (r && r.erro) mostrarToast(r.erro, { erro: true });
}

/* ---------- Notificações ---------- */

function mostrarToast(texto, { erro = false, acoes = [] } = {}) {
  const t = document.createElement("div");
  t.className = `toast vidro${erro ? " erro" : ""}`;
  t.setAttribute("role", erro ? "alert" : "status");
  t.innerHTML = `<svg class="ic"><use href="#${erro ? "i-alerta" : "i-ok"}"/></svg>`;
  t.append(Object.assign(document.createElement("span"), { className: "toast-texto", textContent: texto }));

  const caixa = document.createElement("div");
  caixa.className = "toast-acoes";
  for (const [rotulo, fn] of acoes) {
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

/* ---------- Eventos ---------- */

function ligarEventos() {
  $$(".menu-item").forEach((b) => {
    b.title = b.querySelector(".rotulo").firstChild.textContent.trim(); // aparece quando o menu mostra só ícones
    b.addEventListener("click", () => mostrarView(b.dataset.view));
  });

  $("#sel-mes").addEventListener("change", (e) => { estado.mes = Number(e.target.value); carregar(); });
  $("#sel-ano").addEventListener("change", (e) => { estado.ano = Number(e.target.value); carregar(); });
  $("#btn-atualizar").addEventListener("click", carregar);

  $$(".escolhas[data-config] .escolha").forEach((b) => b.addEventListener("click", () => {
    mudarConfig({ [b.closest(".escolhas").dataset.config]: b.dataset.valor });
  }));
  $$("[data-config-bool]").forEach((b) => b.addEventListener("click", () => {
    mudarConfig({ [b.dataset.configBool]: !estado.cfg[b.dataset.configBool] });
  }));
  $("#escala").addEventListener("input", (e) => mudarConfig({ escala_fonte: Number(e.target.value) }));

  document.addEventListener("click", (e) => {
    const alvo = e.target.closest("[data-acao]");
    if (!alvo || alvo.disabled) return;
    switch (alvo.dataset.acao) {
      case "escolher-pasta": escolherPasta(); break;
      case "abrir-pasta": api().abrir_pasta_notas(); break;
      case "exportar": exportar(alvo.dataset.formato); break;
      case "abrir-nota": abrirNota(alvo.dataset.arquivo); break;
      case "ir-mes":
        estado.ano = Number(alvo.dataset.ano);
        estado.mes = Number(alvo.dataset.mes);
        carregar();
        break;
      case "fonte-mais": mudarFonte(1); break;
      case "fonte-menos": mudarFonte(-1); break;
      case "ver-avisos": {
        const faixa = $("#faixa-avisos");
        if (!faixa.hidden) { faixa.scrollIntoView({ behavior: "smooth", block: "center" }); faixa.focus({ preventScroll: true }); }
        break;
      }
    }
  });

  document.addEventListener("keydown", (e) => {
    if (!e.ctrlKey || e.altKey) return;
    if (e.key === "+" || e.key === "=") { e.preventDefault(); mudarFonte(1); }
    else if (e.key === "-" || e.key === "_") { e.preventDefault(); mudarFonte(-1); }
    else if (e.key === "0") { e.preventDefault(); mudarFonte(0); }
  });
}
