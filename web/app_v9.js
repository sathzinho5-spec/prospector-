const $ = (id) => document.getElementById(id);

let lastBusiness = null;
let lastHandle = null;
let bizCache = [];
let loaderInterval = null;

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

async function init() {
  document.querySelector(".content").classList.add("empty");
  await loadNiches();
  await loadSettings();
  bindEvents();
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

    const iaChip = $("iaChip");
    if (s.openai_api_key) {
      iaChip.classList.add("on"); iaChip.classList.remove("off");
      $("iaChipText").textContent = "IA: " + (s.openai_model || "ativa");
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
  });
  document.querySelectorAll("[data-export]").forEach(function (b) {
    b.addEventListener("click", function () { exportData(b.dataset.export); });
  });
  document.querySelectorAll(".modal-overlay").forEach(function (ov) {
    ov.addEventListener("click", function (ev) { if (ev.target === ov) ov.classList.add("hidden"); });
  });
}

async function doSearch() {
  const locations = selectedStates();
  const bairro = $("bairro").value.trim();

  let finalLocations = locations;
  if (bairro && locations.length) {
    finalLocations = locations.map(function (nome) { return bairro + ", " + nome; });
  }

  const payload = {
    query: $("niche").value,
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

function renderResults(businesses) {
  bizCache = businesses;
  $("resultsCard").classList.remove("hidden");
  $("resultsCount").textContent = businesses.length;
  $("resultsCount").classList.remove("hidden");

  const list = $("resultsList");
  list.innerHTML = businesses
    .map(function (b, i) {
      const subParts = [b.categoria, [b.cidade, b.estado].filter(Boolean).join(" - ")]
        .filter(Boolean).join(" · ");
      let meta = "";
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
        "<button class='btn small primary' onclick='event.stopPropagation();selectBusiness(" + i + ", false);doStrategy()'>Estratégia</button>" +
        "<button class='btn small' onclick='event.stopPropagation();selectBusiness(" + i + ", true)'>Instagram</button>" +
        "</div>" +
        "</div>"
      );
    })
    .join("");
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
  ["refOutput", "igOutput", "strategyOutput"].forEach(function (id) { $(id).classList.add("hidden"); });
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
    if (r.ok) {
      showStatus("settingsStatus", "Configurações salvas.", "ok");
      $("apiKey").value = "";
      $("igSession").value = "";
      $("apiKey").placeholder = s.openai_api_key ? "Chave configurada" : "sk-... / gsk-... (opcional)";
      $("igSession").placeholder = s.instagram_sessionid ? "Cookie configurado" : "Opcional - sessionid";
      await loadSettings();
      setTimeout(function () { clearStatus("settingsStatus"); }, 2500);
    } else {
      showStatus("settingsStatus", "Erro ao salvar.", "error");
    }
  } catch (e) {
    showStatus("settingsStatus", "Erro ao salvar: " + e.message, "error");
  }
}

init();