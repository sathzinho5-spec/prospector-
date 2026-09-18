// proposito: arranque do painel, ligacao de eventos e navegacao entre abas
const PROVIDERS = {
  groq: { url: "https://api.groq.com/openai/v1", model: "groq/compound" },
  gemini: { url: "https://generativelanguage.googleapis.com/v1beta/openai", model: "gemini-2.0-flash" },
  openai: { url: "https://api.openai.com/v1", model: "gpt-4o-mini" }
};

async function init() {
  document.querySelector(".content").classList.add("empty");
  await loadNiches();
  await loadSettings();
  bindEvents();
  renderQuickNiches();
  renderQuickStates();
  loadLastSearch();
  loadDashboard();
  // A aba Disparo liga por ultimo e com guarda: ela e a unica que fala com
  // rotas que podem nao existir numa versao mais velha do servidor, e uma
  // falha aqui nao pode derrubar o arranque do painel inteiro.
  try {
    if (typeof dspIniciarAba === "function") dspIniciarAba();
    if (typeof dspIniciarGaveta === "function") dspIniciarGaveta();
  } catch (err) {
    console.error("Aba Disparo nao iniciou", err);
  }
}

function on(id, ev, fn) {
  const el = document.getElementById(id);
  if (el) el.addEventListener(ev, fn);
}

function bindEvents() {
  on("btnSearch", "click", doSearch);
  on("btnReference", "click", doReference);
  on("btnAnalyzeIg", "click", function () { doInstagram(""); });
  on("btnStrategy", "click", doStrategy);
  on("btnSettings", "click", function () { $("modal").classList.remove("hidden"); });
  on("btnCloseModal", "click", function () { $("modal").classList.add("hidden"); });
  on("btnCloseDetail", "click", function () { $("detailModal").classList.add("hidden"); });
  on("btnCloseMsg", "click", function () { $("msgModal").classList.add("hidden"); });
  on("btnSaveSettings", "click", saveSettings);
  on("btnAllStates", "click", function () {
    document.querySelectorAll("#stateBox input").forEach(function (cb) {
      cb.checked = true;
      cb.closest(".state-pill").classList.add("checked");
    });
    updateStateCount();
  });
  on("btnNoStates", "click", function () {
    document.querySelectorAll("#stateBox input").forEach(function (cb) {
      cb.checked = false;
      cb.closest(".state-pill").classList.remove("checked");
    });
    updateStateCount();
    document.querySelectorAll("#quickStates .quick-chip").forEach(function (c) { c.classList.remove("active"); });
  });
  document.querySelectorAll(".tabbtn").forEach(function (tb) {
    tb.addEventListener("click", function () { switchTab(tb.dataset.tab); });
  });
  document.querySelectorAll("#analyzeTabs .subtab").forEach(function (st) {
    st.addEventListener("click", function () { showOut(st.dataset.out); });
  });
  on("btnQuickSearch", "click", doSearch);
  on("btnReloadLast", "click", reloadLast);
  on("btnCrmRefresh", "click", loadCrm);
  ["crmBusca", "crmUf", "crmStatus", "crmScore"].forEach(function (id) {
    const el = $(id);
    if (el) el.addEventListener(el.tagName === "INPUT" ? "input" : "change", renderCrmBoard);
  });
  on("btnPitch", "click", doPitch);
  on("btnSequencia", "click", doSequencia);
  on("btnProposal", "click", doProposal);
  on("btnEnqueue", "click", enqueueAll);
  on("btnMigrar", "click", migrarMinerados);
  on("btnConnectWa", "click", connectWhatsApp);
  on("btnCloseQr", "click", function () {
    clearInterval(qrPoll);
    $("qrModal").classList.add("hidden");
  });
  on("btnStartDisp", "click", startDisp);
  on("btnPauseDisp", "click", pauseDisp);
  on("btnTestDisp", "click", testDisp);
  on("btnClearDisp", "click", clearDisp);
  on("btnWaRefresh", "click", loadWaChats);
  on("btnWaSend", "click", sendWaReply);
  on("waSearch", "input", renderWaChats);
  on("btnAnalyzeAll", "click", analyzeAll);
  on("btnIgSites", "click", extractIgFromSites);
  on("waInput", "keydown", function (ev) {
    if (ev.key === "Enter") sendWaReply();
  });
  on("provider", "change", function () {
    const p = PROVIDERS[this.value];
    if (p) {
      $("baseUrl").value = p.url;
      $("model").value = p.model;
    }
  });
  on("fSite", "change", function () { filters.site = this.value; renderResults(bizCache); });
  on("fNota", "change", function () { filters.nota = parseFloat(this.value) || 0; renderResults(bizCache); });
  on("fReviews", "input", function () { filters.reviews = parseInt(this.value, 10) || 0; renderResults(bizCache); });
  on("fSort", "change", function () { filters.sort = this.value; renderResults(bizCache); });
  on("fBusca", "input", function () { filters.texto = this.value; renderResults(bizCache); });
  on("perPage", "change", function () { tableState.perPage = parseInt(this.value, 10) || 25; tableState.page = 1; renderResults(bizCache); });
  on("selAll", "change", function () { toggleSelectAll(this.checked); });
  on("btnBulkAnalyze", "click", bulkAnalyze);
  on("btnBulkEnqueue", "click", bulkEnqueue);
  on("btnBulkExport", "click", bulkExportCsv);
  on("btnBulkClear", "click", clearSelection);
  on("btnLeadsRefresh", "click", function () { loadLeadsView(1); });
  on("btnAprRecalc", "click", recalcAprendizado);
  on("leadSearch", "input", function () { leadsState.q = this.value; loadLeadsView(1); });
  on("leadUf", "change", function () { leadsState.uf = this.value; loadLeadsView(1); });
  on("btnMenu", "click", function () {
    $("sidebar").classList.toggle("open");
    $("backdrop").classList.toggle("hidden");
  });
  on("backdrop", "click", function () {
    $("sidebar").classList.remove("open");
    $("backdrop").classList.add("hidden");
  });
  document.querySelectorAll("[data-export]").forEach(function (b) {
    b.addEventListener("click", function () { exportData(b.dataset.export); });
  });
  document.querySelectorAll(".modal-overlay").forEach(function (ov) {
    ov.addEventListener("click", function (ev) { if (ev.target === ov) ov.classList.add("hidden"); });
  });
}

var TAB_TITLES = {
  home: "Dashboard",
  results: "Prospecção",
  leads: "Leads",
  crm: "Pipeline",
  comercial: "Disparo",
  conversas: "Conversas",
  conexao: "Conexão do número",
  metricas: "Métricas"
};

window.switchTab = function (name) {
  ["home", "results", "leads", "crm", "comercial", "conversas", "conexao", "metricas"].forEach(function (t) {
    const sec = $("sec" + t.charAt(0).toUpperCase() + t.slice(1));
    if (sec) sec.classList.toggle("hidden", t !== name);
  });
  document.querySelectorAll(".tabbtn").forEach(function (tb) {
    tb.classList.toggle("active", tb.dataset.tab === name);
  });
  if (TAB_TITLES[name]) $("queryTitle").textContent = TAB_TITLES[name];
  $("sidebar").classList.remove("open");
  $("backdrop").classList.add("hidden");
  if (name === "home") {
    $("emptyCard").classList.remove("hidden");
    $("homeExtra").classList.remove("hidden");
    document.querySelector(".content").classList.add("empty");
  } else {
    document.querySelector(".content").classList.remove("empty");
  }
  if (name === "comercial") {
    renderQueue();
    renderPerformance();
    refreshDisparo();
  }
  if (name === "crm") {
    loadCrm();
  }
  if (name === "conversas") {
    loadWaChats();
  }
  if (name === "leads") {
    loadLeadsView(1);
  }
  if (name === "metricas") {
    renderPerformance();
    renderAprendizado();
  }
  if (name === "home") {
    loadDashboard();
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
};

window.showOut = function (id) {
  ["strategyOutput", "sdrOutput", "pitchOutput", "proposalOutput", "refOutput", "igOutput"].forEach(function (oid) {
    $(oid).classList.add("hidden");
  });
  const el = $(id);
  if (el) {
    el.classList.remove("hidden");
    el.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
  document.querySelectorAll("#analyzeTabs .subtab").forEach(function (st) {
    st.classList.toggle("active", st.dataset.out === id);
  });
  const tabs = $("analyzeTabs");
  if (tabs) tabs.classList.remove("hidden");
};

init();