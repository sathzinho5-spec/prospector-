const $ = (id) => document.getElementById(id);

let lastBusiness = null;
let lastHandle = null;
let bizCache = [];
let loaderInterval = null;
let filters = { site: "all", nota: 0, reviews: 0, sort: "default" };

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
  });
}

function showStatus(id, msg, type) {
  const el = $(id);
  if (!el) return;
  el.textContent = msg;
  el.className = "status " + (type || "info");
}

function clearStatus(id) {
  const el = $(id);
  if (el) el.classList.add("hidden");
}

function showLoader(text) {
  $("loaderText").textContent = text || "Trabalhando...";
  $("loader").classList.remove("hidden");
  const t0 = Date.now();
  clearInterval(loaderInterval);
  loaderInterval = setInterval(function () {
    const secs = Math.floor((Date.now() - t0) / 1000);
    const el = $("loaderTimer");
    if (el) el.textContent = secs >= 60
      ? Math.floor(secs / 60) + " min " + (secs % 60) + "s decorridos"
      : secs + "s decorridos";
  }, 1000);
}

function hideLoader() {
  clearInterval(loaderInterval);
  $("loader").classList.add("hidden");
}

function initials(name) {
  const parts = String(name || "?").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

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

// ===== URGÊNCIA =====
function computeUrgency(b) {
  const nota = parseFloat(String(b.nota || "0").replace(",", "."));
  const av = parseInt(String(b.avaliacoes || "0").replace(/[.,]/g, ""), 10) || 0;

  if (nota > 0 && nota < 4.2 && av >= 15) {
    return { nivel: "alta", motivo: "Nota " + String(b.nota).replace(".", ",") + " com " + av + " avaliações — problema visível ao público" };
  }
  if (!b.website && av >= 30) {
    return { nivel: "media", motivo: av + " avaliações e nenhum site — perdendo clientes agora" };
  }
  if (nota >= 4.0 && nota < 4.6 && !b.website) {
    return { nivel: "media", motivo: "Boa reputação sem site para converter" };
  }
  return { nivel: "baixa", motivo: "Sem sinal urgente" };
}

function urgencyPill(b) {
  const u = b._urg || computeUrgency(b);
  b._urg = u;
  if (u.nivel === "alta") return "<span class='pill urgent' title='" + esc(u.motivo) + "'>URGENTE</span>";
  return "";
}

// ===== CONTATADOS (localStorage) =====
function getContacted() {
  try { return JSON.parse(localStorage.getItem("pp_contacted") || "[]"); } catch (e) { return []; }
}

function isContacted(name) { return getContacted().indexOf(name) !== -1; }

function toggleContacted(name) {
  const arr = getContacted();
  const idx = arr.indexOf(name);
  if (idx === -1) arr.push(name); else arr.splice(idx, 1);
  localStorage.setItem("pp_contacted", JSON.stringify(arr));
}

function waPhone(b) {
  let d = String(b.telefone || "").replace(/\D/g, "");
  if (d.length >= 10 && d.length <= 11 && !d.startsWith("55")) d = "55" + d;
  return d.length >= 12 ? d : "";
}

async function generatePitchFor(b) {
  if (b._pitch) return b._pitch;
  const r = await fetch("/api/business/pitch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ business: b })
  });
  const d = await r.json();
  if (!r.ok) throw new Error(d.detail || "Erro");
  b._pitch = d;
  return d;
}

window.openWhatsApp = async function (i) {
  const b = bizCache[i];
  if (!b) return;
  const phone = waPhone(b);
  if (!phone) {
    showStatus("searchStatus", "Este lead não tem telefone válido para WhatsApp.", "error");
    return;
  }
  showLoader("Gerando mensagem personalizada...");
  try {
    const d = await generatePitchFor(b);
    hideLoader();
    const url = "https://wa.me/" + phone + "?text=" + encodeURIComponent(d.whatsapp);
    window.open(url, "_blank");
    if (!isContacted(b.nome)) {
      toggleContacted(b.nome);
      renderResults(bizCache);
      renderQueue();
    }
  } catch (e) {
    hideLoader();
    showStatus("searchStatus", "Falha: " + e.message, "error");
  }
};

// ===== FILA DE CONTATO =====
window.renderQueue = function () {
  const list = $("queueList");
  if (!list) return;
  const arr = bizCache.slice().sort(function (a, b) {
    const ca = isContacted(a.nome) ? 1 : 0;
    const cb = isContacted(b.nome) ? 1 : 0;
    if (ca !== cb) return ca - cb;
    const ua = a._urg ? (a._urg.nivel === "alta" ? 0 : 1) : 2;
    const ub = b._urg ? (b._urg.nivel === "alta" ? 0 : 1) : 2;
    if (ua !== ub) return ua - ub;
    return (b.score_oportunidade || -1) - (a.score_oportunidade || -1);
  });

  const pend = arr.filter(function (b) { return !isContacted(b.nome); }).length;
  $("queueStats").textContent = pend + " pendentes · " + (arr.length - pend) + " contatados";
  const qb = $("tabQueueBadge");
  if (qb) {
    qb.textContent = pend;
    qb.classList.toggle("hidden", !pend);
  }

  if (!arr.length) {
    list.innerHTML = "<p class='hint'>Nenhum lead carregado. Faça uma busca primeiro.</p>";
    return;
  }

  list.innerHTML = arr.map(function (b) {
    const i = bizCache.indexOf(b);
    const cont = isContacted(b.nome);
    const phone = waPhone(b);
    const u = b._urg || computeUrgency(b);
    return (
      "<div class='queue-item " + (cont ? "done" : "") + "'>" +
      "<div class='queue-info'>" +
      "<div class='biz-name'><span>" + esc(b.nome) + "</span>" + urgencyPill(b) + scorePill(b) + "</div>" +
      "<div class='biz-sub2'>" + esc(u.motivo) + "</div>" +
      "</div>" +
      "<div class='biz-actions'>" +
      (phone
        ? "<button class='btn small wa' onclick='openWhatsApp(" + i + ")'>" + (cont ? "Reabrir WA" : "Abrir WhatsApp") + "</button>"
        : "<span class='mini-tag'>sem telefone</span>") +
      "<button class='btn small " + (cont ? "" : "primary") + "' onclick='event.stopPropagation();toggleAndRender(" + i + ")'>" + (cont ? "Reabrir" : "Marcar contatado") + "</button>" +
      "</div>" +
      "</div>"
    );
  }).join("");
};

window.toggleAndRender = function (i) {
  const b = bizCache[i];
  if (!b) return;
  toggleContacted(b.nome);
  renderResults(bizCache);
  renderQueue();
};

const POPULAR_NICHES = ["restaurantes", "academias", "barbearias", "cafeterias", "pizzarias", "beleza", "petshop", "odontologia"];
const POPULAR_STATES = ["São Paulo", "Rio de Janeiro", "Minas Gerais", "Espírito Santo", "Paraná", "Bahia"];

function renderQuickNiches() {
  const box = $("quickNiches");
  if (!box) return;
  box.innerHTML = POPULAR_NICHES
    .filter(function (id) {
      return Array.prototype.some.call($("niche").options, function (o) { return o.value === id; });
    })
    .map(function (id) {
      const label = Array.prototype.find.call($("niche").options, function (o) { return o.value === id; }).text;
      return '<span class="quick-chip" data-niche="' + esc(id) + '">' + esc(label) + "</span>";
    })
    .join("");
  box.addEventListener("click", function (ev) {
    const chip = ev.target.closest(".quick-chip");
    if (!chip) return;
    $("niche").value = chip.dataset.niche;
    box.querySelectorAll(".quick-chip").forEach(function (c) { c.classList.remove("active"); });
    chip.classList.add("active");
  });
}

function renderQuickStates() {
  const box = $("quickStates");
  if (!box) return;
  box.innerHTML = POPULAR_STATES
    .map(function (nome) { return '<span class="quick-chip" data-state="' + esc(nome) + '">' + esc(nome) + "</span>"; })
    .join("");
  box.addEventListener("click", function (ev) {
    const chip = ev.target.closest(".quick-chip");
    if (!chip) return;
    toggleState(chip.dataset.state, chip);
  });
}

function toggleState(nome, chipEl) {
  const cb = document.querySelector('#stateBox input[value="' + nome.replace(/"/g, '\\"') + '"]');
  if (!cb) return;
  cb.checked = !cb.checked;
  cb.closest(".state-pill").classList.toggle("checked", cb.checked);
  if (chipEl) chipEl.classList.toggle("active", cb.checked);
  updateStateCount();
}

async function loadLastSearch() {
  try {
    const r = await fetch("/api/results");
    const d = await r.json();
    const info = $("lastSearchInfo");
    if (d.businesses && d.businesses.length) {
      info.innerHTML = "<b style='color:#fff'>" + d.businesses.length + " negócios</b> da última busca:<br>" + esc(d.last_search);
      $("btnReloadLast").classList.remove("hidden");
    } else {
      info.textContent = "Nenhuma busca nesta sessão ainda.";
    }

    const s = await (await fetch("/api/settings")).json();
    $("sysStatus").innerHTML =
      "IA: " + (s.openai_api_key ? "<span style='color:var(--green)'>conectada (" + esc(s.openai_model) + ")</span>" : "<span style='color:#ff9aa5'>modo local</span>") +
      "<br>Instagram: " + (s.instagram_sessionid ? "<span style='color:var(--green)'>sessão ativa</span>" : "<span style='color:#ff9aa5'>sem sessão</span>") +
      "<br>Estados disponíveis: 27 · Nichos: " + $("niche").options.length;

    await loadScheduleStatus();
    setInterval(loadScheduleStatus, 60000);
  } catch (e) {
    console.error(e);
  }
}

async function loadScheduleStatus() {
  try {
    const r = await fetch("/api/schedule");
    const s = await r.json();
    const el = $("schedAlert");
    if (!el) return;
    if (s.enabled && s.new_count > 0) {
      el.innerHTML = "<span style='color:var(--green)'>● Busca automática ativa (" + esc(s.time) + ")</span>" +
        " — <b style='color:#fff'>" + s.new_count + " novos leads</b> de " + s.total_count + " na última rodada (" + esc(s.last_run) + ")." +
        " <a class='link' href='#' onclick='loadScheduleResults(); return false;'>Ver novos leads</a>";
    } else if (s.enabled) {
      el.innerHTML = "<span style='color:var(--green)'>● Busca automática ativa (" + esc(s.time) + ")</span> — aguardando próxima rodada.";
    } else {
      el.innerHTML = "Busca automática: <span style='color:#ff9aa5'>desativada</span> (ative nas Configurações).";
    }
  } catch (e) { /* silencioso */ }
}

async function loadScheduleResults() {
  showLoader("Carregando leads da busca agendada...");
  try {
    const r = await fetch("/api/schedule/results");
    const d = await r.json();
    hideLoader();
    if (!r.ok) throw new Error(d.detail || "Nada encontrado");
    $("emptyCard").classList.add("hidden");
    $("homeExtra").classList.add("hidden");
    document.querySelector(".content").classList.remove("empty");
    $("queryTitle").textContent = "Leads novos (agendada)";
    $("exportGroup").classList.remove("hidden");
    switchTab("results");
    renderResults(d.novos.length ? d.novos : d.total ? d.novos : []);
    showStatus("searchStatus", d.novos.length + " leads novos encontrados pela busca agendada!", "ok");
  } catch (e) {
    hideLoader();
    showStatus("searchStatus", e.message, "error");
  }
}

async function loadNiches() {
  try {
    const r = await fetch("/api/niches");
    const data = await r.json();
    $("niche").innerHTML = data.nichos
      .map(function (n) { return '<option value="' + esc(n.id) + '">' + esc(n.label) + "</option>"; })
      .join("");

    $("stateBox").innerHTML = data.estados
      .map(function (e) {
        return (
          '<label class="state-pill">' +
          '<input type="checkbox" value="' + esc(e.nome) + '" data-uf="' + esc(e.uf) + '">' +
          "<span>" + esc(e.uf) + "</span></label>"
        );
      })
      .join("");
    $("stateBox").addEventListener("change", function (ev) {
      if (ev.target && ev.target.tagName === "INPUT") {
        ev.target.closest(".state-pill").classList.toggle("checked", ev.target.checked);
        updateStateCount();
      }
    });

    $("schedNiche").innerHTML = data.nichos
      .map(function (n) { return '<option value="' + esc(n.id) + '">' + esc(n.label) + "</option>"; })
      .join("");
  } catch (e) {
    console.error("Erro ao carregar nichos", e);
  }
}

function selectedStates() {
  return Array.prototype.slice.call(
    document.querySelectorAll("#stateBox input:checked")
  ).map(function (cb) { return cb.value; });
}

function updateStateCount() {
  $("stateCount").textContent = selectedStates().length + " selecionados";
}

async function loadSettings() {
  try {
    const r = await fetch("/api/settings");
    const s = await r.json();
    $("baseUrl").value = s.openai_base_url || "";
    $("model").value = s.openai_model || "";
    $("apiKey").placeholder = s.openai_api_key ? "Chave configurada" : "sk-... / gsk-... (opcional)";
    $("igSession").placeholder = s.instagram_sessionid ? "Cookie configurado" : "Opcional - sessionid";

    $("schedEnabled").checked = !!s.schedule_enabled;
    $("schedTime").value = s.schedule_time || "08:00";
    $("schedNiche").value = s.schedule_niche || "restaurantes";
    $("schedStates").value = (s.schedule_states || []).join(", ");

    const iaChip = $("iaChip");
    if (s.openai_api_key) {
      iaChip.classList.add("on"); iaChip.classList.remove("off");
      const providerName = String(s.openai_base_url || "").includes("gemini") ? "Gemini"
        : String(s.openai_base_url || "").includes("groq") ? "Groq" : "OpenAI";
      $("iaChipText").textContent = "IA: " + providerName;
    } else {
      iaChip.classList.add("off");
      $("iaChipText").textContent = "IA local";
    }

    const igWrap = $("igChipWrap");
    if (s.instagram_sessionid) {
      igWrap.classList.add("on"); igWrap.classList.remove("off");
      $("igChipText").textContent = "Instagram: sessão ativa";
    } else {
      igWrap.classList.add("off"); igWrap.classList.remove("on");
      $("igChipText").textContent = "Instagram: sem sessão";
    }
  } catch (e) {
    console.error("Erro ao carregar configurações", e);
  }
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

async function reloadLast() {
  showLoader("Recarregando última busca...");
  try {
    const r = await fetch("/api/results");
    const d = await r.json();
    hideLoader();
    if (!d.businesses || !d.businesses.length) throw new Error("Nenhum resultado salvo");
    $("emptyCard").classList.add("hidden");
    $("homeExtra").classList.add("hidden");
    document.querySelector(".content").classList.remove("empty");
    $("queryTitle").textContent = d.last_search || "Resultados";
    $("exportGroup").classList.remove("hidden");
    switchTab("results");
    renderResults(d.businesses);
  } catch (e) {
    hideLoader();
    showStatus("searchStatus", e.message, "error");
  }
}

async function doSearch() {
  const locations = selectedStates();
  const bairro = $("bairro").value.trim();

  let finalLocations = locations;
  if (bairro && locations.length) {
    finalLocations = locations.map(function (nome) { return bairro + ", " + nome; });
  }

  const payload = {
    query: $("customQuery").value.trim() || $("niche").value,
    locations: finalLocations,
    max_results: parseInt($("maxResults").value, 10) || 10,
    apenas_novos: $("onlyNew").checked
  };
  if (!payload.query) return;
  if (!finalLocations.length) {
    showStatus("searchStatus", "Selecione pelo menos um estado.", "error");
    return;
  }

  showLoader("Buscando em " + finalLocations.length + " estado(s)...");
  clearStatus("searchStatus");
  try {
    const r = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || "Erro na busca");
    hideLoader();

    let msg = data.total + " negócios novos encontrados.";
    if (data.por_local) {
      msg += " " + Object.keys(data.por_local).map(function (k) { return k.split(",")[0] + ": " + data.por_local[k]; }).join(" | ");
    }
    if (data.repetidos_ocultos > 0) {
      msg += " " + data.repetidos_ocultos + " repetidos foram ocultados (já coletados antes).";
    }
    showStatus("searchStatus", msg, "ok");

    $("emptyCard").classList.add("hidden");
    $("homeExtra").classList.add("hidden");
    document.querySelector(".content").classList.remove("empty");
    $("queryTitle").textContent = data.query.charAt(0).toUpperCase() + data.query.slice(1);
    $("exportGroup").classList.remove("hidden");
    switchTab("results");
    renderResults(data.businesses);
  } catch (e) {
    hideLoader();
    showStatus("searchStatus", "Falha: " + e.message, "error");
  }
}

function avatarHtml(b) {
  if (b.foto) {
    return "<div class='avatar'><img src='" + esc(b.foto) + "' loading='lazy' alt='' onerror=\"this.parentNode.innerHTML='" + esc(initials(b.nome)) + "'\"></div>";
  }
  return "<div class='avatar'>" + esc(initials(b.nome)) + "</div>";
}

function statusPill(b) {
  const s = b.status_funcionamento || "";
  if (/^aberto/i.test(s)) return "<span class='pill open'>Aberto</span>";
  if (/^fechado/i.test(s)) return "<span class='pill closed'>Fechado</span>";
  return "";
}

function filteredBusinesses() {
  let arr = bizCache.slice();
  if (filters.site === "com") arr = arr.filter(function (b) { return b.website; });
  if (filters.site === "sem") arr = arr.filter(function (b) { return !b.website; });
  if (filters.nota > 0) {
    arr = arr.filter(function (b) {
      return parseFloat(String(b.nota || "0").replace(",", ".")) >= filters.nota;
    });
  }
  if (filters.reviews > 0) {
    arr = arr.filter(function (b) {
      return parseInt(String(b.avaliacoes || "0").replace(/[.,]/g, ""), 10) >= filters.reviews;
    });
  }
  if (filters.sort === "score") {
    arr.sort(function (a, b) { return (b.score_oportunidade || -1) - (a.score_oportunidade || -1); });
  } else if (filters.sort === "urgencia") {
    arr.sort(function (a, b) {
      const ua = computeUrgency(a).nivel === "alta" ? 0 : 1;
      const ub = computeUrgency(b).nivel === "alta" ? 0 : 1;
      if (ua !== ub) return ua - ub;
      return (b.score_oportunidade || -1) - (a.score_oportunidade || -1);
    });
  } else if (filters.sort === "nota") {
    arr.sort(function (a, b) {
      return parseFloat(String(b.nota || "0").replace(",", ".")) - parseFloat(String(a.nota || "0").replace(",", "."));
    });
  } else if (filters.sort === "avaliacoes") {
    arr.sort(function (a, b) {
      return parseInt(String(b.avaliacoes || "0").replace(/[.,]/g, ""), 10) - parseInt(String(a.avaliacoes || "0").replace(/[.,]/g, ""), 10);
    });
  }
  return arr;
}

function scorePill(b) {
  if (b.score_oportunidade == null) return "";
  const s = b.score_oportunidade;
  const cls = s >= 70 ? "high" : (s < 45 ? "low" : "med");
  return "<span class='pill " + cls + "'>IA " + s + "%</span>";
}

function renderResults(businesses) {
  bizCache = businesses;
  const tb = $("tabResultsBadge");
  if (tb) {
    tb.textContent = businesses.length;
    tb.classList.toggle("hidden", !businesses.length);
  }

  const arr = filteredBusinesses();
  $("filterInfo").textContent = arr.length + " de " + bizCache.length + " exibidos";

  const list = $("resultsList");
  list.innerHTML = arr
    .map(function (b) {
      const i = bizCache.indexOf(b);
      const subParts = [b.categoria, [b.cidade, b.estado].filter(Boolean).join(" - ")]
        .filter(Boolean).join(" · ");
      let meta = "";
      meta += urgencyPill(b);
      meta += scorePill(b);
      if (isContacted(b.nome)) meta += "<span class='pill done-pill'>Contatado</span>";
      meta += statusPill(b);
      if (b.telefone) meta += "<span class='mini-tag'>" + esc(b.telefone) + "</span>";
      if (b.website) meta += "<span class='mini-tag'>site</span>";
      if (b.preco) meta += "<span class='mini-tag'>" + esc(b.preco) + "</span>";

      return (
        "<div class='biz-row' id='bizRow" + i + "' style='animation-delay:" + (i * 45) + "ms' onclick='showDetails(" + i + ")'>" +
        avatarHtml(b) +
        "<div class='biz-main'>" +
        "<div class='biz-name'><span style='overflow:hidden;text-overflow:ellipsis;'>" + esc(b.nome) + "</span>" +
        (b.nota ? "<span class='star-chip'>&#9733; " + esc(b.nota) + "</span>" : "") +
        "</div>" +
        "<div class='biz-sub2'>" + esc(subParts) +
        (b.avaliacoes ? " · " + esc(b.avaliacoes) + " avaliações" : "") + "</div>" +
        "<div class='biz-meta'>" + meta + "</div>" +
        "</div>" +
        "<div class='biz-actions'>" +
        (waPhone(b) ? "<button class='btn small wa' onclick='event.stopPropagation();openWhatsApp(" + i + ")'>WhatsApp</button>" : "") +
        "<button class='btn small primary' onclick='event.stopPropagation();selectBusiness(" + i + ", false);doStrategy()'>Estratégia</button>" +
        "<button class='btn small' onclick='event.stopPropagation();selectBusiness(" + i + ", true)'>Instagram</button>" +
        "</div>" +
        "</div>"
      );
    })
    .join("");
}

async function analyzeAll() {
  if (!bizCache.length) return;
  const total = bizCache.length;
  const CHUNK = 5;
  showLoader("Analisando 0/" + total + " leads com IA...");
  let done = 0;
  try {
    for (let i = 0; i < total; i += CHUNK) {
      const chunk = bizCache.slice(i, i + CHUNK);
      const r = await fetch("/api/business/strategy_batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ businesses: chunk })
      });
      const d = await r.json();
      if (r.ok && d.results) {
        d.results.forEach(function (res, j) {
          const b = bizCache[i + j];
          if (b && res) {
            b.score_oportunidade = res.score;
            b.nivel_ia = res.nivel;
            b.estrategia_resumo = res.resumo;
            b.oportunidades_ia = res.oportunidades;
            b.strategy_engine = res.engine;
          }
        });
      }
      done += chunk.length;
      $("loaderText").textContent = "Analisando " + done + "/" + total + " leads com IA...";
    }
    hideLoader();
    filters.sort = "score";
    $("fSort").value = "score";
    renderResults(bizCache);
    showStatus("searchStatus", total + " leads pontuados pela IA e ordenados por oportunidade!", "ok");
  } catch (e) {
    hideLoader();
    showStatus("searchStatus", "Falha na análise em lote: " + e.message, "error");
  }
}

async function doPitch() {
  if (!lastBusiness) return;
  showLoader("Gerando mensagem de abordagem com IA...");
  try {
    const r = await fetch("/api/business/pitch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ business: lastBusiness })
    });
    const d = await r.json();
    hideLoader();
    if (!r.ok) throw new Error(d.detail || "Erro");

    const out = $("pitchOutput");
    out.className = "panel";
    let html = "<h3>Mensagem de abordagem — " + esc(lastBusiness.nome) + "</h3>";
    html += "<span class='tag'>" + (d.engine === "local" ? "IA local" : esc(d.engine)) + "</span>";

    html += "<h4>WhatsApp (copie e cole)</h4>";
    html += "<div class='pitch-box'>" + esc(d.whatsapp) + "</div>";
    html += "<button class='btn small primary' onclick=\"copyText(this, 'wa')\">Copiar WhatsApp</button>";

    html += "<h4>E-mail</h4>";
    html += "<div class='pitch-box'><b>Assunto:</b> " + esc(d.email_assunto) + "</div>";
    html += "<div class='pitch-box' style='margin-top:8px;white-space:pre-wrap;'>" + esc(d.email_corpo) + "</div>";
    html += "<button class='btn small primary' onclick=\"copyText(this, 'email')\">Copiar e-mail</button>";

    html += "<h4 style='margin-top:20px;'>Treinador de objeções</h4>";
    html += "<p class='hint'>O cliente respondeu algo? Escreva a objeção e a IA monta a resposta:</p>";
    html += "<div class='btn-row' style='margin:10px 0;'><input id='objectionInput' placeholder='Ex: tá caro, já tenho agência, sem tempo...' style='flex:1;min-width:220px;'>";
    html += "<button class='btn primary' id='btnObjection'>Responder</button></div>";
    html += "<div id='objectionOut'></div>";

    out.innerHTML = html;
    out.dataset.wa = d.whatsapp;
    out.dataset.email = "Assunto: " + d.email_assunto + "\n\n" + d.email_corpo;
    $("btnObjection").addEventListener("click", doObjection);
    showOut("pitchOutput");
  } catch (e) {
    hideLoader();
    showStatus("searchStatus", "Falha ao gerar mensagem: " + e.message, "error");
  }
}

window.copyText = function (btn, which) {
  const out = $("pitchOutput");
  const text = which === "wa" ? out.dataset.wa : out.dataset.email;
  copyToClipboard(btn, text);
};

window.copySeq = function (btn, key) {
  const out = $("sdrOutput");
  copyToClipboard(btn, out.dataset[key] || "");
};

function copyToClipboard(btn, text) {
  if (!text) return;
  navigator.clipboard.writeText(text).then(function () {
    const old = btn.textContent;
    btn.textContent = "Copiado!";
    setTimeout(function () { btn.textContent = old; }, 1500);
  });
}

async function doSequencia() {
  if (!lastBusiness) return;
  showLoader("Gerando sequência SDR com a skill copywriter...");
  try {
    const r = await fetch("/api/business/sequencia", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ business: lastBusiness, niche_id: $("niche").value || "" })
    });
    const d = await r.json();
    hideLoader();
    if (!r.ok) throw new Error(d.detail || "Erro");

    const out = $("sdrOutput");
    out.className = "panel aout";
    let html = "<h3>Sequência SDR — " + esc(lastBusiness.nome) + "</h3>";
    html += "<span class='tag'>" + (d.engine === "local" ? "Skill local" : esc(d.engine)) + "</span> ";
    if (d.alavanca) html += "<span class='tag'>Alavanca: " + esc(d.alavanca) + "</span>";

    const msgs = [["abertura", "Mensagem 1 — Abertura (enviar agora)"],
                  ["followup", "Mensagem 2 — Follow-up (2 dias depois)"],
                  ["fechamento", "Mensagem 3 — Fechamento (5 dias depois)"]];
    msgs.forEach(function (pair, idx) {
      html += "<h4>" + pair[1] + "</h4>";
      html += "<div class='pitch-box'>" + esc(d[pair[0]] || "-") + "</div>";
      html += "<button class='btn small primary' onclick=\"copySeq(this, '" + pair[0] + "')\">Copiar msg " + (idx + 1) + "</button>";
    });

    out.innerHTML = html;
    out.dataset.abertura = d.abertura || "";
    out.dataset.followup = d.followup || "";
    out.dataset.fechamento = d.fechamento || "";
    showOut("sdrOutput");
  } catch (e) {
    hideLoader();
    showStatus("searchStatus", "Falha na sequência: " + e.message, "error");
  }
}

async function doObjection() {
  if (!lastBusiness) return;
  const objection = $("objectionInput").value.trim();
  if (!objection) return;
  const box = $("objectionOut");
  box.innerHTML = "<p class='hint'>Pensando na melhor resposta...</p>";
  try {
    const r = await fetch("/api/business/objection", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ business: lastBusiness, objection: objection })
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "Erro");
    box.innerHTML =
      "<div class='pitch-box'><b>Objeção:</b> " + esc(objection) + "<br><br>" +
      "<b>Resposta sugerida:</b><br>" + esc(d.resposta) + "</div>" +
      "<span class='tag'>" + (d.engine === "local" ? "IA local" : esc(d.engine)) + "</span>";
  } catch (e) {
    box.innerHTML = "<p class='status error'>Falha: " + esc(e.message) + "</p>";
  }
}

// ===== PROPOSTA COMERCIAL =====
async function doProposal() {
  if (!lastBusiness) return;
  showLoader("Gerando proposta comercial com IA...");
  try {
    const r = await fetch("/api/business/proposal", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ business: lastBusiness })
    });
    const d = await r.json();
    hideLoader();
    if (!r.ok) throw new Error(d.detail || "Erro");

    const out = $("proposalOutput");
    out.className = "panel";
    out.innerHTML =
      "<h3>Proposta gerada <span class='tag'>" + (d.engine === "local" ? "IA local" : esc(d.engine)) + "</span></h3>" +
      "<p class='hint'>A proposta abre em uma nova janela pronta para imprimir/salvar como PDF.</p>" +
      "<div class='btn-row'><button class='btn primary' id='btnOpenProposal'>Abrir proposta</button></div>";
    out.dataset.payload = JSON.stringify(d);
    showOut("proposalOutput");
    $("btnOpenProposal").addEventListener("click", function () { openProposalWindow(lastBusiness, d); });
  } catch (e) {
    hideLoader();
    showStatus("searchStatus", "Falha na proposta: " + e.message, "error");
  }
}

function openProposalWindow(b, d) {
  const data = d || JSON.parse($("proposalOutput").dataset.payload);
  const hoje = new Date().toLocaleDateString("pt-BR");
  const li = function (t) { return "<li>" + esc(t) + "</li>"; };

  let planoHtml = "";
  (data.plano || []).forEach(function (f) {
    planoHtml += "<div class='p-fase'><div class='p-fase-title'>" + esc(f.fase) + "</div><ul>" +
      (f.itens || []).map(li).join("") + "</ul></div>";
  });

  const html = `<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><title>Proposta — ${esc(b.nome)}</title>
<style>
  body{font-family:'Segoe UI',Arial,sans-serif;color:#1a1a2e;max-width:800px;margin:0 auto;padding:48px 40px;line-height:1.65;}
  .top{display:flex;justify-content:space-between;align-items:center;border-bottom:4px solid #a94fff;padding-bottom:20px;margin-bottom:28px;}
  .brand{font-size:22px;font-weight:800;background:linear-gradient(90deg,#a94fff,#ff4757);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;}
  .data{color:#777;font-size:13px;}
  h1{font-size:24px;margin:0 0 4px;}
  .lead-info{color:#555;font-size:14px;margin-bottom:30px;}
  h2{font-size:15px;text-transform:uppercase;letter-spacing:2px;color:#a94fff;margin:30px 0 12px;}
  ul{margin:6px 0 0 20px;padding:0;} li{margin:6px 0;}
  .p-fase{background:#f6f2ff;border-left:4px solid #a94fff;border-radius:8px;padding:14px 18px;margin:12px 0;}
  .p-fase-title{font-weight:700;margin-bottom:6px;}
  .result{background:#fff5f6;border-left:4px solid #ff4757;border-radius:8px;padding:14px 18px;margin-top:24px;}
  .cta{margin-top:34px;text-align:center;font-size:17px;font-weight:700;}
  .foot{margin-top:40px;padding-top:16px;border-top:1px solid #ddd;color:#999;font-size:11px;text-align:center;}
  @media print{ body{padding:20px;} .noprint{display:none;} }
</style></head><body>
<div class="top"><div class="brand">Prospector</div><div class="data">Proposta gerada em ${hoje}</div></div>
<h1>Proposta de Crescimento Digital</h1>
<div class="lead-info"><b>${esc(b.nome)}</b> — ${esc([b.categoria, [b.cidade, b.estado].filter(Boolean).join(" - ")].filter(Boolean).join(" · "))}</div>

<h2>Diagnóstico</h2>
<ul>${(data.diagnostico || []).map(li).join("")}</ul>

<h2>Solução recomendada</h2>
<ul>${(data.solucao || []).map(li).join("")}</ul>

<h2>Plano de execução</h2>
${planoHtml}

<div class="result"><b>Resultado esperado:</b> ${esc(data.resultado_esperado || "")}</div>
<div class="cta">${esc(data.cta || "Vamos começar?")}</div>
<div class="foot">Documento gerado pelo Prospector — valores e prazos a combinar diretamente com o cliente.</div>
<script>window.onload=function(){setTimeout(function(){window.print();},400);};</script>
</body></html>`;

  const w = window.open("", "_blank");
  if (!w) {
    showStatus("searchStatus", "Permita pop-ups para abrir a proposta.", "error");
    return;
  }
  w.document.write(html);
  w.document.close();
}

// ===== DASHBOARD DE PERFORMANCE =====
function renderPerformance() {
  const grid = $("perfStats");
  if (!grid) return;

  const total = bizCache.length;
  const contacted = bizCache.filter(function (b) { return isContacted(b.nome); }).length;
  const taxa = total ? Math.round(contacted / total * 100) : 0;
  const urgentes = bizCache.filter(function (b) {
    return computeUrgency(b).nivel === "alta" && !isContacted(b.nome);
  }).length;
  const scored = bizCache.filter(function (b) { return b.score_oportunidade != null; });
  const media = scored.length ? Math.round(scored.reduce(function (s, b) { return s + b.score_oportunidade; }, 0) / scored.length) : 0;

  function stat(label, value, cls) {
    return "<div class='perf-stat " + (cls || "") + "'><div class='perf-num'>" + value + "</div><div class='perf-label'>" + label + "</div></div>";
  }

  grid.innerHTML =
    stat("Leads na sessão", total) +
    stat("Contatados", contacted, "ok") +
    stat("Taxa de contato", taxa + "%", taxa >= 50 ? "ok" : "") +
    stat("Urgentes pendentes", urgentes, urgentes > 0 ? "warn" : "") +
    stat("Score médio IA", scored.length ? media + "%" : "—");

  const top = scored.slice().sort(function (a, b) { return b.score_oportunidade - a.score_oportunidade; }).slice(0, 3);
  $("perfTop").innerHTML = top.length
    ? "<ul>" + top.map(function (b) {
        return "<li><b>" + esc(b.nome) + "</b> — score " + b.score_oportunidade + "% (" + (isContacted(b.nome) ? "contatado" : "pendente") + ")</li>";
      }).join("") + "</ul>"
    : "Rode a análise em lote para ver o ranking aqui.";
}

function detailHtmlFor(b) {
  function row(label, value) {
    if (!value) return "";
    return "<div class='detail-row'><span class='detail-label'>" + label + "</span><span>" + esc(value) + "</span></div>";
  }

  let html = "";
  html += "<div class='detail-hero'>";
  html += avatarHtml(b);
  html += "<div><div class='detail-name'>" + esc(b.nome) + "</div>";
  html += "<div class='biz-sub2'>" + esc([b.categoria, [b.cidade, b.estado].filter(Boolean).join(" - ")].filter(Boolean).join(" · ")) + "</div></div>";
  html += "</div>";
  html += row("Nota", b.nota ? b.nota + " (" + (b.avaliacoes || "0") + " avaliações)" : "");
  html += row("Endereço", b.endereco);
  html += row("Bairro", b.bairro);
  html += row("Cidade / UF", [b.cidade, b.estado].filter(Boolean).join(" - "));
  html += row("Telefone", b.telefone);
  html += row("Site", b.website);
  html += row("Status", b.status_funcionamento);
  html += row("Preço", b.preco);
  html += row("Horários", b.horarios);
  html += row("Plus Code", b.plus_code);
  html += row("Coordenadas", b.latitude ? b.latitude + ", " + b.longitude : "");
  html += row("Descrição", b.descricao);
  html += row("Busca em", b.consulta);
  const atr = b.atributos;
  const atrArr = Array.isArray(atr) ? atr : (atr ? String(atr).split(";").map(function (x) { return x.trim(); }).filter(Boolean) : []);
  if (atrArr.length) {
    html += "<div class='detail-row'><span class='detail-label'>Serviços</span><span>" +
      atrArr.map(function (a) { return "<span class='tag'>" + esc(a) + "</span>"; }).join(" ") +
      "</span></div>";
  }
  if (b.url) {
    html += "<div class='detail-row'><span class='detail-label'>Maps</span><span><a class='link' href='" +
      esc(b.url) + "' target='_blank'>abrir no Google Maps</a></span></div>";
  }

  html += "<div class='btn-row' style='margin-top:16px'>";
  if (b.website) html += "<button class='btn primary' id='btnContacts'>Extrair contatos do site</button>";
  html += "<button class='btn' id='btnShot'>Salvar imagem do Maps</button>";
  html += "<button class='btn primary' id='btnAnalyzeLead'>Analisar com IA</button>";
  html += "</div>";
  html += "<div id='shotArea'></div>";
  html += "<div id='contactsArea'></div>";
  return html;
}

function openDetailModal(b) {
  lastBusiness = b;
  $("detailBody").innerHTML = detailHtmlFor(b);
  $("detailModal").classList.remove("hidden");

  const btn = $("btnContacts");
  if (btn) btn.addEventListener("click", function () { extractContacts(b.website); });
  $("btnShot").addEventListener("click", function () { saveScreenshot(b); });
  $("btnAnalyzeLead").addEventListener("click", function () {
    $("detailModal").classList.add("hidden");
    analyzeLeadObject();
  });
}

window.showLeadDetails = function (id) {
  const lead = crmCache.find(function (l) { return String(l.id) === String(id); });
  if (lead) openDetailModal(lead);
};

window.analyzeLeadObject = function () {
  if (!lastBusiness) return;
  switchTab("results");
  $("analyzeCard").classList.remove("hidden");
  $("bizTitle").textContent = lastBusiness.nome;
  $("bizSub").textContent = [lastBusiness.endereco, lastBusiness.telefone].filter(Boolean).join(" | ");
  ["refOutput", "igOutput", "strategyOutput", "sdrOutput", "pitchOutput", "proposalOutput"].forEach(function (oid) {
    $(oid).classList.add("hidden");
  });
  doStrategy();
};

window.showDetails = function (i) {
  const b = bizCache[i];
  if (!b) return;
  lastBusiness = b;
  markSelected(i);
  openDetailModal(b);
};

function markSelected(i) {
  document.querySelectorAll(".biz-row").forEach(function (el) { el.classList.remove("selected"); });
  const row = $("bizRow" + i);
  if (row) row.classList.add("selected");
}

async function saveScreenshot(b) {
  const area = $("shotArea");
  area.innerHTML = "<p class='hint'>Capturando imagem do Google Maps...</p>";
  try {
    const r = await fetch("/api/business/screenshot", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: b.url, name: b.nome })
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "Erro");
    area.innerHTML =
      "<h4>Imagem salva com sucesso</h4>" +
      "<p style='font-size:12px;color:var(--muted);word-break:break-all;'>" + esc(d.arquivo) + "</p>";
  } catch (e) {
    area.innerHTML = "<p class='status error'>Falha: " + esc(e.message) + "</p>";
  }
}

async function extractContacts(url) {
  const area = $("contactsArea");
  area.innerHTML = "<p class='hint'>Extraindo contatos do site...</p>";
  try {
    const r = await fetch("/api/business/contacts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: url })
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "Erro");

    let html = "<h4>Contatos encontrados no site</h4>";
    if (d.erro) html += "<p class='status error'>" + esc(d.erro) + "</p>";
    html += "<ul class='contacts-list'>";
    html += "<li><b>E-mails:</b> " + ((d.emails || []).map(esc).join(", ") || "-") + "</li>";
    html += "<li><b>WhatsApp:</b> " + ((d.whatsapps || []).map(esc).join(", ") || "-") + "</li>";
    html += "<li><b>Telefones:</b> " + ((d.telefones || []).map(esc).join(", ") || "-") + "</li>";
    html += "<li><b>Instagram:</b> " + (d.instagram ? "@" + esc(d.instagram) : "-") + "</li>";
    html += "<li><b>Facebook:</b> " + (d.facebook ? esc(d.facebook) : "-") + "</li>";
    html += "<li><b>TikTok:</b> " + (d.tiktok ? "@" + esc(d.tiktok) : "-") + "</li>";
    if (d.descricao) html += "<li><b>Descrição:</b> " + esc(d.descricao) + "</li>";
    html += "</ul>";
    area.innerHTML = html;
  } catch (e) {
    area.innerHTML = "<p class='status error'>Falha: " + esc(e.message) + "</p>";
  }
}

window.selectBusiness = function (i, analyze) {
  lastBusiness = bizCache[i];
  if (!lastBusiness) return;
  switchTab("results");
  markSelected(i);
  $("analyzeCard").classList.remove("hidden");
  $("bizTitle").textContent = lastBusiness.nome;
  $("bizSub").textContent = [lastBusiness.endereco, lastBusiness.telefone].filter(Boolean).join(" | ");
  ["refOutput", "igOutput", "strategyOutput", "sdrOutput", "pitchOutput", "proposalOutput"].forEach(function (id) { $(id).classList.add("hidden"); });
  $("analyzeCard").scrollIntoView({ behavior: "smooth", block: "nearest" });
  if (analyze) doInstagram("");
};

async function doStrategy() {
  if (!lastBusiness) return;
  showLoader("Gerando análise estratégica com IA...");
  try {
    const r = await fetch("/api/business/strategy", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ business: lastBusiness })
    });
    const d = await r.json();
    hideLoader();
    if (!r.ok) throw new Error(d.detail || "Erro");

    const out = $("strategyOutput");
    out.className = "panel";
    const score = d.score_oportunidade != null ? d.score_oportunidade : 50;
    const nivelPill = d.nivel === "Alto" ? "high" : (d.nivel === "Baixo" ? "low" : "med");

    let html = "<h3>Análise Estratégica — " + esc(lastBusiness.nome) + "</h3>";
    html += "<div class='score-line'>";
    html += "<span>Oportunidade: <b>" + score + "%</b></span>";
    html += "<div class='progress'><div style='width:" + score + "%'></div></div>";
    html += "<span class='pill " + nivelPill + "'>" + esc(d.nivel || "-") + "</span>";
    html += "<span class='tag'>" + (d.engine === "local" ? "IA local" : esc(d.engine)) + "</span>";
    html += "</div>";

    if (d.resumo) html += "<p>" + esc(d.resumo) + "</p>";
    [["presenca_digital", "Presença digital"], ["oportunidades", "Oportunidades de serviço"], ["acoes_imediatas", "Ações imediatas"]].forEach(function (pair) {
      if (d[pair[0]] && d[pair[0]].length) {
        html += "<h4>" + pair[1] + "</h4><ul>";
        d[pair[0]].forEach(function (x) { html += "<li>" + esc(x) + "</li>"; });
        html += "</ul>";
      }
    });
    if (d.abordagem) html += "<h4>Como abordar</h4><p>" + esc(d.abordagem) + "</p>";
    out.innerHTML = html;
    showOut("strategyOutput");
  } catch (e) {
    hideLoader();
    showStatus("searchStatus", "Falha na estratégia: " + e.message, "error");
  }
}

async function doReference() {
  if (!lastBusiness) return;
  showLoader("Buscando referência para \"" + lastBusiness.nome + "\"...");
  try {
    const r = await fetch("/api/google/reference", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: lastBusiness.nome, location: lastBusiness.endereco || "" })
    });
    const data = await r.json();
    hideLoader();
    if (!r.ok) throw new Error(data.detail || "Erro");
    lastHandle = data.instagram_handle;
    const out = $("refOutput");
    out.className = "panel";
    let html = "<h3>Referência de \"" + esc(lastBusiness.nome) + "\"</h3>";
    html += "<p>Instagram encontrado: <b>" + (lastHandle ? "@" + esc(lastHandle) : "não encontrado") + "</b></p>";
    if (lastHandle) {
      html += "<div class='btn-row'><button class='btn small primary' onclick=\"doInstagram('" + esc(lastHandle) + "')\">Analisar @" + esc(lastHandle) + "</button></div>";
    }
    html += "<h4>Links encontrados</h4><ul>";
    (data.web_results || []).forEach(function (r2) {
      html += "<li><a class='link' href='" + esc(r2.url) + "' target='_blank'>" + esc(r2.title) + "</a></li>";
    });
    if (!(data.web_results || []).length) html += "<li>Nenhum</li>";
    html += "</ul>";
    out.innerHTML = html;
    showOut("refOutput");
  } catch (e) {
    hideLoader();
    showStatus("searchStatus", "Falha na referência: " + e.message, "error");
  }
}

async function doInstagram(forceHandle) {
  if (!lastBusiness) return;
  const username = forceHandle || lastHandle || "";
  showLoader("Analisando Instagram" + (username ? " @" + username : "") + "...");
  try {
    const r = await fetch("/api/instagram/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: lastBusiness.nome, username: username, download: true, max_posts: 12 })
    });
    const data = await r.json();
    hideLoader();
    if (!r.ok) throw new Error(data.detail || "Erro na análise");
    lastHandle = data.username;
    renderInstagram(data);
  } catch (e) {
    hideLoader();
    showStatus("searchStatus", "Falha na análise: " + e.message, "error");
  }
}

function renderInstagram(data) {
  const ig = $("igOutput");
  ig.className = "panel";
  const p = data.perfil || {};
  const rel = data.relatorio || {};

  let html = "<h3>Perfil @" + esc(data.username) + (data.auto_descoberto ? " <span class='tag'>auto-detectado</span>" : "") + "</h3>";
  html += "<div class='profile-stats'>";
  html += "<span><b>" + (p.seguidores != null ? p.seguidores : 0) + "</b> seguidores</span>";
  html += "<span><b>" + (p.total_posts != null ? p.total_posts : 0) + "</b> posts</span>";
  if (p.categoria) html += "<span>" + esc(p.categoria) + "</span>";
  if (p.verificado) html += "<span style='color:var(--accent)'>verificado</span>";
  html += "</div>";
  if (p.biografia) html += "<div class='bio'>" + esc(p.biografia) + "</div>";

  const score = rel.score_positividade != null ? rel.score_positividade : 50;
  html += "<div class='score-line'>";
  html += "<span>Positividade: <b>" + score + "%</b></span>";
  html += "<div class='progress'><div style='width:" + score + "%'></div></div>";
  html += "<span class='tag'>" + (rel.engine === "openai" ? "IA Groq/OpenAI" : "IA local") + "</span>";
  html += "</div>";
  if (rel.resumo) html += "<p>" + esc(rel.resumo) + "</p>";

  [["pontos_fortes", "Pontos fortes"], ["sugestoes", "Sugestões de melhoria"], ["conteudo_recomendado", "Conteúdo recomendado pela IA"]].forEach(function (pair) {
    if (rel[pair[0]] && rel[pair[0]].length) {
      html += "<h4>" + pair[1] + "</h4><ul>";
      rel[pair[0]].forEach(function (x) { html += "<li>" + esc(x) + "</li>"; });
      html += "</ul>";
    }
  });

  if (rel.tom_de_voz) html += "<h4>Tom de voz</h4><p>" + esc(rel.tom_de_voz) + "</p>";

  const tags = (rel.hashtags || []).slice(0, 8).map(function (h) {
    return "<span class='tag'>" + esc(h.hashtag || h) + "</span>";
  }).join("");
  html += "<h4>Hashtags</h4><div>" + (tags || "<span class='tag'>sem hashtags</span>") + "</div>";

  html += "<h4 style='margin-top:18px'>Postagens recentes (" + (data.posts ? data.posts.length : 0) + ")</h4>";
  html += "<div class='posts-grid'>";
  (data.posts || []).forEach(function (post) {
    html += "<div>";
    html += "<div class='post-thumb'>";
    if (post.url_imagem) html += "<img src='" + esc(post.url_imagem) + "' loading='lazy' alt=''>";
    html += "<div class='post-stats'>" + (post.curtidas || 0) + " curtidas · " + (post.comentarios || 0) + " comentários</div>";
    html += "</div>";
    html += "<div class='post-caption'>" + esc((post.legenda || "").slice(0, 110)) + "</div>";
    html += "</div>";
  });
  html += "</div>";

  if (data.conteudos_baixados && data.conteudos_baixados.length) {
    html += "<h4>Conteúdo baixado (" + data.conteudos_baixados.length + ")</h4><ul style='font-size:12px;color:var(--muted)'>";
    data.conteudos_baixados.forEach(function (c) { html += "<li>" + esc(c.arquivo) + "</li>"; });
    html += "</ul>";
  }

  ig.innerHTML = html;
  showOut("igOutput");
}

async function exportData(format) {
  const r = await fetch("/api/export?format=" + format);
  if (!r.ok) return;
  const blob = await r.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "negocios." + format;
  a.click();
}

async function saveSettings() {
  const body = {};
  if ($("apiKey").value.trim()) body.openai_api_key = $("apiKey").value.trim();
  if ($("baseUrl").value.trim()) body.openai_base_url = $("baseUrl").value.trim();
  if ($("model").value.trim()) body.openai_model = $("model").value.trim();
  if ($("igSession").value.trim()) body.instagram_sessionid = $("igSession").value.trim();
  if ($("dispProvider")) {
    body.disparo_provider = $("dispProvider").value;
    if ($("dispEvoUrl").value.trim()) body.disparo_evo_url = $("dispEvoUrl").value.trim();
    if ($("dispEvoKey").value.trim()) body.disparo_evo_key = $("dispEvoKey").value.trim();
    if ($("dispEvoInstance").value.trim()) body.disparo_evo_instance = $("dispEvoInstance").value.trim();
    if ($("dispEvoChip2").value.trim()) body.disparo_evo_chip2 = $("dispEvoChip2").value.trim();
    if ($("dispEvoChip3").value.trim()) body.disparo_evo_chip3 = $("dispEvoChip3").value.trim();
    if ($("dispTom")) body.disparo_tom = $("dispTom").value;
    if ($("dispPrompt").value.trim()) body.disparo_prompt = $("dispPrompt").value.trim();
    if ($("dispMetaToken").value.trim()) body.disparo_meta_token = $("dispMetaToken").value.trim();
    if ($("dispMetaPhone").value.trim()) body.disparo_meta_phone_id = $("dispMetaPhone").value.trim();
  }
  if ($("sbUrl") && $("sbUrl").value.trim()) body.supabase_url = $("sbUrl").value.trim();
  if ($("sbSecret") && $("sbSecret").value.trim()) body.supabase_secret = $("sbSecret").value.trim();
  try {
    const r = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    const s = await r.json();

    const schedBody = {
      enabled: $("schedEnabled").checked,
      time: $("schedTime").value || "08:00",
      niche: $("schedNiche").value,
      states: $("schedStates").value.split(",").map(function (x) { return x.trim(); }).filter(Boolean),
      max: parseInt($("maxResults").value, 10) || 10
    };
    await fetch("/api/schedule", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(schedBody)
    });

    if (r.ok) {
      showStatus("settingsStatus", schedBody.enabled
        ? "Salvo! Busca automática diária às " + schedBody.time + "."
        : "Configurações salvas.", "ok");
      $("apiKey").value = "";
      $("igSession").value = "";
      $("apiKey").placeholder = s.openai_api_key ? "Chave configurada" : "sk-... / gsk-... (opcional)";
    $("igSession").placeholder = s.instagram_sessionid ? "Cookie configurado" : "Opcional - sessionid";

    if ($("dispProvider")) {
      $("dispProvider").value = s.disparo_provider || "simulado";
      $("dispEvoUrl").value = s.disparo_evo_url || "";
      $("dispEvoInstance").value = s.disparo_evo_instance || "";
      $("dispEvoChip2").value = s.disparo_evo_chip2 || "";
      $("dispEvoChip3").value = s.disparo_evo_chip3 || "";
      $("dispTom").value = s.disparo_tom || "direto";
      $("dispPrompt").value = "";
      $("dispPrompt").placeholder = s.disparo_prompt ? "Prompt personalizado ativo" : "Vazio = prompt da skill";
      $("dispMetaPhone").value = s.disparo_meta_phone_id || "";
      $("dispEvoKey").placeholder = s.disparo_evo_key ? "Key configurada" : "sua apikey";
      $("dispMetaToken").placeholder = s.disparo_meta_token ? "Token configurado" : "token permanente";
    }
    if ($("sbUrl")) {
      $("sbUrl").value = s.supabase_url || "";
      $("sbSecret").placeholder = s.supabase_secret ? "Secret configurada" : "sb_secret_... (opcional)";
    }

    try {
      fetch("/api/cloud/status").then(function (r) { return r.json(); }).then(function (cs) {
        const cc = $("cloudChip");
        if (!cc) return;
        if (cs.online) {
          cc.classList.add("on"); cc.classList.remove("off");
          $("cloudChipText").textContent = "Nuvem: conectada";
        } else {
          cc.classList.add("off"); cc.classList.remove("on");
          $("cloudChipText").textContent = "Nuvem: local";
        }
      }).catch(function () { /* mantém padrão */ });
    } catch (e) { /* mantém padrão */ }
      await loadSettings();
      setTimeout(function () { clearStatus("settingsStatus"); }, 3000);
    } else {
      showStatus("settingsStatus", "Erro ao salvar.", "error");
    }
  } catch (e) {
    showStatus("settingsStatus", "Erro ao salvar: " + e.message, "error");
  }
}

// ===== CONEXÃO WHATSAPP (Evolution QR) =====
let qrPoll = null;

async function refreshInstances() {
  const box = $("instList");
  if (!box) return;
  try {
    const r = await fetch("/api/disparo/instancias");
    const d = await r.json();
    const arr = d.instancias || [];
    if (!arr.length) {
      box.innerHTML = "<span class='hint'>Nenhuma instância cadastrada. Configure nas Configurações.</span>";
      return;
    }
    box.innerHTML = arr.map(function (it) {
      const dot = it.conectado ? "on" : "off";
      return "<span class='chip " + dot + "' style='margin:2px;'>" +
        "<span class='dot'></span><b>" + esc(it.instance || "?") + "</b>&nbsp;" +
        esc(it.conectado ? "conectado" : (it.estado || "off")) +
        " <a class='link' href='#' onclick='connectWhatsApp(\"" + esc(it.instance || "") + "\");return false;'>conectar</a></span>";
    }).join("");
  } catch (e) {
    box.innerHTML = "<span class='hint'>Falha ao ver instâncias.</span>";
  }
}

async function connectWhatsApp(instance) {
  $("qrModal").classList.remove("hidden");
  $("qrHint").textContent = "Gerando QR code" + (instance ? " para " + instance : "") + "...";
  $("qrBox").innerHTML = "";
  $("qrStatus").textContent = "aguardando...";
  clearInterval(qrPoll);
  try {
    const r = await fetch("/api/disparo/evolution/qrcode" + (instance ? "?instance=" + encodeURIComponent(instance) : ""), { method: "POST" });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "Erro");
    if (d.qrcode) {
      const src = d.qrcode.indexOf("base64,") !== -1 ? d.qrcode : "data:image/png;base64," + d.qrcode;
      $("qrBox").innerHTML = "<img src='" + src + "' style='width:100%;border-radius:12px;' alt='QR'>";
      $("qrHint").textContent = "Escaneie com o WhatsApp do chip de disparo.";
    } else {
      $("qrHint").textContent = "Instância já criada. Verificando conexão...";
    }
    qrPoll = setInterval(checkWaState, 4000);
    checkWaState();
  } catch (e) {
    $("qrHint").textContent = "Falha: " + e.message;
    $("qrStatus").textContent = "Evolution fora do ar? Suba com: cd evolution && docker compose up -d";
  }
}

async function checkWaState() {
  try {
    const r = await fetch("/api/disparo/evolution/estado");
    const d = await r.json();
    if (d.conectado) {
      $("qrStatus").textContent = "Conectado! Pode fechar e iniciar o disparo.";
      clearInterval(qrPoll);
    } else {
      $("qrStatus").textContent = "Estado: " + (d.estado || "aguardando scan...") + (d.erro ? " — " + d.erro : "");
    }
  } catch (e) { /* tenta de novo no próximo ciclo */ }
}

// ===== DISPARO AUTOMÁTICO =====
let dispPoll = null;
let dispModo = "auto";

function paintModo() {
  document.querySelectorAll("#modoSeg .seg-btn").forEach(function (b) {
    b.classList.toggle("active", b.dataset.modo === dispModo);
  });
  $("modoHint").textContent = dispModo === "auto"
    ? "O robô envia sozinho respeitando pausas, limite e horário."
    : "Você envia um por um pelo botão Enviar de cada linha.";
}

async function setModo(modo) {
  dispModo = modo;
  paintModo();
  try {
    await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ disparo_modo: modo })
    });
  } catch (e) { /* silencioso */ }
}

async function migrarMinerados() {
  showLoader("Puxando todos os leads minerados para a fila...");
  try {
    const r = await fetch("/api/disparo/migrar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ origem: "minerados" })
    });
    const d = await r.json();
    hideLoader();
    if (!r.ok) throw new Error(d.detail || "Erro");
    showStatus("searchStatus",
      d.enfileirados + " leads minerados na fila (de " + d.total_minerados + " no total, sem repetir telefone)!", "ok");
    refreshDisparo();
  } catch (e) {
    hideLoader();
    showStatus("searchStatus", "Falha: " + e.message, "error");
  }
}

window.enviarAgora = async function (id) {
  try {
    const r = await fetch("/api/disparo/enviar-agora", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: id })
    });
    const d = await r.json();
    showStatus("searchStatus",
      d.ok ? "Enviado via " + d.provider + "!" : "Falha: " + d.erro,
      d.ok ? "ok" : "error");
  } catch (e) {
    showStatus("searchStatus", "Falha: " + e.message, "error");
  }
  refreshDisparo();
};

window.refazerMensagem = async function (id, btn) {
  const old = btn ? btn.textContent : "";
  if (btn) { btn.textContent = "Gerando..."; btn.disabled = true; }
  try {
    const r = await fetch("/api/disparo/refazer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: id })
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "Erro");
    showStatus("searchStatus", "Mensagem refeita com " + (d.engine === "local" ? "o motor local" : d.engine) + "! Confira na tabela.", "ok");
  } catch (e) {
    showStatus("searchStatus", "Falha ao refazer: " + e.message, "error");
  } finally {
    if (btn) { btn.textContent = old; btn.disabled = false; }
  }
  refreshDisparo();
};

window.verMensagem = async function (id) {
  try {
    const r = await fetch("/api/disparo/item/" + id);
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "Erro");
    let html = "<div class='detail-hero'>";
    html += "<div class='avatar'>" + esc(initials(d.nome)) + "</div>";
    html += "<div><div class='detail-name'>" + esc(d.nome) + "</div>";
    html += "<div class='biz-sub2'>" + esc(d.telefone) + " · <span class='st-" + d.status + "'>" + d.status + "</span></div></div>";
    html += "</div>";
    if (d.enviado_em) html += "<p class='hint'>Enviada em: " + esc(d.enviado_em) + (d.instancia ? " · via chip <b>" + esc(d.instancia) + "</b>" : "") + "</p>";
    if (d.tentativas) html += "<p class='hint'>Tentativas: " + d.tentativas + "</p>";
    if (d.erro) html += "<p class='status error'>" + esc(d.erro) + "</p>";
    html += "<h4>Mensagem que " + (d.status === "enviado" ? "foi enviada" : "será enviada") + "</h4>";
    html += "<div class='pitch-box' style='white-space:pre-wrap;'>" + esc(d.mensagem || "(vazia)") + "</div>";
    if (d.status === "pendente") {
      html += "<div class='btn-row'><button class='btn small wa' onclick='enviarAgora(" + d.id + ");closeMsgModal();'>Enviar agora</button>" +
        "<button class='btn small' onclick='refazerMensagem(" + d.id + ", null);closeMsgModal();'>Refazer com IA</button></div>";
    }
    $("msgBody").innerHTML = html;
    $("msgModal").classList.remove("hidden");
  } catch (e) {
    showStatus("searchStatus", "Falha: " + e.message, "error");
  }
};

window.closeMsgModal = function () {
  $("msgModal").classList.add("hidden");
};

async function enqueueAll() {
  if (!bizCache.length) {
    showStatus("searchStatus", "Faça uma busca primeiro.", "error");
    return;
  }
  const alvos = bizCache.filter(function (b) { return waPhone(b); });
  if (!alvos.length) {
    showStatus("searchStatus", "Nenhum lead com telefone válido.", "error");
    return;
  }
  showLoader("Gerando mensagens 0/" + alvos.length + "...");
  const itens = [];
  try {
    for (let i = 0; i < alvos.length; i++) {
      const b = alvos[i];
      if (b._pitch && b._pitch.whatsapp) {
        itens.push({ nome: b.nome, telefone: b.telefone, mensagem: b._pitch.whatsapp });
      } else {
        const r = await fetch("/api/business/pitch?rapido=1", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ business: b })
        });
        const d = await r.json();
        if (r.ok && d.whatsapp) {
          b._pitch = d;
          itens.push({ nome: b.nome, telefone: b.telefone, mensagem: d.whatsapp });
        }
      }
      $("loaderText").textContent = "Gerando mensagens " + (i + 1) + "/" + alvos.length + "...";
    }
    const r2 = await fetch("/api/disparo/enfileirar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ itens: itens, origem: $("queryTitle").textContent || "" })
    });
    const d2 = await r2.json();
    hideLoader();
    if (!r2.ok) throw new Error(d2.detail || "Erro");
    showStatus("searchStatus", d2.enfileirados + " leads na fila de disparo!", "ok");
    refreshDisparo();
  } catch (e) {
    hideLoader();
    showStatus("searchStatus", "Falha: " + e.message, "error");
  }
}

async function refreshDisparo() {
  try {
    if (typeof window._instLast === "undefined" || Date.now() - window._instLast > 30000) {
      window._instLast = Date.now();
      refreshInstances();
    }
    const s = await (await fetch("/api/settings")).json();
    if (s.disparo_modo) {
      dispModo = s.disparo_modo;
      paintModo();
    }
    const r = await fetch("/api/disparo/status");
    const st = await r.json();

    const line = $("disparoStatusLine");
    line.textContent = st.rodando
      ? "RODANDO · " + st.enviados_hoje + " hoje · " + st.pendentes + " na fila · próximo: " + (st.proximo_em || "já")
      : "parado · " + st.pendentes + " na fila · " + st.enviados + " enviados";
    line.className = "tag" + (st.rodando ? " on" : "");

    const r2 = await fetch("/api/disparo/fila?limite=50");
    const d2 = await r2.json();
    const rows = (d2.fila || []).map(function (f) {
      const action = f.status === "pendente"
        ? "<button class='btn small wa' onclick='enviarAgora(" + f.id + ")'>Enviar</button>" +
          "<button class='btn small' onclick='refazerMensagem(" + f.id + ", this)'>Refazer IA</button>"
        : "";
      return "<tr><td>" + esc(f.nome) + "</td><td>" + esc(f.telefone) + "</td>" +
        "<td class='st-" + f.status + "'>" + f.status + "</td>" +
        "<td>" + (f.instancia ? esc(f.instancia) : "<span class='hint'>—</span>") + "</td>" +
        "<td>" + esc((f.mensagem || "").slice(0, 60)) + "…</td>" +
        "<td><div class='row-actions'><button class='btn small' onclick='verMensagem(" + f.id + ")'>Ver</button>" + action + "</div></td></tr>";
    }).join("");
    $("disparoTable").innerHTML = rows
      ? "<table class='disp-table'><thead><tr><th>Lead</th><th>Telefone</th><th>Status</th><th>Chip</th><th>Mensagem</th><th></th></tr></thead><tbody>" + rows + "</tbody></table>"
      : "<p class='hint'>Fila vazia. Clique em 'Enfileirar resultados' ou 'Puxar todos os minerados'.</p>";

    clearInterval(dispPoll);
    if (st.rodando) {
      dispPoll = setInterval(refreshDisparo, 5000);
    }
  } catch (e) { /* silencioso */ }
}

async function startDisp() {
  const body = {
    provider: "simulado",
    delay_min: parseFloat($("dispDelayMin").value) || 45,
    delay_max: parseFloat($("dispDelayMax").value) || 120,
    limite_dia: parseInt($("dispLimite").value, 10) || 30,
    hora_ini: $("dispHoraIni").value || "08:00",
    hora_fim: $("dispHoraFim").value || "20:00",
    optout: true
  };
  try {
    const s = await (await fetch("/api/settings")).json();
    body.provider = s.disparo_provider || "simulado";
  } catch (e) { /* usa simulado */ }
  const r = await fetch("/api/disparo/iniciar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  const d = await r.json();
  if (d.iniciado || d.rodando) {
    showStatus("searchStatus", "Disparo rodando no modo " + body.provider + "! Acompanhe aqui.", "ok");
  } else if (d.motivo) {
    showStatus("searchStatus", d.motivo + ". Use o botão Enviar de cada linha.", "info");
  } else {
    showStatus("searchStatus", "Disparo já estava rodando.", "info");
  }
  refreshDisparo();
}

async function pauseDisp() {
  await fetch("/api/disparo/pausar", { method: "POST" });
  clearInterval(dispPoll);
  refreshDisparo();
}

async function testDisp() {
  const phone = prompt("Digite SEU número com DDD para teste (ex: 11999998888):");
  if (!phone) return;
  showLoader("Enviando mensagem de teste...");
  try {
    const r = await fetch("/api/disparo/testar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone: phone })
    });
    const d = await r.json();
    hideLoader();
    showStatus("searchStatus",
      d.ok ? "Teste enviado via " + d.provider + "! Verifique seu WhatsApp."
           : "Falha no teste (" + d.provider + "): " + d.erro,
      d.ok ? "ok" : "error");
  } catch (e) {
    hideLoader();
    showStatus("searchStatus", "Falha: " + e.message, "error");
  }
  refreshDisparo();
}

async function clearDisp() {
  await fetch("/api/disparo/limpar", { method: "POST" });
  refreshDisparo();
}

// ===== CONVERSAS WHATSAPP =====
let waJid = "";
let waPoll = null;
let waChatsCache = [];
let waLimit = 50;

function tempoRel(iso) {
  if (!iso) return "";
  const t = new Date(iso).getTime();
  if (isNaN(t)) return String(iso).slice(0, 16).replace("T", " ");
  const diff = Date.now() - t;
  if (diff < 0) return "agora";
  const min = Math.floor(diff / 60000);
  if (min < 1) return "agora";
  if (min < 60) return "há " + min + "min";
  const h = Math.floor(min / 60);
  if (h < 24) return "há " + h + "h";
  const d = Math.floor(h / 24);
  if (d === 1) return "ontem";
  if (d < 7) return "há " + d + " dias";
  const dt = new Date(t);
  return ("0" + dt.getDate()).slice(-2) + "/" + ("0" + (dt.getMonth() + 1)).slice(-2);
}

function renderWaChats() {
  const box = $("waChats");
  const q = ($("waSearch").value || "").trim().toLowerCase();
  const qDigits = q.replace(/\D/g, "");
  const arr = waChatsCache.filter(function (c) {
    if (!q) return true;
    if ((c.nome || "").toLowerCase().indexOf(q) !== -1) return true;
    if (qDigits && (c.telefone || "").indexOf(qDigits) !== -1) return true;
    return false;
  });
  if (!arr.length) {
    box.innerHTML = "<p class='hint'>" + (waChatsCache.length ? "Nenhuma conversa bate com a busca." : "Nenhuma conversa.") + "</p>";
    return;
  }
  box.innerHTML = arr.map(function (c) {
    return (
      "<div class='wa-chat" + (c.jid === waJid ? " selected" : "") + (c.nao_lidas ? " unread" : "") + "' onclick=\"openWaChat('" + c.jid.replace(/'/g, "") + "')\">" +
      (c.foto ? "<img src='" + esc(c.foto) + "' class='crm-avatar' loading='lazy' alt=''>" : "<div class='crm-avatar'>" + esc(initials(c.nome)) + "</div>") +
      "<div style='min-width:0;flex:1;'>" +
      "<div class='crm-name'>" + esc(c.nome) +
      (c.nao_lidas ? " <span class='wa-unread'>" + c.nao_lidas + "</span>" : "") + "</div>" +
      "<div class='biz-sub2'>" + esc(c.ultima || "") + "</div>" +
      "</div>" +
      "<span class='wa-when'>" + esc(tempoRel(c.quando)) + "</span>" +
      "</div>"
    );
  }).join("");
}

async function loadWaChats() {
  const box = $("waChats");
  box.innerHTML = "<p class='hint'>Carregando conversas...</p>";
  try {
    const r = await fetch("/api/wa/chats");
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "Erro");
    waChatsCache = d.chats || [];
    const unread = waChatsCache.reduce(function (s, c) { return s + (c.nao_lidas || 0); }, 0);
    const badge = $("tabWaBadge");
    if (badge) {
      badge.textContent = unread;
      badge.classList.toggle("hidden", !unread);
    }
    $("waStatus").textContent = waChatsCache.length + " conversas";
    renderWaChats();
  } catch (e) {
    box.innerHTML = "<p class='status error'>Falha: " + esc(e.message) + "</p>";
    $("waStatus").textContent = "offline";
  }
}

window.openWaChat = async function (jid) {
  waJid = jid;
  waLimit = 50;
  document.querySelectorAll(".wa-chat").forEach(function (el) {
    el.classList.toggle("selected", el.getAttribute("onclick").indexOf(jid) !== -1);
  });
  const c = waChatsCache.find(function (x) { return x.jid === jid; });
  const fone = c ? (c.telefone || "") : "";
  $("waThreadHead").innerHTML =
    "<div style='display:flex;align-items:center;gap:10px;'>" +
    (c && c.foto ? "<img src='" + esc(c.foto) + "' class='crm-avatar' style='width:36px;height:36px;min-width:36px;min-height:36px;' alt=''>" : "") +
    "<div style='min-width:0;'><b>" + esc(c ? c.nome : jid) + "</b>" +
    (fone ? "<div class='hint' style='margin:0;'>" + esc(fone) + "</div>" : "") + "</div>" +
    (fone ? "<button class='btn small' style='margin-left:auto;' onclick='verLeadWa(\"" + esc(fone) + "\")'>Ver lead</button>" : "") +
    "</div>";
  $("waReply").classList.remove("hidden");
  await loadWaMsgs();
  clearInterval(waPoll);
  waPoll = setInterval(function () {
    if (!$("secConversas").classList.contains("hidden") && waJid) loadWaMsgs(true);
  }, 8000);
};

window.verLeadWa = async function (fone) {
  try {
    const r = await fetch("/api/wa/lead?telefone=" + encodeURIComponent(fone));
    const d = await r.json();
    if (d.lead) {
      lastBusiness = d.lead;
      switchTab("crm");
      showStatus("searchStatus", "Lead da conversa: " + d.lead.nome, "info");
    } else {
      showStatus("searchStatus", "Este contato ainda não é um lead minerado.", "info");
      switchTab("crm");
    }
  } catch (e) {
    showStatus("searchStatus", "Falha: " + e.message, "error");
  }
};

function diaKey(ts) {
  try {
    const d = new Date(Number(ts) * 1000);
    if (isNaN(d.getTime())) return "";
    return ("0" + d.getDate()).slice(-2) + "/" + ("0" + (d.getMonth() + 1)).slice(-2) + "/" + d.getFullYear();
  } catch (e) { return ""; }
}

async function loadWaMsgs(quiet) {
  if (!waJid) return;
  try {
    const r = await fetch("/api/wa/mensagens?jid=" + encodeURIComponent(waJid) + "&limite=" + waLimit);
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "Erro");
    const box = $("waMsgs");
    const msgs = d.mensagens || [];
    let html = "<button class='btn small' id='waMore'>Carregar mais antigas</button>";
    let lastDay = "";
    html += msgs.map(function (m) {
      let div = "";
      const day = diaKey(m.ts);
      if (day && day !== lastDay) {
        lastDay = day;
        div += "<div class='wa-day'>" + day + "</div>";
      }
      div += "<div class='wa-msg " + (m.de_mim ? "mine" : "theirs") + "'>" +
        (m.texto ? esc(m.texto) : "<i class='hint'>[mídia]</i>") +
        "<span class='wa-time'>" + esc(m.quando || "") + "</span></div>";
      return div;
    }).join("");
    box.innerHTML = msgs.length ? html : "<p class='hint'>Sem mensagens.</p>";
    const more = $("waMore");
    if (more) {
      more.addEventListener("click", function () {
        waLimit += 50;
        loadWaMsgs(true);
      });
    }
    box.scrollTop = box.scrollHeight;
  } catch (e) {
    if (!quiet) $("waMsgs").innerHTML = "<p class='status error'>Falha: " + esc(e.message) + "</p>";
  }
}

async function sendWaReply() {
  const txt = $("waInput").value.trim();
  if (!txt || !waJid) return;
  $("waInput").value = "";
  try {
    const r = await fetch("/api/wa/responder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jid: waJid, texto: txt })
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "Erro");
    await loadWaMsgs(true);
  } catch (e) {
    showStatus("searchStatus", "Falha ao responder: " + e.message, "error");
  }
}

// ===== CRM =====
let crmCache = [];

const CRM_STAGES = [
  ["novo", "Novos"],
  ["enviado", "Enviados"],
  ["contatado", "Contatados"],
  ["respondido", "Responderam"],
  ["negociando", "Negociando"],
  ["fechado", "Fechados"],
  ["perdido", "Perdidos"]
];

async function loadCrm() {
  const board = $("crmBoard");
  board.innerHTML = "<p class='hint'>Carregando leads da nuvem...</p>";
  let leads = [];
  let erroCarga = "";
  try {
    const r = await fetch("/api/crm/leads?limite=500");
    if (!r.ok) throw new Error("HTTP " + r.status);
    const d = await r.json();
    leads = d.leads || [];
  } catch (e) {
    leads = [];
    erroCarga = e.message;
  }

  if (!leads.length && bizCache.length) {
    leads = bizCache.map(function (b) {
      return {
        id: "local-" + b.nome,
        nome: b.nome, categoria: b.categoria, nota: b.nota, avaliacoes: b.avaliacoes,
        cidade: b.cidade, estado: b.estado, telefone: b.telefone, website: b.website,
        foto: b.foto, score_oportunidade: b.score_oportunidade, nivel: b.nivel || b.nivel_ia,
        contato_status: isContacted(b.nome) ? "contatado" : "novo",
        observacao: "", _local: true
      };
    });
    board.dataset.fonte = "sessão (nuvem vazia/offline)";
  } else {
    board.dataset.fonte = "nuvem";
  }

  crmCache = leads;

  const ufs = {};
  leads.forEach(function (l) { if (l.estado) ufs[l.estado] = true; });
  const sel = $("crmUf");
  const cur = sel.value;
  sel.innerHTML = '<option value="">UF: todas</option>' + Object.keys(ufs).sort().map(function (u) {
    return '<option value="' + esc(u) + '">' + esc(u) + "</option>";
  }).join("");
  sel.value = cur;

  const badge = $("tabCrmBadge");
  if (badge) {
    badge.textContent = leads.length;
    badge.classList.toggle("hidden", !leads.length);
  }

  if (erroCarga && !leads.length && !bizCache.length) {
    board.innerHTML = "<div class='crm-empty-col' style='padding:26px;'>Falha ao carregar da nuvem: " +
      esc(erroCarga) + "<br><br><button class='btn small primary' onclick='loadCrm()'>Tentar de novo</button></div>";
    renderCrmKpis([]);
    return;
  }

  renderCrmBoard();
}

function crmFiltered() {
  const q = ($("crmBusca").value || "").trim().toLowerCase();
  const uf = $("crmUf").value;
  const st = $("crmStatus").value;
  const ms = parseInt($("crmScore").value, 10) || 0;
  return crmCache.filter(function (l) {
    if (q && !(String(l.nome || "").toLowerCase().includes(q) ||
               String(l.cidade || "").toLowerCase().includes(q) ||
               String(l.categoria || "").toLowerCase().includes(q))) return false;
    if (uf && String(l.estado || "").toUpperCase() !== uf) return false;
    if (st && String(l.contato_status || "novo") !== st) return false;
    if (ms && (l.score_oportunidade || 0) < ms) return false;
    return true;
  });
}

function renderCrmBoard() {
  let arr = crmFiltered();
  if (crmSort === "score") {
    arr = arr.slice().sort(function (a, b) { return (b.score_oportunidade || -1) - (a.score_oportunidade || -1); });
  } else if (crmSort === "nome") {
    arr = arr.slice().sort(function (a, b) { return String(a.nome || "").localeCompare(String(b.nome || "")); });
  } else if (crmSort === "recentes") {
    arr = arr.slice().sort(function (a, b) { return String(b.created_at || "") < String(a.created_at || "") ? -1 : 1; });
  }
  const board = $("crmBoard");
  if (!crmCache.length) {
    board.innerHTML = "<div class='crm-empty-col' style='padding:26px;'>Nenhum lead na nuvem ainda.<br>Faça uma busca para minerar — tudo cai aqui automaticamente.</div>";
    renderCrmKpis([]);
    return;
  }
  if (!arr.length) {
    board.innerHTML = "<div class='crm-empty-col' style='padding:26px;'>Nenhum lead com esses filtros.<br><br><button class='btn small primary' onclick='clearCrmFilters()'>Limpar filtros</button></div>";
    renderCrmKpis(crmCache);
    return;
  }
  renderCrmKpis(arr);

  board.innerHTML = CRM_STAGES.map(function (pair) {
    const st = pair[0], label = pair[1];
    const dot = { novo: "#a94fff", enviado: "#2ea6ff", contatado: "#ffce54",
                  respondido: "#4dd07a", negociando: "#ff9f43", fechado: "#3cc878",
                  perdido: "#ff4757" }[st] || "#70818f";
    const cards = arr.filter(function (l) { return String(l.contato_status || "novo") === st; });
    let html = "<div class='crm-col' data-stage='" + st + "'>";
    html += "<div class='crm-col-head'><span><span class='stage-dot' style='background:" + dot + ";box-shadow:0 0 8px " + dot + ";'></span>" + label + "</span><span class='tag'>" + cards.length + "</span></div>";
    html += "<div class='crm-col-body'>";
    html += cards.map(function (l) { return crmCard(l); }).join("") || "<div class='crm-empty-col'>Nenhum lead neste estágio</div>";
    html += "</div></div>";
    return html;
  }).join("");
}

let crmSelected = {};
let crmSort = "score";

function scoreRing(s) {
  if (s == null) return "";
  const col = s >= 70 ? "#3cc878" : (s < 45 ? "#ff4757" : "#ffce54");
  return "<span class='score-ring' title='Score IA: " + s + "%'>" +
    "<svg viewBox='0 0 36 36'><circle cx='18' cy='18' r='15.9' class='ring-bg'/>" +
    "<circle cx='18' cy='18' r='15.9' class='ring-fg' stroke='" + col +
    "' stroke-dasharray='" + s + ", 100'/></svg>" +
    "<b>" + s + "</b></span>";
}

function kpiIcon(path) {
  return "<span class='kpi-ico'><svg viewBox='0 0 24 24'><path d='" + path + "'/></svg></span>";
}

const ICO = {
  total: "M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5s-3 1.34-3 3 1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z",
  novo: "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm5 11h-4v4h-2v-4H7v-2h4V7h2v4h4v2z",
  andamento: "M7 2v11h3v9l7-12h-4l4-8z",
  fechado: "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z",
  taxa: "M16 6l2.29 2.29-4.88 4.88-4-4L2 16.59 3.41 18l6-6 4 4 6.3-6.29L22 12V6z",
  score: "M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z",
  fone: "M6.62 10.79c1.44 2.83 3.76 5.14 6.59 6.59l2.2-2.2c.27-.27.67-.36 1.02-.24 1.12.37 2.33.57 3.57.57.55 0 1 .45 1 1V20c0 .55-.45 1-1 1-9.39 0-17-7.61-17-17 0-.55.45-1 1-1h3.5c.55 0 1 .45 1 1 0 1.25.2 2.45.57 3.57.11.35.03.74-.25 1.02l-2.2 2.2z",
  site: "M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zm6.93 6h-2.95c-.32-1.25-.78-2.45-1.38-3.56 1.84.63 3.37 1.91 4.33 3.56zM12 4.04c.83 1.2 1.48 2.53 1.91 3.96h-3.82c.43-1.43 1.08-2.76 1.91-3.96zM4.26 14C4.1 13.36 4 12.69 4 12s.1-1.36.26-2h3.38c-.08.66-.14 1.32-.14 2 0 .68.06 1.34.14 2H4.26zm.82 2h2.95c.32 1.25.78 2.45 1.38 3.56-1.84-.63-3.37-1.9-4.33-3.56zm2.95-8H5.08c.96-1.66 2.49-2.93 4.33-3.56C8.81 5.55 8.35 6.75 8.03 8zM12 19.96c-.83-1.2-1.48-2.53-1.91-3.96h3.82c-.43 1.43-1.08 2.76-1.91 3.96zM14.34 14H9.66c-.09-.66-.16-1.32-.16-2 0-.68.07-1.35.16-2h4.68c.09.65.16 1.32.16 2 0 .68-.07 1.34-.16 2zm.27 5.56c.6-1.11 1.06-2.31 1.38-3.56h2.95c-.96 1.65-2.49 2.93-4.33 3.56zM16.36 14c.08-.66.14-1.32.14-2 0-.68-.06-1.34-.14-2h3.38c.16.64.26 1.31.26 2s-.1 1.36-.26 2h-3.38z"
};

function crmCard(l) {
  const score = l.score_oportunidade;
  const scoreHtml = score != null
    ? "<span class='pill " + (score >= 70 ? "high" : (score < 45 ? "low" : "med")) + "'>" + score + "%</span>" : "";
  const opts = CRM_STAGES.map(function (pair) {
    return "<option value='" + pair[0] + "'" + (String(l.contato_status || "novo") === pair[0] ? " selected" : "") + ">" + pair[1] + "</option>";
  }).join("");
  const waDigits = String(l.telefone || "").replace(/\D/g, "");
  const waLink = waDigits.length >= 10
    ? "https://wa.me/" + (waDigits.length <= 11 && waDigits.slice(0, 2) !== "55" ? "55" + waDigits : waDigits)
    : "";
  const lid = String(l.id || "").replace(/"/g, "");
  const checked = crmSelected[lid] ? " checked" : "";

  let extra = "";
  if (l.endereco) extra += "<div><b>Endereço:</b> " + esc(l.endereco) + "</div>";
  if (l.horarios) extra += "<div><b>Horários:</b> " + esc(l.horarios) + "</div>";
  if (l.status_funcionamento) extra += "<div><b>Status:</b> " + esc(l.status_funcionamento) + "</div>";
  if (l.descricao) extra += "<div><b>Sobre:</b> " + esc(String(l.descricao).slice(0, 220)) + "</div>";
  if (l.website) extra += "<div><b>Site:</b> <a class='link' href='" + esc(l.website) + "' target='_blank'>" + esc(l.website) + "</a></div>";

  return (
    "<div class='crm-card' id='crm-" + esc(lid) + "'>" +
    "<div class='crm-card-top'>" +
    "<input type='checkbox' class='crm-check' data-id='" + esc(lid) + "'" + checked + " title='Selecionar para ação em massa'>" +
    (l.foto ? "<img src='" + esc(l.foto) + "' class='crm-avatar' loading='lazy' alt='' onerror=\"this.outerHTML='<div class=\\'crm-avatar\\'>" + esc(initials(l.nome)) + "</div>'\">" : "<div class='crm-avatar'>" + esc(initials(l.nome)) + "</div>") +
    "<div style='min-width:0;flex:1;'>" +
    "<div class='crm-name'>" + esc(l.nome) + "</div>" +
    "<div class='biz-sub2'>" + esc(l.categoria || "—") + "</div>" +
    "<div class='biz-sub2'>" +
    (l.nota ? "★ " + esc(l.nota) + (l.avaliacoes ? " (" + esc(l.avaliacoes) + ")" : "") + " · " : "") +
    esc([l.cidade, l.estado].filter(Boolean).join(" - ")) +
    (l.telefone ? " · " + esc(l.telefone) : "") + "</div>" +
    "</div>" +
    "</div>" +
    "<div class='biz-meta' style='margin-top:8px;'>" + scoreRing(score) +
    (waLink ? "<a class='btn small wa' style='font-size:11px;padding:4px 10px;' href='" + waLink + "' target='_blank'>WhatsApp</a>" : "") +
    "<button class='btn small' onclick='showLeadDetails(\"" + esc(lid) + "\")'>Detalhes</button>" +
    "<button class='btn small' onclick='toggleCrmExtra(\"" + esc(lid) + "\")'>Ver mais</button>" +
    "</div>" +
    "<div class='crm-extra hidden' id='extra-" + esc(lid) + "'>" + (extra || "<span class='hint'>Sem detalhes extras.</span>") + "</div>" +
    "<select class='crm-stage' data-id='" + esc(lid) + "' data-nome='" + esc(l.nome || "") + "'>" + opts + "</select>" +
    (l.observacao ? "<div class='crm-obs'>" + esc(l.observacao) + "</div>" : "") +
    "<button class='btn small' style='margin-top:8px;' onclick='editCrmObs(\"" + esc(lid) + "\")'>Anotação</button>" +
    "</div>"
  );
}

window.toggleCrmExtra = function (id) {
  const el = $("extra-" + id);
  if (el) el.classList.toggle("hidden");
};

function renderBulkBar() {
  const n = Object.keys(crmSelected).length;
  const bar = $("crmBulkBar");
  if (!bar) return;
  if (!n) {
    bar.classList.add("hidden");
    return;
  }
  bar.classList.remove("hidden");
  $("crmBulkCount").textContent = n + " selecionado(s)";
}

window.crmBulkMove = async function () {
  const stage = $("crmBulkStage").value;
  const ids = Object.keys(crmSelected);
  if (!ids.length || !stage) return;
  showLoader("Movendo " + ids.length + " lead(s)...");
  try {
    for (const id of ids) {
      await crmSetStatus(id, stage, undefined, null);
    }
    crmSelected = {};
    hideLoader();
  } catch (e) {
    hideLoader();
  }
  renderBulkBar();
  renderCrmBoard();
};

window.crmBulkClear = function () {
  crmSelected = {};
  document.querySelectorAll(".crm-check").forEach(function (cb) { cb.checked = false; });
  renderBulkBar();
};

window.clearCrmFilters = function () {
  $("crmBusca").value = "";
  $("crmUf").value = "";
  $("crmStatus").value = "";
  $("crmScore").value = "0";
  renderCrmBoard();
};

function renderCrmKpis(arr) {
  const grid = $("crmKpis");
  const total = arr.length;
  const by = function (s) { return arr.filter(function (l) { return String(l.contato_status || "novo") === s; }).length; };
  const novos = by("novo"), fech = by("fechado"), perd = by("perdido");
  const andamento = total - novos - fech - perd;
  const taxa = total ? Math.round(fech / total * 100) : 0;
  const scored = arr.filter(function (l) { return l.score_oportunidade != null; });
  const media = scored.length ? Math.round(scored.reduce(function (s, l) { return s + l.score_oportunidade; }, 0) / scored.length) : 0;

  function stat(label, value, cls, icon) {
    return "<div class='perf-stat " + (cls || "") + "'>" + kpiIcon(ICO[icon] || ICO.total) +
      "<div><div class='perf-num'>" + value + "</div><div class='perf-label'>" + label + "</div></div></div>";
  }
  grid.innerHTML =
    stat("Total de leads", total, "", "total") +
    stat("Novos", novos, "", "novo") +
    stat("Em andamento", andamento, "", "andamento") +
    stat("Fechados", fech, fech > 0 ? "ok" : "", "fechado") +
    stat("Taxa fechamento", taxa + "%", taxa >= 20 ? "ok" : "", "taxa") +
    stat("Score médio", scored.length ? media + "%" : "—", "", "score") +
    stat("Com telefone", arr.filter(function (l) { return l.telefone; }).length, "", "fone") +
    stat("Com site", arr.filter(function (l) { return l.website; }).length, "", "site");

  const fonte = $("crmBoard").dataset.fonte;
  if (fonte) {
    grid.innerHTML += "<div style='grid-column:1/-1;'><span class='hint'>Fonte: " + esc(fonte) + " · " + total + " leads</span></div>";
  }
}

document.addEventListener("change", function (ev) {
  if (ev.target && ev.target.classList && ev.target.classList.contains("crm-stage")) {
    const sel = ev.target;
    crmSetStatus(sel.dataset.id, sel.value, null, sel);
  }
  if (ev.target && ev.target.id === "crmSortSel") {
    crmSort = ev.target.value;
    renderCrmBoard();
  }
  if (ev.target && ev.target.classList && ev.target.classList.contains("crm-check")) {
    const id = ev.target.dataset.id;
    if (ev.target.checked) crmSelected[id] = true;
    else delete crmSelected[id];
    renderBulkBar();
  }
});

async function crmSetStatus(id, status, observacao, selEl) {
  const lead = crmCache.find(function (l) { return String(l.id) === String(id); });
  const body = { id: id, status: status };
  if (lead && !lead._local) {
    if (observacao !== undefined && observacao !== null) body.observacao = observacao;
  } else if (lead) {
    lead.contato_status = status;
    if (observacao !== undefined && observacao !== null) lead.observacao = observacao;
    if (lead._local && lead.id && lead.id.indexOf("local-") === 0) {
      const real = bizCache.find(function (b) { return b.nome === lead.nome; });
      if (real) {
        if (status === "contatado" && !isContacted(real.nome)) toggleContacted(real.nome);
        if (status === "novo" && isContacted(real.nome)) toggleContacted(real.nome);
      }
    }
    renderCrmBoard();
    return;
  }
  try {
    const r = await fetch("/api/crm/status", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    const d = await r.json();
    if (!r.ok || !d.ok) throw new Error((d && d.detail) || "falha ao salvar");
    if (lead) {
      lead.contato_status = status;
      if (observacao !== undefined && observacao !== null) lead.observacao = observacao;
    }
    renderCrmBoard();
  } catch (e) {
    showStatus("searchStatus", "Falha ao salvar status: " + e.message, "error");
    if (selEl && lead) selEl.value = lead.contato_status || "novo";
  }
}

window.editCrmObs = function (id) {
  const lead = crmCache.find(function (l) { return String(l.id) === String(id); });
  if (!lead) return;
  const atual = lead.observacao || "";
  const nova = prompt("Anotação para " + (lead.nome || "lead") + ":", atual);
  if (nova === null) return;
  crmSetStatus(id, lead.contato_status || "novo", nova, null);
};

init();