// proposito: CRM: carregar leads, filtrar e montar o quadro por estagio
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

