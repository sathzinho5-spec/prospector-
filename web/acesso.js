// proposito: decide qual das quatro telas de acesso aparece, pelo endereco e pela sessao
/* Comportamento das telas de acesso.
 *
 * As quatro telas vivem no mesmo acesso.html. Este arquivo decide qual cartao
 * aparece, a partir de duas coisas: o endereco que a pessoa abriu e o estado da
 * sessao, que vem de /api/acesso/eu.
 *
 * Os nomes de classe usados aqui sao os do contrato no topo do acesso.css. Uma
 * tela e mostrada e escondida pelo atributo [hidden], nunca por classe.
 */
(function () {
  "use strict";

  var TELAS = {
    entrar: document.getElementById("telaEntrar"),
    criar: document.getElementById("telaCriar"),
    aguardando: document.getElementById("telaAguardando"),
    acessos: document.getElementById("telaAcessos"),
    senha: document.getElementById("telaSenha"),
  };

  function mostrar(nome) {
    Object.keys(TELAS).forEach(function (k) {
      if (TELAS[k]) TELAS[k].hidden = k !== nome;
    });
  }

  function erro(caixa, texto, elemento) {
    if (!caixa) return;
    if (!texto) {
      caixa.hidden = true;
      return;
    }
    if (elemento) elemento.textContent = texto;
    caixa.hidden = false;
  }

  /** Data no formato que ele le nas notas: 16/09/26 21h02. */
  function quando(iso) {
    if (!iso) return "";
    var d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    function dois(n) { return String(n).padStart(2, "0"); }
    return dois(d.getDate()) + "/" + dois(d.getMonth() + 1) + "/" +
      String(d.getFullYear()).slice(2) + " " + dois(d.getHours()) + "h" + dois(d.getMinutes());
  }

  async function pedir(caminho, corpo) {
    var opcoes = { method: corpo ? "POST" : "GET", headers: {} };
    if (corpo) {
      opcoes.headers["Content-Type"] = "application/json";
      opcoes.body = JSON.stringify(corpo);
    }
    var r = await fetch(caminho, opcoes);
    var dados = {};
    try { dados = await r.json(); } catch { dados = {}; }
    if (!r.ok) {
      throw new Error(dados.erro || dados.detail || "Nao deu pra completar. Tente de novo.");
    }
    return dados;
  }

  /* ----------------------------------------------------------- entrar --- */

  var formEntrar = document.getElementById("formEntrar");
  if (formEntrar) {
    formEntrar.addEventListener("submit", async function (e) {
      e.preventDefault();
      var botao = document.getElementById("botaoEntrar");
      erro(document.getElementById("erroEntrar"), "");
      botao.disabled = true;
      try {
        var r = await pedir("/api/acesso/entrar", {
          email: document.getElementById("entrarEmail").value,
          senha: document.getElementById("entrarSenha").value,
        });
        window.location.href = r.status === "aprovado" ? "/" : "/aguardando";
      } catch (err) {
        erro(document.getElementById("erroEntrar"), err.message,
             document.getElementById("erroEntrarTexto"));
        botao.disabled = false;
      }
    });
  }

  /* ------------------------------------------------------ criar conta --- */

  var formCriar = document.getElementById("formCriar");
  if (formCriar) {
    formCriar.addEventListener("submit", async function (e) {
      e.preventDefault();
      var botao = document.getElementById("botaoCriar");
      var caixa = document.getElementById("erroCriar");
      var texto = document.getElementById("erroCriarTexto");
      erro(caixa, "");

      var senha = document.getElementById("criarSenha").value;
      if (senha !== document.getElementById("criarSenha2").value) {
        erro(caixa, "As duas senhas nao sao iguais.", texto);
        return;
      }

      botao.disabled = true;
      try {
        var r = await pedir("/api/acesso/criar", {
          email: document.getElementById("criarEmail").value,
          senha: senha,
        });
        window.location.href = r.status === "aprovado" ? "/" : "/aguardando";
      } catch (err) {
        erro(caixa, err.message, texto);
        botao.disabled = false;
      }
    });
  }

  /* ------------------------------------------------------- aguardando --- */

  function sair() {
    pedir("/api/acesso/sair", {}).finally(function () {
      window.location.href = "/entrar";
    });
  }

  ["botaoSairAguardando", "botaoSairAcessos"].forEach(function (id) {
    var b = document.getElementById(id);
    if (b) b.addEventListener("click", sair);
  });

  /* ------------------------------------------------------ trocar senha --- */

  var formSenha = document.getElementById("formSenha");
  if (formSenha) {
    formSenha.addEventListener("submit", async function (e) {
      e.preventDefault();
      var botao = document.getElementById("botaoSenha");
      var caixa = document.getElementById("erroSenha");
      var texto = document.getElementById("erroSenhaTexto");
      var ok = document.getElementById("okSenha");
      erro(caixa, "");
      ok.hidden = true;

      var nova = document.getElementById("senhaNova").value;
      if (nova !== document.getElementById("senhaNova2").value) {
        erro(caixa, "As duas senhas novas nao sao iguais.", texto);
        return;
      }

      botao.disabled = true;
      try {
        await pedir("/api/acesso/trocar-senha", {
          senha_atual: document.getElementById("senhaAtual").value,
          senha_nova: nova,
        });
        formSenha.reset();
        ok.hidden = false;
      } catch (err) {
        erro(caixa, err.message, texto);
      }
      botao.disabled = false;
    });
  }

  /* ----------------------------------------------------------- acessos -- */

  function linha(conta) {
    var div = document.createElement("div");
    div.className = "acesso-linha";

    var info = document.createElement("div");
    info.className = "acesso-linha-info";

    var nome = document.createElement("div");
    nome.className = "acesso-linha-nome";
    var email = document.createElement("span");
    email.textContent = conta.email;
    nome.appendChild(email);

    if (conta.status === "aprovado") {
      var etiqueta = document.createElement("span");
      etiqueta.className = "pill " + (conta.papel === "dono" ? "med" : "open");
      etiqueta.textContent = conta.papel === "dono" ? "dono" : "liberado";
      nome.appendChild(etiqueta);
    }
    info.appendChild(nome);

    var data = document.createElement("div");
    data.className = "acesso-linha-quando";
    data.textContent = conta.status === "aprovado"
      ? (conta.papel === "dono" ? "desde " + quando(conta.criada_em)
                                : "liberado em " + quando(conta.aprovada_em))
      : "pediu em " + quando(conta.criada_em);
    info.appendChild(data);
    div.appendChild(info);

    var acoes = document.createElement("div");
    acoes.className = "acesso-linha-acoes";

    if (conta.status === "pendente") {
      acoes.appendChild(botaoDeAcao("Liberar", "btn primary", "/api/acesso/liberar", conta.email));
      acoes.appendChild(botaoDeAcao("Recusar", "btn", "/api/acesso/recusar", conta.email));
    } else if (conta.papel !== "dono") {
      acoes.appendChild(botaoDeAcao("Tirar acesso", "btn", "/api/acesso/tirar", conta.email));
    }

    if (acoes.children.length) div.appendChild(acoes);
    return div;
  }

  function botaoDeAcao(texto, classe, caminho, email) {
    var b = document.createElement("button");
    b.className = classe;
    b.type = "button";
    b.textContent = texto;
    b.addEventListener("click", async function () {
      b.disabled = true;
      try {
        await pedir(caminho, { email: email });
        await carregarAcessos();
      } catch (err) {
        erro(document.getElementById("erroAcessos"), err.message,
             document.getElementById("erroAcessosTexto"));
        b.disabled = false;
      }
    });
    return b;
  }

  function encher(lista, contas, vazio) {
    lista.textContent = "";
    if (!contas.length) {
      var p = document.createElement("p");
      p.className = "acesso-vazio";
      p.textContent = vazio;
      lista.appendChild(p);
      return;
    }
    contas.forEach(function (c) { lista.appendChild(linha(c)); });
  }

  async function carregarAcessos() {
    erro(document.getElementById("erroAcessos"), "");
    var dados = await pedir("/api/acesso/contas");
    var todas = dados.contas || [];
    var pendentes = todas.filter(function (c) { return c.status === "pendente"; });
    var liberadas = todas.filter(function (c) { return c.status === "aprovado"; });

    var contagem = document.getElementById("contagemPendentes");
    contagem.textContent = String(pendentes.length);
    contagem.hidden = pendentes.length === 0;

    encher(document.getElementById("listaPendentes"), pendentes, "Ninguem esperando.");
    encher(document.getElementById("listaLiberados"), liberadas, "Ninguem com acesso.");
  }

  /* ------------------------------------------------------------ partida -- */

  async function iniciar() {
    var caminho = window.location.pathname;
    var eu = await pedir("/api/acesso/eu").catch(function () { return { entrou: false }; });

    if (caminho === "/acessos") {
      if (!eu.dono) { window.location.href = "/"; return; }
      document.getElementById("acessosQuem").textContent = eu.email;
      mostrar("acessos");
      carregarAcessos().catch(function (err) {
        erro(document.getElementById("erroAcessos"), err.message,
             document.getElementById("erroAcessosTexto"));
      });
      return;
    }

    if (caminho === "/senha") {
      if (!eu.entrou) { window.location.href = "/entrar"; return; }
      document.getElementById("senhaQuem").textContent = eu.email;
      mostrar("senha");
      return;
    }

    if (caminho === "/aguardando") {
      if (!eu.entrou) { window.location.href = "/entrar"; return; }
      if (eu.status === "aprovado") { window.location.href = "/"; return; }
      document.getElementById("aguardandoEmail").textContent = eu.email;
      document.getElementById("aguardandoQuando").textContent = quando(eu.criada_em);
      mostrar("aguardando");
      return;
    }

    // Quem ja esta dentro nao precisa ver a tela de entrar de novo.
    if (eu.entrou && eu.status === "aprovado") { window.location.href = "/"; return; }
    if (eu.entrou) { window.location.href = "/aguardando"; return; }

    mostrar(caminho === "/criar-conta" ? "criar" : "entrar");
  }

  iniciar();
})();
