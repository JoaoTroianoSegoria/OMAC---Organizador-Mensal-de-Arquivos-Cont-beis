/* OMAC — Backup (Configurações > Backup).
 *
 * O automático é conferido ao abrir o OMAC e de hora em hora com ele aberto; o Python
 * decide se já passou a data. Falha nunca trava o app: vira aviso aqui e no Início.
 */
"use strict";

const backup = { situacao: null, restaurando: null };
const UMA_HORA = 60 * 60 * 1000;

modulos.backup = {
  ligar() {
    $("#bk-dia-mes").replaceChildren(...Array.from({ length: 28 }, (_, i) => new Option(`Dia ${i + 1}`, String(i + 1))));
    aplicarConfig();
  },
  /* A frequência mostra só o campo que vale para ela. */
  aoAplicarConfig(c) {
    $("#bk-quando").hidden = !c.backup_automatico;
    $("#bk-campo-semana").hidden = c.backup_frequencia !== "semana";
    $("#bk-campo-mes").hidden = c.backup_frequencia !== "mes";
  },
  aoIniciar() {
    // Um pouco depois de abrir, para não disputar com a primeira leitura das notas.
    setTimeout(verificarBackup, 4000);
    setInterval(verificarBackup, UMA_HORA);
  },
};

/* As Configurações não são um módulo: o que elas precisam carregar ao aparecer fica aqui. */
modulos.config = {
  aoMostrar() {
    carregarBackup();
    carregarDestinatario();
    carregarConfiguracoes(); // configuracoes.js: formato das notas e mensagens
  },
  irParaAba(grupo) {
    $(`#g-${grupo}`)?.closest("section")?.scrollIntoView({ block: "start" });
  },
};

Object.assign(acoes, {
  "bk-pasta": escolherPastaDoBackup,
  "bk-agora": fazerBackupAgora,
  "bk-restaurar": escolherBackupParaRestaurar,
  "bk-cancelar": () => $("#bk-restaurar").close(),
  "bk-confirmar": restaurarBackup,
});

function quandoFoi(iso) {
  const d = new Date(iso);
  return `${d.toLocaleDateString("pt-BR")} às ${d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`;
}

function desenharSituacaoDoBackup() {
  const s = backup.situacao;
  const el = $("#bk-situacao");
  el.classList.toggle("bk-erro", !!s.erro);
  if (s.erro) el.textContent = `A última tentativa não deu certo: ${s.erro}`;
  else if (!s.pasta) el.textContent = "Escolha a pasta onde os backups vão ficar.";
  else if (!s.ultimo) el.textContent = "Nenhum backup feito ainda.";
  else el.textContent = `Último backup: ${quandoFoi(s.ultimo)}${s.dias > 0 ? ` (há ${plural(s.dias, "dia", "dias")})` : ""}.`;
  $("#bk-agora").disabled = !s.pasta;
}

function aplicarBackup(r) {
  if (r.config) {
    estado.cfg = r.config;
    aplicarConfig();
  }
  backup.situacao = r;
  desenharSituacaoDoBackup();
}

async function carregarBackup() {
  const r = await api().backup_situacao();
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  aplicarBackup(r);
}

async function escolherPastaDoBackup() {
  const r = await api().backup_escolher_pasta();
  if (!r || r.cancelado) return;
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  aplicarBackup(r);
}

async function fazerBackupAgora() {
  const botao = $("#bk-agora");
  botao.disabled = true;
  const r = await api().backup_agora();
  botao.disabled = false;
  if (r.erro) {
    carregarBackup();
    return mostrarToast(`O backup não deu certo: ${r.erro}`, { erro: true });
  }
  aplicarBackup(r);
  const extra = r.copiados ? ` e ${plural(r.copiados, "arquivo copiado", "arquivos copiados")} das notas e extratos` : "";
  toastDeArquivo(`Backup feito${extra}.`, r.arquivo);
}

async function verificarBackup() {
  const r = await api().backup_verificar();
  if (r.erro) return;
  aplicarBackup(r);
  if (r.feito) {
    mostrarToast("Backup automático feito.");
    atualizarInicioSeAberto();
  } else if (r.falhou) {
    mostrarToast(`O backup automático não deu certo: ${r.erro}`, {
      erro: true, acoes: [["Abrir Configurações", () => irPara("config", "backup")]],
    });
    atualizarInicioSeAberto();
  }
}

/* ---------- Restaurar ---------- */

const NOMES_DOS_ARQUIVOS = {
  "config.json": "Configurações",
  "contatos.json": "Contatos",
  "tratamentos.json": "Tratamentos de orto",
  "atendimentos.json": "Atendimentos (ficha)",
  "lembretes.json": "Contas e lembretes",
  "notas-enviadas.json": "Notas já enviadas",
  "comandos.json": "Textos prontos",
  "modelos.json": "Modelos",
  "regras-extrato.json": "Regras do extrato",
};

async function escolherBackupParaRestaurar() {
  const r = await api().backup_escolher_para_restaurar();
  if (!r || r.cancelado) return;
  if (r.erro) return mostrarToast(r.erro, { erro: true });
  backup.restaurando = r;
  $("#bk-restaurar-texto").textContent = `Backup de ${r.data ? quandoFoi(r.data) : "data desconhecida"}, feito na versão ${r.versao || "?"} do OMAC. Ele tem:`;
  // Os arquivos dos modelos (modelos/…) aparecem numa linha só.
  const dados = r.arquivos.filter((n) => !n.startsWith("modelos/"));
  const qtdModelos = r.arquivos.length - dados.length;
  const linhas = dados.map((n) => texto("li", NOMES_DOS_ARQUIVOS[n] || n));
  if (qtdModelos) linhas.push(texto("li", plural(qtdModelos, "arquivo de modelo", "arquivos de modelos")));
  $("#bk-restaurar-arquivos").replaceChildren(...linhas);
  $("#bk-restaurar-erro").hidden = true;
  $("#bk-restaurar").showModal();
}

async function restaurarBackup() {
  const r = await api().backup_restaurar(backup.restaurando.caminho);
  if (r.erro) {
    $("#bk-restaurar-erro").textContent = r.erro;
    $("#bk-restaurar-erro").hidden = false;
    return;
  }
  $("#bk-restaurar").close();
  // Como reabrir o app: a tela inteira volta a ler tudo.
  try { sessionStorage.setItem("omac-restaurado", r.guardados_em); } catch { /* sem armazenamento: só não avisa */ }
  location.reload();
}

/* Depois de recarregar, diz que deu certo e onde ficaram os dados de antes. */
omacQuandoPronto(() => {
  let guardados = null;
  try {
    guardados = sessionStorage.getItem("omac-restaurado");
    sessionStorage.removeItem("omac-restaurado");
  } catch { /* nada */ }
  if (guardados) setTimeout(() => mostrarToast(`Backup restaurado. Os dados de antes ficaram em “${guardados}”.`), 1500);
});
