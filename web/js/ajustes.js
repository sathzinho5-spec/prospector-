// proposito: ajustes do painel: ler e salvar as configuracoes
async function loadSettings() {
  try {
    const r = await fetch("/api/settings");
    const s = await r.json();
    $("baseUrl").value = s.openai_base_url || "";
    $("model").value = s.openai_model || "";
    $("apiKey").placeholder = s.openai_api_key ? "Chave configurada" : "sk-... / gsk-... (opcional)";
    $("igSession").placeholder = s.instagram_sessionid ? "Cookie configurado" : "Opcional - sessionid";

    $("schedEnabled").checked = !!s.schedule_enabled;
    $("schedTime").value = s.schedule_time || "08:00";
    $("schedNiche").value = s.schedule_niche || "restaurantes";
    $("schedStates").value = (s.schedule_states || []).join(", ");

    const iaChip = $("iaChip");
    if (s.openai_api_key) {
      iaChip.classList.add("on"); iaChip.classList.remove("off");
      const providerName = String(s.openai_base_url || "").includes("gemini") ? "Gemini"
        : String(s.openai_base_url || "").includes("groq") ? "Groq" : "OpenAI";
      $("iaChipText").textContent = "IA: " + providerName;
    } else {
      iaChip.classList.add("off");
      $("iaChipText").textContent = "IA local";
    }

    const abordIaMax = $("abordIaMax");
    if (abordIaMax) abordIaMax.value = (s.abordagem_ia_max === undefined || s.abordagem_ia_max === null) ? "" : s.abordagem_ia_max;

    // O valor salvo aparece no campo, senao nao ha como apagar o que foi colado.
    const abordPrompt = $("abordPrompt");
    if (abordPrompt) {
      abordPrompt.value = s.abordagem_prompt || "";
      abordPrompt.placeholder = "Vazio = prompt da skill";
    }
    const dispPromptEl = $("dispPrompt");
    if (dispPromptEl) {
      dispPromptEl.value = s.disparo_prompt || "";
      dispPromptEl.placeholder = "Vazio = prompt da skill";
    }

    const igWrap = $("igChipWrap");
    if (s.instagram_sessionid) {
      igWrap.classList.add("on"); igWrap.classList.remove("off");
      $("igChipText").textContent = "Instagram: sessão ativa";
    } else {
      igWrap.classList.add("off"); igWrap.classList.remove("on");
      $("igChipText").textContent = "Instagram: sem sessão";
    }

    loadTiming();
  } catch (e) {
    console.error("Erro ao carregar configurações", e);
  }
}

// Janelas por nicho: uma linha por nicho (inicio, fim, dias). Vazio = padrao:
// so o que foi preenchido viaja no save, o resto continua herdando a tabela.
async function loadTiming() {
  const box = $("timingTable");
  if (!box) return;
  try {
    const r = await fetch("/api/timing/janelas");
    const d = await r.json();
    const padrao = d.padrao || {};
    const salvas = d.salvas || {};
    box.innerHTML = (d.nichos || []).map(function (n) {
      const p = padrao[n.id] || {};
      const s = salvas[n.id] || {};
      const dica = p.ini ? ("Padrão: " + p.ini + "–" + p.fim) : "Padrão: janela geral";
      return "<div class='timing-row' data-nicho='" + esc(n.id) + "'>" +
        "<span class='timing-nome' title='" + esc(dica) + "'>" + esc(n.label) + "</span>" +
        "<input type='time' class='timing-ini' value='" + esc(s.ini || "") + "' aria-label='Início " + esc(n.label) + "'>" +
        "<input type='time' class='timing-fim' value='" + esc(s.fim || "") + "' aria-label='Fim " + esc(n.label) + "'>" +
        "<select class='timing-dias' aria-label='Dias " + esc(n.label) + "'>" +
        "<option value=''>(padrão)</option>" +
        "<option value='uteis'" + (s.dias === "uteis" ? " selected" : "") + ">seg–sex</option>" +
        "<option value='todos'" + (s.dias === "todos" ? " selected" : "") + ">todos</option>" +
        "</select></div>";
    }).join("");
  } catch (e) {
    box.innerHTML = "<p class='hint'>Não deu pra carregar as janelas.</p>";
  }
}

function collectTiming() {
  const out = {};
  document.querySelectorAll("#timingTable .timing-row").forEach(function (row) {
    const ini = row.querySelector(".timing-ini").value;
    const fim = row.querySelector(".timing-fim").value;
    const dias = row.querySelector(".timing-dias").value;
    if (ini && fim) out[row.dataset.nicho] = { ini: ini, fim: fim, dias: dias || "uteis" };
  });
  return out;
}

async function saveSettings() {
  const body = {};
  if ($("apiKey").value.trim()) body.openai_api_key = $("apiKey").value.trim();
  if ($("baseUrl").value.trim()) body.openai_base_url = $("baseUrl").value.trim();
  if ($("model").value.trim()) body.openai_model = $("model").value.trim();
  if ($("igSession").value.trim()) body.instagram_sessionid = $("igSession").value.trim();
  if ($("dispProvider")) {
    body.disparo_provider = $("dispProvider").value;
    if ($("dispEvoUrl").value.trim()) body.disparo_evo_url = $("dispEvoUrl").value.trim();
    if ($("dispEvoKey").value.trim()) body.disparo_evo_key = $("dispEvoKey").value.trim();
    if ($("dispEvoInstance").value.trim()) body.disparo_evo_instance = $("dispEvoInstance").value.trim();
    if ($("dispEvoChip2").value.trim()) body.disparo_evo_chip2 = $("dispEvoChip2").value.trim();
    if ($("dispEvoChip3").value.trim()) body.disparo_evo_chip3 = $("dispEvoChip3").value.trim();
    if ($("dispTom")) body.disparo_tom = $("dispTom").value;
    // Mandados SEMPRE, inclusive vazios: campo apagado tem que chegar como ""
    // no back-end, senao nao existe como voltar pro prompt da skill.
    body.disparo_prompt = $("dispPrompt").value.trim();
    body.abordagem_prompt = $("abordPrompt").value.trim();
    if ($("abordIaMax") && $("abordIaMax").value !== "") body.abordagem_ia_max = parseInt($("abordIaMax").value, 10) || 0;
    if ($("dispMetaToken").value.trim()) body.disparo_meta_token = $("dispMetaToken").value.trim();
    if ($("dispMetaPhone").value.trim()) body.disparo_meta_phone_id = $("dispMetaPhone").value.trim();
  }
  if ($("sbUrl") && $("sbUrl").value.trim()) body.supabase_url = $("sbUrl").value.trim();
  if ($("sbSecret") && $("sbSecret").value.trim()) body.supabase_secret = $("sbSecret").value.trim();
  body.timing_janelas = collectTiming();
  try {
    const r = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    const s = await r.json();

    const schedBody = {
      enabled: $("schedEnabled").checked,
      time: $("schedTime").value || "08:00",
      niche: $("schedNiche").value,
      states: $("schedStates").value.split(",").map(function (x) { return x.trim(); }).filter(Boolean),
      max: parseInt($("maxResults").value, 10) || 10
    };
    await fetch("/api/schedule", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(schedBody)
    });

    if (r.ok) {
      showStatus("settingsStatus", schedBody.enabled
        ? "Salvo! Busca automática diária às " + schedBody.time + "."
        : "Configurações salvas.", "ok");
      $("apiKey").value = "";
      $("igSession").value = "";
      $("apiKey").placeholder = s.openai_api_key ? "Chave configurada" : "sk-... / gsk-... (opcional)";
    $("igSession").placeholder = s.instagram_sessionid ? "Cookie configurado" : "Opcional - sessionid";

    if ($("dispProvider")) {
      $("dispProvider").value = s.disparo_provider || "simulado";
      $("dispEvoUrl").value = s.disparo_evo_url || "";
      $("dispEvoInstance").value = s.disparo_evo_instance || "";
      $("dispEvoChip2").value = s.disparo_evo_chip2 || "";
      $("dispEvoChip3").value = s.disparo_evo_chip3 || "";
      $("dispTom").value = s.disparo_tom || "direto";
      $("dispPrompt").value = s.disparo_prompt || "";
      $("dispPrompt").placeholder = "Vazio = prompt da skill";
      $("abordPrompt").value = s.abordagem_prompt || "";
      $("abordPrompt").placeholder = "Vazio = prompt da skill";
      $("dispMetaPhone").value = s.disparo_meta_phone_id || "";
      $("dispEvoKey").placeholder = s.disparo_evo_key ? "Key configurada" : "sua apikey";
      $("dispMetaToken").placeholder = s.disparo_meta_token ? "Token configurado" : "token permanente";
    }
    if ($("sbUrl")) {
      $("sbUrl").value = s.supabase_url || "";
      $("sbSecret").placeholder = s.supabase_secret ? "Secret configurada" : "sb_secret_... (opcional)";
    }

    try {
      fetch("/api/cloud/status").then(function (r) { return r.json(); }).then(function (cs) {
        const cc = $("cloudChip");
        if (!cc) return;
        if (cs.online) {
          cc.classList.add("on"); cc.classList.remove("off");
          $("cloudChipText").textContent = "Nuvem: conectada";
        } else {
          cc.classList.add("off"); cc.classList.remove("on");
          $("cloudChipText").textContent = "Nuvem: local";
        }
      }).catch(function () { /* mantém padrão */ });
    } catch { /* mantém padrão */ }
      await loadSettings();
      setTimeout(function () { clearStatus("settingsStatus"); }, 3000);
    } else {
      showStatus("settingsStatus", "Erro ao salvar.", "error");
    }
  } catch (e) {
    showStatus("settingsStatus", "Erro ao salvar: " + e.message, "error");
  }
}

