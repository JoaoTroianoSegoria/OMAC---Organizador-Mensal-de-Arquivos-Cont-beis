/* OMAC — Atendimentos: a ficha do mês (pagamento e nota de cada atendimento).
 *
 * O paciente é um contato: o campo completa com a lista de contatos, e um nome que
 * não existe vira contato novo ao salvar.
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
  nota: "", // "" (falta), "ok", "nao_precisa"
  notaSugerida: false, // "não precisa" veio sozinho da forma de pagamento (troca junto com ela)
  semNotaPorPadrao: [],
};

const PARCELAS_MAX = 12;

modulos.atendimentos = {
  // Chegou nota nova desde a última leitura? A conferência já redesenha a ficha.
  async aoMostrar() { if (!(await conferirNotas())) carregarFicha(); },
  carregar: carregarFicha,
  ligar() {
    const hoje = new Date();
    ficha.ano = hoje.getFullYear();
    ficha.mes = hoje.getMonth() + 1;
    $("#form-atendimento").addEventListener("submit", salvarAtendimento);
    $("#form-tratamento").addEventListener("submit", adicionarTratamento);
    $("#pg-nome").addEventListener("change", sugerirDaOrtodontia);
    $("#pg-nome").addEventListener("input", avisarContatoNovo);
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
  "pg-emitir": (alvo) => { const a = atendimentoDa(alvo); if (a) abrirEmissao(a.contato_id, a); },
  "pg-fechar": () => $("#pg-atendimento").close(),
  "pg-forma": (alvo) => escolherForma(ficha.forma === alvo.dataset.forma ? "" : alvo.dataset.forma, true),
  "pg-nota": (alvo) => { ficha.notaSugerida = false; escolherNota(alvo.dataset.nota); },
  "pg-pago": marcarPagoNaLista,
  "pg-filtro": (alvo) => { ficha.filtro = alvo.dataset.filtro; desenharFicha(); },
  "pg-excluir": excluirAtendimento,
  "pg-exportar": exportarFicha,
  "pg-tirar-tratamento": (alvo) => tirarTratamento(alvo.dataset.nome),
});

/* ---------- Lista ---------- */

async function carregarFicha() {
  aplicarFicha(await api().atendimentos_listar(ficha.ano, ficha.mes));
}

function irParaMesDaFicha(ano, mes) {
  ficha.ano = ano;
  ficha.mes = mes;
  carregarFicha();
}

function aplicarFicha(r) {
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  Object.assign(ficha, { ano: r.ano, mes: r.mes, atendimentos: r.atendimentos, nomes: r.nomes, orto: r.orto,
    semNotaPorPadrao: r.sem_nota_por_padrao });
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
  if (ficha.filtro === "sem_nota") return a.nota_situacao === "falta";
  return true;
}

function desenharFicha() {
  const t = ficha.totais;
  const vazio = ficha.atendimentos.length === 0;
  seletoresDaFicha();
  $("#pg-mes-nome").textContent = `${MESES[ficha.mes - 1]} de ${ficha.ano}`;
  $("#pg-recebido").replaceChildren(dinheiro(t.recebido_centavos));
  $("#pg-a-receber").replaceChildren(dinheiro(t.a_receber_centavos));
  $("#pg-nao-pago").replaceChildren(dinheiro(t.nao_pago_centavos));
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
  if (a.nota_situacao === "ok") {
    tdNota.innerHTML = '<svg class="ic pg-ok"><use href="#i-ok"/></svg>';
    tdNota.append(" ok");
    tdNota.title = a.nota_numero && a.nota === "" ? `Nota nº ${a.nota_numero}, achada na pasta` : "Marcada à mão como emitida";
  } else if (a.nota_situacao === "nao_precisa") {
    tdNota.textContent = "não precisa";
    tdNota.classList.add("pg-nao-precisa");
  } else if (a.situacao === "pago" && a.contato_id && a.nome !== "(contato apagado)") {
    // Falta a nota e já foi pago: o botão abre a janela com o nome e o CPF para copiar.
    // Antes de pagar não aparece, para não emitir a nota de quem ainda não pagou.
    const emitir = Object.assign(document.createElement("button"), { type: "button", className: "btn btn-peq pg-emitir", textContent: "Emitir" });
    emitir.dataset.acao = "pg-emitir";
    emitir.dataset.id = a.id;
    emitir.title = "Falta emitir: ver o nome e o CPF para a nota";
    emitir.setAttribute("aria-label", `Emitir a nota de ${a.nome}`);
    tdNota.append(emitir);
  } else {
    tdNota.textContent = "—";
    tdNota.title = a.situacao === "pago" ? "Falta emitir" : "Falta emitir: marque como pago para aparecer o botão Emitir";
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
    a.valor_centavos == null ? celula("Sem valor", "c-valor ag-sem-dado") : celula(dinheiro(a.valor_centavos), "c-valor"),
    a.forma_texto ? celula(a.forma_texto, "pg-c-forma") : celula("—", "pg-c-forma ag-sem-dado"),
    tdNota,
    tdAcao,
  );
  return tr;
}

async function marcarPagoNaLista(caixa) {
  const r = await api().atendimentos_marcar_pago(caixa.dataset.id, caixa.checked, ficha.ano, ficha.mes);
  if (r.erro) {
    caixa.checked = !caixa.checked;
    return mostrarToast(r.erro, { erro: true });
  }
  aplicarFicha(r);
}

async function exportarFicha() {
  const r = await api().atendimentos_exportar(ficha.ano, ficha.mes);
  if (!r || r.cancelado) return;
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  estado.cfg.pasta_saida = r.caminho.replace(/[\\/][^\\/]*$/, "");
  toastDeArquivo(`Ficha salva com ${r.qtd} ${r.qtd === 1 ? "atendimento" : "atendimentos"}.`, r.caminho);
}

/* ---------- Novo atendimento / alterar atendimento ---------- */

function escolherForma(forma, clicada = false) {
  ficha.forma = forma;
  $$(".pg-formas .escolha").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.forma === forma)));
  $("#pg-parcelas-campo").hidden = forma !== "credito";
  if (!clicada) return;
  // Dinheiro e Pix PF já sugerem "não precisa" de nota; trocar a forma desfaz a sugestão.
  const semNota = ficha.semNotaPorPadrao.includes(forma);
  if (semNota && ficha.nota === "") {
    ficha.notaSugerida = true;
    escolherNota("nao_precisa");
  } else if (!semNota && ficha.notaSugerida) {
    ficha.notaSugerida = false;
    escolherNota("");
  }
}

function escolherNota(nota) {
  ficha.nota = nota;
  $$(".pg-notas .escolha").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.nota === nota)));
}

function avisarContatoNovo() {
  const nome = normalizarNome($("#pg-nome").value);
  $("#pg-contato-novo").hidden = !nome || ficha.nomes.some((n) => normalizarNome(n) === nome);
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

  // O que o automático achou (vale quando a escolha é "Automático"; as outras passam por cima).
  const achada = a && a.nota_numero;
  $("#pg-nota-achada").hidden = !a;
  $("#pg-nota-achada").classList.toggle("pg-nota-nada", !achada);
  $("#pg-nota-achada-texto").textContent = !a ? ""
    : achada ? `Automático: nota nº ${a.nota_numero}${a.nota_valor_centavos != null ? ` (${dinheiroTexto(a.nota_valor_centavos)})` : ""} achada na pasta.`
      : "Automático: nenhuma nota da pasta é deste atendimento.";
  ficha.notaSugerida = false;
  escolherNota(a ? a.nota : "");
  $("#pg-contato-novo").hidden = true;

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
  const r = await api().atendimentos_salvar({
    nome: $("#pg-nome").value,
    tratamento: $("#pg-tratamento").value,
    data: $("#pg-data").value,
    valor: $("#pg-valor").value,
    forma: ficha.forma,
    parcelas: Number($("#pg-parcelas").value),
    pago: $("#pg-pago").checked,
    nota: ficha.nota,
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
  const r = await api().atendimentos_apagar(ficha.editando.id, ficha.ano, ficha.mes);
  $("#pg-atendimento").close();
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  aplicarFicha(r);
  mostrarToast(`Atendimento excluído: ${r.apagado_nome}`, {
    acoes: [["Desfazer", async () => aplicarFicha(await api().atendimentos_restaurar(r.apagado, ficha.ano, ficha.mes))]],
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

/* ---------- Widget do Início ---------- */

registrarWidget("atendimentos", {
  icone: "i-dinheiro",
  desenhar(corpo, f) {
    if (!f.qtd) {
      corpo.append(texto("p", "Nenhum atendimento na ficha deste mês.", "dica"), rodape(botaoIr("Abrir atendimentos", "atendimentos")));
      return;
    }
    corpo.append(numeros([
      ["Recebido", dinheiro(f.recebido_centavos)],
      ["A receber", dinheiro(f.a_receber_centavos)],
      ["Sem nota", String(f.sem_nota), f.sem_nota ? "ini-alerta" : ""],
    ]));
    corpo.append(rodape(botaoIr("Abrir atendimentos", "atendimentos")));
  },
});
