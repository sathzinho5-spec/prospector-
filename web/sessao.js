/* Sessao dentro da ferramenta: mostra o link de Acessos pra quem e dono e faz
 * o Sair sair de verdade.
 *
 * Vive num arquivo proprio de proposito. O app.js e reescrito toda semana, e o
 * que mora aqui nao tem nada a ver com prospeccao: e a porta de entrada.
 */
(function () {
  "use strict";

  var linkAcessos = document.getElementById("btnAcessos");
  var linkSair = document.getElementById("btnSair");

  if (linkSair) {
    linkSair.addEventListener("click", function (e) {
      // Sem isto o clique so navegaria pro /entrar com o cookie ainda de pe, e
      // a porta de acesso mandaria a pessoa direto de volta pra ferramenta.
      e.preventDefault();
      fetch("/api/acesso/sair", { method: "POST" })
        .catch(function () {})
        .then(function () { window.location.href = "/entrar"; });
    });
  }

  if (linkAcessos) {
    fetch("/api/acesso/eu")
      .then(function (r) { return r.json(); })
      .then(function (eu) { if (eu && eu.dono) linkAcessos.hidden = false; })
      .catch(function () {});
  }
})();
