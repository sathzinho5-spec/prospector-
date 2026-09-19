// proposito: o painel de conversao por versao do playbook, na aba Disparo
//
// Arquivo proprio porque a pergunta e outra. A lista responde "o que fazer
// agora"; este painel responde "o que a operacao aprendeu", e e ele que a
// copywriter-expert le antes de escrever a versao seguinte do playbook.
//
// Nada e calculado aqui: a taxa vem pronta de /api/disparo/conversao. Conta
// refeita na tela e conta que passa a divergir do banco.

function dspConvLinha(rotulo, valor) {
  return "<div class='dsp-ficha-linha'>" +
    "<div class='dsp-ficha-rotulo'>" + esc(rotulo) + "</div>" +
    "<div class='dsp-ficha-valor'>" + esc(valor) + "</div></div>";
}

function dspConvRotulo(linha) {
  // 'sem_versao' e o carimbo do que saiu antes de o playbook existir. Fica
  // legivel de proposito: some da tela seria perder a linha de base contra a
  // qual a primeira versao vai ser comparada.
  const v = linha.copy_versao === "sem_versao" ? "antes do playbook"
                                               : "playbook " + linha.copy_versao;
  return v + " · " + linha.copy_origem;
}

async function dspCarregarConversao() {
  const corpo = $("dspConversaoCorpo");
  if (!corpo) return;
  try {
    const d = await (await fetch("/api/disparo/conversao")).json();

    const versao = $("dspConversaoVersao");
    if (versao) {
      versao.textContent = d.playbook_disponivel
        ? "versão no ar: " + d.versao_no_ar
        : "playbook não chegou no servidor, a copy está saindo pelas regras mínimas";
    }

    const linhas = d.por_versao || [];
    const vazia = $("dspConversaoVazia");
    if (vazia) vazia.classList.toggle("hidden", linhas.length > 0);

    corpo.innerHTML = linhas.map(function (l) {
      return dspConvLinha(dspConvRotulo(l),
        l.respondidas + " de " + l.enviadas + " · " + l.taxa + "%");
    }).join("") + (linhas.length > 1
      ? dspConvLinha("total", d.conversas_iniciadas + " de " + d.enviadas + " · " + d.taxa + "%")
      : "");
  } catch {
    corpo.innerHTML = "";
    if ($("dspConversaoVazia")) $("dspConversaoVazia").classList.remove("hidden");
  }
}

window.dspCarregarConversao = dspCarregarConversao;
