// proposito: disparo automatico: fila, migracao, envio e status
// ===== DISPARO AUTOMÁTICO =====
let dispPoll = null;

// O seletor "Modo: automatico / manual" saiu a pedido do fundador. Ele nao
// controlava nada: o motor nunca leu o valor, e o envio avulso deixou de ser
// barrado pelo modo manual quando a trava atomica da fila passou a fazer os dois
// caminhos conviverem. Era um interruptor que so pintava um texto na tela.

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
    let resumo = d.enfileirados + " leads minerados na fila (de " + d.total_minerados
      + " no total, sem repetir telefone)!";
    if (d.desativados) resumo += " " + d.desativados + " pulados: desativados para disparo.";
    if (d.com_ia || d.com_template) resumo += " " + (d.com_ia || 0) + " com IA, " + (d.com_template || 0) + " com template.";
    if (d.sem_mensagem) resumo += " " + d.sem_mensagem + " ficaram de fora: a IA nao cobriu (teto " + (d.teto_ia || 0) + ").";
    showStatus("searchStatus", resumo, "ok");
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

window.refazerMensagem = async function (id, btn, editada) {
  if (editada && !window.confirm("Esta mensagem foi escrita por você. Refazer com IA apaga o seu texto. Continuar?")) return;
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
    closeMsgModal();
    showStatus("searchStatus", "Mensagem refeita com " + (d.engine === "local" ? "o motor local" : d.engine) + "! Confira na tabela.", "ok");
  } catch (e) {
    showStatus("searchStatus", "Falha ao refazer: " + e.message, "error");
  } finally {
    if (btn) { btn.textContent = old; btn.disabled = false; }
  }
  refreshDisparo();
};

window.salvarMensagem = async function (id) {
  const campo = $("msgEdit");
  if (!campo) return;
  const texto = campo.value.trim();
  if (!texto) {
    showStatus("searchStatus", "A mensagem não pode ficar vazia.", "error");
    return;
  }
  try {
    const r = await fetch("/api/disparo/mensagem", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: id, mensagem: texto })
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || "Erro");
    closeMsgModal();
    showStatus("searchStatus", "Mensagem salva. Ela sai exatamente assim.", "ok");
    refreshDisparo();
  } catch (e) {
    showStatus("searchStatus", "Falha ao salvar: " + e.message, "error");
  }
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
    if (d.editada_em) {
      html += "<p class='hint'>Escrita à mão em " + esc(d.editada_em) +
        ". Refazer com IA apaga esta versão.</p>";
    }
    if (d.status === "pendente") {
      html += "<textarea id='msgEdit' rows='8' style='width:100%;background:var(--panel2);border:1px solid var(--border);color:var(--text);padding:10px 12px;border-radius:8px;font-size:13px;resize:vertical;'>" + esc(d.mensagem || "") + "</textarea>";
      html += "<div class='btn-row'>" +
        "<button class='btn small primary' onclick='salvarMensagem(" + d.id + ")'>Salvar mensagem</button>" +
        "<button class='btn small wa' onclick='enviarAgora(" + d.id + ");closeMsgModal();'>Enviar agora</button>" +
        "<button class='btn small' onclick='refazerMensagem(" + d.id + ", null, " + (d.editada_em ? "true" : "false") + ")'>Refazer com IA</button>" +
        "</div>";
    } else {
      html += "<div class='pitch-box' style='white-space:pre-wrap;'>" + esc(d.mensagem || "(vazia)") + "</div>";
      html += "<p class='hint'>Esta mensagem está como \"" + esc(d.status) +
        "\" e não pode mais ser editada.</p>";
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
        itens.push({ nome: b.nome, telefone: b.telefone, mensagem: b._pitch.whatsapp, categoria: b.categoria || "" });
      } else {
        const r = await fetch("/api/business/pitch?rapido=1", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ business: b })
        });
        const d = await r.json();
        if (r.ok && d.whatsapp) {
          b._pitch = d;
          itens.push({ nome: b.nome, telefone: b.telefone, mensagem: d.whatsapp, categoria: b.categoria || "" });
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
          "<button class='btn small' onclick='refazerMensagem(" + f.id + ", this, " + (f.editada_em ? "true" : "false") + ")'>Refazer IA</button>"
        : "";
      return "<tr><td>" + esc(f.nome) + "</td><td>" + esc(f.telefone) + "</td>" +
        "<td class='st-" + f.status + "'>" + f.status + "</td>" +
        "<td>" + (f.instancia ? esc(f.instancia) : "<span class='hint'>—</span>") + "</td>" +
        "<td>" + (f.editada_em ? "<span class='pill open' style='margin-right:6px;'>sua</span>" : "") +
        esc((f.mensagem || "").slice(0, 60)) + "…</td>" +
        "<td><div class='row-actions'><button class='btn small' onclick='verMensagem(" + f.id + ")'>Ver</button>" + action + "</div></td></tr>";
    }).join("");
    // A tabela da fila virou a lista de leads da aba Disparo, em disparo_aba.js.
    // A guarda fica porque o poll logo abaixo depende desta funcao chegar ao fim.
    const tabelaVelha = $("disparoTable");
    if (tabelaVelha) {
      tabelaVelha.innerHTML = rows
        ? "<table class='disp-table'><tbody>" + rows + "</tbody></table>"
        : "<p class='hint'>Fila vazia.</p>";
    }

    clearInterval(dispPoll);
    if (st.rodando) {
      dispPoll = setInterval(refreshDisparo, 5000);
    }
  } catch { /* silencioso */ }
}

async function startDisp() {
  const body = {
    provider: "simulado",
    limite_dia: parseInt($("dispLimite").value, 10) || 30,
    hora_ini: $("dispHoraIni").value || "08:00",
    hora_fim: $("dispHoraFim").value || "20:00"
  };
  try {
    const s = await (await fetch("/api/settings")).json();
    body.provider = s.disparo_provider || "simulado";
  } catch { /* usa simulado */ }
  const r = await fetch("/api/disparo/iniciar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  const d = await r.json();
  // A fila nasce no mesmo clique, entao o resultado dela e a primeira coisa que
  // quem opera precisa ver: "rodando" com fila vazia nao manda nada, e antes
  // disso nao havia nada na tela dizendo que ninguem tinha entrado.
  if (typeof window.dspMostrarCarga === "function") window.dspMostrarCarga(d);
  const entraram = ((d.carga || {}).enfileirados) || 0;
  if (d.iniciado || d.rodando) {
    showStatus("searchStatus",
      entraram
        ? "Disparo rodando no modo " + body.provider + " com " + entraram + " na fila."
        : "Disparo ligado, mas nenhum lead entrou na fila. Veja o aviso na aba.",
      entraram ? "ok" : "info");
  } else if (d.motivo) {
    showStatus("searchStatus", d.motivo + ". Use o botão Enviar de cada linha.", "info");
  } else {
    showStatus("searchStatus", "Disparo já estava rodando.", "info");
  }
  refreshDisparo();
  if (typeof window.dspAtualizarTudo === "function") window.dspAtualizarTudo();
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

