// proposito: quem ja foi contatado e a fila de contato do painel
// ===== CONTATADOS (localStorage) =====
function getContacted() {
  try { return JSON.parse(localStorage.getItem("pp_contacted") || "[]"); } catch { return []; }
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
    }
  } catch (e) {
    hideLoader();
    showStatus("searchStatus", "Falha: " + e.message, "error");
  }
};

window.toggleAndRender = function (i) {
  const b = bizCache[i];
  if (!b) return;
  toggleContacted(b.nome);
  renderResults(bizCache);
};

