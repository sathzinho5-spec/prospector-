// proposito: aba de conexao do numero, faixa de estado e quem esta logado
/* Painel: a aba Conexao do numero, a faixa de estado e quem esta logado.
 *
 * Tudo aqui vive POR FORA do app.js, de proposito. O app.js e reescrito toda
 * semana pelo socio; o que e nosso mora neste arquivo e nao entra em conflito.
 *
 * O unico ponto de contato e o window.switchTab, que o app.js publica no
 * window. Este arquivo o embrulha em vez de reescreve-lo: a versao original
 * continua fazendo o que sempre fez, e o embrulho so cuida da aba que ela nao
 * conhece.
 */
(function () {
  "use strict";

  var pegar = function (id) { return document.getElementById(id); };

  /* ------------------------------------------------- a aba que ele nao ve -- */

  var secConexao = pegar("secConexao");
  var original = window.switchTab;

  if (typeof original === "function" && secConexao) {
    window.switchTab = function (nome) {
      // A original esconde as cinco abas que ela conhece. Quando o alvo e
      // "conexao", nenhuma delas casa, entao ela esconde todas - que e
      // exatamente o que a aba nova precisa.
      original(nome);
      secConexao.classList.toggle("hidden", nome !== "conexao");
      if (nome === "conexao") lerEstado();
    };
  }

  /* ------------------------------------------------------ faixa de estado -- */

  function pintar(elemento, texto, classe) {
    if (!elemento) return;
    elemento.className = "pill " + classe;
    elemento.textContent = texto;
  }

  /** O estado do chip e do disparo, que antes so existia dentro do Comercial. */
  async function lerEstado() {
    try {
      var r = await fetch("/api/disparo/evolution/estado");
      var d = await r.json();
      if (d && d.conectado) {
        pintar(pegar("estadoChip"), "chip conectado", "open");
        pintar(pegar("conexaoEstado"), "conectado", "open");
      } else {
        var motivo = (d && d.estado === "nao_configurado")
          ? "chip nao configurado" : "chip desconectado";
        pintar(pegar("estadoChip"), motivo, "closed");
        pintar(pegar("conexaoEstado"), motivo, "closed");
      }
      var lista = pegar("conexaoLista");
      if (lista) {
        lista.textContent = (d && d.erro)
          ? d.erro
          : ((d && d.estado) ? "Estado da conexao: " + d.estado : "");
      }
    } catch {
      pintar(pegar("estadoChip"), "chip: nao deu pra conferir", "closed");
    }

    try {
      var r2 = await fetch("/api/disparo/status");
      var s = await r2.json();
      if (s && s.rodando) {
        pintar(pegar("estadoDisparo"), "disparo ARMADO", "high");
      } else {
        // Desarmado e o estado normal, e precisa ser legivel sem assustar.
        pintar(pegar("estadoDisparo"), "disparo desarmado", "closed");
      }
      var hoje = pegar("estadoHoje");
      if (hoje && s) {
        var enviadas = s.enviados_hoje || 0;
        var pendentes = s.pendentes || 0;
        hoje.textContent = enviadas + " enviadas hoje · " + pendentes + " na fila";
      }
    } catch {
      pintar(pegar("estadoDisparo"), "disparo: nao deu pra conferir", "closed");
    }
  }

  /* ------------------------------------------------------- quem esta aqui -- */

  async function lerConta() {
    try {
      var r = await fetch("/api/acesso/eu");
      var eu = await r.json();
      if (!eu || !eu.entrou) return;
      var nome = pegar("quemNome");
      var papel = pegar("quemPapel");
      if (nome) nome.textContent = eu.email;
      if (papel) papel.textContent = eu.dono ? "dono" : "afiliado";
      // A fila de acessos so existe pra quem pode liberar alguem.
      var acessos = pegar("btnAcessos");
      if (acessos && eu.dono) acessos.hidden = false;
    } catch { /* o rodape fica em branco, e a ferramenta segue */ }
  }

  /* -------------------------------------------------------------- ligacao -- */

  // O botao de conectar da aba nova reaproveita o que o app.js ja faz: em vez
  // de duplicar o fluxo do QR, ele clica no botao original, que continua vivo
  // dentro do Comercial. Duplicar significaria manter dois fluxos de QR.
  var conectar = pegar("btnConexaoConectar");
  if (conectar) {
    conectar.addEventListener("click", function () {
      // Direto, e nao mais clicando no botao original: o btnConnectWa saiu da
      // aba Comercial quando ela virou Disparo, e o clique simulado passou a
      // nao fazer NADA, sem erro na tela. O clique fica so de compatibilidade.
      if (typeof window.connectWhatsApp === "function") {
        window.connectWhatsApp();
        return;
      }
      var original = pegar("btnConnectWa");
      if (original) original.click();
    });
  }

  var atualizar = pegar("btnConexaoAtualizar");
  if (atualizar) atualizar.addEventListener("click", lerEstado);

  lerConta();
  lerEstado();
  // A faixa precisa envelhecer sozinha: o chip pode cair enquanto a pessoa esta
  // em outra aba, e era justamente isso que ninguem via antes.
  setInterval(lerEstado, 60000);
})();
