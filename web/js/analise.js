// proposito: analise do lead por IA: score, estrategia, referencia e Instagram
async function analyzeAll() {
  if (!bizCache.length) return;
  const total = bizCache.length;
  const CHUNK = 5;
  showLoader("Analisando 0/" + total + " leads com IA...");
  let done = 0;
  try {
    for (let i = 0; i < total; i += CHUNK) {
      const chunk = bizCache.slice(i, i + CHUNK);
      const r = await fetch("/api/business/strategy_batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ businesses: chunk })
      });
      const d = await r.json();
      if (r.ok && d.results) {
        d.results.forEach(function (res, j) {
          const b = bizCache[i + j];
          if (b && res) {
            b.score_oportunidade = res.score;
            b.nivel_ia = res.nivel;
            b.estrategia_resumo = res.resumo;
            b.oportunidades_ia = res.oportunidades;
            b.strategy_engine = res.engine;
          }
        });
      }
      done += chunk.length;
      $("loaderText").textContent = "Analisando " + done + "/" + total + " leads com IA...";
    }
    hideLoader();
    filters.sort = "score";
    $("fSort").value = "score";
    renderResults(bizCache);
    showStatus("searchStatus", total + " leads pontuados pela IA e ordenados por oportunidade!", "ok");
  } catch (e) {
    hideLoader();
    showStatus("searchStatus", "Falha na análise em lote: " + e.message, "error");
  }
}

// ===== DASHBOARD DE PERFORMANCE =====
function renderPerformance() {
  const grid = $("perfStats");
  if (!grid) return;

  const total = bizCache.length;
  const contacted = bizCache.filter(function (b) { return isContacted(b.nome); }).length;
  const taxa = total ? Math.round(contacted / total * 100) : 0;
  const urgentes = bizCache.filter(function (b) {
    return computeUrgency(b).nivel === "alta" && !isContacted(b.nome);
  }).length;
  const scored = bizCache.filter(function (b) { return scoreOf(b) != null; });
  const media = scored.length ? Math.round(scored.reduce(function (s, b) { return s + scoreOf(b); }, 0) / scored.length) : 0;

  function stat(label, value, cls) {
    return "<div class='perf-stat " + (cls || "") + "'><div><div class='perf-num'>" + value + "</div><div class='perf-label'>" + label + "</div></div></div>";
  }

  grid.innerHTML =
    stat("Leads na sessão", total) +
    stat("Contatados", contacted, "ok") +
    stat("Taxa de contato", taxa + "%", taxa >= 50 ? "ok" : "") +
    stat("Urgentes pendentes", urgentes, urgentes > 0 ? "warn" : "") +
    stat("Score médio IA", scored.length ? media + "%" : "—");

  const top = scored.slice().sort(function (a, b) { return scoreOf(b) - scoreOf(a); }).slice(0, 3);
  $("perfTop").innerHTML = top.length
    ? "<ul>" + top.map(function (b) {
        return "<li><b>" + esc(b.nome) + "</b> — score " + scoreOf(b) + "% (" + (isContacted(b.nome) ? "contatado" : "pendente") + ")</li>";
      }).join("") + "</ul>"
    : "Rode a análise em lote para ver o ranking aqui.";
}

async function doStrategy() {
  if (!lastBusiness) return;
  showLoader("Gerando análise estratégica com IA...");
  try {
    const r = await fetch("/api/business/strategy", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ business: lastBusiness })
    });
    const d = await r.json();
    hideLoader();
    if (!r.ok) throw new Error(d.detail || "Erro");

    const out = $("strategyOutput");
    out.className = "panel";
    const score = d.score_oportunidade != null ? d.score_oportunidade : 50;
    const nivelPill = d.nivel === "Alto" ? "high" : (d.nivel === "Baixo" ? "low" : "med");

    let html = "<h3>Análise Estratégica — " + esc(lastBusiness.nome) + "</h3>";
    html += "<div class='score-line'>";
    html += "<span>Oportunidade: <b>" + score + "%</b></span>";
    html += "<div class='progress'><div style='width:" + score + "%'></div></div>";
    html += "<span class='pill " + nivelPill + "'>" + esc(d.nivel || "-") + "</span>";
    html += "<span class='tag'>" + (d.engine === "local" ? "IA local" : esc(d.engine)) + "</span>";
    html += "</div>";

    if (d.resumo) html += "<p>" + esc(d.resumo) + "</p>";
    [["presenca_digital", "Presença digital"], ["oportunidades", "Oportunidades de serviço"], ["acoes_imediatas", "Ações imediatas"]].forEach(function (pair) {
      if (d[pair[0]] && d[pair[0]].length) {
        html += "<h4>" + pair[1] + "</h4><ul>";
        d[pair[0]].forEach(function (x) { html += "<li>" + esc(x) + "</li>"; });
        html += "</ul>";
      }
    });
    if (d.abordagem) html += "<h4>Como abordar</h4><p>" + esc(d.abordagem) + "</p>";
    out.innerHTML = html;
    showOut("strategyOutput");
  } catch (e) {
    hideLoader();
    showStatus("searchStatus", "Falha na estratégia: " + e.message, "error");
  }
}

async function doReference() {
  if (!lastBusiness) return;
  showLoader("Buscando referência para \"" + lastBusiness.nome + "\"...");
  try {
    const r = await fetch("/api/google/reference", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: lastBusiness.nome, location: lastBusiness.endereco || "" })
    });
    const data = await r.json();
    hideLoader();
    if (!r.ok) throw new Error(data.detail || "Erro");
    lastHandle = data.instagram_handle;
    const out = $("refOutput");
    out.className = "panel";
    let html = "<h3>Referência de \"" + esc(lastBusiness.nome) + "\"</h3>";
    html += "<p>Instagram encontrado: <b>" + (lastHandle ? "@" + esc(lastHandle) : "não encontrado") + "</b></p>";
    if (lastHandle) {
      html += "<div class='btn-row'><button class='btn small primary' onclick=\"doInstagram('" + esc(lastHandle) + "')\">Analisar @" + esc(lastHandle) + "</button></div>";
    }
    html += "<h4>Links encontrados</h4><ul>";
    (data.web_results || []).forEach(function (r2) {
      html += "<li><a class='link' href='" + esc(r2.url) + "' target='_blank'>" + esc(r2.title) + "</a></li>";
    });
    if (!(data.web_results || []).length) html += "<li>Nenhum</li>";
    html += "</ul>";
    out.innerHTML = html;
    showOut("refOutput");
  } catch (e) {
    hideLoader();
    showStatus("searchStatus", "Falha na referência: " + e.message, "error");
  }
}

async function doInstagram(forceHandle) {
  if (!lastBusiness) return;
  const username = forceHandle || lastHandle || "";
  showLoader("Analisando Instagram" + (username ? " @" + username : "") + "...");
  try {
    const r = await fetch("/api/instagram/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: lastBusiness.nome, username: username, download: true, max_posts: 12 })
    });
    const data = await r.json();
    hideLoader();
    if (!r.ok) throw new Error(data.detail || "Erro na análise");
    lastHandle = data.username;
    renderInstagram(data);
  } catch (e) {
    hideLoader();
    showStatus("searchStatus", "Falha na análise: " + e.message, "error");
  }
}

function renderInstagram(data) {
  const ig = $("igOutput");
  ig.className = "panel";
  const p = data.perfil || {};
  const rel = data.relatorio || {};

  let html = "<h3>Perfil @" + esc(data.username) + (data.auto_descoberto ? " <span class='tag'>auto-detectado</span>" : "") + "</h3>";
  html += "<div class='profile-stats'>";
  html += "<span><b>" + (p.seguidores != null ? p.seguidores : 0) + "</b> seguidores</span>";
  html += "<span><b>" + (p.total_posts != null ? p.total_posts : 0) + "</b> posts</span>";
  if (p.categoria) html += "<span>" + esc(p.categoria) + "</span>";
  if (p.verificado) html += "<span style='color:var(--accent)'>verificado</span>";
  html += "</div>";
  if (p.biografia) html += "<div class='bio'>" + esc(p.biografia) + "</div>";

  const score = rel.score_positividade != null ? rel.score_positividade : 50;
  html += "<div class='score-line'>";
  html += "<span>Positividade: <b>" + score + "%</b></span>";
  html += "<div class='progress'><div style='width:" + score + "%'></div></div>";
  html += "<span class='tag'>" + (rel.engine === "openai" ? "IA Groq/OpenAI" : "IA local") + "</span>";
  html += "</div>";
  if (rel.resumo) html += "<p>" + esc(rel.resumo) + "</p>";

  [["pontos_fortes", "Pontos fortes"], ["sugestoes", "Sugestões de melhoria"], ["conteudo_recomendado", "Conteúdo recomendado pela IA"]].forEach(function (pair) {
    if (rel[pair[0]] && rel[pair[0]].length) {
      html += "<h4>" + pair[1] + "</h4><ul>";
      rel[pair[0]].forEach(function (x) { html += "<li>" + esc(x) + "</li>"; });
      html += "</ul>";
    }
  });

  if (rel.tom_de_voz) html += "<h4>Tom de voz</h4><p>" + esc(rel.tom_de_voz) + "</p>";

  const tags = (rel.hashtags || []).slice(0, 8).map(function (h) {
    return "<span class='tag'>" + esc(h.hashtag || h) + "</span>";
  }).join("");
  html += "<h4>Hashtags</h4><div>" + (tags || "<span class='tag'>sem hashtags</span>") + "</div>";

  html += "<h4 style='margin-top:18px'>Postagens recentes (" + (data.posts ? data.posts.length : 0) + ")</h4>";
  html += "<div class='posts-grid'>";
  (data.posts || []).forEach(function (post) {
    html += "<div>";
    html += "<div class='post-thumb'>";
    if (post.url_imagem) html += "<img src='" + esc(post.url_imagem) + "' loading='lazy' alt=''>";
    html += "<div class='post-stats'>" + (post.curtidas || 0) + " curtidas · " + (post.comentarios || 0) + " comentários</div>";
    html += "</div>";
    html += "<div class='post-caption'>" + esc((post.legenda || "").slice(0, 110)) + "</div>";
    html += "</div>";
  });
  html += "</div>";

  if (data.conteudos_baixados && data.conteudos_baixados.length) {
    html += "<h4>Conteúdo baixado (" + data.conteudos_baixados.length + ")</h4><ul style='font-size:12px;color:var(--muted)'>";
    data.conteudos_baixados.forEach(function (c) { html += "<li>" + esc(c.arquivo) + "</li>"; });
    html += "</ul>";
  }

  ig.innerHTML = html;
  showOut("igOutput");
}

// ===== APRENDIZADO (O QUE MAIS CONVERTE) =====
async function renderAprendizado() {
  const box = $("aprBody");
  if (!box) return;
  try {
    const r = await (await fetch("/api/crm/aprendizado")).json();
    if (!r.ok) {
      box.innerHTML = "<div class='empty-box'><b>Ainda aprendendo</b><span>" +
        esc(r.eventos || 0) + " leads tocados — marco " + esc(r.minimo || 15) +
        " pra calibrar. Mova cards no pipeline.</span></div>";
      return;
    }
    const dimNome = { nota: "Nota", avaliacoes: "Avaliações", site: "Site", nicho: "Nicho" };
    box.innerHTML =
      "<p class='hint'>Base: " + esc(r.base) + "% de conversão em " + esc(r.eventos) + " leads tocados.</p>" +
      "<table class='table'><thead><tr><th>Perfil</th><th class='num'>Leads</th>" +
      "<th class='num'>Converte</th><th class='num'>Lift</th></tr></thead><tbody>" +
      r.tabela.slice(0, 8).map(function (t) {
        return "<tr><td>" + esc((dimNome[t.dim] || t.dim) + ": " + t.valor) + "</td>" +
          "<td class='num'>" + esc(t.n) + "</td>" +
          "<td class='num'>" + esc(t.taxa) + "%</td>" +
          "<td class='num'>" + esc(t.lift) + "x</td></tr>";
      }).join("") + "</tbody></table>";
  } catch (e) {
    box.innerHTML = "<div class='empty-box'><b>Falha ao carregar</b><span>" + esc(e.message) + "</span></div>";
  }
}

async function recalcAprendizado() {
  const box = $("aprBody");
  if (box) box.innerHTML = "<p class='hint'>Recalculando...</p>";
  try {
    const r = await (await fetch("/api/crm/aprendizado/recalcular", { method: "POST" })).json();
    if (r.ok) toast(Object.keys(r.ajustes || {}).length + " scores ajustados (" + r.gravados + " gravados)", "ok");
    else toast("Ainda aprendendo: " + (r.eventos || 0) + "/" + (r.minimo || 15), "error");
  } catch (e) {
    toast("Falha: " + e.message, "error");
  }
  renderAprendizado();
}

// ===== PAINEL INICIAL (DASHBOARD) =====
async function loadDashboard() {
  const grid = $("dashKpis");
  if (!grid) return;
  grid.innerHTML = "<div class='perf-stat'><div class='skel' style='width:60%'></div></div>".repeat(4);
  try {
    const out = await Promise.all([
      fetch("/api/crm/leads?limite=500").then(function (r) { return r.json(); }).catch(function () { return { leads: [] }; }),
      fetch("/api/disparo/status").then(function (r) { return r.json(); }).catch(function () { return {}; }),
      fetch("/api/results").then(function (r) { return r.json(); }).catch(function () { return {}; }),
      fetch("/api/schedule").then(function (r) { return r.json(); }).catch(function () { return {}; })
    ]);
    const leads = out[0].leads || [];
    const disp = out[1] || {};
    const counts = {};
    leads.forEach(function (l) {
      const s = String(l.contato_status || "novo");
      counts[s] = (counts[s] || 0) + 1;
    });
    const novos = counts.novo || 0;
    const andamento = Math.max(0, leads.length - novos - (counts.fechado || 0) - (counts.perdido || 0));
    const scored = leads.filter(function (l) { return scoreOf(l) != null; });
    const media = scored.length ? Math.round(scored.reduce(function (s, l) { return s + scoreOf(l); }, 0) / scored.length) : null;

    function stat(label, value, cls, goto) {
      return "<div class='perf-stat dash-kpi" + (cls ? " " + cls : "") + "'" + (goto ? " data-goto='" + goto + "' role='button' tabindex='0'" : "") + ">" +
        "<div><div class='perf-num'>" + value + "</div><div class='perf-label'>" + label + "</div></div></div>";
    }
    grid.innerHTML =
      stat("Empresas na base", leads.length, "", "leads") +
      stat("Leads novos", novos, "", "crm") +
      stat("Em andamento", andamento, "", "crm") +
      stat("Score médio IA", media != null ? media + "%" : "—") +
      stat("Fila de disparo", disp.pendentes != null ? disp.pendentes : "—", "", "comercial") +
      stat("Enviados", disp.enviados != null ? disp.enviados : "—", disp.enviados > 0 ? "ok" : "");

    const act = [];
    if (out[2].last_search) act.push(["Última busca", out[2].last_search, "results"]);
    if (out[3].last_run) act.push(["Busca agendada", "rodou em " + out[3].last_run + " · " + (out[3].new_count || 0) + " novos", "home"]);
    if ((disp.enviados || 0) > 0) act.push(["Disparo", disp.enviados + " enviados · " + (disp.pendentes || 0) + " pendentes", "comercial"]);
    if (!act.length) act.push(["Nada por aqui ainda", "Rode sua primeira busca para começar", "results"]);
    $("dashActivity").innerHTML = act.map(function (a) {
      return "<button class='activity-item' data-goto='" + a[2] + "'><b>" + esc(a[0]) + "</b><span>" + esc(a[1]) + "</span></button>";
    }).join("");

    document.querySelectorAll("[data-goto]").forEach(function (b) {
      if (b.dataset.bound) return;
      b.dataset.bound = "1";
      b.addEventListener("click", function () { switchTab(b.dataset.goto); });
      b.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); switchTab(b.dataset.goto); }
      });
    });
  } catch (e) {
    grid.innerHTML = "<div class='empty-box'><b>Falha ao carregar painel</b><span>" + esc(e.message) + "</span><button class='btn small primary' onclick='loadDashboard()'>Tentar de novo</button></div>";
  }
}

async function extractIgFromSites() {
  if (!bizCache.length) {
    showStatus("searchStatus", "Faça uma busca no Maps primeiro.", "error");
    return;
  }
  showLoader("Varrendo os sites em busca de Instagram...");
  try {
    const r = await fetch("/api/instagram/dos-sites", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ businesses: bizCache, apenas_novos: $("onlyNew").checked })
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || "Erro");
    hideLoader();

    let msg = data.total + " Instagrams extraídos dos sites.";
    if (!data.enriquecidos) {
      msg += " Sem sessionid: sem seguidores/bio. Cole o sessionid para enriquecer.";
    }
    if (data.repetidos_ocultos > 0) {
      msg += " " + data.repetidos_ocultos + " repetidos foram ocultados.";
    }
    showStatus("searchStatus", msg, "ok");

    $("queryTitle").textContent = "Instagram via sites";
    selectedKeys = {};
    tableState.page = 1;
    renderResults(data.businesses);
  } catch (e) {
    hideLoader();
    showStatus("searchStatus", "Falha: " + e.message, "error");
  }
}

