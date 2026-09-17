// proposito: conexao do WhatsApp por QR code das instancias Evolution
// ===== CONEXÃO WHATSAPP (Evolution QR) =====
let qrPoll = null;

async function refreshInstances() {
  const box = $("instList");
  if (!box) return;
  try {
    const r = await fetch("/api/disparo/instancias");
    const d = await r.json();
    const arr = d.instancias || [];
    if (!arr.length) {
      box.innerHTML = "<span class='hint'>Nenhuma instância cadastrada. Configure nas Configurações.</span>";
      return;
    }
    box.innerHTML = arr.map(function (it) {
      const dot = it.conectado ? "on" : "off";
      return "<span class='chip " + dot + "' style='margin:2px;'>" +
        "<span class='dot'></span><b>" + esc(it.instance || "?") + "</b>&nbsp;" +
        esc(it.conectado ? "conectado" : (it.estado || "off")) +
        " <a class='link' href='#' onclick='connectWhatsApp(\"" + esc(it.instance || "") + "\");return false;'>conectar</a></span>";
    }).join("");
  } catch {
    box.innerHTML = "<span class='hint'>Falha ao ver instâncias.</span>";
  }
}

async function connectWhatsApp(instance) {
  $("qrModal").classList.remove("hidden");
  $("qrHint").textContent = "Gerando QR code" + (instance ? " para " + instance : "") + "...";
  $("qrBox").innerHTML = "";
  $("qrStatus").textContent = "aguardando...";
  clearInterval(qrPoll);
  try {
    const r = await fetch("/api/disparo/evolution/qrcode" + (instance ? "?instance=" + encodeURIComponent(instance) : ""), { method: "POST" });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "Erro");
    if (d.qrcode) {
      const src = d.qrcode.indexOf("base64,") !== -1 ? d.qrcode : "data:image/png;base64," + d.qrcode;
      $("qrBox").innerHTML = "<img src='" + src + "' style='width:100%;border-radius:12px;' alt='QR'>";
      $("qrHint").textContent = "Escaneie com o WhatsApp do chip de disparo.";
    } else {
      $("qrHint").textContent = "Instância já criada. Verificando conexão...";
    }
    qrPoll = setInterval(checkWaState, 4000);
    checkWaState();
  } catch (e) {
    $("qrHint").textContent = "Falha: " + e.message;
    $("qrStatus").textContent = "Evolution fora do ar? Suba com: cd evolution && docker compose up -d";
  }
}

async function checkWaState() {
  try {
    const r = await fetch("/api/disparo/evolution/estado");
    const d = await r.json();
    if (d.conectado) {
      $("qrStatus").textContent = "Conectado! Pode fechar e iniciar o disparo.";
      clearInterval(qrPoll);
    } else {
      $("qrStatus").textContent = "Estado: " + (d.estado || "aguardando scan...") + (d.erro ? " — " + d.erro : "");
    }
  } catch { /* tenta de novo no próximo ciclo */ }
}

