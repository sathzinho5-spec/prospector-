// proposito: aba Disparo: os KPIs, a cadencia mostrada e a lista de leads
//
// A metade de comportamento da tela que a frontend-expert entregou. O contrato
// de ids e o dela; as rotas sao as do servidor. Nenhum numero e recalculado
// aqui de proposito: o intervalo da cadencia vem pronto de /api/disparo/cadencia,
// porque conta refeita na tela e conta que passa a divergir do motor.

// O estado da tela vive num lugar so, senao o filtro e a gaveta discordam.
var dspLeads = [];
var dspSelecionados = {};

// A tela fala em classe de CSS (com hifen) e o servidor em estado (com
// sublinhado). A traducao mora aqui, nos dois sentidos, pra nenhum dos lados
// precisar conhecer o vocabulario do outro.
function dspClasseDoEstado(estado) {
  return String(estado || "").replace(/_/g, "-");
}
function dspEstadoDaClasse(classe) {
  return String(classe || "").replace(/-/g, "_");
}

var DSP_ROTULO = {
  sem_copy: "sem copy",
  copy_pronta: "copy pronta",
  na_fila: "na fila",
  enviado: "enviado",
  falha: "falha",
  respondeu: "respondeu",
  duplicado: "duplicado",
  bloqueado: "bloqueado"
};

async function dspCarregarKpis() {
  try {
    const k = await (await fetch("/api/disparo/kpis")).json();
    if ($("dspKpiNovos")) $("dspKpiNovos").textContent = k.leads_novos ?? 0;
    if ($("dspKpiEnviadas")) $("dspKpiEnviadas").textContent = k.enviadas_hoje ?? 0;
    if ($("dspKpiFila")) $("dspKpiFila").textContent = k.na_fila ?? 0;
    if ($("dspKpiConversas")) $("dspKpiConversas").textContent = k.conversas_iniciadas ?? 0;

    // O badge da aba na barra lateral era alimentado pela fila antiga, que saiu
    // da tela. Sem isto ele congela no ultimo valor e passa a mentir.
    const badge = $("tabQueueBadge");
    if (badge) {
      const naFila = Number(k.na_fila || 0);
      badge.textContent = naFila;
      badge.classList.toggle("hidden", naFila === 0);
    }

    // A conta embaixo do destaque so aparece quando ha denominador: "3 de 0
    // enviadas" nao informa nada e ainda parece defeito.
    const nota = $("dspKpiConversasNota");
    if (nota) {
      const env = Number(k.enviadas_hoje || 0);
      nota.textContent = env > 0
        ? (k.conversas_iniciadas || 0) + " de " + env + " enviadas hoje"
        : "";
    }
  } catch { /* KPI que nao carrega nao pode derrubar a aba */ }
}

async function dspCarregarCadencia() {
  const alvo = $("dspIntervalo");
  if (!alvo) return;
  try {
    const ini = $("dispHoraIni") ? $("dispHoraIni").value : "";
    const fim = $("dispHoraFim") ? $("dispHoraFim").value : "";
    const lim = $("dispLimite") ? $("dispLimite").value : "";
    const q = "?hora_ini=" + encodeURIComponent(ini) +
              "&hora_fim=" + encodeURIComponent(fim) +
              "&limite_dia=" + encodeURIComponent(lim || 0);
    const c = await (await fetch("/api/disparo/cadencia" + q)).json();
    // O CSS mostra "calculando..." enquanto o elemento esta :empty, entao
    // texto em branco apagaria o placeholder sem por valor no lugar.
    alvo.textContent = (c.resumo || "").trim();
  } catch {
    alvo.textContent = "";
  }
}

function dspLinha(l) {
  const cls = dspClasseDoEstado(l.estado);
  const rot = DSP_ROTULO[l.estado] || l.estado;
  const sua = l.editada ? "<span class='pill open'>sua</span>" : "";
  const marcada = dspSelecionados[l.telefone] ? " checked" : "";
  const classeLinha = "dsp-linha" + (l.estado === "sem_copy" ? " sem-copy" : "") +
                      (dspSelecionados[l.telefone] ? " selecionada" : "");
  const local = [l.cidade, l.uf].filter(Boolean).join("/");
  const sub = [l.categoria, local].filter(Boolean).join(" · ");

  // A coluna Copy carrega o estado de copy; a coluna Disparo carrega o que
  // aconteceu depois dela. Lead sem copy nao tem o que mostrar na segunda.
  const estadoCopy = (l.estado === "sem_copy" || l.estado === "copy_pronta")
    ? "<span class='dsp-estado " + cls + "'>" + esc(rot) + "</span>"
    : "<span class='dsp-estado copy-pronta'>copy pronta</span>";
  const estadoDisp = (l.estado === "sem_copy" || l.estado === "copy_pronta")
    ? (l.disparo_ativo ? "<span class='hint'>—</span>"
                       : "<span class='dsp-estado bloqueado'>desligado</span>")
    : "<span class='dsp-estado " + cls + "'>" + esc(rot) + "</span>";

  return "<tr class='" + classeLinha + "' data-telefone='" + esc(l.telefone) + "'>" +
    "<td class='dsp-col-check'><input type='checkbox' onchange='dspMarcar(\"" +
      esc(l.telefone) + "\", this.checked)'" + marcada + "></td>" +
    "<td class='dsp-col-lead' data-rotulo='Lead'>" +
      "<div class='dsp-lead-nome'>" + esc(l.nome || "(sem nome)") + "</div>" +
      "<div class='dsp-lead-cat'>" + esc(sub) + "</div></td>" +
    "<td class='dsp-tel' data-rotulo='Telefone'>" + esc(l.telefone) + "</td>" +
    "<td data-rotulo='Copy'><span class='dsp-celula-estado'>" + estadoCopy + sua + "</span></td>" +
    "<td data-rotulo='Disparo'>" + estadoDisp + "</td>" +
    "<td class='dsp-col-acao' data-rotulo='Acao'>" +
      "<button class='btn small' onclick='dspAbrirGaveta(\"" + esc(l.telefone) + "\")'>Ver</button>" +
    "</td></tr>";
}

async function dspCarregarLeads() {
  const corpo = $("dspTabelaBody");
  if (!corpo) return;
  const filtro = $("dspFiltroEstado") ? $("dspFiltroEstado").value : "";
  const estado = filtro ? dspEstadoDaClasse(filtro) : "";
  try {
    const r = await fetch("/api/disparo/leads?limite=500" +
                          (estado ? "&estado=" + encodeURIComponent(estado) : ""));
    const d = await r.json();
    dspLeads = d.leads || [];
    corpo.innerHTML = dspLeads.map(dspLinha).join("");

    const vazia = $("dspTabelaVazia");
    if (vazia) vazia.classList.toggle("hidden", dspLeads.length > 0);

    const info = $("dspLeadsInfo");
    if (info) {
      const t = d.totais || {};
      const sem = t.sem_copy || 0;
      info.textContent = d.total + " lead" + (d.total === 1 ? "" : "s") +
        (sem ? ", " + sem + " sem copy" : "");
    }
  } catch {
    corpo.innerHTML = "";
    if ($("dspTabelaVazia")) $("dspTabelaVazia").classList.remove("hidden");
  }
}

function dspMarcar(telefone, marcado) {
  if (marcado) dspSelecionados[telefone] = true;
  else delete dspSelecionados[telefone];
  const tr = document.querySelector(".dsp-linha[data-telefone='" + telefone + "']");
  if (tr) tr.classList.toggle("selecionada", !!marcado);
}

function dspMarcarTodos(marcado) {
  dspSelecionados = {};
  if (marcado) dspLeads.forEach(function (l) { dspSelecionados[l.telefone] = true; });
  dspCarregarLeads();
}

function dspTelefonesSelecionados() {
  return Object.keys(dspSelecionados);
}

async function dspCriarCopy() {
  const btn = $("btnDspCriarCopy");
  const alvos = dspTelefonesSelecionados();
  if (btn) { btn.disabled = true; btn.textContent = "Criando..."; }
  try {
    const r = await fetch("/api/disparo/criar-copy", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // Selecao vazia = todos os que estao sem copy, que e o contrato da rota.
      body: JSON.stringify({ telefones: alvos })
    });
    const d = await r.json();
    if (!r.ok) {
      toast(d.detail || "Nao deu pra criar a copy.", "error");
    } else {
      const n = d.criadas ?? d.total ?? 0;
      toast(n ? ("Copy criada para " + n + " lead" + (n === 1 ? "" : "s") + ".")
              : "Nenhum lead estava sem copy.", n ? "ok" : "info");
    }
  } catch (err) {
    toast("Erro ao criar copy: " + err.message, "error");
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "Criar copy"; }
    await dspAtualizarTudo();
  }
}

async function dspAtualizarTudo() {
  await Promise.all([dspCarregarKpis(), dspCarregarLeads(), dspCarregarCadencia()]);
}

function dspIniciarAba() {
  if (!$("dspTabelaBody")) return;
  if ($("dspFiltroEstado")) $("dspFiltroEstado").addEventListener("change", dspCarregarLeads);
  if ($("btnDspAtualizar")) $("btnDspAtualizar").addEventListener("click", dspAtualizarTudo);
  if ($("btnDspCriarCopy")) $("btnDspCriarCopy").addEventListener("click", dspCriarCopy);
  if ($("dspSelTodos")) {
    $("dspSelTodos").addEventListener("change", function () { dspMarcarTodos(this.checked); });
  }
  // A cadencia muda quando a janela ou o limite mudam, e o operador precisa ver
  // o ritmo novo antes de apertar iniciar.
  ["dispHoraIni", "dispHoraFim", "dispLimite"].forEach(function (id) {
    if ($(id)) $(id).addEventListener("change", dspCarregarCadencia);
  });
  dspAtualizarTudo();
}

window.dspMarcar = dspMarcar;
window.dspCriarCopy = dspCriarCopy;
window.dspAtualizarTudo = dspAtualizarTudo;
window.dspIniciarAba = dspIniciarAba;
