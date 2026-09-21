// proposito: cartao do lead, acao em massa e KPIs do CRM
function scoreRing(s) {
  if (s == null) return "";
  const col = s >= 70 ? "#3cc878" : (s < 45 ? "#ff4757" : "#ffce54");
  return "<span class='score-ring' title='Score IA: " + s + "%'>" +
    "<svg viewBox='0 0 36 36'><circle cx='18' cy='18' r='15.9' class='ring-bg'/>" +
    "<circle cx='18' cy='18' r='15.9' class='ring-fg' stroke='" + col +
    "' stroke-dasharray='" + s + ", 100'/></svg>" +
    "<b>" + s + "</b></span>";
}

function kpiIcon(path) {
  return "<span class='kpi-ico'><svg viewBox='0 0 24 24'><path d='" + path + "'/></svg></span>";
}

const ICO = {
  total: "M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5s-3 1.34-3 3 1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z",
  novo: "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm5 11h-4v4h-2v-4H7v-2h4V7h2v4h4v2z",
  andamento: "M7 2v11h3v9l7-12h-4l4-8z",
  fechado: "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z",
  taxa: "M16 6l2.29 2.29-4.88 4.88-4-4L2 16.59 3.41 18l6-6 4 4 6.3-6.29L22 12V6z",
  score: "M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z",
  fone: "M6.62 10.79c1.44 2.83 3.76 5.14 6.59 6.59l2.2-2.2c.27-.27.67-.36 1.02-.24 1.12.37 2.33.57 3.57.57.55 0 1 .45 1 1V20c0 .55-.45 1-1 1-9.39 0-17-7.61-17-17 0-.55.45-1 1-1h3.5c.55 0 1 .45 1 1 0 1.25.2 2.45.57 3.57.11.35.03.74-.25 1.02l-2.2 2.2z",
  site: "M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zm6.93 6h-2.95c-.32-1.25-.78-2.45-1.38-3.56 1.84.63 3.37 1.91 4.33 3.56zM12 4.04c.83 1.2 1.48 2.53 1.91 3.96h-3.82c.43-1.43 1.08-2.76 1.91-3.96zM4.26 14C4.1 13.36 4 12.69 4 12s.1-1.36.26-2h3.38c-.08.66-.14 1.32-.14 2 0 .68.06 1.34.14 2H4.26zm.82 2h2.95c.32 1.25.78 2.45 1.38 3.56-1.84-.63-3.37-1.9-4.33-3.56zm2.95-8H5.08c.96-1.66 2.49-2.93 4.33-3.56C8.81 5.55 8.35 6.75 8.03 8zM12 19.96c-.83-1.2-1.48-2.53-1.91-3.96h3.82c-.43 1.43-1.08 2.76-1.91 3.96zM14.34 14H9.66c-.09-.66-.16-1.32-.16-2 0-.68.07-1.35.16-2h4.68c.09.65.16 1.32.16 2 0 .68-.07 1.34-.16 2zm.27 5.56c.6-1.11 1.06-2.31 1.38-3.56h2.95c-.96 1.65-2.49 2.93-4.33 3.56zM16.36 14c.08-.66.14-1.32.14-2 0-.68-.06-1.34-.14-2h3.38c.16.64.26 1.31.26 2s-.1 1.36-.26 2h-3.38z"
};

// Espelha cloud_store.disparo_liberado: campo ausente ou nulo conta como
// ligado, para lead recem-minerado nao aparecer barrado sem ninguem ter barrado.
function dispAtivoDe(l) {
  const v = l ? l.disparo_ativo : undefined;
  return (v === undefined || v === null) ? true : !!v;
}

function crmCard(l) {
  const score = l.score_oportunidade;
  // ACHADO, nao e sujeira: este scoreHtml e montado e nunca usado no cartao.
  // Parece pastilha de score que faltou ser ligada, nao codigo morto de verdade.
  // Apagar esconderia a pergunta, entao fica silenciado com o motivo a vista.
  // eslint-disable-next-line no-unused-vars
  const scoreHtml = score != null
    ? "<span class='pill " + (score >= 70 ? "high" : (score < 45 ? "low" : "med")) + "'>" + score + "%</span>" : "";
  const opts = CRM_STAGES.map(function (pair) {
    return "<option value='" + pair[0] + "'" + (String(l.contato_status || "novo") === pair[0] ? " selected" : "") + ">" + pair[1] + "</option>";
  }).join("");
  const waDigits = String(l.telefone || "").replace(/\D/g, "");
  const waLink = waDigits.length >= 10
    ? "https://wa.me/" + (waDigits.length <= 11 && waDigits.slice(0, 2) !== "55" ? "55" + waDigits : waDigits)
    : "";
  const lid = String(l.id || "").replace(/"/g, "");
  const dispAtivo = dispAtivoDe(l);
  const checked = crmSelected[lid] ? " checked" : "";

  let extra = "";
  if (l.endereco) extra += "<div><b>Endereço:</b> " + esc(l.endereco) + "</div>";
  if (l.horarios) extra += "<div><b>Horários:</b> " + esc(l.horarios) + "</div>";
  if (l.status_funcionamento) extra += "<div><b>Status:</b> " + esc(l.status_funcionamento) + "</div>";
  if (l.descricao) extra += "<div><b>Sobre:</b> " + esc(String(l.descricao).slice(0, 220)) + "</div>";
  if (l.website) extra += "<div><b>Site:</b> <a class='link' href='" + esc(l.website) + "' target='_blank'>" + esc(l.website) + "</a></div>";

  return (
    "<div class='crm-card' id='crm-" + esc(lid) + "'>" +
    "<div class='crm-card-top'>" +
    "<input type='checkbox' class='crm-check' data-id='" + esc(lid) + "'" + checked + " title='Selecionar para ação em massa'>" +
    (l.foto ? "<img src='" + esc(l.foto) + "' class='crm-avatar' loading='lazy' alt='' onerror=\"this.outerHTML='<div class=\\'crm-avatar\\'>" + esc(initials(l.nome)) + "</div>'\">" : "<div class='crm-avatar'>" + esc(initials(l.nome)) + "</div>") +
    "<div style='min-width:0;flex:1;'>" +
    "<div class='crm-name'>" + esc(l.nome) + "</div>" +
    "<div class='biz-sub2'>" + esc(l.categoria || "—") + "</div>" +
    "<div class='biz-sub2'>" +
    (l.nota ? "★ " + esc(l.nota) + (l.avaliacoes ? " (" + esc(l.avaliacoes) + ")" : "") + " · " : "") +
    esc([l.cidade, l.estado].filter(Boolean).join(" - ")) +
    (l.telefone ? " · " + esc(l.telefone) : "") + "</div>" +
    "<div style='margin-top:4px;'><span class='pill " + (dispAtivo ? "open" : "closed") + "'>" +
    (dispAtivo ? "disparo ligado" : "disparo desligado") + "</span></div>" +
    "</div>" +
    "</div>" +
    "<div class='biz-meta' style='margin-top:8px;'>" + scoreRing(score) +
    (waLink ? "<a class='btn small wa' style='font-size:11px;padding:4px 10px;' href='" + waLink + "' target='_blank'>WhatsApp</a>" : "") +
    "<button class='btn small' onclick='showLeadDetails(\"" + esc(lid) + "\")'>Detalhes</button>" +
    "<button class='btn small' onclick='toggleCrmExtra(\"" + esc(lid) + "\")'>Ver mais</button>" +
    "<button class='btn small' title='Liga ou desliga este lead para o disparo' " +
    "onclick='toggleDisparoLead(\"" + esc(lid) + "\")'>" +
    (dispAtivo ? "Desligar disparo" : "Ligar disparo") + "</button>" +
    "</div>" +
    "<div class='crm-extra hidden' id='extra-" + esc(lid) + "'>" + (extra || "<span class='hint'>Sem detalhes extras.</span>") + "</div>" +
    "<select class='crm-stage' data-id='" + esc(lid) + "' data-nome='" + esc(l.nome || "") + "'>" + opts + "</select>" +
    (l.observacao ? "<div class='crm-obs'>" + esc(l.observacao) + "</div>" : "") +
    "<button class='btn small' style='margin-top:8px;' onclick='editCrmObs(\"" + esc(lid) + "\")'>Anotação</button>" +
    "</div>"
  );
}

window.toggleCrmExtra = function (id) {
  const el = $("extra-" + id);
  if (el) el.classList.toggle("hidden");
};

function renderBulkBar() {
  const n = Object.keys(crmSelected).length;
  const bar = $("crmBulkBar");
  if (!bar) return;
  if (!n) {
    bar.classList.add("hidden");
    return;
  }
  bar.classList.remove("hidden");
  $("crmBulkCount").textContent = n + " selecionado(s)";
}

window.crmBulkMove = async function () {
  const stage = $("crmBulkStage").value;
  const ids = Object.keys(crmSelected);
  if (!ids.length || !stage) return;
  showLoader("Movendo " + ids.length + " lead(s)...");
  try {
    for (const id of ids) {
      await crmSetStatus(id, stage, undefined, null);
    }
    crmSelected = {};
    hideLoader();
  } catch {
    hideLoader();
  }
  renderBulkBar();
  renderCrmBoard();
};

// Grava o interruptor na nuvem e so mexe na tela depois que a nuvem confirmou:
// pintar antes mostraria "ligado" para um lead que continua desligado no banco.
async function setDisparoAtivo(ids, ativo) {
  const alvos = (ids || []).filter(function (id) {
    const lead = crmCache.find(function (l) { return String(l.id) === String(id); });
    return lead && !lead._local;
  });
  if (!alvos.length) {
    showStatus("searchStatus", "Lead da sessao ainda nao esta na nuvem: nao da pra ligar o disparo dele.", "error");
    return 0;
  }
  const r = await fetch("/api/crm/disparo-ativo", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: alvos, ativo: !!ativo })
  });
  const d = await r.json();
  if (!r.ok || !d.ok) throw new Error((d && d.detail) || "falha ao gravar");
  alvos.forEach(function (id) {
    const lead = crmCache.find(function (l) { return String(l.id) === String(id); });
    if (lead) lead.disparo_ativo = !!ativo;
  });
  return alvos.length;
}

window.toggleDisparoLead = async function (id) {
  const lead = crmCache.find(function (l) { return String(l.id) === String(id); });
  if (!lead) return;
  const alvo = !dispAtivoDe(lead);
  try {
    const n = await setDisparoAtivo([id], alvo);
    if (!n) return;
    showStatus("searchStatus", "Disparo " + (alvo ? "ligado" : "desligado") + " para " + (lead.nome || "o lead") + ".", "ok");
    renderCrmBoard();
  } catch (e) {
    showStatus("searchStatus", "Falha ao mudar o disparo: " + e.message, "error");
  }
};

window.crmBulkDisparo = async function (ativo) {
  const ids = Object.keys(crmSelected);
  if (!ids.length) return;
  showLoader((ativo ? "Ligando" : "Desligando") + " o disparo de " + ids.length + " lead(s)...");
  try {
    const n = await setDisparoAtivo(ids, ativo);
    hideLoader();
    if (!n) return;
    showStatus("searchStatus", "Disparo " + (ativo ? "ligado" : "desligado") + " em " + n + " lead(s).", "ok");
    renderCrmBoard();
  } catch (e) {
    hideLoader();
    showStatus("searchStatus", "Falha ao mudar o disparo: " + e.message, "error");
  }
};

window.crmBulkClear = function () {
  crmSelected = {};
  document.querySelectorAll(".crm-check").forEach(function (cb) { cb.checked = false; });
  renderBulkBar();
};

window.clearCrmFilters = function () {
  $("crmBusca").value = "";
  $("crmUf").value = "";
  $("crmStatus").value = "";
  $("crmScore").value = "0";
  renderCrmBoard();
};

function renderCrmKpis(arr) {
  const grid = $("crmKpis");
  const total = arr.length;
  const by = function (s) { return arr.filter(function (l) { return String(l.contato_status || "novo") === s; }).length; };
  const novos = by("novo"), fech = by("fechado"), perd = by("perdido");
  const andamento = Math.max(0, total - novos - fech - perd);
  const taxa = total ? Math.round(fech / total * 100) : 0;

  function stat(label, value, cls, icon) {
    return "<div class='perf-stat " + (cls || "") + "'>" + kpiIcon(ICO[icon] || ICO.total) +
      "<div><div class='perf-num'>" + value + "</div><div class='perf-label'>" + label + "</div></div></div>";
  }
  grid.innerHTML =
    stat("Total de leads", total, "", "total") +
    stat("Novos", novos, "", "novo") +
    stat("Em andamento", andamento, "", "andamento") +
    stat("Fechados", fech, fech > 0 ? "ok" : "", "fechado") +
    stat("Taxa fechamento", taxa + "%", taxa >= 20 ? "ok" : "", "taxa") +
    stat("Com telefone", arr.filter(function (l) { return l.telefone; }).length, "", "fone") +
    stat("Com site", arr.filter(function (l) { return l.website; }).length, "", "site");

  const fonte = $("crmBoard").dataset.fonte;
  if (fonte) {
    grid.innerHTML += "<div style='grid-column:1/-1;'><span class='hint'>Fonte: " + esc(fonte) + " · " + total + " leads</span></div>";
  }
}

document.addEventListener("change", function (ev) {
  if (ev.target && ev.target.classList && ev.target.classList.contains("crm-stage")) {
    const sel = ev.target;
    crmSetStatus(sel.dataset.id, sel.value, null, sel);
  }
  if (ev.target && ev.target.id === "crmSortSel") {
    crmSort = ev.target.value;
    renderCrmBoard();
  }
  if (ev.target && ev.target.classList && ev.target.classList.contains("crm-check")) {
    const id = ev.target.dataset.id;
    if (ev.target.checked) crmSelected[id] = true;
    else delete crmSelected[id];
    renderBulkBar();
  }
});

async function crmSetStatus(id, status, observacao, selEl) {
  const lead = crmCache.find(function (l) { return String(l.id) === String(id); });
  const body = { id: id, status: status };
  if (lead && !lead._local) {
    if (observacao !== undefined && observacao !== null) body.observacao = observacao;
  } else if (lead) {
    lead.contato_status = status;
    if (observacao !== undefined && observacao !== null) lead.observacao = observacao;
    if (lead._local && lead.id && lead.id.indexOf("local-") === 0) {
      const real = bizCache.find(function (b) { return b.nome === lead.nome; });
      if (real) {
        if (status === "contatado" && !isContacted(real.nome)) toggleContacted(real.nome);
        if (status === "novo" && isContacted(real.nome)) toggleContacted(real.nome);
      }
    }
    renderCrmBoard();
    return;
  }
  try {
    const r = await fetch("/api/crm/status", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    const d = await r.json();
    if (!r.ok || !d.ok) throw new Error((d && d.detail) || "falha ao salvar");
    if (lead) {
      lead.contato_status = status;
      if (observacao !== undefined && observacao !== null) lead.observacao = observacao;
    }
    renderCrmBoard();
  } catch (e) {
    showStatus("searchStatus", "Falha ao salvar status: " + e.message, "error");
    if (selEl && lead) selEl.value = lead.contato_status || "novo";
  }
}

window.editCrmObs = function (id) {
  const lead = crmCache.find(function (l) { return String(l.id) === String(id); });
  if (!lead) return;
  const atual = lead.observacao || "";
  const nova = prompt("Anotação para " + (lead.nome || "lead") + ":", atual);
  if (nova === null) return;
  crmSetStatus(id, lead.contato_status || "novo", nova, null);
};

