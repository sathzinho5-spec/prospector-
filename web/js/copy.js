// proposito: geracao de copy de venda: pitch, sequencia, objecao e proposta
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

