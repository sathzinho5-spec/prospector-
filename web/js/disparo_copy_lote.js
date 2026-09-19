// proposito: criar a copy dos leads em lote, respeitando tempo de proxy e teto de IA
//
// Saiu de web/js/disparo_aba.js porque a pergunta e outra: aquele arquivo monta a
// lista e os KPIs, este gasta chamada paga de IA. A separacao tambem isola a
// unica parte da aba que demora minutos, e que por isso precisa de lote e de
// progresso na tela.

// Cada copy custa uma chamada de IA que leva perto de 9 segundos. A carteira
// inteira num request so passa de 4 minutos, e o proxy da VPS corta MUITO antes
// disso: quem clicasse veria erro enquanto o servidor seguia gerando. Entao vai
// de tres em tres, que e ~26s por request, com folga pra qualquer timeout de
// proxy. Mesmo padrao do analyzeAll, que ja fatia em lote por este motivo.
var DSP_LOTE_COPY = 3;

async function dspTetoDeIa() {
  // O teto existe pra uma carteira grande nao virar centenas de chamadas pagas
  // num clique. Ele era por request; como agora o cliente fatia, a conta teria
  // escapado dele. Por isso o teto e aplicado aqui, no TOTAL do clique.
  try {
    const s = await (await fetch("/api/settings")).json();
    const n = parseInt(s.abordagem_ia_max, 10);
    return n > 0 ? n : 30;
  } catch {
    return 30;
  }
}

function dspAlvosDaCopy() {
  const marcados = dspTelefonesSelecionados();
  // Com selecao: sao esses, e refazer vale, porque marcar e clicar "criar copy"
  // so pode querer dizer "refaz estes". Sem selecao: vale quem esta sem copy, e
  // refazer fica FALSO, pra um clique distraido nunca reescrever copy que ja
  // existe. Filtrar aqui, em vez de mandar lista vazia, e o que permite contar
  // o progresso e aplicar o teto antes de gastar chamada paga.
  if (marcados.length) return { telefones: marcados, refazer: true };
  return {
    telefones: dspLeads.filter(function (l) { return l.estado === "sem_copy"; })
                       .map(function (l) { return l.telefone; }),
    refazer: false
  };
}

async function dspCriarCopy() {
  const btn = $("btnDspCriarCopy");
  const rotulo = btn ? btn.textContent : "";
  const pedido = dspAlvosDaCopy();
  let alvos = pedido.telefones;
  if (!alvos.length) {
    toast("Nenhum lead sem copy. Marque leads na lista para refazer a copy deles.", "info");
    return;
  }

  const teto = await dspTetoDeIa();
  const cortados = Math.max(0, alvos.length - teto);
  alvos = alvos.slice(0, teto);

  const soma = { criados: 0, ja_tinham: 0, sem_mensagem: 0, desativados: 0,
                 manuais_preservadas: 0 };
  let falhou = "";
  if (btn) btn.disabled = true;

  for (let i = 0; i < alvos.length; i += DSP_LOTE_COPY) {
    const lote = alvos.slice(i, i + DSP_LOTE_COPY);
    if (btn) btn.textContent = "Criando " + (i + lote.length) + "/" + alvos.length + "...";
    try {
      const r = await fetch("/api/disparo/criar-copy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ telefones: lote, refazer: pedido.refazer })
      });
      const d = await r.json();
      if (!r.ok) { falhou = d.detail || "erro no servidor"; break; }
      Object.keys(soma).forEach(function (k) { soma[k] += (d[k] || 0); });
    } catch (err) {
      falhou = err.message;
      break;
    }
  }

  if (btn) { btn.disabled = false; btn.textContent = rotulo || "Criar copy"; }

  // O nome do campo e 'criados', com o do servidor. A versao anterior lia
  // 'criadas' e 'total', que nunca existiram: criava as 29 e dizia na tela que
  // nao tinha criado nenhuma.
  const partes = [];
  if (soma.criados) partes.push(soma.criados + " copy" + (soma.criados === 1 ? "" : "s") + " criada" + (soma.criados === 1 ? "" : "s"));
  if (soma.ja_tinham) partes.push(soma.ja_tinham + " já tinham");
  if (soma.sem_mensagem) partes.push(soma.sem_mensagem + " a IA não cobriu");
  if (soma.manuais_preservadas) {
    partes.push(soma.manuais_preservadas + " mantiveram o texto que você escreveu");
  }
  if (cortados) partes.push(cortados + " ficaram para a próxima pelo teto de " + teto);
  if (soma.desativados) partes.push(soma.desativados + " estão com o disparo desligado");

  if (falhou) {
    toast("Parou no meio: " + falhou + ". " + (partes.join(", ") || "nada foi criado") + ".", "error");
  } else {
    toast(partes.join(", ") + ".", soma.criados ? "ok" : "info");
  }
  await dspAtualizarTudo();
}

window.dspCriarCopy = dspCriarCopy;
