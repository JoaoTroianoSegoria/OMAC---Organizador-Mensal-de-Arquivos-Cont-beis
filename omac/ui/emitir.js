/* OMAC — Janela "Emitir nota" (botão Emitir da ficha de Atendimentos).
 *
 * À esquerda, o que o site da nota pede, cada um com Copiar: nome e CPF de quem recebe a nota
 * (o paciente ou um responsável; a última escolha fica guardada no contato), data e valor do
 * atendimento e, quando a nota sai no nome de um responsável, os dados do dependente.
 * À direita, os Comandos da categoria escolhida, com as [variáveis] já preenchidas. O [numero-nota]
 * é o maior número da pasta + 1: um palpite, que a conferência do PDF baixado corrige (notas.js).
 *
 * O CPF que estiver numa nota já emitida aparece como sugestão, e só é guardado quando alguém
 * clica em "Usar este CPF". Tudo fica só neste computador.
 */
"use strict";

const emissao = {
  dados: null, // contatos_cpf: {id, nome, pessoas, escolhido, site, categoria, proximo_numero}
  atendimento: null,
  escolhido: "",
  editando: false,
  categorias: [],
  copiados: new Set(), // ids dos comandos já copiados nesta emissão (o ✓)
};

// Variáveis dos comandos (iguais em maiúscula ou minúscula). As do dependente só existem
// quando a nota sai no nome de outra pessoa.
const VARIAVEIS_DO_DEPENDENTE = ["nome-do-dependente", "cpf-dependente", "data-nascimento-dependente"];
const RE_VARIAVEL = /\[([^\[\]\n]{1,40})\]/g;

modulos.emitir = {
  ligar() {
    $("#form-emitir-cpf").addEventListener("submit", (e) => { e.preventDefault(); salvarCpfDaEmissao($("#emitir-cpf-campo").value); });
    $("#form-emitir-dep").addEventListener("submit", (e) => { e.preventDefault(); salvarDependente(); });
    $("#emitir-categoria").addEventListener("change", (e) => escolherCategoriaDaEmissao(e.target.value));
  },
};

Object.assign(acoes, {
  "emitir-quem": (alvo) => escolherQuemRecebeANota(alvo.dataset.id),
  "emitir-copiar": (alvo) => copiarDaEmissao(alvo.dataset.campo),
  "emitir-copiar-comando": (alvo) => copiarComandoDaEmissao(alvo.dataset.id),
  "emitir-alterar-cpf": () => { emissao.editando = true; desenharEmissao(); $("#emitir-cpf-campo").focus(); },
  "emitir-cancelar-cpf": () => { emissao.editando = false; desenharEmissao(); },
  "emitir-usar-sugestao": () => salvarCpfDaEmissao(pessoaDaEmissao().sugestao.cpf),
  "emitir-dep-alterar": () => abrirFormDependente(),
  "emitir-dep-cancelar": () => { $("#form-emitir-dep").hidden = true; },
  "emitir-site": async () => { const r = await api().abrir_site_nota(); if (r.erro) mostrarToast(r.erro, { erro: true }); },
  "emitir-fechar": () => $("#emitir").close(),
});

/* `atendimento` (opcional): a linha da ficha, para a data, o valor e o tratamento. */
async function abrirEmissao(contatoId, atendimento = null) {
  const [r, cmds] = await Promise.all([api().contatos_cpf(contatoId), api().comandos_listar()]);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  emissao.dados = r;
  emissao.atendimento = atendimento;
  emissao.escolhido = r.escolhido;
  emissao.editando = false;
  emissao.copiados = new Set();
  emissao.categorias = cmds.erro ? [] : cmds.categorias;
  $("#emitir-titulo").textContent = `Emitir nota: ${r.nome}`;
  const linha = $("#emitir-atendimento");
  linha.replaceChildren();
  if (atendimento) {
    linha.append(`Atendimento de ${dataBR(atendimento.data)}`);
    if (atendimento.tratamento) linha.append(` · ${atendimento.tratamento}`);
  }
  linha.hidden = !atendimento;
  $("#emitir-site").hidden = !r.site;
  $("#form-emitir-dep").hidden = true;
  desenharCategoriasDaEmissao();
  desenharEmissao();
  $("#emitir").showModal();
  if (!$("#form-emitir-cpf").hidden) $("#emitir-cpf-campo").focus();
}

const pessoaDaEmissao = () => emissao.dados.pessoas.find((p) => p.contato_id === emissao.escolhido) || emissao.dados.pessoas[0];

/* O paciente do atendimento, quando a nota sai no nome de outra pessoa (mãe, pai...). */
function dependenteDaEmissao() {
  const p = pessoaDaEmissao();
  return p.contato_id === emissao.dados.id ? null : emissao.dados.pessoas.find((x) => x.contato_id === emissao.dados.id);
}

/* Valor só com número, como o site da nota pede: 180,00. */
const valorDaEmissao = () => {
  const a = emissao.atendimento;
  return a && a.valor_centavos != null ? (a.valor_centavos / 100).toFixed(2).replace(".", ",") : "";
};

function desenharEmissao() {
  const r = emissao.dados;
  const p = pessoaDaEmissao();
  const a = emissao.atendimento;
  $("#emitir-quem-campo").hidden = r.pessoas.length < 2;
  $("#emitir-quem").replaceChildren(...r.pessoas.map((x) => {
    const b = Object.assign(document.createElement("button"), { type: "button", className: "escolha" });
    b.dataset.acao = "emitir-quem";
    b.dataset.id = x.contato_id;
    const papel = x.papel ? x.papel[0].toUpperCase() + x.papel.slice(1) : "Paciente";
    b.textContent = `${papel}: ${x.nome}`;
    b.setAttribute("aria-pressed", String(x.contato_id === p.contato_id));
    return b;
  }));
  $("#emitir-nome").textContent = p.nome;
  const cpf = $("#emitir-cpf");
  cpf.textContent = p.cpf || "Sem CPF guardado";
  cpf.classList.toggle("emitir-falta", !p.cpf);
  $("#emitir-copiar-cpf").hidden = !p.cpf;
  $("#emitir-alterar-cpf").hidden = !p.cpf || emissao.editando;
  $("#emitir-linha-data").hidden = !a;
  if (a) $("#emitir-data").textContent = dataBR(a.data);
  $("#emitir-linha-valor").hidden = !a || a.valor_centavos == null;
  if (a && a.valor_centavos != null) $("#emitir-valor").replaceChildren(dinheiro(a.valor_centavos));
  const sugestao = p.sugestao;
  $("#emitir-sugestao").hidden = !sugestao || emissao.editando;
  if (sugestao) {
    $("#emitir-sugestao-texto").textContent = p.cpf
      ? `A nota nº ${sugestao.numero} saiu com outro CPF: ${sugestao.cpf}. Confira qual está certo.`
      : `Achei o CPF na nota nº ${sugestao.numero}: ${sugestao.cpf}.`;
  }
  // Sem CPF, o campo já aparece para digitar; com CPF, só pelo lápis.
  const digitar = !p.cpf || emissao.editando;
  $("#form-emitir-cpf").hidden = !digitar;
  $("#emitir-cpf-rotulo").textContent = `CPF de ${p.nome}`;
  $("#emitir-cancelar-cpf").hidden = !p.cpf;
  if (digitar) $("#emitir-cpf-campo").value = p.cpf || "";
  $("#emitir-erro").hidden = true;

  const dep = dependenteDaEmissao();
  $("#emitir-dependente").hidden = !dep;
  if (dep) {
    $("#emitir-dep-nome").textContent = dep.nome;
    $("#emitir-dep-dados").textContent = [
      dep.cpf ? `CPF ${dep.cpf}` : "sem CPF",
      dep.nascimento ? `nasc. ${dataBR(dep.nascimento)}` : "sem data de nascimento",
    ].join(" · ");
  }
  desenharComandosDaEmissao();
}

function escolherQuemRecebeANota(id) {
  emissao.escolhido = id;
  emissao.editando = false;
  $("#form-emitir-dep").hidden = true;
  desenharEmissao();
  api().contatos_nota_para(emissao.dados.id, id); // só lembra a escolha; não precisa esperar
}

async function copiarDaEmissao(campo) {
  const p = pessoaDaEmissao();
  const a = emissao.atendimento;
  const valores = { nome: p.nome, cpf: p.cpf, data: a ? dataBR(a.data) : "", valor: valorDaEmissao() };
  const rotulos = { nome: "Nome", cpf: "CPF", data: "Data", valor: "Valor" };
  const valor = valores[campo];
  if (!valor) return;
  if (await copiarTexto(valor)) mostrarToast(`${rotulos[campo]} copiado: ${campo === "valor" ? dinheiroTexto(a.valor_centavos) : valor}`);
  else mostrarToast("Não consegui copiar. Selecione o texto e use Ctrl+C.", { erro: true });
}

function lembrarDasMudancas(r) {
  emissao.dados = r;
  if (contatos.lista.length) carregarContatos(); // a janela de contato mostra o dado novo
}

async function salvarCpfDaEmissao(valor) {
  const p = pessoaDaEmissao();
  const r = await api().contatos_salvar_cpf(emissao.dados.id, p.contato_id, valor);
  if (r.erro) {
    $("#emitir-erro").textContent = r.erro;
    $("#emitir-erro").hidden = false;
    return;
  }
  lembrarDasMudancas(r);
  emissao.escolhido = p.contato_id;
  emissao.editando = false;
  desenharEmissao();
  mostrarToast(valor.trim() ? `CPF de ${p.nome} guardado.` : `CPF de ${p.nome} apagado.`);
}

/* ---------- Dependente: CPF e nascimento ---------- */

function abrirFormDependente() {
  const dep = dependenteDaEmissao();
  if (!dep) return;
  $("#emitir-dep-cpf").value = dep.cpf || "";
  $("#emitir-dep-nasc").value = dep.nascimento || "";
  $("#form-emitir-dep").hidden = false;
  (dep.cpf ? $("#emitir-dep-nasc") : $("#emitir-dep-cpf")).focus();
}

async function salvarDependente() {
  const dep = dependenteDaEmissao();
  const id = emissao.dados.id;
  let r = await api().contatos_salvar_cpf(id, dep.contato_id, $("#emitir-dep-cpf").value);
  if (!r.erro) r = await api().contatos_salvar_nascimento(id, dep.contato_id, $("#emitir-dep-nasc").value);
  if (r.erro) {
    $("#emitir-erro").textContent = r.erro;
    $("#emitir-erro").hidden = false;
    return;
  }
  const escolhido = emissao.escolhido;
  lembrarDasMudancas(r);
  emissao.escolhido = escolhido; // guardar o CPF do dependente não muda de quem é a nota
  api().contatos_nota_para(id, escolhido);
  $("#form-emitir-dep").hidden = true;
  desenharEmissao();
  mostrarToast(`Dados de ${dep.nome} guardados.`);
}

/* ---------- Comandos ao lado ---------- */

function desenharCategoriasDaEmissao() {
  const sel = $("#emitir-categoria");
  sel.replaceChildren(new Option("Escolha a categoria", ""),
    ...emissao.categorias.map((c) => new Option(c.nome, c.id)));
  const guardada = emissao.categorias.some((c) => c.id === emissao.dados.categoria) ? emissao.dados.categoria : "";
  sel.value = guardada;
}

async function escolherCategoriaDaEmissao(id) {
  emissao.dados.categoria = id;
  desenharComandosDaEmissao();
  const r = await api().contatos_categoria_emissao(id);
  if (r.erro) mostrarToast(r.erro, { erro: true });
}

/* Os valores das variáveis agora (mudam quando troca quem recebe a nota). "" = falta o dado. */
function valoresDaEmissao() {
  const p = pessoaDaEmissao();
  const a = emissao.atendimento;
  const dep = dependenteDaEmissao();
  return {
    "nome": p.nome,
    "cpf": p.cpf,
    "data-competencia": a ? dataBR(a.data) : "",
    "valor": valorDaEmissao(),
    // Para o nome do PDF: 000000013, 23-11 e 21-11.
    "numero-nota": emissao.dados.proximo_numero ? String(emissao.dados.proximo_numero).padStart(9, "0") : "",
    "data-hoje": diaMesHoje(),
    "comp": a ? dataBR(a.data).slice(0, 5).replace("/", "-") : "",
    "tratamento": a ? a.tratamento : "",
    "nome-do-dependente": dep ? dep.nome : "",
    "cpf-dependente": dep ? dep.cpf : "",
    "data-nascimento-dependente": dep && dep.nascimento ? dataBR(dep.nascimento) : "",
  };
}

function diaMesHoje() {
  const hoje = new Date();
  return `${String(hoje.getDate()).padStart(2, "0")}-${String(hoje.getMonth() + 1).padStart(2, "0")}`;
}

const ROTULOS_DA_FALTA = {
  "cpf": (v) => `o CPF de ${v.nome}`,
  "data-competencia": () => "a data do atendimento",
  "comp": () => "a data do atendimento",
  "numero-nota": () => "o número da próxima nota: a pasta das notas está vazia ou não foi escolhida",
  "valor": () => "o valor do atendimento",
  "tratamento": () => "o tratamento do atendimento",
  "cpf-dependente": (v) => `o CPF de ${v["nome-do-dependente"]}`,
  "data-nascimento-dependente": (v) => `a data de nascimento de ${v["nome-do-dependente"]}`,
};

/* O texto pronto, o que falta preencher e se o comando precisa de dependente (e não tem). */
function preencherComando(texto) {
  const v = valoresDaEmissao();
  const usadas = [...texto.matchAll(RE_VARIAVEL)].map((m) => m[1].trim().toLowerCase()).filter((n) => n in v);
  const semDependente = !dependenteDaEmissao() && usadas.some((n) => VARIAVEIS_DO_DEPENDENTE.includes(n));
  const faltam = semDependente ? [] : [...new Set(usadas.filter((n) => !v[n]))].map((n) => (ROTULOS_DA_FALTA[n] || (() => n))(v));
  const pronto = texto.replace(RE_VARIAVEL, (todo, nome) => {
    const chave = nome.trim().toLowerCase();
    return chave in v && v[chave] ? v[chave] : todo;
  });
  return { pronto, faltam, semDependente };
}

function desenharComandosDaEmissao() {
  const categoria = emissao.categorias.find((c) => c.id === emissao.dados.categoria);
  const lista = $("#emitir-comandos-lista");
  const vazio = $("#emitir-comandos-vazio");
  vazio.hidden = !!(categoria && categoria.comandos.length);
  vazio.textContent = !emissao.categorias.length ? "Nenhum comando ainda. Crie em Lembretes → Comandos."
    : !categoria ? "Escolha a categoria com os textos que você usa para emitir a nota."
      : "Essa categoria não tem comandos. Crie em Lembretes → Comandos.";
  if (!categoria) return lista.replaceChildren();
  lista.replaceChildren(...categoria.comandos.map((c) => {
    const { pronto, faltam, semDependente } = preencherComando(c.texto);
    const li = Object.assign(document.createElement("li"), { className: "emitir-comando" });
    li.classList.toggle("emitir-comando-inativo", semDependente);
    const cab = Object.assign(document.createElement("div"), { className: "emitir-comando-cab" });
    const nome = texto("strong", c.nome);
    if (emissao.copiados.has(c.id)) nome.append(texto("span", " ✓", "emitir-copiado"));
    const b = Object.assign(document.createElement("button"), { type: "button", className: "btn btn-peq" });
    b.dataset.acao = "emitir-copiar-comando";
    b.dataset.id = c.id;
    b.innerHTML = '<svg class="ic"><use href="#i-copiar"/></svg><span>Copiar</span>';
    b.setAttribute("aria-label", `Copiar ${c.nome}`);
    b.disabled = semDependente;
    cab.append(nome, b);
    li.append(cab, texto("p", pronto, "emitir-comando-texto"));
    if (semDependente) li.append(texto("p", "Esta nota não tem dependente.", "dica"));
    else if (faltam.length) li.append(texto("p", `Falta ${faltam.join(", ")}.`, "emitir-comando-falta"));
    return li;
  }));
}

async function copiarComandoDaEmissao(id) {
  const categoria = emissao.categorias.find((c) => c.id === emissao.dados.categoria);
  const comando = categoria && categoria.comandos.find((c) => c.id === id);
  if (!comando) return;
  const { pronto, faltam, semDependente } = preencherComando(comando.texto);
  if (semDependente) return;
  if (faltam.length) {
    // Melhor não mandar a descrição pela metade para a nota: pede o dado antes.
    mostrarToast(`Preencha antes: ${faltam.join(", ")}.`, { erro: true });
    if (faltam.some((f) => f.includes(dependenteDaEmissao()?.nome || "\u0000"))) abrirFormDependente();
    else if (!pessoaDaEmissao().cpf) $("#emitir-cpf-campo").focus();
    return;
  }
  if (await copiarTexto(pronto)) {
    emissao.copiados.add(id);
    desenharComandosDaEmissao();
    mostrarToast(`Copiado: ${comando.nome}`);
  } else {
    mostrarToast("Não consegui copiar. Selecione o texto e use Ctrl+C.", { erro: true });
  }
}
