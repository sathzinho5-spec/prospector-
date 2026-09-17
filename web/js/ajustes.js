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

    const igWrap = $("igChipWrap");
    if (s.instagram_sessionid) {
      igWrap.classList.add("on"); igWrap.classList.remove("off");
      $("igChipText").textContent = "Instagram: sessão ativa";
    } else {
      igWrap.classList.add("off"); igWrap.classList.remove("on");
      $("igChipText").textContent = "Instagram: sem sessão";
    }
  } catch (e) {
    console.error("Erro ao carregar configurações", e);
  }
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
    if ($("dispPrompt").value.trim()) body.disparo_prompt = $("dispPrompt").value.trim();
    if ($("dispMetaToken").value.trim()) body.disparo_meta_token = $("dispMetaToken").value.trim();
    if ($("dispMetaPhone").value.trim()) body.disparo_meta_phone_id = $("dispMetaPhone").value.trim();
  }
  if ($("sbUrl") && $("sbUrl").value.trim()) body.supabase_url = $("sbUrl").value.trim();
  if ($("sbSecret") && $("sbSecret").value.trim()) body.supabase_secret = $("sbSecret").value.trim();
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
      $("dispPrompt").value = "";
      $("dispPrompt").placeholder = s.disparo_prompt ? "Prompt personalizado ativo" : "Vazio = prompt da skill";
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

