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

async function exportData(format) {
  const r = await fetch("/api/export?format=" + format);
  if (!r.ok) return;
  const blob = await r.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "negocios." + format;
  a.click();
}

