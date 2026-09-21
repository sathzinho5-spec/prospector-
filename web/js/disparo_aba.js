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

// "2026-09-21 15:04:37" -> "hoje 15:04" | "amanhã 09:12" | "seg 10:41".
// O horario do plano, nao uma sugestao: e a hora em que aquele lead sai.
function dspHorario(l) {
  if (!l.agendado_para) return "";
  const m = String(l.agendado_para).match(/(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})/);
  if (!m) return "";
  const dt = new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]);
  if (isNaN(dt.getTime())) return "";
  const hoje = new Date();
  // Horario que ja passou quer dizer "e o proximo da vez", nao um horario
  // futuro. Mostrar a hora vencida faria o operador achar que travou.
  if (dt <= hoje) return "sai agora";
  const dias = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];
  const amanha = new Date(hoje);
  amanha.setDate(amanha.getDate() + 1);
  let quando = dias[dt.getDay()];
  if (dt.toDateString() === hoje.toDateString()) quando = "hoje";
  else if (dt.toDateString() === amanha.toDateString()) quando = "amanhã";
  return quando + " " + m[4] + ":" + m[5];
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
    if ($("dspKpiDisparados")) $("dspKpiDisparados").textContent = k.enviados_total ?? 0;
    if ($("dspKpiBloqueados")) $("dspKpiBloqueados").textContent = k.desligados ?? 0;

    // O badge da aba na barra lateral era alimentado pela fila antiga, que saiu
    // da tela. Sem isto ele congela no ultimo valor e passa a mentir.
    const badge = $("tabQueueBadge");
    if (badge) {
      const naFila = Number(k.na_fila || 0);
      badge.textContent = naFila;
      badge.classList.toggle("hidden", naFila === 0);
    }
  } catch { /* KPI que nao carrega nao pode derrubar a aba */ }
}

// Os campos da janela nascem com o valor fixo do HTML (08:00 as 20:00). Sem
// ler o que esta salvo, recarregar a pagina e clicar em Iniciar gravava o
// valor do HTML por cima da janela escolhida, e o motor passava a seguir ela.
async function dspCarregarJanelaSalva() {
  try {
    const c = await (await fetch("/api/disparo/cadencia")).json();
    if ($("dispHoraIni") && c.hora_ini) $("dispHoraIni").value = c.hora_ini;
    if ($("dispHoraFim") && c.hora_fim) $("dispHoraFim").value = c.hora_fim;
    if ($("dispLimite") && c.limite_dia) $("dispLimite").value = c.limite_dia;
  } catch { /* sem o salvo, os campos seguem com o padrao do HTML */ }
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
  // Lead na fila mostra a HORA em que ele sai, nao o rotulo "na fila". Pedido do
  // fundador: "na fila" ele ja sabe olhando a coluna; o que ele precisa saber e
  // quando. Os outros estados seguem com o rotulo, porque ali ja aconteceu algo.
  const horario = dspHorario(l);
  const estadoDisp = (l.estado === "sem_copy" || l.estado === "copy_pronta")
    ? (l.disparo_ativo ? "<span class='hint'>—</span>"
                       : "<span class='dsp-estado bloqueado'>desligado</span>")
    : (l.estado === "na_fila" && horario
        ? "<span class='dsp-estado na-fila'>" + esc(horario) + "</span>"
        : "<span class='dsp-estado " + cls + "'>" + esc(rot) + "</span>");

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

// Os motivos que o servidor devolve em carga.fora, na lingua de quem opera.
var DSP_MOTIVO = {
  ja_abordado: "já receberam a abordagem",
  ja_na_fila: "já estavam na fila",
  // Sobra de linha de fila anterior a 18/09, quando existia lista de bloqueio.
  // O servidor ainda conta isso; rótulo que falta aqui some da mensagem calado.
  bloqueado: "com linha de fila antiga (limpe a fila)",
  desligado: "com o disparo desligado",
  sem_copy: "sem copy pronta"
};

function dspMostrarCarga(resposta) {
  const alvo = $("dspCargaInfo");
  if (!alvo) return;
  const c = (resposta || {}).carga;
  if (!c) { alvo.textContent = ""; return; }
  const fora = Object.keys(DSP_MOTIVO)
    .filter(function (k) { return (c.fora || {})[k]; })
    .map(function (k) { return c.fora[k] + " " + DSP_MOTIVO[k]; });
  let txt = c.enfileirados + " lead" + (c.enfileirados === 1 ? "" : "s") + " na fila";
  if (fora.length) txt += ". Fora: " + fora.join(", ") + ".";
  // Aviso do servidor vem junto: e onde o modo ensaio se anuncia.
  const avisos = (resposta.avisos || []).join(" ");
  alvo.textContent = avisos ? txt + " " + avisos : txt;
}

async function dspLigarSelecionados(ativo) {
  const alvos = dspTelefonesSelecionados();
  if (!alvos.length) {
    toast("Marque pelo menos um lead na lista.", "info");
    return;
  }
  // A rota trabalha por id do lead, nao por telefone: e a mesma que o CRM usa.
  const ids = dspLeads
    .filter(function (l) { return dspSelecionados[l.telefone]; })
    .map(function (l) { return l.id; })
    .filter(Boolean);
  if (!ids.length) { toast("Não achei o id desses leads.", "error"); return; }
  try {
    const r = await fetch("/api/crm/disparo-ativo", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: ids, ativo: !!ativo })
    });
    const d = await r.json();
    if (!r.ok) { toast(d.detail || "Não deu pra gravar.", "error"); return; }
    toast((d.atualizados || 0) + " lead(s) com disparo " +
          (ativo ? "ligado" : "desligado") + ".", "ok");
    await dspAtualizarTudo();
  } catch (err) {
    toast("Erro: " + err.message, "error");
  }
}

async function dspAtualizarTudo() {
  const tarefas = [dspCarregarKpis(), dspCarregarLeads(), dspCarregarCadencia()];
  // A conversao mora em outro arquivo e pode nao estar carregada: guarda em vez
  // de assumir, pelo mesmo motivo de todo o resto desta aba.
  if (typeof window.dspCarregarConversao === "function") {
    tarefas.push(window.dspCarregarConversao());
  }
  await Promise.all(tarefas);
}

function dspIniciarAba() {
  if (!$("dspTabelaBody")) return;
  if ($("dspFiltroEstado")) $("dspFiltroEstado").addEventListener("change", dspCarregarLeads);
  if ($("btnDspAtualizar")) $("btnDspAtualizar").addEventListener("click", dspAtualizarTudo);
  if ($("btnDspCriarCopy")) $("btnDspCriarCopy").addEventListener("click", dspCriarCopy);
  if ($("btnDspLigar")) {
    $("btnDspLigar").addEventListener("click", function () { dspLigarSelecionados(true); });
  }
  if ($("btnDspDesligar")) {
    $("btnDspDesligar").addEventListener("click", function () { dspLigarSelecionados(false); });
  }
  if ($("dspSelTodos")) {
    $("dspSelTodos").addEventListener("change", function () { dspMarcarTodos(this.checked); });
  }
  // A cadencia muda quando a janela ou o limite mudam, e o operador precisa ver
  // o ritmo novo antes de apertar iniciar.
  ["dispHoraIni", "dispHoraFim", "dispLimite"].forEach(function (id) {
    if ($(id)) $(id).addEventListener("change", dspCarregarCadencia);
  });
  // A janela salva entra nos campos ANTES da primeira conta do ritmo, senao o
  // "Ritmo calculado" nasce com a janela do HTML e so corrige no proximo clique.
  dspCarregarJanelaSalva().then(dspAtualizarTudo);
}

window.dspMarcar = dspMarcar;
window.dspMostrarCarga = dspMostrarCarga;
window.dspLigarSelecionados = dspLigarSelecionados;
window.dspAtualizarTudo = dspAtualizarTudo;
window.dspIniciarAba = dspIniciarAba;
