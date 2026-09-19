// proposito: a gaveta de detalhe do lead na aba Disparo: ficha, copy e resposta
//
// Separada da lista pela mesma costura do CSS. Ela e a nossa, e nao o drawer do
// socio (#detailModal): os dois convivem e nao compartilham classe nem id, por
// decisao do fundador de manter a aba Disparo isolada do frontend que ele
// reescreve toda semana.

var dspLeadAberto = null;

function dspFichaLinha(rotulo, valor) {
  if (valor === null || valor === undefined || valor === "") return "";
  return "<div class='dsp-ficha-linha'>" +
    "<div class='dsp-ficha-rotulo'>" + esc(rotulo) + "</div>" +
    "<div class='dsp-ficha-valor'>" + esc(String(valor)) + "</div></div>";
}

function dspPill(el, estado, rotulo) {
  if (!el) return;
  if (!estado) { el.classList.add("hidden"); return; }
  el.className = "dsp-estado " + dspClasseDoEstado(estado);
  el.textContent = rotulo || DSP_ROTULO[estado] || estado;
  el.classList.remove("hidden");
}

function dspAbrirGaveta(telefone) {
  const l = dspLeads.find(function (x) { return x.telefone === telefone; });
  if (!l) return;
  dspLeadAberto = l;

  if ($("dspGavetaTitulo")) $("dspGavetaTitulo").textContent = l.nome || "(sem nome)";
  if ($("dspGavetaSub")) {
    $("dspGavetaSub").textContent =
      [l.categoria, [l.cidade, l.uf].filter(Boolean).join("/")].filter(Boolean).join(" · ");
  }

  const jaSaiu = ["enviado", "respondeu", "falha", "duplicado"].indexOf(l.estado) >= 0;
  dspPill($("dspGavetaEstadoCopy"), l.mensagem ? "copy_pronta" : "sem_copy");
  dspPill($("dspGavetaEstadoDisparo"), jaSaiu || l.estado === "na_fila" ? l.estado : null);
  const sua = $("dspGavetaSua");
  if (sua) sua.classList.toggle("hidden", !l.editada);

  if ($("dspGavetaFicha")) {
    $("dspGavetaFicha").innerHTML =
      dspFichaLinha("Telefone", l.telefone_bruto || l.telefone) +
      dspFichaLinha("Categoria", l.categoria) +
      dspFichaLinha("Cidade", [l.cidade, l.uf].filter(Boolean).join("/")) +
      dspFichaLinha("Nota", l.nota) +
      dspFichaLinha("Avaliacoes", l.avaliacoes) +
      dspFichaLinha("Site", l.website) +
      dspFichaLinha("Disparo", l.disparo_ativo ? "ligado" : "desligado") +
      // Mesma hora que a lista mostra, vinda da mesma funcao: se a gaveta
      // formatasse por conta, as duas telas passariam a discordar.
      dspFichaLinha("Sai em", l.estado === "na_fila" ? dspHorario(l) : "") +
      dspFichaLinha("Enviado em", l.enviado_em) +
      dspFichaLinha("Respondeu em", l.respondido_em) +
      dspFichaLinha("Erro", l.erro);
  }

  const ta = $("dspGavetaMensagem");
  if (ta) {
    ta.value = l.mensagem || "";
    // Texto do que ja saiu nao se reescreve: e a metrica da operacao.
    ta.readOnly = jaSaiu;
  }
  if ($("dspGavetaMsgInfo")) {
    $("dspGavetaMsgInfo").textContent = jaSaiu
      ? "Ja enviada. O texto do que saiu nao pode mais ser alterado."
      : (l.editada ? "Escrita a mao por voce." : (l.mensagem ? "Escrita pela IA." : "Sem copy ainda."));
  }
  if ($("btnDspSalvarMensagem")) $("btnDspSalvarMensagem").disabled = jaSaiu;
  if ($("btnDspEnviarAgora")) $("btnDspEnviarAgora").disabled = !l.fila_id;
  const liga = $("btnDspLigarLead");
  if (liga) {
    // O botao diz o que vai FAZER, nao o estado atual: rotulo que descreve o
    // estado faz quem opera clicar achando que esta confirmando.
    liga.textContent = l.disparo_ativo ? "Desligar disparo" : "Ligar disparo";
    liga.disabled = jaSaiu;
  }
  if ($("btnDspConversaIniciada")) {
    $("btnDspConversaIniciada").disabled = !jaSaiu || l.estado === "respondeu";
  }

  if ($("dspGaveta")) $("dspGaveta").classList.remove("hidden");
}

function dspFecharGaveta() {
  if ($("dspGaveta")) $("dspGaveta").classList.add("hidden");
  dspLeadAberto = null;
}

async function dspLigarLead() {
  if (!dspLeadAberto || !dspLeadAberto.id) return;
  const ativo = !dspLeadAberto.disparo_ativo;
  try {
    const r = await fetch("/api/crm/disparo-ativo", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: [dspLeadAberto.id], ativo: ativo })
    });
    const d = await r.json();
    if (!r.ok) { toast(d.detail || "Não deu pra gravar.", "error"); return; }
    toast("Disparo " + (ativo ? "ligado" : "desligado") + " para este lead.", "ok");
    dspFecharGaveta();
    await dspAtualizarTudo();
  } catch (err) {
    toast("Erro: " + err.message, "error");
  }
}


async function dspSalvarMensagem() {
  if (!dspLeadAberto) return;
  const ta = $("dspGavetaMensagem");
  const msg = ta ? ta.value.trim() : "";
  if (!msg) { toast("A mensagem nao pode ficar vazia.", "error"); return; }
  try {
    // Uma rota so, pelo telefone: ela grava na copy do lead E na fila quando o
    // item ainda esta pendente, pra os dois nunca divergirem.
    const r = await fetch("/api/disparo/copy", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ telefone: dspLeadAberto.telefone, mensagem: msg })
    });
    const d = await r.json();
    if (!r.ok) { toast(d.detail || "Nao deu pra salvar.", "error"); return; }
    toast("Mensagem salva. Ela sai exatamente assim.", "ok");
    dspFecharGaveta();
    await dspAtualizarTudo();
  } catch (err) {
    toast("Erro ao salvar: " + err.message, "error");
  }
}

async function dspMarcarConversa() {
  if (!dspLeadAberto) return;
  try {
    const r = await fetch("/api/disparo/respondido", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ telefone: dspLeadAberto.telefone })
    });
    const d = await r.json();
    if (!r.ok) { toast(d.detail || "Nao deu pra marcar.", "error"); return; }
    toast("Conversa iniciada registrada.", "ok");
    dspFecharGaveta();
    await dspAtualizarTudo();
  } catch (err) {
    toast("Erro ao marcar: " + err.message, "error");
  }
}

async function dspEnviarAgora() {
  if (!dspLeadAberto || !dspLeadAberto.fila_id) return;
  const btn = $("btnDspEnviarAgora");
  if (btn) { btn.disabled = true; btn.textContent = "Enviando..."; }
  try {
    const r = await fetch("/api/disparo/enviar-agora", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: dspLeadAberto.fila_id })
    });
    const d = await r.json();
    toast(d.ok ? "Enviado." : ("Nao saiu: " + (d.erro || "erro desconhecido")),
          d.ok ? "ok" : "error");
    dspFecharGaveta();
    await dspAtualizarTudo();
  } catch (err) {
    toast("Erro ao enviar: " + err.message, "error");
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "Enviar agora"; }
  }
}

function dspIniciarGaveta() {
  if (!$("dspGaveta")) return;
  if ($("btnDspGavetaFechar")) $("btnDspGavetaFechar").addEventListener("click", dspFecharGaveta);
  if ($("dspGavetaFundo")) $("dspGavetaFundo").addEventListener("click", dspFecharGaveta);
  if ($("btnDspSalvarMensagem")) $("btnDspSalvarMensagem").addEventListener("click", dspSalvarMensagem);
  if ($("btnDspConversaIniciada")) $("btnDspConversaIniciada").addEventListener("click", dspMarcarConversa);
  if ($("btnDspEnviarAgora")) $("btnDspEnviarAgora").addEventListener("click", dspEnviarAgora);
  if ($("btnDspLigarLead")) $("btnDspLigarLead").addEventListener("click", dspLigarLead);
  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape" && $("dspGaveta") && !$("dspGaveta").classList.contains("hidden")) {
      dspFecharGaveta();
    }
  });
}

window.dspAbrirGaveta = dspAbrirGaveta;
window.dspFecharGaveta = dspFecharGaveta;
window.dspIniciarGaveta = dspIniciarGaveta;
