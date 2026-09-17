// proposito: estado e resultados da busca agendada
async function loadScheduleStatus() {
  try {
    const r = await fetch("/api/schedule");
    const s = await r.json();
    const el = $("schedAlert");
    if (!el) return;
    if (s.enabled && s.new_count > 0) {
      el.innerHTML = "<span style='color:var(--green)'>● Busca automática ativa (" + esc(s.time) + ")</span>" +
        " — <b style='color:#fff'>" + s.new_count + " novos leads</b> de " + s.total_count + " na última rodada (" + esc(s.last_run) + ")." +
        " <a class='link' href='#' onclick='loadScheduleResults(); return false;'>Ver novos leads</a>";
    } else if (s.enabled) {
      el.innerHTML = "<span style='color:var(--green)'>● Busca automática ativa (" + esc(s.time) + ")</span> — aguardando próxima rodada.";
    } else {
      el.innerHTML = "Busca automática: <span style='color:#ff9aa5'>desativada</span> (ative nas Configurações).";
    }
  } catch { /* silencioso */ }
}

async function loadScheduleResults() {
  showLoader("Carregando leads da busca agendada...");
  try {
    const r = await fetch("/api/schedule/results");
    const d = await r.json();
    hideLoader();
    if (!r.ok) throw new Error(d.detail || "Nada encontrado");
    $("emptyCard").classList.add("hidden");
    $("homeExtra").classList.add("hidden");
    document.querySelector(".content").classList.remove("empty");
    $("queryTitle").textContent = "Leads novos (agendada)";
    $("exportGroup").classList.remove("hidden");
    switchTab("results");
    renderResults(d.novos.length ? d.novos : d.total ? d.novos : []);
    showStatus("searchStatus", d.novos.length + " leads novos encontrados pela busca agendada!", "ok");
  } catch (e) {
    hideLoader();
    showStatus("searchStatus", e.message, "error");
  }
}

