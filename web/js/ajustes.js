// proposito: ajustes do painel: ler e salvar as configuracoes
var KEY_URLS = {
  groq: "https://console.groq.com/keys",
  gemini: "https://aistudio.google.com/apikey",
  openai: "https://platform.openai.com/api-keys"
};

function provedorAtual() {
  const sel = $("provider") ? $("provider").value : "";
  if (sel && KEY_URLS[sel]) return sel;
  const base = String($("baseUrl") ? $("baseUrl").value : "");
  if (base.includes("gemini")) return "gemini";
  if (base.includes("groq")) return "groq";
  if (base.includes("openai")) return "openai";
  return "";
}

// O botao "Pegar chave" acompanha o provedor: cada IA tem a pagina dela.
function atualizarLinkChave() {
  const a = $("btnPegarChave");
  if (!a) return;
  const p = provedorAtual();
  if (p && KEY_URLS[p]) {
    a.href = KEY_URLS[p];
    a.style.display = "";
  } else {
    a.style.display = "none";
  }
}

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
    (function () {
      const salvos = s.schedule_niches && s.schedule_niches.length ? s.schedule_niches
        : (s.schedule_niche ? [s.schedule_niche] : []);
      document.querySelectorAll("#schedNiches input").forEach(function (cb) {
        cb.checked = salvos.indexOf(cb.value) !== -1;
        cb.closest(".state-pill").classList.toggle("checked", cb.checked);
      });
    })();
    $("schedStates").value = (s.schedule_states || []).join(", ");

    const iaLine = $("iaStatusLine");
    if (iaLine) {
      if (s.openai_api_key) {
        const providerName = String(s.openai_base_url || "").includes("gemini") ? "Gemini"
          : String(s.openai_base_url || "").includes("groq") ? "Groq" : "OpenAI";
        iaLine.textContent = "Ativa: " + providerName + " (" + (s.openai_model || "modelo padrão") + ")";
      } else {
        iaLine.textContent = "Sem chave: usando análise local gratuita.";
      }
    }
    atualizarLinkChave();

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
      niche: "",
      niches: selectedSchedNiches(),
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
        const cl = $("cloudStatusLine");
        if (!cl) return;
        cl.textContent = cs.online ? "Conectada." : "Modo local (sem nuvem).";
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

