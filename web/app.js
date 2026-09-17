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
}

function bindEvents() {
  $("btnSearch").addEventListener("click", doSearch);
  $("btnReference").addEventListener("click", doReference);
  $("btnAnalyzeIg").addEventListener("click", function () { doInstagram(""); });
  $("btnStrategy").addEventListener("click", doStrategy);
  $("btnSettings").addEventListener("click", function () { $("modal").classList.remove("hidden"); });
  $("btnCloseModal").addEventListener("click", function () { $("modal").classList.add("hidden"); });
  $("btnCloseDetail").addEventListener("click", function () { $("detailModal").classList.add("hidden"); });
  $("btnCloseMsg").addEventListener("click", function () { $("msgModal").classList.add("hidden"); });
  $("btnSaveSettings").addEventListener("click", saveSettings);
  $("btnAllStates").addEventListener("click", function () {
    document.querySelectorAll("#stateBox input").forEach(function (cb) {
      cb.checked = true;
      cb.closest(".state-pill").classList.add("checked");
    });
    updateStateCount();
  });
  $("btnNoStates").addEventListener("click", function () {
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
  $("btnQuickSearch").addEventListener("click", doSearch);
  $("btnReloadLast").addEventListener("click", reloadLast);
  $("btnCrmRefresh").addEventListener("click", loadCrm);
  ["crmBusca", "crmUf", "crmStatus", "crmScore"].forEach(function (id) {
    const el = $(id);
    if (el) el.addEventListener(el.tagName === "INPUT" ? "input" : "change", renderCrmBoard);
  });
  $("btnPitch").addEventListener("click", doPitch);
  $("btnSequencia").addEventListener("click", doSequencia);
  $("btnProposal").addEventListener("click", doProposal);
  $("btnEnqueue").addEventListener("click", enqueueAll);
  $("btnMigrar").addEventListener("click", migrarMinerados);
  $("btnConnectWa").addEventListener("click", connectWhatsApp);
  $("btnCloseQr").addEventListener("click", function () {
    clearInterval(qrPoll);
    $("qrModal").classList.add("hidden");
  });
  $("btnStartDisp").addEventListener("click", startDisp);
  $("btnPauseDisp").addEventListener("click", pauseDisp);
  $("btnTestDisp").addEventListener("click", testDisp);
  $("btnClearDisp").addEventListener("click", clearDisp);
  $("btnWaRefresh").addEventListener("click", loadWaChats);
  $("btnWaSend").addEventListener("click", sendWaReply);
  $("waSearch").addEventListener("input", renderWaChats);
  $("waInput").addEventListener("keydown", function (ev) {
    if (ev.key === "Enter") sendWaReply();
  });
  document.querySelectorAll("#modoSeg .seg-btn").forEach(function (b) {
    b.addEventListener("click", function () { setModo(b.dataset.modo); });
  });
  $("btnAnalyzeAll").addEventListener("click", analyzeAll);
  $("provider").addEventListener("change", function () {
    const p = PROVIDERS[this.value];
    if (p) {
      $("baseUrl").value = p.url;
      $("model").value = p.model;
    }
  });
  $("fSite").addEventListener("change", function () { filters.site = this.value; renderResults(bizCache); });
  $("fNota").addEventListener("change", function () { filters.nota = parseFloat(this.value) || 0; renderResults(bizCache); });
  $("fReviews").addEventListener("input", function () { filters.reviews = parseInt(this.value, 10) || 0; renderResults(bizCache); });
  $("fSort").addEventListener("change", function () { filters.sort = this.value; renderResults(bizCache); });
  document.querySelectorAll("[data-export]").forEach(function (b) {
    b.addEventListener("click", function () { exportData(b.dataset.export); });
  });
  document.querySelectorAll(".modal-overlay").forEach(function (ov) {
    ov.addEventListener("click", function (ev) { if (ev.target === ov) ov.classList.add("hidden"); });
  });
}

window.switchTab = function (name) {
  ["home", "results", "crm", "comercial", "conversas"].forEach(function (t) {
    const sec = $("sec" + t.charAt(0).toUpperCase() + t.slice(1));
    if (sec) sec.classList.toggle("hidden", t !== name);
  });
  document.querySelectorAll(".tabbtn").forEach(function (tb) {
    tb.classList.toggle("active", tb.dataset.tab === name);
  });
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