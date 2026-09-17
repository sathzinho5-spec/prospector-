// proposito: busca de negocios, filtro dos resultados e exportacao
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

function filteredBusinesses() {
  let arr = bizCache.slice();
  if (filters.texto) {
    const q = filters.texto.trim().toLowerCase();
    const qDigits = q.replace(/\D/g, "");
    if (q) {
      arr = arr.filter(function (b) {
        if (String(b.nome || "").toLowerCase().indexOf(q) !== -1) return true;
        if (String(b.cidade || "").toLowerCase().indexOf(q) !== -1) return true;
        if (String(b.categoria || "").toLowerCase().indexOf(q) !== -1) return true;
        if (qDigits && String(b.telefone || "").indexOf(qDigits) !== -1) return true;
        return false;
      });
    }
  }
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
  if (tableState.sortKey === "nome") {
    arr.sort(function (a, b) {
      const r = String(a.nome || "").localeCompare(String(b.nome || ""));
      return r * tableState.sortDir;
    });
  } else if (tableState.sortKey === "cidade") {
    arr.sort(function (a, b) {
      const r = String(a.cidade || "").localeCompare(String(b.cidade || ""));
      return r * tableState.sortDir;
    });
  }
  return arr;
}

async function loadLeadsView(page) {
  leadsState.page = page || 1;
  const body = $("leadsBody");
  if (!body) return;
  body.innerHTML = "<tr><td colspan='6'><div class='skel' style='width:40%'></div><div class='skel' style='width:60%'></div><div class='skel' style='width:50%'></div></td></tr>";
  try {
    const r = await fetch("/api/crm/leads?limite=500");
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "Erro");
    let arr = d.leads || [];
    const q = (leadsState.q || "").trim().toLowerCase();
    if (q) {
      arr = arr.filter(function (l) {
        return String(l.nome || "").toLowerCase().indexOf(q) !== -1 ||
          String(l.cidade || "").toLowerCase().indexOf(q) !== -1 ||
          String(l.categoria || "").toLowerCase().indexOf(q) !== -1;
      });
    }
    if (leadsState.uf) {
      arr = arr.filter(function (l) { return String(l.estado || "").toUpperCase() === leadsState.uf; });
    }
    $("leadsInfo").textContent = arr.length + " leads na base";
    const tb = $("tabLeadsBadge");
    if (tb) {
      tb.textContent = arr.length;
      tb.classList.toggle("hidden", !arr.length);
    }
    const perPage = leadsState.perPage;
    const pages = Math.max(1, Math.ceil(arr.length / perPage));
    if (leadsState.page > pages) leadsState.page = pages;
    const rows = arr.slice((leadsState.page - 1) * perPage, leadsState.page * perPage);
    if (!rows.length) {
      body.innerHTML = "<tr><td colspan='6'><div class='empty-box'><b>Nenhum lead encontrado</b><span>Ajuste os filtros ou rode uma busca.</span></div></td></tr>";
    } else {
      body.innerHTML = rows.map(function (l) {
        const st = String(l.contato_status || "novo");
        return "<tr>" +
          "<td><div class='cell-main'><div style='min-width:0;'><div class='cell-name'>" + esc(l.nome) + "</div>" +
          "<div class='cell-sub'>" + esc(l.categoria || "—") + "</div></div></div></td>" +
          "<td>" + esc([l.cidade, l.estado].filter(Boolean).join(" - ") || "—") + "</td>" +
          "<td class='nowrap'>" + (esc(l.telefone) || "—") + "</td>" +
          "<td>" + (l.score_oportunidade != null ? "<span class='pill " + (l.score_oportunidade >= 70 ? "high" : (l.score_oportunidade < 45 ? "low" : "med")) + "'>" + l.score_oportunidade + "%</span>" : "—") + "</td>" +
          "<td><span class='pill'>" + esc(st) + "</span></td>" +
          "<td><button class='btn small' onclick='viewCloudLead(\"" + String(l.id || "").replace(/"/g, "") + "\")'>Ver</button></td>" +
          "</tr>";
      }).join("");
    }
    const pg = renderPager(arr.length, leadsState.page, perPage, "gotoLeadsPage");
    leadsState.page = pg.page;
    $("leadsPager").innerHTML = pg.html;
  } catch (e) {
    body.innerHTML = "<tr><td colspan='6'><div class='empty-box'><b>Falha ao carregar leads</b><span>" +
      esc(e.message) + "</span><button class='btn small primary' onclick='loadLeadsView(1)'>Tentar de novo</button></div></td></tr>";
    $("leadsPager").innerHTML = "";
  }
}

window.gotoLeadsPage = function (p) {
  loadLeadsView(p);
};

window.viewCloudLead = async function (id) {
  try {
    const r = await fetch("/api/crm/leads?limite=500");
    const d = await r.json();
    const lead = (d.leads || []).find(function (l) { return String(l.id) === String(id); });
    if (lead) openDetailModal(lead);
  } catch (e) {
    toast("Falha ao abrir lead", "error");
  }
};

async function exportData(format) {
  const r = await fetch("/api/export?format=" + format);
  if (!r.ok) return;
  const blob = await r.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "negocios." + format;
  a.click();
}

