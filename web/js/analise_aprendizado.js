// proposito: o painel de aprendizado: o que mais converte e o recalculo do score
//
// Saiu de web/js/analise.js pela costura que o proprio arquivo marcava com o
// cabecalho "APRENDIZADO". As outras funcoes de la respondem "o que este lead
// e"; estas duas respondem "o que a carteira inteira ensinou". JS classico sem
// modulo: as duas seguem globais e o app.js continua chamando pelo mesmo nome,
// entao nenhuma chamada de fora mudou.

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
