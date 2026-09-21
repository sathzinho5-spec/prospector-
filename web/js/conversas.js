// proposito: conversas do WhatsApp: listar chats, ler e responder
// ===== CONVERSAS WHATSAPP =====
let waJid = "";
let waPoll = null;
let waChatsCache = [];
let waLimit = 50;
let waInstance = "";
let waConectado = false;

function waInstParam() {
  return waInstance ? "&instance=" + encodeURIComponent(waInstance) : "";
}

function waInstQuery() {
  return waInstance ? "?instance=" + encodeURIComponent(waInstance) : "";
}

// O chip das conversas: a aba sempre lia o Chip 1, entao numero pareado no
// chip 2 ou 3 aparecia como "Nenhuma conversa". Salva a escolha no navegador.
async function loadWaChips() {
  const sel = $("waChip");
  if (!sel) return;
  try {
    const d = await (await fetch("/api/disparo/instancias")).json();
    const arr = d.instancias || [];
    const salvos = [];
    try { salvos.push(localStorage.getItem("waInstance") || ""); } catch { salvos.push(""); }
    sel.innerHTML = arr.map(function (it) {
      const nome = it.instance || "?";
      return "<option value='" + esc(nome) + "'" +
        (salvos[0] && salvos[0] === nome ? " selected" : "") + ">" +
        esc(nome + (it.conectado ? " (conectado)" : "")) + "</option>";
    }).join("") || "<option value=''>sem chip</option>";
    if (salvos[0] && Array.prototype.some.call(sel.options, function (o) { return o.value === salvos[0]; })) {
      waInstance = salvos[0];
    } else {
      waInstance = sel.value || "";
    }
    if (!sel.dataset.bound) {
      sel.dataset.bound = "1";
      sel.addEventListener("change", function () {
        waInstance = sel.value || "";
        try { localStorage.setItem("waInstance", waInstance); } catch { /* sem storage, esquece ao sair */ }
        waJid = "";
        $("waMsgs").innerHTML = "";
        $("waReply").classList.add("hidden");
        loadWaChats();
      });
    }
  } catch {
    /* sem instancias: segue no padrao (chip 1) */
  }
}

function tempoRel(iso) {
  if (!iso) return "";
  const t = new Date(iso).getTime();
  if (isNaN(t)) return String(iso).slice(0, 16).replace("T", " ");
  const diff = Date.now() - t;
  if (diff < 0) return "agora";
  const min = Math.floor(diff / 60000);
  if (min < 1) return "agora";
  if (min < 60) return "há " + min + "min";
  const h = Math.floor(min / 60);
  if (h < 24) return "há " + h + "h";
  const d = Math.floor(h / 24);
  if (d === 1) return "ontem";
  if (d < 7) return "há " + d + " dias";
  const dt = new Date(t);
  return ("0" + dt.getDate()).slice(-2) + "/" + ("0" + (dt.getMonth() + 1)).slice(-2);
}

function renderWaChats() {
  const box = $("waChats");
  const q = ($("waSearch").value || "").trim().toLowerCase();
  const qDigits = q.replace(/\D/g, "");
  const arr = waChatsCache.filter(function (c) {
    if (!q) return true;
    if ((c.nome || "").toLowerCase().indexOf(q) !== -1) return true;
    if (qDigits && (c.telefone || "").indexOf(qDigits) !== -1) return true;
    return false;
  });
  if (!arr.length) {
    let dica = "Nenhuma conversa.";
    if (!waChatsCache.length) {
      dica = "Nenhuma conversa" + (waInstance ? " no chip " + esc(waInstance) : "") + "." +
        "<br><span class='hint'>Se o número tem conversas no celular: confira o chip acima" +
        (waConectado ? "" : " (este parece off)") +
        ", aguarde a sincronização após parear, ou ative o banco na Evolution (sem ele o histórico não lista).</span>";
    }
    box.innerHTML = "<p class='hint'>" + dica + "</p>";
    return;
  }
  box.innerHTML = arr.map(function (c) {
    return (
      "<div class='wa-chat" + (c.jid === waJid ? " selected" : "") + (c.nao_lidas ? " unread" : "") + "' onclick=\"openWaChat('" + c.jid.replace(/'/g, "") + "')\">" +
      (c.foto ? "<img src='" + esc(c.foto) + "' class='crm-avatar' loading='lazy' alt=''>" : "<div class='crm-avatar'>" + esc(initials(c.nome)) + "</div>") +
      "<div style='min-width:0;flex:1;'>" +
      "<div class='crm-name'>" + esc(c.nome) +
      (c.nao_lidas ? " <span class='wa-unread'>" + c.nao_lidas + "</span>" : "") + "</div>" +
      "<div class='biz-sub2'>" + esc(c.ultima || "") + "</div>" +
      "</div>" +
      "<span class='wa-when'>" + esc(tempoRel(c.quando)) + "</span>" +
      "</div>"
    );
  }).join("");
}

async function loadWaChats() {
  const box = $("waChats");
  box.innerHTML = "<p class='hint'>Carregando conversas...</p>";
  try {
    await loadWaChips();
    const r = await fetch("/api/wa/chats" + waInstQuery());
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "Erro");
    waChatsCache = d.chats || [];
    waConectado = !!d.conectado;
    if (d.instance) waInstance = d.instance;
    const unread = waChatsCache.reduce(function (s, c) { return s + (c.nao_lidas || 0); }, 0);
    const badge = $("tabWaBadge");
    if (badge) {
      badge.textContent = unread;
      badge.classList.toggle("hidden", !unread);
    }
    $("waStatus").textContent = waChatsCache.length + " conversas" +
      (waInstance ? " · " + waInstance : "") + (waConectado ? "" : " (chip off?)");
    renderWaChats();
  } catch (e) {
    box.innerHTML = "<p class='status error'>Falha: " + esc(e.message) + "</p>";
    $("waStatus").textContent = "offline";
  }
}

window.openWaChat = async function (jid) {
  waJid = jid;
  waLimit = 50;
  document.querySelectorAll(".wa-chat").forEach(function (el) {
    el.classList.toggle("selected", el.getAttribute("onclick").indexOf(jid) !== -1);
  });
  const c = waChatsCache.find(function (x) { return x.jid === jid; });
  const fone = c ? (c.telefone || "") : "";
  $("waThreadHead").innerHTML =
    "<div style='display:flex;align-items:center;gap:10px;'>" +
    (c && c.foto ? "<img src='" + esc(c.foto) + "' class='crm-avatar' style='width:36px;height:36px;min-width:36px;min-height:36px;' alt=''>" : "") +
    "<div style='min-width:0;'><b>" + esc(c ? c.nome : jid) + "</b>" +
    (fone ? "<div class='hint' style='margin:0;'>" + esc(fone) + "</div>" : "") + "</div>" +
    (fone ? "<button class='btn small' style='margin-left:auto;' onclick='verLeadWa(\"" + esc(fone) + "\")'>Ver lead</button>" : "") +
    "</div>";
  $("waReply").classList.remove("hidden");
  await loadWaMsgs();
  clearInterval(waPoll);
  waPoll = setInterval(function () {
    if (!$("secConversas").classList.contains("hidden") && waJid) loadWaMsgs(true);
  }, 8000);
};

window.verLeadWa = async function (fone) {
  try {
    const r = await fetch("/api/wa/lead?telefone=" + encodeURIComponent(fone));
    const d = await r.json();
    if (d.lead) {
      lastBusiness = d.lead;
      switchTab("crm");
      showStatus("searchStatus", "Lead da conversa: " + d.lead.nome, "info");
    } else {
      showStatus("searchStatus", "Este contato ainda não é um lead minerado.", "info");
      switchTab("crm");
    }
  } catch (e) {
    showStatus("searchStatus", "Falha: " + e.message, "error");
  }
};

function diaKey(ts) {
  try {
    const d = new Date(Number(ts) * 1000);
    if (isNaN(d.getTime())) return "";
    return ("0" + d.getDate()).slice(-2) + "/" + ("0" + (d.getMonth() + 1)).slice(-2) + "/" + d.getFullYear();
  } catch { return ""; }
}

async function loadWaMsgs(quiet) {
  if (!waJid) return;
  try {
    const r = await fetch("/api/wa/mensagens?jid=" + encodeURIComponent(waJid) + "&limite=" + waLimit + waInstParam());
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "Erro");
    const box = $("waMsgs");
    const msgs = d.mensagens || [];
    let html = "<button class='btn small' id='waMore'>Carregar mais antigas</button>";
    let lastDay = "";
    html += msgs.map(function (m) {
      let div = "";
      const day = diaKey(m.ts);
      if (day && day !== lastDay) {
        lastDay = day;
        div += "<div class='wa-day'>" + day + "</div>";
      }
      div += "<div class='wa-msg " + (m.de_mim ? "mine" : "theirs") + "'>" +
        (m.texto ? esc(m.texto) : "<i class='hint'>[mídia]</i>") +
        "<span class='wa-time'>" + esc(m.quando || "") + "</span></div>";
      return div;
    }).join("");
    box.innerHTML = msgs.length ? html : "<p class='hint'>Sem mensagens.</p>";
    const more = $("waMore");
    if (more) {
      more.addEventListener("click", function () {
        waLimit += 50;
        loadWaMsgs(true);
      });
    }
    box.scrollTop = box.scrollHeight;
  } catch (e) {
    if (!quiet) $("waMsgs").innerHTML = "<p class='status error'>Falha: " + esc(e.message) + "</p>";
  }
}

async function sendWaReply() {
  const txt = $("waInput").value.trim();
  if (!txt || !waJid) return;
  $("waInput").value = "";
  try {
    const r = await fetch("/api/wa/responder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jid: waJid, texto: txt, instance: waInstance || "" })
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "Erro");
    await loadWaMsgs(true);
  } catch (e) {
    showStatus("searchStatus", "Falha ao responder: " + e.message, "error");
  }
}

