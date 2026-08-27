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
  $("btnQueue").addEventListener("click", function () {
    $("queueCard").classList.remove("hidden");
    renderQueue();
    $("queueCard").scrollIntoView({ behavior: "smooth", block: "nearest" });
  });
  $("btnCloseQueue").addEventListener("click", function () { $("queueCard").classList.add("hidden"); });
  $("btnQuickSearch").addEventListener("click", doSearch);
  $("btnReloadLast").addEventListener("click", reloadLast);
  $("btnPitch").addEventListener("click", doPitch);
  $("btnProposal").addEventListener("click", doProposal);
  $("btnPerf").addEventListener("click", function () {
    $("perfCard").classList.remove("hidden");
    renderPerformance();
    $("perfCard").scrollIntoView({ behavior: "smooth", block: "nearest" });
  });
  $("btnClosePerf").addEventListener("click", function () { $("perfCard").classList.add("hidden"); });
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
    max_results: parseInt($("maxResults").value, 10) || 10
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

    let msg = data.total + " negócios encontrados.";
    if (data.por_local) {
      msg += " " + Object.keys(data.por_local).map(function (k) { return k.split(",")[0] + ": " + data.por_local[k]; }).join(" | ");
    }
    showStatus("searchStatus", msg, "ok");

    $("emptyCard").classList.add("hidden");
    $("homeExtra").classList.add("hidden");
    document.querySelector(".content").classList.remove("empty");
    $("queryTitle").textContent = data.query.charAt(0).toUpperCase() + data.query.slice(1);
    $("exportGroup").classList.remove("hidden");
    renderResults(data.businesses);
  } catch (e) {
    hideLoader();
    showStatus("searchStatus", "Falha: " + e.message, "error");
  }
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
  $("resultsCard").classList.remove("hidden");
  $("resultsCount").textContent = businesses.length;
  $("resultsCount").classList.remove("hidden");

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
        "<div class='avatar'>" + esc(initials(b.nome)) + "</div>" +
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
    out.scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (e) {
    hideLoader();
    showStatus("searchStatus", "Falha ao gerar mensagem: " + e.message, "error");
  }
}

window.copyText = function (btn, which) {
  const out = $("pitchOutput");
  const text = which === "wa" ? out.dataset.wa : out.dataset.email;
  navigator.clipboard.writeText(text).then(function () {
    const old = btn.textContent;
    btn.textContent = "Copiado!";
    setTimeout(function () { btn.textContent = old; }, 1500);
  });
};

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
    out.classList.remove("hidden");
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

window.showDetails = function (i) {
  const b = bizCache[i];
  if (!b) return;
  lastBusiness = b;
  markSelected(i);

  function row(label, value) {
    if (!value) return "";
    return "<div class='detail-row'><span class='detail-label'>" + label + "</span><span>" + esc(value) + "</span></div>";
  }

  let html = "";
  html += "<div class='detail-hero'>";
  html += "<div class='avatar'>" + esc(initials(b.nome)) + "</div>";
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
  html += row("Busca em", b.consulta);
  if (b.atributos && b.atributos.length) {
    html += "<div class='detail-row'><span class='detail-label'>Serviços</span><span>" +
      b.atributos.map(function (a) { return "<span class='tag'>" + esc(a) + "</span>"; }).join(" ") +
      "</span></div>";
  }
  if (b.url) {
    html += "<div class='detail-row'><span class='detail-label'>Maps</span><span><a class='link' href='" +
      esc(b.url) + "' target='_blank'>abrir no Google Maps</a></span></div>";
  }

  html += "<div class='btn-row' style='margin-top:16px'>";
  if (b.website) html += "<button class='btn primary' id='btnContacts'>Extrair contatos do site</button>";
  html += "<button class='btn' id='btnShot'>Salvar imagem do Maps</button>";
  html += "</div>";
  html += "<div id='shotArea'></div>";
  html += "<div id='contactsArea'></div>";

  $("detailBody").innerHTML = html;
  $("detailModal").classList.remove("hidden");

  const btn = $("btnContacts");
  if (btn) btn.addEventListener("click", function () { extractContacts(b.website); });
  $("btnShot").addEventListener("click", function () { saveScreenshot(b); });
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
  markSelected(i);
  $("analyzeCard").classList.remove("hidden");
  $("bizTitle").textContent = lastBusiness.nome;
  $("bizSub").textContent = [lastBusiness.endereco, lastBusiness.telefone].filter(Boolean).join(" | ");
  ["refOutput", "igOutput", "strategyOutput", "pitchOutput", "proposalOutput"].forEach(function (id) { $(id).classList.add("hidden"); });
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
    out.scrollIntoView({ behavior: "smooth", block: "nearest" });
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
      await loadSettings();
      setTimeout(function () { clearStatus("settingsStatus"); }, 3000);
    } else {
      showStatus("settingsStatus", "Erro ao salvar.", "error");
    }
  } catch (e) {
    showStatus("settingsStatus", "Erro ao salvar: " + e.message, "error");
  }
}

init();