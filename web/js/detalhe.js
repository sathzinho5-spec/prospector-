// proposito: modal de detalhe do lead, screenshot e extracao de contato
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
  if (b.website) {
    html += "<div class='detail-row'><span class='detail-label'>Site</span><span><a class='link' href='" +
      esc(b.website) + "' target='_blank' rel='noopener'>" + esc(b.website) + "</a></span></div>";
  }
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

