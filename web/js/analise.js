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
  const scored = bizCache.filter(function (b) { return b.score_oportunidade != null; });
  const media = scored.length ? Math.round(scored.reduce(function (s, b) { return s + b.score_oportunidade; }, 0) / scored.length) : 0;

  function stat(label, value, cls) {
    return "<div class='perf-stat " + (cls || "") + "'><div class='perf-num'>" + value + "</div><div class='perf-label'>" + label + "</div></div>";
  }

  grid.innerHTML =
    stat("Leads na sessão", total) +
    stat("Contatados", contacted, "ok") +
    stat("Taxa de contato", taxa + "%", taxa >= 50 ? "ok" : "") +
    stat("Urgentes pendentes", urgentes, urgentes > 0 ? "warn" : "") +
    stat("Score médio IA", scored.length ? media + "%" : "—");

  const top = scored.slice().sort(function (a, b) { return b.score_oportunidade - a.score_oportunidade; }).slice(0, 3);
  $("perfTop").innerHTML = top.length
    ? "<ul>" + top.map(function (b) {
        return "<li><b>" + esc(b.nome) + "</b> — score " + b.score_oportunidade + "% (" + (isContacted(b.nome) ? "contatado" : "pendente") + ")</li>";
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

