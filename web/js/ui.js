// proposito: estado compartilhado do painel e as pecas visuais reusadas
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

function scorePill(b) {
  if (b.score_oportunidade == null) return "";
  const s = b.score_oportunidade;
  const cls = s >= 70 ? "high" : (s < 45 ? "low" : "med");
  return "<span class='pill " + cls + "'>IA " + s + "%</span>";
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

