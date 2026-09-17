// proposito: disparo automatico: fila, migracao, envio e status
// ===== DISPARO AUTOMÁTICO =====
let dispPoll = null;
let dispModo = "auto";

function paintModo() {
  document.querySelectorAll("#modoSeg .seg-btn").forEach(function (b) {
    b.classList.toggle("active", b.dataset.modo === dispModo);
  });
  $("modoHint").textContent = dispModo === "auto"
    ? "O robô envia sozinho respeitando pausas, limite e horário."
    : "Você envia um por um pelo botão Enviar de cada linha.";
}

async function setModo(modo) {
  dispModo = modo;
  paintModo();
  try {
    await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ disparo_modo: modo })
    });
  } catch (e) { /* silencioso */ }
}

async function migrarMinerados() {
  showLoader("Puxando todos os leads minerados para a fila...");
  try {
    const r = await fetch("/api/disparo/migrar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ origem: "minerados" })
    });
    const d = await r.json();
    hideLoader();
    if (!r.ok) throw new Error(d.detail || "Erro");
    showStatus("searchStatus",
      d.enfileirados + " leads minerados na fila (de " + d.total_minerados + " no total, sem repetir telefone)!", "ok");
    refreshDisparo();
  } catch (e) {
    hideLoader();
    showStatus("searchStatus", "Falha: " + e.message, "error");
  }
}

window.enviarAgora = async function (id) {
  try {
    const r = await fetch("/api/disparo/enviar-agora", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: id })
    });
    const d = await r.json();
    showStatus("searchStatus",
      d.ok ? "Enviado via " + d.provider + "!" : "Falha: " + d.erro,
      d.ok ? "ok" : "error");
  } catch (e) {
    showStatus("searchStatus", "Falha: " + e.message, "error");
  }
  refreshDisparo();
};

window.refazerMensagem = async function (id, btn) {
  const old = btn ? btn.textContent : "";
  if (btn) { btn.textContent = "Gerando..."; btn.disabled = true; }
  try {
    const r = await fetch("/api/disparo/refazer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: id })
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "Erro");
    showStatus("searchStatus", "Mensagem refeita com " + (d.engine === "local" ? "o motor local" : d.engine) + "! Confira na tabela.", "ok");
  } catch (e) {
    showStatus("searchStatus", "Falha ao refazer: " + e.message, "error");
  } finally {
    if (btn) { btn.textContent = old; btn.disabled = false; }
  }
  refreshDisparo();
};

window.verMensagem = async function (id) {
  try {
    const r = await fetch("/api/disparo/item/" + id);
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "Erro");
    let html = "<div class='detail-hero'>";
    html += "<div class='avatar'>" + esc(initials(d.nome)) + "</div>";
    html += "<div><div class='detail-name'>" + esc(d.nome) + "</div>";
    html += "<div class='biz-sub2'>" + esc(d.telefone) + " · <span class='st-" + d.status + "'>" + d.status + "</span></div></div>";
    html += "</div>";
    if (d.enviado_em) html += "<p class='hint'>Enviada em: " + esc(d.enviado_em) + (d.instancia ? " · via chip <b>" + esc(d.instancia) + "</b>" : "") + "</p>";
    if (d.tentativas) html += "<p class='hint'>Tentativas: " + d.tentativas + "</p>";
    if (d.erro) html += "<p class='status error'>" + esc(d.erro) + "</p>";
    html += "<h4>Mensagem que " + (d.status === "enviado" ? "foi enviada" : "será enviada") + "</h4>";
    html += "<div class='pitch-box' style='white-space:pre-wrap;'>" + esc(d.mensagem || "(vazia)") + "</div>";
    if (d.status === "pendente") {
      html += "<div class='btn-row'><button class='btn small wa' onclick='enviarAgora(" + d.id + ");closeMsgModal();'>Enviar agora</button>" +
        "<button class='btn small' onclick='refazerMensagem(" + d.id + ", null);closeMsgModal();'>Refazer com IA</button></div>";
    }
    $("msgBody").innerHTML = html;
    $("msgModal").classList.remove("hidden");
  } catch (e) {
    showStatus("searchStatus", "Falha: " + e.message, "error");
  }
};

window.closeMsgModal = function () {
  $("msgModal").classList.add("hidden");
};

async function enqueueAll() {
  if (!bizCache.length) {
    showStatus("searchStatus", "Faça uma busca primeiro.", "error");
    return;
  }
  const alvos = bizCache.filter(function (b) { return waPhone(b); });
  if (!alvos.length) {
    showStatus("searchStatus", "Nenhum lead com telefone válido.", "error");
    return;
  }
  showLoader("Gerando mensagens 0/" + alvos.length + "...");
  const itens = [];
  try {
    for (let i = 0; i < alvos.length; i++) {
      const b = alvos[i];
      if (b._pitch && b._pitch.whatsapp) {
        itens.push({ nome: b.nome, telefone: b.telefone, mensagem: b._pitch.whatsapp });
      } else {
        const r = await fetch("/api/business/pitch?rapido=1", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ business: b })
        });
        const d = await r.json();
        if (r.ok && d.whatsapp) {
          b._pitch = d;
          itens.push({ nome: b.nome, telefone: b.telefone, mensagem: d.whatsapp });
        }
      }
      $("loaderText").textContent = "Gerando mensagens " + (i + 1) + "/" + alvos.length + "...";
    }
    const r2 = await fetch("/api/disparo/enfileirar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ itens: itens, origem: $("queryTitle").textContent || "" })
    });
    const d2 = await r2.json();
    hideLoader();
    if (!r2.ok) throw new Error(d2.detail || "Erro");
    showStatus("searchStatus", d2.enfileirados + " leads na fila de disparo!", "ok");
    refreshDisparo();
  } catch (e) {
    hideLoader();
    showStatus("searchStatus", "Falha: " + e.message, "error");
  }
}

async function refreshDisparo() {
  try {
    if (typeof window._instLast === "undefined" || Date.now() - window._instLast > 30000) {
      window._instLast = Date.now();
      refreshInstances();
    }
    const s = await (await fetch("/api/settings")).json();
    if (s.disparo_modo) {
      dispModo = s.disparo_modo;
      paintModo();
    }
    const r = await fetch("/api/disparo/status");
    const st = await r.json();

    const line = $("disparoStatusLine");
    line.textContent = st.rodando
      ? "RODANDO · " + st.enviados_hoje + " hoje · " + st.pendentes + " na fila · próximo: " + (st.proximo_em || "já")
      : "parado · " + st.pendentes + " na fila · " + st.enviados + " enviados";
    line.className = "tag" + (st.rodando ? " on" : "");

    const r2 = await fetch("/api/disparo/fila?limite=50");
    const d2 = await r2.json();
    const rows = (d2.fila || []).map(function (f) {
      const action = f.status === "pendente"
        ? "<button class='btn small wa' onclick='enviarAgora(" + f.id + ")'>Enviar</button>" +
          "<button class='btn small' onclick='refazerMensagem(" + f.id + ", this)'>Refazer IA</button>"
        : "";
      return "<tr><td>" + esc(f.nome) + "</td><td>" + esc(f.telefone) + "</td>" +
        "<td class='st-" + f.status + "'>" + f.status + "</td>" +
        "<td>" + (f.instancia ? esc(f.instancia) : "<span class='hint'>—</span>") + "</td>" +
        "<td>" + esc((f.mensagem || "").slice(0, 60)) + "…</td>" +
        "<td><div class='row-actions'><button class='btn small' onclick='verMensagem(" + f.id + ")'>Ver</button>" + action + "</div></td></tr>";
    }).join("");
    $("disparoTable").innerHTML = rows
      ? "<table class='disp-table'><thead><tr><th>Lead</th><th>Telefone</th><th>Status</th><th>Chip</th><th>Mensagem</th><th></th></tr></thead><tbody>" + rows + "</tbody></table>"
      : "<p class='hint'>Fila vazia. Clique em 'Enfileirar resultados' ou 'Puxar todos os minerados'.</p>";

    clearInterval(dispPoll);
    if (st.rodando) {
      dispPoll = setInterval(refreshDisparo, 5000);
    }
  } catch (e) { /* silencioso */ }
}

async function startDisp() {
  const body = {
    provider: "simulado",
    delay_min: parseFloat($("dispDelayMin").value) || 45,
    delay_max: parseFloat($("dispDelayMax").value) || 120,
    limite_dia: parseInt($("dispLimite").value, 10) || 30,
    hora_ini: $("dispHoraIni").value || "08:00",
    hora_fim: $("dispHoraFim").value || "20:00",
    optout: true
  };
  try {
    const s = await (await fetch("/api/settings")).json();
    body.provider = s.disparo_provider || "simulado";
  } catch (e) { /* usa simulado */ }
  const r = await fetch("/api/disparo/iniciar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  const d = await r.json();
  if (d.iniciado || d.rodando) {
    showStatus("searchStatus", "Disparo rodando no modo " + body.provider + "! Acompanhe aqui.", "ok");
  } else if (d.motivo) {
    showStatus("searchStatus", d.motivo + ". Use o botão Enviar de cada linha.", "info");
  } else {
    showStatus("searchStatus", "Disparo já estava rodando.", "info");
  }
  refreshDisparo();
}

async function pauseDisp() {
  await fetch("/api/disparo/pausar", { method: "POST" });
  clearInterval(dispPoll);
  refreshDisparo();
}

async function testDisp() {
  const phone = prompt("Digite SEU número com DDD para teste (ex: 11999998888):");
  if (!phone) return;
  showLoader("Enviando mensagem de teste...");
  try {
    const r = await fetch("/api/disparo/testar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone: phone })
    });
    const d = await r.json();
    hideLoader();
    showStatus("searchStatus",
      d.ok ? "Teste enviado via " + d.provider + "! Verifique seu WhatsApp."
           : "Falha no teste (" + d.provider + "): " + d.erro,
      d.ok ? "ok" : "error");
  } catch (e) {
    hideLoader();
    showStatus("searchStatus", "Falha: " + e.message, "error");
  }
  refreshDisparo();
}

async function clearDisp() {
  await fetch("/api/disparo/limpar", { method: "POST" });
  refreshDisparo();
}

