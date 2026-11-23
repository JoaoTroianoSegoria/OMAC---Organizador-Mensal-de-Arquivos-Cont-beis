/* OMAC — Contatos: nome e telefone de cada pessoa, num lugar só.
 *
 * A janela de contato é a mesma em todo o app: em Contatos, em Tratamentos ("Novo
 * paciente" e o lápis) e de onde mais precisar. Ela também liga a ortodontia
 * ("Em tratamento de orto"), que põe o contato em Tratamentos.
 */
"use strict";

const contatos = {
  lista: [],
  aConferir: [],
  busca: "",
  filtro: "todos",
  editando: null, // contato aberto na janela
  orto: false,
  situacao: "ativo",
  depoisDeSalvar: null, // quem abriu a janela quer saber (ex.: Tratamentos recarrega)
};

const PAPEIS = [["mae", "Mãe"], ["pai", "Pai"], ["conjuge", "Cônjuge"], ["outro", "Outro"]];
const NOMES_DAS_SITUACOES = { ativo: "Em tratamento", alta: "Alta temporária", finalizado: "Finalizados" };

modulos.contatos = {
  aoMostrar: carregarContatos,
  carregar: carregarContatos,
  ligar() {
    $("#form-contato").addEventListener("submit", salvarContato);
    $("#ct-tem-responsaveis").addEventListener("change", mostrarResponsaveisDoContato);
    $("#ct-nome").addEventListener("change", carregarSeJaExiste);
    $("#ct-busca").addEventListener("input", (e) => { contatos.busca = e.target.value; desenharContatos(); });
    $("#ct-resp-lista").addEventListener("change", (e) => {
      if (e.target.classList.contains("ct-resp-nome")) preencherTelefoneDoResponsavel(e.target);
    });
  },
};

Object.assign(acoes, {
  "ct-novo": () => abrirContato(null),
  "ct-editar": (alvo) => abrirContato(contatoPorId(alvo.dataset.id)),
  "ct-fechar": () => $("#ct-contato").close(),
  "ct-apagar": apagarContato,
  "ct-orto": () => ligarOrto(!contatos.orto),
  "ag-situacao": (alvo) => escolherSituacao(alvo.dataset.situacao),
  "ct-mais-responsavel": () => { $("#ct-resp-lista").append(linhaDeResponsavel(null)); $("#ct-resp-lista li:last-child input").focus(); },
  "ct-tirar-responsavel": (alvo) => { alvo.closest("li").remove(); },
  "ct-filtro": (alvo) => { contatos.filtro = alvo.dataset.filtro; desenharContatos(); },
  "ct-juntar": (alvo) => juntarContatos(alvo.dataset.manter, alvo.dataset.tirar),
  "ct-diferentes": (alvo) => conferido(api().contatos_sao_diferentes(alvo.dataset.ids.split(","))),
  "ct-telefone": (alvo) => conferido(api().contatos_escolher_telefone(alvo.dataset.id, alvo.dataset.telefone)),
  "ct-usar-cpf": () => { $("#ct-cpf").value = $("#ct-cpf-sugestao").dataset.cpf; $("#ct-cpf-sugestao").hidden = true; },
});

const contatoPorId = (id) => contatos.lista.find((c) => c.id === id);
const contatoPorNome = (nome) => contatos.lista.find((c) => normalizarNome(c.nome) === normalizarNome(nome));

/* ---------- Lista ---------- */

async function carregarContatos() {
  aplicarContatos(await api().contatos_listar());
}

function aplicarContatos(r) {
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  contatos.lista = r.contatos;
  contatos.aConferir = r.a_conferir;
  $("#ct-nomes").replaceChildren(...r.contatos.map((c) => Object.assign(document.createElement("option"), { value: c.nome })));
  if (estado.view === "contatos") desenharContatos();
}

function passaNaBusca(c) {
  if (contatos.filtro === "orto" && !c.tratamento) return false;
  if (contatos.filtro === "sem_telefone" && c.telefone) return false;
  const busca = normalizarNome(contatos.busca);
  if (!busca) return true;
  const digitos = contatos.busca.replace(/\D/g, "");
  return normalizarNome(c.nome).includes(busca) || (digitos.length >= 3 && c.telefone.includes(digitos));
}

function etiqueta(textoDela, classe = "") {
  return Object.assign(document.createElement("span"), { className: `etiqueta ${classe}`, textContent: textoDela });
}

function ligacoesDoContato(c) {
  const td = document.createElement("td");
  const caixa = Object.assign(document.createElement("div"), { className: "ct-ligacoes" });
  if (c.tratamento) {
    caixa.append(etiqueta(`orto: ${NOMES_DAS_SITUACOES[c.tratamento.situacao].toLowerCase()}`, "etiqueta-acento"));
  }
  for (const r of c.responsaveis) caixa.append(etiqueta(`${r.papel_texto}: ${r.nome}`));
  if (c.dependentes.length) caixa.append(etiqueta(`responsável por ${c.dependentes.join(", ")}`));
  if (c.atendimentos) caixa.append(etiqueta(plural(c.atendimentos, "atendimento", "atendimentos")));
  if (c.recebe_lembretes) caixa.append(etiqueta("recebe os lembretes"));
  td.append(caixa);
  return td;
}

function desenharContatos() {
  const vazio = contatos.lista.length === 0;
  $("#ct-caixa").hidden = vazio;
  $("#ct-vazio").hidden = !vazio;
  $(".ct-barra").hidden = vazio;
  $$("#ct-filtros .escolha").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.filtro === contatos.filtro)));
  desenharConferir();

  const visiveis = contatos.lista.filter(passaNaBusca);
  $("#ct-qtd").textContent = vazio ? "" : visiveis.length === contatos.lista.length
    ? plural(contatos.lista.length, "contato", "contatos")
    : `${visiveis.length} de ${plural(contatos.lista.length, "contato", "contatos")}`;
  if (!visiveis.length) {
    const tr = document.createElement("tr");
    const td = celula("Nenhum contato com essa pesquisa.", "ag-nada");
    td.colSpan = 4;
    tr.append(td);
    $("#ct-corpo").replaceChildren(tr);
    return;
  }
  $("#ct-corpo").replaceChildren(...visiveis.map((c) => {
    const tr = document.createElement("tr");
    const tdAcao = document.createElement("td");
    tdAcao.className = "c-acao";
    tdAcao.append(botaoIcone("ct-editar", "i-lapis", `Alterar ${c.nome}`, { id: c.id }));
    tr.append(celula(c.nome),
      c.telefone ? celula(telefoneBR(c.telefone), "c-telefone") : celula("Sem telefone", "c-telefone ag-sem-dado"),
      ligacoesDoContato(c), tdAcao);
    return tr;
  }));
}

/* ---------- Conferir contatos (o que a passagem para a 1.6.0 não juntou sozinha) ---------- */

function botaoConferir(rotulo, acao, dados, primario = false) {
  const b = Object.assign(document.createElement("button"), { type: "button", className: `btn btn-peq${primario ? " btn-primario" : ""}`, textContent: rotulo });
  b.dataset.acao = acao;
  Object.assign(b.dataset, dados);
  return b;
}

function desenharConferir() {
  $("#ct-conferir").hidden = contatos.aConferir.length === 0;
  $("#ct-conferir-lista").replaceChildren(...contatos.aConferir.map((item) => {
    const li = Object.assign(document.createElement("li"), { className: "ct-conferir-item" });
    const pergunta = document.createElement("p");
    const botoes = Object.assign(document.createElement("div"), { className: "ct-conferir-botoes" });
    if (item.tipo === "parecidos") {
      const [a, b] = item.ids;
      const [na, nb] = item.nomes;
      const pessoa = (nome, tel) => {
        const span = document.createElement("span");
        span.append(Object.assign(document.createElement("b"), { textContent: nome }));
        if (tel) span.append(Object.assign(document.createElement("span"), { className: "ct-tel", textContent: ` · ${telefoneBR(tel)}` }));
        return span;
      };
      pergunta.append(pessoa(na, item.telefones[0]), " e ", pessoa(nb, item.telefones[1]), " são a mesma pessoa?");
      botoes.append(botaoConferir(`Sim, fica “${na}”`, "ct-juntar", { manter: a, tirar: b }),
        botaoConferir(`Sim, fica “${nb}”`, "ct-juntar", { manter: b, tirar: a }),
        botaoConferir("Não, são pessoas diferentes", "ct-diferentes", { ids: item.ids.join(",") }));
    } else {
      pergunta.append(Object.assign(document.createElement("b"), { textContent: item.nome }), " tinha dois telefones. Qual vale?");
      for (const t of item.telefones) {
        botoes.append(botaoConferir(telefoneBR(t) + (t === item.atual ? " (o de agora)" : ""), "ct-telefone", { id: item.id, telefone: t }));
      }
    }
    li.append(pergunta, botoes);
    return li;
  }));
}

async function conferido(promessa) {
  const r = await promessa;
  aplicarContatos(r);
  if (!r.erro) mostrarToast("Pronto, contato conferido.");
}

async function juntarContatos(manter, tirar) {
  const r = await api().contatos_juntar(manter, tirar);
  aplicarContatos(r);
  if (!r.erro) mostrarToast(`Juntados: tudo de “${r.juntados[1]}” agora é de “${r.juntados[0]}”.`);
}

/* ---------- Janela de contato ---------- */

function escolherSituacao(situacao) {
  contatos.situacao = situacao;
  $$(".ag-situacoes .escolha").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.situacao === situacao)));
  $("#ag-alta-campos").hidden = situacao !== "alta";
}

function ligarOrto(ligado) {
  contatos.orto = ligado;
  $("#ct-orto").setAttribute("aria-checked", String(ligado));
  $("#ct-orto-campos").hidden = !ligado;
  // Quem tinha tratamento e desligou: avisa o que vai acontecer ao salvar.
  $("#ct-orto-desligar").hidden = ligado || !(contatos.editando && contatos.editando.tratamento);
}

function mostrarResponsaveisDoContato() {
  const tem = $("#ct-tem-responsaveis").checked;
  $("#ct-responsaveis").hidden = !tem;
  if (tem && !$("#ct-resp-lista").children.length) $("#ct-resp-lista").append(linhaDeResponsavel(null));
}

function linhaDeResponsavel(r) {
  const li = Object.assign(document.createElement("li"), { className: "ct-resp" });
  const n = Math.random().toString(36).slice(2, 8);
  // `caixa` é o que vai no campo (o select vem dentro da caixa que desenha a setinha).
  const campo = (rotulo, el, caixa = el) => {
    const div = Object.assign(document.createElement("div"), { className: `campo campo-texto ct-resp-campo-${el.dataset.parte}` });
    el.id = `ct-resp-${el.dataset.parte}-${n}`;
    div.append(Object.assign(document.createElement("label"), { className: "rotulo-campo", htmlFor: el.id, textContent: rotulo }), caixa);
    return div;
  };
  const nome = Object.assign(document.createElement("input"), { type: "text", autocomplete: "off", className: "ct-resp-nome", value: r ? r.nome : "" });
  nome.setAttribute("list", "ct-nomes");
  nome.dataset.parte = "nome";
  const papel = Object.assign(document.createElement("select"), { className: "ct-resp-papel" });
  papel.dataset.parte = "papel";
  papel.append(...PAPEIS.map(([v, t]) => new Option(t, v)));
  papel.value = r ? r.papel : "mae";
  const caixaPapel = Object.assign(document.createElement("span"), { className: "select" });
  caixaPapel.append(papel);
  const tel = Object.assign(document.createElement("input"), { type: "tel", autocomplete: "off", className: "ct-resp-tel", placeholder: "(61) 90000-0000", value: r && r.telefone ? telefoneBR(r.telefone) : "" });
  tel.dataset.parte = "tel";
  const cpf = Object.assign(document.createElement("input"), { type: "text", inputMode: "numeric", autocomplete: "off", className: "ct-resp-cpf campo-cpf", placeholder: "000.000.000-00", value: r && r.cpf ? cpfBR(r.cpf) : "" });
  cpf.dataset.parte = "cpf";
  li.append(campo("Nome do responsável", nome), campo("Quem é", papel, caixaPapel), campo("Telefone", tel),
    campo("CPF (opcional)", cpf), botaoIcone("ct-tirar-responsavel", "i-fechar", "Tirar este responsável", {}));
  return li;
}

/* Escolheu da lista um contato que já tem telefone: o campo já vem preenchido. */
function preencherTelefoneDoResponsavel(campoNome) {
  const existente = contatoPorNome(campoNome.value);
  const tel = campoNome.closest("li").querySelector(".ct-resp-tel");
  if (existente && existente.telefone && !tel.value.trim()) tel.value = telefoneBR(existente.telefone);
  const cpf = campoNome.closest("li").querySelector(".ct-resp-cpf");
  if (existente && existente.cpf && !cpf.value.trim()) cpf.value = cpfBR(existente.cpf);
}

function preencherContato(c) {
  $("#ct-nome").value = c ? c.nome : "";
  $("#ct-telefone").value = c && c.telefone ? telefoneBR(c.telefone) : "";
  $("#ct-cpf").value = c && c.cpf ? cpfBR(c.cpf) : "";
  $("#ct-nascimento").value = c && c.nascimento ? c.nascimento : "";
  sugerirCpfDoContato(c);
  const responsaveis = c ? c.responsaveis : [];
  $("#ct-tem-responsaveis").checked = responsaveis.length > 0;
  $("#ct-resp-lista").replaceChildren(...responsaveis.map(linhaDeResponsavel));
  mostrarResponsaveisDoContato();
  const t = c && c.tratamento;
  $("#ag-valor").value = t ? valorParaCampo(t.valor_centavos) : "";
  $("#ag-alta-inicio").value = t ? t.alta_inicio : "";
  $("#ag-alta-fim").value = t ? t.alta_fim : "";
  escolherSituacao(t ? t.situacao : "ativo");
  $("#ct-apagar").hidden = !c;
  $("#ag-ver-historico").hidden = !t;
}

/* Sem CPF guardado: se ele está numa nota já emitida, oferece usar (só entra ao salvar). */
async function sugerirCpfDoContato(c) {
  const faixa = $("#ct-cpf-sugestao");
  faixa.hidden = true;
  if (!c || c.cpf) return;
  const r = await api().contatos_sugestao_cpf(c.nome);
  if (r.erro || !r.sugestao || contatos.editando !== c || $("#ct-cpf").value.trim()) return;
  faixa.dataset.cpf = r.sugestao.cpf;
  $("#ct-cpf-sugestao-texto").textContent = `Achei o CPF na nota nº ${r.sugestao.numero}: ${r.sugestao.cpf}.`;
  faixa.hidden = false;
}

/* `opcoes.orto`: abrir já com a ortodontia ligada (o "Novo paciente" de Tratamentos). */
async function abrirContato(c, opcoes = {}) {
  if (!contatos.lista.length || (c && !contatoPorId(c.id))) await carregarContatos();
  c = c ? contatoPorId(c.id) || c : null;
  contatos.editando = c;
  contatos.depoisDeSalvar = opcoes.depoisDeSalvar || null;
  const orto = opcoes.orto || !!(c && c.tratamento);
  $("#ct-contato-titulo").textContent = c ? (orto ? "Alterar paciente" : "Alterar contato") : (opcoes.orto ? "Novo paciente" : "Novo contato");
  $("#ct-carregado").hidden = true;
  // Sugerir nomes só serve no "novo" (para achar quem já existe); ao alterar, atrapalha.
  if (c) $("#ct-nome").removeAttribute("list"); else $("#ct-nome").setAttribute("list", "ct-nomes");
  preencherContato(c);
  ligarOrto(orto);
  $("#ct-contato-erro").hidden = true;
  $("#ct-contato").showModal();
  $("#ct-nome").focus();
}

async function abrirContatoPorId(id, opcoes = {}) {
  await carregarContatos();
  const c = contatoPorId(id);
  if (!c) return mostrarToast("Não encontrei esse contato. Ele pode ter sido apagado.", { erro: true });
  abrirContato(c, opcoes);
}

/* No "novo", escrever o nome de quem já existe abre esse contato (em vez de recusar no fim). */
function carregarSeJaExiste() {
  if (contatos.editando) return;
  const existente = contatoPorNome($("#ct-nome").value);
  if (!existente) return;
  const orto = contatos.orto;
  contatos.editando = existente;
  preencherContato(existente);
  ligarOrto(orto || !!existente.tratamento);
  $("#ct-contato-titulo").textContent = "Alterar contato";
  $("#ct-nome").removeAttribute("list");
  $("#ct-carregado-texto").textContent = `“${existente.nome}” já está nos contatos: abri o cadastro dele.`;
  $("#ct-carregado").hidden = false;
}

function dadosDosResponsaveis() {
  if (!$("#ct-tem-responsaveis").checked) return [];
  return $$("#ct-resp-lista li").map((li) => {
    const nome = li.querySelector(".ct-resp-nome").value;
    const existente = contatoPorNome(nome);
    return {
      contato_id: existente ? existente.id : "",
      nome,
      telefone: li.querySelector(".ct-resp-tel").value,
      cpf: li.querySelector(".ct-resp-cpf").value,
      papel: li.querySelector(".ct-resp-papel").value,
    };
  });
}

async function salvarContato(e) {
  e.preventDefault();
  const anterior = contatos.editando;
  const situacao = contatos.situacao;
  const r = await api().contatos_salvar({
    nome: $("#ct-nome").value,
    telefone: $("#ct-telefone").value,
    cpf: $("#ct-cpf").value,
    nascimento: $("#ct-nascimento").value,
    responsaveis: dadosDosResponsaveis(),
    orto: contatos.orto,
    valor: $("#ag-valor").value,
    situacao,
    alta_inicio: $("#ag-alta-inicio").value,
    alta_fim: $("#ag-alta-fim").value,
  }, anterior ? anterior.id : null);
  if (r.erro) {
    // Um aviso comum ficaria escondido atrás da janela.
    $("#ct-contato-erro").textContent = r.erro;
    $("#ct-contato-erro").hidden = false;
    return;
  }
  $("#ct-contato").close();
  aplicarContatos(r);
  const antes = anterior && anterior.tratamento ? anterior.tratamento.situacao : null;
  if (r.tratamento_apagado) {
    mostrarToast(`${r.salvo.nome} saiu de Tratamentos.`, {
      acoes: [["Desfazer", async () => { aplicarContatos(await api().contatos_restaurar_tratamento(r.tratamento_apagado)); depoisDeMudarContato(); }]],
    });
  } else if (contatos.orto && situacao !== antes && (antes || situacao !== "ativo")) {
    mostrarToast(`${r.salvo.nome} foi para ${NOMES_DAS_SITUACOES[situacao]}.`);
  } else if (contatos.orto && !antes) {
    mostrarToast(`${r.salvo.nome} entrou em Tratamentos.`);
  }
  depoisDeMudarContato();
}

/* Outras telas mostram nomes e telefones: elas recarregam quando um contato muda. */
function depoisDeMudarContato() {
  contatos.depoisDeSalvar?.();
  if (estado.view === "tratamentos") carregarAgenda();
}

async function apagarContato() {
  const c = contatos.editando;
  const r = await api().contatos_apagar(c.id);
  if (r.erro) {
    $("#ct-contato-erro").textContent = r.erro;
    $("#ct-contato-erro").hidden = false;
    return;
  }
  $("#ct-contato").close();
  aplicarContatos(r);
  depoisDeMudarContato();
  mostrarToast(`Contato apagado: ${c.nome}${r.apagado.tratamento ? " (e o tratamento de orto)" : ""}`, {
    acoes: [["Desfazer", async () => { aplicarContatos(await api().contatos_restaurar(r.apagado)); depoisDeMudarContato(); }]],
  });
}


/* ---------- Widget do Início ---------- */

registrarWidget("contatos", {
  icone: "i-pessoas",
  desenhar(corpo, c) {
    if (!c.total) {
      corpo.append(texto("p", "Nenhum contato ainda.", "dica"), rodape(botaoIr("Abrir contatos", "contatos")));
      return;
    }
    corpo.append(numeros([
      ["Contatos", String(c.total)],
      ["Sem telefone", String(c.sem_telefone), c.sem_telefone ? "ini-alerta" : ""],
      ["Novos no mês", String(c.novos_no_mes)],
    ]));
    if (c.a_conferir) {
      corpo.append(texto("p", `${plural(c.a_conferir, "contato precisa", "contatos precisam")} ser conferido${c.a_conferir === 1 ? "" : "s"}.`, "ini-alerta"));
    }
    corpo.append(rodape(botaoIr(c.a_conferir ? "Conferir contatos" : "Abrir contatos", "contatos")));
  },
});
