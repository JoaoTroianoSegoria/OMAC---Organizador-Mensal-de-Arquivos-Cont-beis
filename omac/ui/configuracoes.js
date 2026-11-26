/* OMAC — Configurações com mais de um campo: como ler as notas (formato do nome do arquivo e
 * descrição esperada) e as mensagens do WhatsApp com [variáveis] (categoria Mensagens).
 *
 * Diferente dos outros campos das Configurações, estes só valem ao clicar em Salvar: o formato
 * muda a leitura de todas as notas, e uma mensagem pela metade não pode ir para o WhatsApp.
 *
 * Cada mensagem é um cartão. As que vão para o paciente ou para um responsável têm duas abas,
 * cada uma com o seu texto; o que a pessoa escreveu e não salvou fica guardado ao trocar de aba.
 * A lista de mensagens vem do Python (whatsapp/catalogo.py): mensagem nova aparece sozinha.
 */
"use strict";

const ajustes = {
  editado: { leitura: false }, // a pessoa mexeu e ainda não salvou
  // tipo → { dados (do Python), versao (aba aberta), rascunhos: {versao: texto não salvo} }
  mensagens: new Map(),
  timers: {},
};

modulos.configuracoes = {
  ligar() {
    $("#form-cfg-leitura").addEventListener("submit", (e) => { e.preventDefault(); salvarLeitura(); });
    $("#cfg-formato").addEventListener("input", () => { ajustes.editado.leitura = true; depois("teste", testarFormato); });
    $("#cfg-servico").addEventListener("input", () => { ajustes.editado.leitura = true; });
    const lista = $("#cfg-msg-lista");
    lista.addEventListener("submit", (e) => {
      e.preventDefault();
      salvarMensagem(e.target.closest(".cfg-msg").dataset.tipo);
    });
    lista.addEventListener("input", (e) => {
      if (!e.target.matches(".cfg-msg textarea")) return;
      const tipo = e.target.closest(".cfg-msg").dataset.tipo;
      const m = ajustes.mensagens.get(tipo);
      m.rascunhos[m.versao] = e.target.value;
      marcarAbas(tipo);
      depois(tipo, () => mostrarPrevia(tipo));
    });
    // Abas com as setas, como em qualquer lista de abas.
    lista.addEventListener("keydown", (e) => {
      const aba = e.target.closest(".cfg-aba");
      if (!aba || (e.key !== "ArrowLeft" && e.key !== "ArrowRight")) return;
      const vizinha = e.key === "ArrowRight" ? aba.nextElementSibling : aba.previousElementSibling;
      if (!vizinha) return;
      e.preventDefault();
      trocarAba(vizinha.dataset.tipo, vizinha.dataset.versao);
      vizinha.focus();
    });
  },
  aoAplicarConfig(cfg) {
    if (!ajustes.editado.leitura) preencherLeitura(cfg);
  },
};

Object.assign(acoes, {
  "cfg-variavel": (alvo) => inserirVariavel(alvo),
  "cfg-leitura-padrao": leituraPadrao,
  "cfg-msg-padrao": (alvo) => mensagemPadrao(alvo.dataset.tipo),
  "cfg-msg-aba": (alvo) => trocarAba(alvo.dataset.tipo, alvo.dataset.versao),
});

function depois(chave, fn, ms = 350) {
  clearTimeout(ajustes.timers[chave]);
  ajustes.timers[chave] = setTimeout(fn, ms);
}

async function carregarConfiguracoes() {
  if (!ajustes.editado.leitura) preencherLeitura(estado.cfg);
  testarFormato();
  const r = await api().mensagens_modelos();
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  aplicarModelosDeMensagem(r);
}

/* Põe a variável onde está o cursor do campo (ou no fim), como se tivesse sido digitada. */
function inserirVariavel(botao) {
  const campo = $(`#${botao.closest("[data-alvo]").dataset.alvo}`);
  const texto = `[${botao.dataset.variavel}]`;
  const inicio = campo.selectionStart ?? campo.value.length;
  const fim = campo.selectionEnd ?? campo.value.length;
  campo.setRangeText(texto, inicio, fim, "end");
  campo.focus();
  campo.dispatchEvent(new Event("input", { bubbles: true }));
}

/* ---------- Como ler as notas ---------- */

function preencherLeitura(cfg) {
  if (!cfg) return;
  $("#cfg-formato").value = cfg.formato_arquivo;
  $("#cfg-servico").value = cfg.servico_esperado;
}

async function testarFormato() {
  const caixa = $("#cfg-formato-teste");
  const r = await api().notas_testar_formato($("#cfg-formato").value);
  caixa.className = "cfg-teste";
  if (r.erro) {
    caixa.classList.add("cfg-teste-erro");
    caixa.replaceChildren(r.erro);
    return;
  }
  if (r.sem_pasta) {
    caixa.replaceChildren("Escolha a pasta das notas para testar o formato.");
    return;
  }
  if (!r.total) {
    caixa.replaceChildren("A pasta das notas não tem nenhum PDF para testar.");
    return;
  }
  const tudo = r.entendidos === r.total;
  caixa.classList.add(tudo ? "cfg-teste-ok" : r.entendidos ? "cfg-teste-aviso" : "cfg-teste-erro");
  const partes = [texto("strong", `Entendi ${r.entendidos} de ${plural(r.total, "arquivo", "arquivos")} da pasta.`)];
  if (r.exemplos.length) {
    const ul = Object.assign(document.createElement("ul"), { className: "cfg-teste-lista" });
    for (const e of r.exemplos) ul.append(texto("li", `${e.arquivo} → nº ${e.numero}, ${e.nome}`));
    partes.push(ul);
  }
  if (r.fora.length) {
    partes.push(texto("span", r.entendidos ? "Fora do formato (o OMAC usa o nome que está dentro da nota):" : "Nenhum arquivo bate com o formato. Exemplos da pasta:"));
    const ul = Object.assign(document.createElement("ul"), { className: "cfg-teste-lista" });
    for (const nome of r.fora) ul.append(texto("li", nome));
    partes.push(ul);
  }
  caixa.replaceChildren(...partes);
}

async function salvarLeitura() {
  const r = await api().notas_salvar_regras($("#cfg-formato").value, $("#cfg-servico").value);
  if (r.erro) {
    $("#cfg-leitura-erro").textContent = r.erro;
    $("#cfg-leitura-erro").hidden = false;
    return;
  }
  $("#cfg-leitura-erro").hidden = true;
  ajustes.editado.leitura = false;
  estado.cfg = r.config;
  aplicarConfig();
  testarFormato();
  mostrarToast("Salvo. As notas vão ser lidas de novo com o formato novo.");
}

async function leituraPadrao() {
  const r = await api().notas_regras_padrao();
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  $("#cfg-formato").value = r.formato;
  $("#cfg-servico").value = r.servico;
  ajustes.editado.leitura = true;
  testarFormato();
  mostrarToast("Voltou ao padrão. Clique em Salvar para valer.");
}

/* ---------- Mensagens com variáveis ---------- */

/* `r.grupos`: [{nome: "Tratamentos", mensagens: [{tipo, titulo, dica, variaveis, versoes: [{versao, rotulo,
 * modelo, padrao, mudada}]}]}]. Os cartões são feitos uma vez; depois só os textos são atualizados. */
function aplicarModelosDeMensagem(r) {
  const tipos = r.grupos.flatMap((g) => g.mensagens.map((m) => m.tipo));
  const feitos = $$("#cfg-msg-lista .cfg-msg").map((c) => c.dataset.tipo);
  for (const g of r.grupos) {
    for (const dados of g.mensagens) {
      const m = ajustes.mensagens.get(dados.tipo);
      if (m) m.dados = dados;
      else ajustes.mensagens.set(dados.tipo, { dados, versao: dados.versoes[0].versao, rascunhos: {} });
    }
  }
  if (JSON.stringify(tipos) !== JSON.stringify(feitos)) {
    $("#cfg-msg-lista").replaceChildren(...r.grupos.flatMap((g) => [
      texto("h2", g.nome, "cfg-msg-grupo"),
      ...g.mensagens.map((m) => cartaoDaMensagem(m)),
    ]));
    desenharAtalhosDasMensagens(r.grupos); // cfg-menu.js
  }
  for (const tipo of tipos) mostrarVersao(tipo);
}

function cartaoDaMensagem(m) {
  const id = `cfg-msg-${m.tipo}`;
  const cartao = Object.assign(document.createElement("section"), { className: "grupo vidro cfg-msg", id });
  cartao.dataset.tipo = m.tipo;
  cartao.setAttribute("aria-labelledby", `${id}-titulo`);
  const titulo = texto("h3", m.titulo);
  titulo.id = `${id}-titulo`;
  cartao.append(titulo, texto("p", m.dica, "dica"));

  if (m.versoes.length > 1) {
    const abas = Object.assign(document.createElement("div"), { className: "cfg-abas" });
    abas.setAttribute("role", "tablist");
    abas.setAttribute("aria-label", `Para quem vai: ${m.titulo}`);
    for (const v of m.versoes) {
      const aba = Object.assign(document.createElement("button"), { type: "button", className: "cfg-aba", id: `${id}-aba-${v.versao}` });
      aba.setAttribute("role", "tab");
      aba.setAttribute("aria-controls", `${id}-form`);
      aba.dataset.acao = "cfg-msg-aba";
      aba.dataset.tipo = m.tipo;
      aba.dataset.versao = v.versao;
      aba.append(texto("span", v.rotulo), texto("small", "", "cfg-aba-marca"));
      abas.append(aba);
    }
    cartao.append(abas);
  }

  const form = Object.assign(document.createElement("form"), { className: "cfg-mensagem", id: `${id}-form` });
  if (m.versoes.length > 1) form.setAttribute("role", "tabpanel");
  const campo = Object.assign(document.createElement("div"), { className: "campo campo-texto" });
  const variaveis = Object.assign(document.createElement("div"), { className: "cfg-variaveis" });
  variaveis.dataset.alvo = `${id}-texto`;
  variaveis.append(...m.variaveis.map((v) => {
    const b = Object.assign(document.createElement("button"), { type: "button", className: "btn btn-peq", textContent: `[${v.nome}]` });
    b.dataset.acao = "cfg-variavel";
    b.dataset.variavel = v.nome;
    b.title = v.descricao;
    return b;
  }));
  const area = Object.assign(document.createElement("textarea"), { id: `${id}-texto`, rows: 5, spellcheck: true });
  area.setAttribute("aria-label", `Texto da mensagem: ${m.titulo}`);
  campo.append(variaveis, area);

  const previa = Object.assign(document.createElement("div"), { className: "cfg-previa" });
  const previaTexto = texto("p", "", "cfg-previa-texto");
  previaTexto.id = `${id}-previa`;
  previa.append(texto("span", "Como fica (com um exemplo inventado)", "cfg-previa-rotulo"), previaTexto);

  const erro = texto("p", "", "modal-erro");
  erro.id = `${id}-erro`;
  erro.setAttribute("role", "alert");
  erro.hidden = true;

  const botoes = Object.assign(document.createElement("div"), { className: "form-acoes" });
  const salvar = Object.assign(document.createElement("button"), { type: "submit", className: "btn btn-primario", textContent: "Salvar mensagem" });
  const padrao = Object.assign(document.createElement("button"), { type: "button", className: "btn", textContent: "Voltar ao padrão" });
  padrao.dataset.acao = "cfg-msg-padrao";
  padrao.dataset.tipo = m.tipo;
  botoes.append(salvar, padrao);

  form.append(campo, previa, erro, botoes);
  cartao.append(form);
  return cartao;
}

function versaoAberta(tipo) {
  const m = ajustes.mensagens.get(tipo);
  return m.dados.versoes.find((v) => v.versao === m.versao) || m.dados.versoes[0];
}

/* Põe no cartão o texto da aba aberta (o rascunho, se houver) e acerta as abas e a prévia. */
function mostrarVersao(tipo) {
  const m = ajustes.mensagens.get(tipo);
  const v = versaoAberta(tipo);
  m.versao = v.versao;
  const area = $(`#cfg-msg-${tipo}-texto`);
  const valor = m.rascunhos[v.versao] ?? v.modelo;
  if (area.value !== valor) area.value = valor;
  $(`#cfg-msg-${tipo}-form`).setAttribute("aria-labelledby", m.dados.versoes.length > 1 ? `cfg-msg-${tipo}-aba-${v.versao}` : `cfg-msg-${tipo}-titulo`);
  marcarAbas(tipo);
  mostrarPrevia(tipo);
}

function marcarAbas(tipo) {
  const m = ajustes.mensagens.get(tipo);
  for (const v of m.dados.versoes) {
    const aba = $(`#cfg-msg-${tipo}-aba-${v.versao}`);
    if (!aba) continue;
    aba.setAttribute("aria-selected", String(v.versao === m.versao));
    aba.tabIndex = v.versao === m.versao ? 0 : -1;
    const naoSalva = v.versao in m.rascunhos && m.rascunhos[v.versao] !== v.modelo;
    aba.querySelector(".cfg-aba-marca").textContent = naoSalva ? "não salva" : v.mudada ? "personalizada" : "";
  }
}

function trocarAba(tipo, versao) {
  ajustes.mensagens.get(tipo).versao = versao;
  $(`#cfg-msg-${tipo}-erro`).hidden = true;
  mostrarVersao(tipo);
}

async function mostrarPrevia(tipo) {
  const { versao } = ajustes.mensagens.get(tipo);
  const r = await api().mensagens_previa(tipo, versao, $(`#cfg-msg-${tipo}-texto`).value);
  if (r.erro || ajustes.mensagens.get(tipo).versao !== versao) return; // trocou de aba no meio
  $(`#cfg-msg-${tipo}-previa`).textContent = r.texto;
  const erro = $(`#cfg-msg-${tipo}-erro`);
  erro.hidden = !r.desconhecidas.length;
  erro.textContent = r.desconhecidas.length
    ? `Não conheço ${r.desconhecidas.map((v) => `[${v}]`).join(", ")}. Use os botões para pôr as variáveis certas.` : "";
}

function nomeDaMensagem(tipo) {
  const m = ajustes.mensagens.get(tipo);
  const v = versaoAberta(tipo);
  return v.rotulo ? `“${m.dados.titulo}” (${v.rotulo.toLowerCase()})` : `“${m.dados.titulo}”`;
}

async function salvarMensagem(tipo) {
  const m = ajustes.mensagens.get(tipo);
  const versao = m.versao;
  const r = await api().mensagens_salvar(tipo, versao, $(`#cfg-msg-${tipo}-texto`).value);
  if (r.erro) {
    $(`#cfg-msg-${tipo}-erro`).textContent = r.erro;
    $(`#cfg-msg-${tipo}-erro`).hidden = false;
    return;
  }
  delete m.rascunhos[versao];
  estado.cfg = r.config;
  aplicarModelosDeMensagem(r);
  mostrarToast(`Mensagem ${nomeDaMensagem(tipo)} salva.`);
}

async function mensagemPadrao(tipo) {
  const m = ajustes.mensagens.get(tipo);
  const r = await api().mensagens_padrao(tipo, m.versao);
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  delete m.rascunhos[m.versao];
  estado.cfg = r.config;
  aplicarModelosDeMensagem(r);
  mostrarToast(`A mensagem ${nomeDaMensagem(tipo)} voltou ao texto padrão.`);
}
