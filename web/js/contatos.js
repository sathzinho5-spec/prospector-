// proposito: quem ja foi contatado e a fila de contato do painel
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

