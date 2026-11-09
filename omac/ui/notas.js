/* OMAC — módulo de notas fiscais. */
"use strict";

const notasEstado = { dados: null, enviadas: new Set(), carregando: false, chave: "" };
const chaveNotas = () => `${estado.ano}-${estado.mes}-${estado.cfg.pasta_notas}`;

modulos.notas = {
  aoMostrar() { if (notasEstado.chave !== chaveNotas()) carregarNotas(); },
  carregar: carregarNotas,
  ligar() { $("#btn-atualizar").addEventListener("click", carregarNotas); },
};

Object.assign(acoes, {
  exportar: (alvo) => exportar(alvo.dataset.formato),
  "abrir-nota": (alvo) => abrirNota(alvo.dataset.arquivo),
  "ver-avisos": () => {
    const faixa = $("#faixa-avisos");
    if (faixa.hidden) return;
    recolherFaixa(faixa, false);
    faixa.scrollIntoView({ behavior: "smooth", block: "center" });
    faixa.focus({ preventScroll: true });
  },
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
    notasEstado.dados = r;
    const env = await api().whatsapp_enviadas();
    notasEstado.enviadas = new Set(env.numeros ?? []);
    preencherSeletores($("#sel-mes"), $("#sel-ano"), r.competencias);
    desenharNotas();
  } finally {
    clearTimeout(progressoTimer);
    $("#progresso").hidden = true;
    btn.disabled = false;
    btn.classList.remove("girando");
    notasEstado.carregando = false;
  }
}

function desenharNotas() {
  const { notas, total_centavos, avisos, canceladas_movidas } = notasEstado.dados;
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
    const enviada = notasEstado.enviadas.has(n.numero);
    const enviar = document.createElement("button");
    enviar.className = `btn-linha${enviada ? " btn-enviada" : ""}`;
    enviar.dataset.acao = "whats-enviar";
    enviar.dataset.numero = n.numero;
    enviar.title = enviada ? "Já enviada. Clique para enviar de novo" : "Enviar a nota pelo WhatsApp";
    enviar.setAttribute("aria-label", `${enviada ? "Enviar de novo" : "Enviar"} a nota ${n.numero} pelo WhatsApp`);
    enviar.innerHTML = `<svg class="ic"><use href="#${enviada ? "i-ok" : "i-whats"}"/></svg>`;
    tdAcao.append(enviar, abrir);

    tr.append(tdNum, tdPac, tdValor, tdEm, tdComp, tdAcao);
    corpo.append(tr);
  }
  $("#tabela-corpo").replaceChildren(corpo);
  desenharVazio(nomeMes);

  // Avisos: os de cada nota do mês + os gerais da pasta
  const itens = [];
  for (const n of notas) for (const a of n.avisos) itens.push([`Nota nº ${n.numero}`, a]);
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

  $$('[data-acao="exportar"]').forEach((b) => { b.disabled = notas.length === 0; });
}

/* Sem notas: no lugar dos cartões e da tabela, explica o porquê e o que fazer. */
function desenharVazio(nomeMes) {
  const { notas, qtd_pasta, competencias } = notasEstado.dados;
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
  $("#notas-vazio-meses").replaceChildren(...botoesDeMeses(competencias, "nota", "notas"));
}

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
