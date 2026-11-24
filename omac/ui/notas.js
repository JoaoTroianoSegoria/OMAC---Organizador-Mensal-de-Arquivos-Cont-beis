/* OMAC — notas fiscais: a aba "Notas fiscais" do Relatório mensal, com a pesquisa e a escolha
 * de notas para enviar juntas (a ilha embaixo fica em relatorio.js). */
"use strict";

const notasEstado = {
  dados: null,          // o mês escolhido (notas, avisos, meses com notas…)
  lista: [],            // o que a tabela mostra: o mês ou o resultado da pesquisa
  total: 0,
  enviadas: new Set(),
  carregando: false,
  chave: "",
  busca: "",
  escopo: "mes",        // "mes" | "ano" | "periodo"
  de: "",
  ate: "",
  selecao: new Map(),   // número → nota; não se perde ao pesquisar de novo
};
const chaveNotas = () => `${estado.ano}-${estado.mes}-${estado.cfg.pasta_notas}`;
const pesquisando = () => notasEstado.busca.trim() !== "" || notasEstado.escopo !== "mes";

/* Não é uma tela: o Relatório mensal (relatorio.js) chama quando a aba aparece. */
modulos.notas = {
  aoMostrar() {
    if (notasEstado.dados) preencherSeletores($("#sel-mes"), $("#sel-ano"), notasEstado.dados.competencias);
    if (notasEstado.chave !== chaveNotas()) carregarNotas();
    else conferirNotas();
  },
  carregar: carregarNotas,
  ligar() {
    let espera = null;
    $("#rel-busca").addEventListener("input", (e) => {
      notasEstado.busca = e.target.value;
      clearTimeout(espera);
      espera = setTimeout(pesquisarNotas, 200);
    });
    $("#rel-de").addEventListener("change", (e) => { notasEstado.de = e.target.value; pesquisarNotas(); });
    $("#rel-ate").addEventListener("change", (e) => { notasEstado.ate = e.target.value; pesquisarNotas(); });
    $("#tabela-corpo").addEventListener("change", (e) => {
      if (e.target.matches(".rel-escolher")) escolherParaEnviar(Number(e.target.dataset.numero), e.target.checked);
    });
    $("#rel-marcar-todas").addEventListener("change", (e) => escolherTodas(e.target.checked));
    $("#form-nt-renomear").addEventListener("submit", (e) => { e.preventDefault(); renomearNota(); });
  },
};

Object.assign(acoes, {
  // O atalho de Atendimentos: o mesmo Atualizar das notas do Relatório mensal.
  "notas-atualizar": atualizarNotas,
  exportar: (alvo) => exportar(alvo.dataset.formato),
  "abrir-nota": (alvo) => abrirNota(alvo.dataset.arquivo),
  "ver-avisos": () => {
    const faixa = $("#faixa-avisos");
    if (faixa.hidden) return;
    recolherFaixa(faixa, false);
    faixa.scrollIntoView({ behavior: "smooth", block: "center" });
    faixa.focus({ preventScroll: true });
  },
  "rel-escopo": (alvo) => mudarEscopo(alvo.dataset.escopo),
  "rel-limpar-pesquisa": limparPesquisa,
  "nt-renomear": (alvo) => {
    const n = notasEstado.lista.find((x) => x.arquivo === alvo.dataset.arquivo);
    if (n) abrirRenomear(n);
  },
  "nt-renomear-fechar": () => $("#nt-renomear").close(),
});

let progressoTimer = null;
window.omacProgresso = (feitos, total) => {
  const pct = total ? Math.round((feitos / total) * 100) : 100;
  $("#progresso-texto").textContent = `Lendo as notas… ${feitos} de ${total}`;
  $("#progresso-cheio").style.width = `${pct}%`;
  $("#progresso-barra").setAttribute("aria-valuenow", String(pct));
};

async function carregarNotas() {
  if (notasEstado.carregando) return;
  if (!estado.cfg.pasta_notas) {
    $("#sem-pasta").hidden = false;
    $("#painel-notas").hidden = true;
    return;
  }
  notasEstado.carregando = true;
  notasEstado.chave = chaveNotas();
  const botoes = $$("[data-gira-notas]");
  botoes.forEach((b) => { b.disabled = true; b.classList.add("girando"); });
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
    notasEstado.dados = r;
    mostrarLeitura(r.lida_em);
    avisarNotasNovas(r.novas);
    const env = await api().notas_enviadas();
    notasEstado.enviadas = new Set(env.numeros ?? []);
    if (relatorio.aba === "notas") preencherSeletores($("#sel-mes"), $("#sel-ano"), r.competencias);
    $("#rel-qtd-notas").textContent = `(${r.notas.length})`;
    await pesquisarNotas();
  } finally {
    clearTimeout(progressoTimer);
    $("#progresso").hidden = true;
    botoes.forEach((b) => { b.disabled = false; b.classList.remove("girando"); });
    notasEstado.carregando = false;
  }
}

/* ---------- Notas que chegam na pasta ----------
 *
 * Emitiu a nota no site e salvou o PDF: ao voltar para o OMAC (a janela ganha o foco), ele só
 * compara nome, tamanho e data dos PDFs com a última leitura. Igual, não faz nada; mudou, faz
 * o mesmo que o botão Atualizar, que lê só os arquivos novos (os outros vêm do cache).
 * Nada fica vigiando a pasta enquanto o OMAC está parado. */

function mostrarLeitura(hora) {
  const p = $("#rel-lidas");
  p.querySelector("span").textContent = hora ? `Notas lidas às ${hora}` : "";
  p.hidden = !hora || relatorio.aba !== "notas";
  $("#pg-atualizar-notas").title = hora
    ? `Notas lidas às ${hora}. Clique para ler a pasta de novo (o mesmo Atualizar do Relatório mensal).`
    : "Ler a pasta das notas de novo (o mesmo Atualizar do Relatório mensal)";
}

function avisarNotasNovas(novas) {
  if (!novas || !novas.length) return;
  // O PDF veio do site com um nome só de números (ou com o número errado): oferece o nome certo.
  // Esse aviso fica até alguém fechar, porque a nota sem o nome certo fica sem o paciente.
  for (const n of novas.filter((x) => x.renomear)) {
    mostrarToast(`Nota nova nº ${n.numero} – ${n.renomear.nome}: o nome do PDF ${n.renomear.motivo === "numero_diferente"
      ? "tem outro número" : "está fora do formato"}.`, {
      fica: true,
      acoes: [["Renomear", () => abrirRenomear(n)]],
    });
  }
  novas = novas.filter((x) => !x.renomear);
  if (!novas.length) return;
  const lista = [...novas].sort((a, b) => a.numero - b.numero);
  if (lista.length === 1) return mostrarToast(`1 nota nova: nº ${lista[0].numero} – ${lista[0].paciente}`);
  const primeiras = lista.slice(0, 3).map((n) => `nº ${n.numero}`).join(", ");
  mostrarToast(`${lista.length} notas novas: ${primeiras}${lista.length > 3 ? "…" : ""}`);
}

/* Lê a pasta de novo e redesenha a tela aberta (o Relatório já se redesenha na leitura). */
async function atualizarNotas() {
  if (notasEstado.carregando) return;
  await carregarNotas();
  if (estado.view !== "relatorio") await modulos[estado.view]?.carregar?.();
}

let notasConferindo = false;
let notasConferidasEm = 0;
/* Devolve true quando leu a pasta de novo (e a tela aberta já foi redesenhada). */
async function conferirNotas() {
  if (!estado.cfg || !estado.cfg.notas_automatico || !estado.cfg.pasta_notas) return false;
  if (notasConferindo || notasEstado.carregando || Date.now() - notasConferidasEm < 400) return false;
  notasConferindo = true;
  try {
    const r = await api().notas_conferir();
    notasConferidasEm = Date.now();
    if (!r || !r.mudou) return false;
    await atualizarNotas();
    return true;
  } finally {
    notasConferindo = false;
  }
}
window.addEventListener("focus", () => conferirNotas());
document.addEventListener("visibilitychange", () => { if (!document.hidden) conferirNotas(); });

/* ---------- Renomear o PDF (o site baixa com um nome só de números) ----------
 *
 * O número, as datas e o nome de quem recebe vêm de dentro do PDF (o nome, dos Contatos
 * quando dá para achar). O Python monta pelo formato das Configurações e não passa por cima
 * de arquivo nenhum; depois a pasta é lida de novo. */

let notaRenomeando = null;

function botaoRenomear(n) {
  const b = Object.assign(document.createElement("button"), { type: "button", className: "btn btn-peq aviso-renomear" });
  b.dataset.acao = "nt-renomear";
  b.dataset.arquivo = n.arquivo;
  b.innerHTML = '<svg class="ic"><use href="#i-lapis"/></svg><span>Renomear</span>';
  b.title = `Renomear para ${n.renomear.para}`;
  b.setAttribute("aria-label", `Renomear o PDF da nota ${n.numero} para ${n.renomear.para}`);
  return b;
}

/* `n`: uma nota da lista ou da leitura nova ({numero, arquivo?, renomear: {motivo, para}}). */
function abrirRenomear(n) {
  const arquivo = n.arquivo || n.renomear.de;
  notaRenomeando = { numero: n.numero, arquivo };
  $("#nt-renomear-motivo").textContent = n.renomear.motivo === "numero_diferente"
    ? `O número no nome do PDF é diferente do número da nota (${n.numero}).`
    : `O nome do PDF da nota nº ${n.numero} está fora do formato, então o OMAC não sabe de quem ela é.`;
  $("#nt-renomear-de").textContent = arquivo;
  $("#nt-renomear-para").value = n.renomear.para.replace(/\.pdf$/i, "");
  $("#nt-renomear-erro").hidden = true;
  $("#nt-renomear").showModal();
  $("#nt-renomear-para").focus();
}

async function renomearNota() {
  if (!notaRenomeando) return;
  const r = await api().notas_renomear(notaRenomeando.arquivo, $("#nt-renomear-para").value);
  if (r.erro) {
    $("#nt-renomear-erro").textContent = r.erro;
    $("#nt-renomear-erro").hidden = false;
    return;
  }
  $("#nt-renomear").close();
  notaRenomeando = null;
  mostrarToast(`PDF renomeado: ${r.arquivo}`);
  await atualizarNotas();
}

/* ---------- Pesquisa ---------- */

async function pesquisarNotas() {
  if (!notasEstado.dados) return;
  if (!pesquisando()) {
    notasEstado.lista = notasEstado.dados.notas;
    notasEstado.total = notasEstado.dados.total_centavos;
  } else {
    const { busca, escopo, de, ate } = notasEstado;
    const r = await api().notas_pesquisar(busca, escopo, estado.ano, estado.mes, de, ate);
    if (r.erro) return mostrarToast(r.erro, { erro: true });
    // Outra pesquisa começou enquanto esta voltava: fica a mais nova.
    if (busca !== notasEstado.busca || escopo !== notasEstado.escopo || de !== notasEstado.de || ate !== notasEstado.ate) return;
    notasEstado.lista = r.notas;
    notasEstado.total = r.total_centavos;
  }
  desenharNotas();
}

function mudarEscopo(escopo) {
  notasEstado.escopo = escopo;
  $$("#rel-escopo .escolha").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.escopo === escopo)));
  $("#rel-periodo").hidden = escopo !== "periodo";
  // Fora do "Mês escolhido", o mês e o ano de cima não valem para a lista.
  $("#sel-mes").disabled = escopo !== "mes";
  $("#sel-ano").disabled = escopo !== "mes";
  if (escopo === "periodo" && !notasEstado.de && !notasEstado.ate) {
    const mes = String(estado.mes).padStart(2, "0");
    const ultimo = new Date(estado.ano, estado.mes, 0).getDate();
    notasEstado.de = $("#rel-de").value = `${estado.ano}-${mes}-01`;
    notasEstado.ate = $("#rel-ate").value = `${estado.ano}-${mes}-${ultimo}`;
  }
  pesquisarNotas();
}

function limparPesquisa() {
  notasEstado.busca = $("#rel-busca").value = "";
  mudarEscopo("mes");
  $("#rel-busca").focus();
}

/* ---------- Tabela ---------- */

function desenharNotas() {
  const { avisos, canceladas_movidas } = notasEstado.dados;
  const notas = notasEstado.lista;
  $("#sem-pasta").hidden = true;
  $("#painel-notas").hidden = false;

  const nomeMes = `${MESES[estado.mes - 1]} de ${estado.ano}`;
  $("#res-qtd").textContent = String(notas.length);
  $("#res-qtd").previousElementSibling.textContent = pesquisando() ? "Notas encontradas" : "Notas no mês";
  $("#res-total").replaceChildren(dinheiro(notasEstado.total));
  $("#rod-qtd").textContent = `Total (${plural(notas.length, "nota", "notas")})`;
  $("#rod-total").replaceChildren(dinheiro(notasEstado.total));
  $("#tabela-legenda").textContent = pesquisando()
    ? "Notas fiscais encontradas na pesquisa"
    : `Notas fiscais com competência em ${nomeMes}`;

  const corpo = document.createDocumentFragment();
  for (const n of notas) corpo.append(linhaDaNota(n));
  $("#tabela-corpo").replaceChildren(corpo);
  marcarCabecalho();
  desenharVazio(nomeMes);

  // Avisos: os de cada nota da lista + os gerais da pasta. O do nome do arquivo ganha o Renomear.
  const itens = [];
  for (const n of notas) {
    const doNome = n.renomear ? n.avisos.findIndex((a) => a.includes("nome do arquivo")) : -1;
    n.avisos.forEach((a, i) => itens.push([`Nota nº ${n.numero}`, a, i === doNome ? botaoRenomear(n) : null]));
    if (n.renomear && doNome < 0) itens.push([`Nota nº ${n.numero}`, "O nome do arquivo está fora do formato.", botaoRenomear(n)]);
  }
  for (const a of avisos) itens.push([a.arquivo || "", a.mensagem]);
  $("#avisos-lista").replaceChildren(...listaDeAvisos(itens));
  mostrarQtdAvisos($("#faixa-avisos"), itens.length);
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

  // A planilha é sempre a do mês escolhido.
  $$('[data-acao="exportar"]').forEach((b) => { b.disabled = notasEstado.dados.notas.length === 0; });
  desenharIlha();
}

function linhaDaNota(n) {
  const tr = document.createElement("tr");
  const escolhida = notasEstado.selecao.has(n.numero);
  tr.classList.toggle("rel-escolhida", escolhida);

  const tdSel = document.createElement("td");
  tdSel.className = "c-sel";
  const caixaSel = Object.assign(document.createElement("input"), { type: "checkbox", className: "confere rel-escolher", checked: escolhida });
  caixaSel.dataset.numero = n.numero;
  caixaSel.setAttribute("aria-label", `Escolher a nota ${n.numero} de ${n.paciente}`);
  tdSel.append(caixaSel);

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
      title: `Dependente de ${n.responsavel}, nome que está na descrição do serviço`,
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
  tdValor.append(dinheiro(n.valor_centavos));

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
  const enviada = notasEstado.enviadas.has(n.numero);
  const enviar = document.createElement("button");
  enviar.className = `btn-linha${enviada ? " btn-enviada" : ""}`;
  enviar.dataset.acao = "whats-enviar";
  enviar.dataset.numero = n.numero;
  enviar.title = enviada ? "Já enviada. Clique para enviar de novo" : "Enviar a nota pelo WhatsApp";
  enviar.setAttribute("aria-label", `${enviada ? "Enviar de novo" : "Enviar"} a nota ${n.numero} pelo WhatsApp`);
  enviar.innerHTML = `<svg class="ic"><use href="#${enviada ? "i-ok" : "i-whats"}"/></svg>`;
  tdAcao.append(enviar, abrir);

  tr.append(tdSel, tdNum, tdPac, tdValor, tdEm, tdComp, tdAcao);
  return tr;
}

/* Sem notas: no lugar dos cartões e da tabela, explica o porquê e o que fazer. */
function desenharVazio(nomeMes) {
  const { qtd_pasta, competencias } = notasEstado.dados;
  const vazio = notasEstado.lista.length === 0;
  $("#resumo").hidden = vazio;
  $("#tabela-caixa").hidden = vazio;
  $("#notas-vazio").hidden = !vazio;
  if (!vazio) return;

  const pastaVazia = qtd_pasta === 0;
  $("#notas-vazio-ic").setAttribute("href", pastaVazia ? "#i-pasta" : pesquisando() ? "#i-busca" : "#i-notas");
  $("#notas-vazio-acoes").hidden = !pastaVazia;
  $("#notas-vazio-pesquisa").hidden = pastaVazia || !pesquisando();
  $("#notas-vazio-meses").replaceChildren();
  if (pastaVazia) {
    $("#notas-vazio-titulo").textContent = "Nenhuma nota nesta pasta";
    $("#notas-vazio-texto").textContent =
      "Não encontrei PDFs de notas direto na pasta escolhida. O OMAC não olha dentro de subpastas: " +
      "confira se é a pasta onde as notas do ano ficam (por exemplo, NFS‑e 2026).";
    return;
  }
  if (pesquisando()) {
    const onde = { mes: `em ${nomeMes}`, ano: "no ano todo", periodo: "no período escolhido" }[notasEstado.escopo];
    $("#notas-vazio-titulo").textContent = "Nenhuma nota encontrada";
    $("#notas-vazio-texto").textContent = notasEstado.busca.trim()
      ? `Nenhuma nota ${onde} tem “${notasEstado.busca.trim()}”. Confira o que foi digitado ou procure no ano todo.`
      : `Nenhuma nota ${onde}.`;
    return;
  }
  $("#notas-vazio-titulo").textContent = `Nenhuma nota em ${nomeMes}`;
  $("#notas-vazio-texto").textContent =
    `A pasta tem ${plural(qtd_pasta, "nota", "notas")}, mas nenhuma com competência neste mês. Meses com notas:`;
  $("#notas-vazio-meses").replaceChildren(...botoesDeMeses(competencias, "nota", "notas"));
}

/* ---------- Escolher notas ---------- */

function escolherParaEnviar(numero, escolher) {
  const n = notasEstado.lista.find((x) => x.numero === numero) || notasEstado.selecao.get(numero);
  if (escolher && n) notasEstado.selecao.set(numero, n);
  else notasEstado.selecao.delete(numero);
  const caixa = $(`#tabela-corpo .rel-escolher[data-numero="${numero}"]`);
  if (caixa) {
    caixa.checked = notasEstado.selecao.has(numero);
    caixa.closest("tr").classList.toggle("rel-escolhida", caixa.checked);
  }
  marcarCabecalho();
  desenharIlha();
}

function escolherTodas(escolher) {
  for (const n of notasEstado.lista) {
    if (escolher) notasEstado.selecao.set(n.numero, n);
    else notasEstado.selecao.delete(n.numero);
  }
  $$("#tabela-corpo .rel-escolher").forEach((c) => {
    c.checked = escolher;
    c.closest("tr").classList.toggle("rel-escolhida", escolher);
  });
  marcarCabecalho();
  desenharIlha();
}

/* A caixa do cabeçalho: marcada se todas da lista estão escolhidas, "meio" se só algumas. */
function marcarCabecalho() {
  const caixa = $("#rel-marcar-todas");
  const qtd = notasEstado.lista.filter((n) => notasEstado.selecao.has(n.numero)).length;
  caixa.checked = qtd > 0 && qtd === notasEstado.lista.length;
  caixa.indeterminate = qtd > 0 && qtd < notasEstado.lista.length;
  caixa.disabled = notasEstado.lista.length === 0;
}

/* ---------- Planilha e PDF ---------- */

async function exportar(formato) {
  const r = await api().exportar(estado.ano, estado.mes, formato);
  if (!r || r.cancelado) return;
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  estado.cfg.formato = formato;
  aplicarConfig();
  toastDeArquivo(`Planilha salva: ${r.caminho.split(/[\\/]/).pop()}`, r.caminho);
}

async function abrirNota(arquivo) {
  const r = await api().abrir_nota(arquivo);
  if (r && r.erro) mostrarToast(r.erro, { erro: true });
}
