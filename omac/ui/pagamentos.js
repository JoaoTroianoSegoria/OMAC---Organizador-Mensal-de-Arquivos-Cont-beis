/* OMAC — ficha de pagamentos: o papel dos atendimentos pagos, mês a mês.
 *
 * O mês daqui é o do dia a dia (o atual), e não o do relatório dos outros módulos,
 * que no começo do mês costuma ser o anterior. Por isso ele tem os próprios seletores.
 */
"use strict";

const ficha = {
  ano: 0,
  mes: 0,
  filtro: "todos",
  atendimentos: [],
  nomes: [],
  orto: {}, // nome → valor da manutenção em centavos (ou null)
  editando: null,
  forma: "",
};

const PARCELAS_MAX = 12;

modulos.pagamentos = {
  aoMostrar: carregarFicha,
  carregar: carregarFicha,
  ligar() {
    const hoje = new Date();
    ficha.ano = hoje.getFullYear();
    ficha.mes = hoje.getMonth() + 1;
    $("#form-atendimento").addEventListener("submit", salvarAtendimento);
    $("#form-tratamento").addEventListener("submit", adicionarTratamento);
    $("#pg-nome").addEventListener("change", sugerirDaOrtodontia);
    $("#pg-sel-mes").addEventListener("change", (e) => irParaMesDaFicha(ficha.ano, Number(e.target.value)));
    $("#pg-sel-ano").addEventListener("change", (e) => irParaMesDaFicha(Number(e.target.value), ficha.mes));
    $("#pg-parcelas").replaceChildren(...Array.from({ length: PARCELAS_MAX }, (_, i) =>
      new Option(i === 0 ? "À vista (1x)" : `${i + 1}x`, String(i + 1))));
  },
  aoIniciar: desenharTratamentos,
};

const atendimentoDa = (alvo) => ficha.atendimentos.find((a) => a.id === alvo.dataset.id);

Object.assign(acoes, {
  "pg-novo": () => abrirAtendimento(null),
  "pg-editar": (alvo) => abrirAtendimento(atendimentoDa(alvo)),
  "pg-fechar": () => $("#pg-atendimento").close(),
  "pg-forma": (alvo) => escolherForma(ficha.forma === alvo.dataset.forma ? "" : alvo.dataset.forma),
  "pg-pago": marcarPagoNaLista,
  "pg-filtro": (alvo) => { ficha.filtro = alvo.dataset.filtro; desenharFicha(); },
  "pg-excluir": excluirAtendimento,
  "pg-exportar": exportarFicha,
  "pg-tirar-tratamento": (alvo) => tirarTratamento(alvo.dataset.nome),
});

/* ---------- Lista ---------- */

async function carregarFicha() {
  aplicarFicha(await api().pagamentos_listar(ficha.ano, ficha.mes));
}

function irParaMesDaFicha(ano, mes) {
  ficha.ano = ano;
  ficha.mes = mes;
  carregarFicha();
}

function aplicarFicha(r) {
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  Object.assign(ficha, { ano: r.ano, mes: r.mes, atendimentos: r.atendimentos, nomes: r.nomes, orto: r.orto });
  ficha.totais = r.totais;
  ficha.meses = r.meses;
  ficha.notasLidas = r.notas_lidas;
  desenharFicha();
}

function seletoresDaFicha() {
  const qtd = new Map(ficha.meses.map(([a, m, n]) => [`${a}-${m}`, n]));
  const anos = new Set([...ficha.meses.map(([a]) => a), ficha.ano, new Date().getFullYear()]);
  $("#pg-sel-ano").replaceChildren(...[...anos].sort().map((a) => new Option(String(a), String(a))));
  $("#pg-sel-ano").value = String(ficha.ano);
  $("#pg-sel-mes").replaceChildren(...MESES.map((nome, i) => {
    const n = qtd.get(`${ficha.ano}-${i + 1}`);
    return new Option(n ? `${nome} (${n})` : nome, String(i + 1));
  }));
  $("#pg-sel-mes").value = String(ficha.mes);
}

function passaNoFiltro(a) {
  if (ficha.filtro === "aguardando") return a.situacao === "aguardando";
  if (ficha.filtro === "nao_pago") return a.situacao === "nao_pago";
  if (ficha.filtro === "sem_nota") return !a.nota;
  return true;
}

function desenharFicha() {
  const t = ficha.totais;
  const vazio = ficha.atendimentos.length === 0;
  seletoresDaFicha();
  $("#pg-mes-nome").textContent = `${MESES[ficha.mes - 1]} de ${ficha.ano}`;
  $("#pg-recebido").textContent = real.format(t.recebido_centavos / 100);
  $("#pg-a-receber").textContent = real.format(t.a_receber_centavos / 100);
  $("#pg-nao-pago").textContent = real.format(t.nao_pago_centavos / 100);
  $("#pg-sem-nota").textContent = String(t.sem_nota);
  $("#pg-resumo").hidden = vazio;
  $("#pg-filtros").hidden = vazio;
  $("#pg-caixa").hidden = vazio;
  $("#pg-vazio").hidden = !vazio;
  $("#pg-exportar").disabled = vazio;
  $("#pg-sem-pasta").hidden = vazio || ficha.notasLidas;
  $$("#pg-filtros .escolha").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.filtro === ficha.filtro)));

  const visiveis = ficha.atendimentos.filter(passaNoFiltro);
  if (visiveis.length === 0) {
    const tr = document.createElement("tr");
    const td = celula("Nenhum atendimento neste filtro.", "ag-nada");
    td.colSpan = 8;
    tr.append(td);
    $("#pg-corpo").replaceChildren(tr);
    return;
  }
  $("#pg-corpo").replaceChildren(...visiveis.map(linhaDoAtendimento));
}

function linhaDoAtendimento(a) {
  const tr = document.createElement("tr");

  const tdPago = document.createElement("td");
  tdPago.className = "c-confere";
  const caixa = Object.assign(document.createElement("input"), { type: "checkbox", className: "confere", checked: a.situacao === "pago" });
  caixa.dataset.acao = "pg-pago";
  caixa.dataset.id = a.id;
  caixa.setAttribute("aria-label", `${a.nome} já pagou`);
  tdPago.append(caixa);
  if (a.situacao === "nao_pago") {
    tdPago.append(Object.assign(document.createElement("span"), { className: "etiqueta etiqueta-erro pg-nao", textContent: "não" }));
  }

  const tdNota = document.createElement("td");
  tdNota.className = "pg-c-nota";
  if (a.nota) {
    tdNota.innerHTML = '<svg class="ic pg-ok"><use href="#i-ok"/></svg>';
    tdNota.append(" ok");
    tdNota.title = a.nota_numero ? `Nota nº ${a.nota_numero}, achada na pasta` : "Marcada à mão";
  } else {
    tdNota.textContent = "—";
    tdNota.classList.add("ag-sem-dado");
  }

  const tdAcao = document.createElement("td");
  tdAcao.className = "c-acao";
  tdAcao.append(botaoIcone("pg-editar", "i-lapis", `Alterar o atendimento de ${a.nome}`, { id: a.id }));

  tr.append(
    tdPago,
    celula(a.nome),
    a.tratamento ? celula(a.tratamento, "pg-c-tratamento") : celula("—", "pg-c-tratamento ag-sem-dado"),
    celula(dataBR(a.data).slice(0, 5), "c-data"),
    a.valor_centavos == null ? celula("Sem valor", "c-valor ag-sem-dado") : celula(real.format(a.valor_centavos / 100), "c-valor"),
    a.forma_texto ? celula(a.forma_texto, "pg-c-forma") : celula("—", "pg-c-forma ag-sem-dado"),
    tdNota,
    tdAcao,
  );
  return tr;
}

async function marcarPagoNaLista(caixa) {
  const r = await api().pagamentos_marcar_pago(caixa.dataset.id, caixa.checked, ficha.ano, ficha.mes);
  if (r.erro) {
    caixa.checked = !caixa.checked;
    return mostrarToast(r.erro, { erro: true });
  }
  aplicarFicha(r);
}

async function exportarFicha() {
  const r = await api().pagamentos_exportar(ficha.ano, ficha.mes);
  if (!r || r.cancelado) return;
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  estado.cfg.pasta_saida = r.caminho.replace(/[\\/][^\\/]*$/, "");
  toastDeArquivo(`Ficha salva com ${r.qtd} ${r.qtd === 1 ? "atendimento" : "atendimentos"}.`, r.caminho);
}

/* ---------- Novo atendimento / alterar atendimento ---------- */

function escolherForma(forma) {
  ficha.forma = forma;
  $$(".pg-formas .escolha").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.forma === forma)));
  $("#pg-parcelas-campo").hidden = forma !== "credito";
}

function opcoes(lista) {
  return lista.map((texto) => Object.assign(document.createElement("option"), { value: texto }));
}

function dataPadrao() {
  // No mês de hoje, a data de hoje; em outro mês, o dia 1 dele.
  const hoje = new Date();
  if (hoje.getFullYear() === ficha.ano && hoje.getMonth() + 1 === ficha.mes) {
    return `${ficha.ano}-${String(ficha.mes).padStart(2, "0")}-${String(hoje.getDate()).padStart(2, "0")}`;
  }
  return `${ficha.ano}-${String(ficha.mes).padStart(2, "0")}-01`;
}

function valorParaCampo(centavos) {
  return centavos == null ? "" : (centavos / 100).toFixed(2).replace(".", ",");
}

function abrirAtendimento(a) {
  ficha.editando = a;
  $("#pg-nomes").replaceChildren(...opcoes(ficha.nomes));
  $("#pg-tratamentos").replaceChildren(...opcoes(estado.cfg.tratamentos));
  $("#pg-atendimento-titulo").textContent = a ? "Alterar atendimento" : "Novo atendimento";
  $("#pg-nome").value = a ? a.nome : "";
  $("#pg-tratamento").value = a ? a.tratamento : "";
  $("#pg-data").value = a ? a.data : dataPadrao();
  $("#pg-valor").value = a ? valorParaCampo(a.valor_centavos) : "";
  $("#pg-parcelas").value = String(a ? a.parcelas : 1);
  escolherForma(a ? a.forma : "");
  $("#pg-pago").checked = !!(a && a.pago_em);

  // Nota achada na pasta não precisa (nem pode) ser marcada à mão.
  const achada = a && a.nota_numero;
  $("#pg-nota-achada").hidden = !achada;
  $("#pg-nota-achada-texto").textContent = achada ? `Nota nº ${a.nota_numero} achada na pasta.` : "";
  $("#pg-nota-campo").hidden = !!achada;
  $("#pg-nota-dica").hidden = !!achada;
  $("#pg-nota-manual").checked = !!(a && a.nota_manual);

  $("#pg-excluir").hidden = !a;
  $("#pg-atendimento-erro").hidden = true;
  $("#pg-atendimento").showModal();
  $("#pg-nome").focus();
}

/* Paciente de orto escolhido na lista já vem com a manutenção e o valor dela. */
function sugerirDaOrtodontia() {
  const nome = $("#pg-nome").value.trim();
  const orto = Object.keys(ficha.orto).find((n) => n.localeCompare(nome, "pt-BR", { sensitivity: "base" }) === 0);
  if (orto === undefined) return;
  if (!$("#pg-tratamento").value.trim()) $("#pg-tratamento").value = "Manutenção";
  if (!$("#pg-valor").value.trim() && ficha.orto[orto] != null) $("#pg-valor").value = valorParaCampo(ficha.orto[orto]);
}

async function salvarAtendimento(e) {
  e.preventDefault();
  const anterior = ficha.editando;
  const r = await api().pagamentos_salvar({
    nome: $("#pg-nome").value,
    tratamento: $("#pg-tratamento").value,
    data: $("#pg-data").value,
    valor: $("#pg-valor").value,
    forma: ficha.forma,
    parcelas: Number($("#pg-parcelas").value),
    pago: $("#pg-pago").checked,
    nota_manual: $("#pg-nota-manual").checked,
  }, anterior ? anterior.id : null);
  if (r.erro) {
    $("#pg-atendimento-erro").textContent = r.erro;
    $("#pg-atendimento-erro").hidden = false;
    return;
  }
  $("#pg-atendimento").close();
  const outroMes = r.ano !== ficha.ano || r.mes !== ficha.mes;
  aplicarFicha(r);
  if (outroMes) mostrarToast(`O atendimento foi para ${MESES[r.mes - 1]} de ${r.ano}, o mês da data dele.`);
}

async function excluirAtendimento() {
  const r = await api().pagamentos_apagar(ficha.editando.id, ficha.ano, ficha.mes);
  $("#pg-atendimento").close();
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  aplicarFicha(r);
  mostrarToast(`Atendimento excluído: ${r.apagado.nome}`, {
    acoes: [["Desfazer", async () => aplicarFicha(await api().pagamentos_restaurar(r.apagado, ficha.ano, ficha.mes))]],
  });
}

/* ---------- Tratamentos sugeridos (Configurações) ---------- */

function desenharTratamentos() {
  $("#cfg-tratamentos").replaceChildren(...estado.cfg.tratamentos.map((nome) => {
    const li = Object.assign(document.createElement("li"), { className: "pg-chip" });
    li.append(Object.assign(document.createElement("span"), { textContent: nome }),
      botaoIcone("pg-tirar-tratamento", "i-fechar", `Tirar ${nome} da lista`, { nome }));
    return li;
  }));
  if (!estado.cfg.tratamentos.length) {
    $("#cfg-tratamentos").append(Object.assign(document.createElement("li"), {
      className: "ag-sem-dado", textContent: "Nenhum tratamento na lista.",
    }));
  }
}

function tirarTratamento(nome) {
  mudarConfig({ tratamentos: estado.cfg.tratamentos.filter((t) => t !== nome) });
  desenharTratamentos();
  $("#cfg-tratamento-novo").focus(); // o botão clicado sumiu: o foco não pode se perder
}

function adicionarTratamento(e) {
  e.preventDefault();
  const campo = $("#cfg-tratamento-novo");
  const nome = campo.value.trim().replace(/\s+/g, " ");
  if (!nome) return;
  const igual = (t) => t.localeCompare(nome, "pt-BR", { sensitivity: "base" }) === 0;
  if (!estado.cfg.tratamentos.some(igual)) mudarConfig({ tratamentos: [...estado.cfg.tratamentos, nome] });
  campo.value = "";
  desenharTratamentos();
  campo.focus();
}
