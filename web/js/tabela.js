// proposito: tabela de resultados: ordenacao, selecao, paginacao e acoes em lote
let tableState = { page: 1, perPage: 25, sortKey: "", sortDir: 1 };
let selectedKeys = {};

function bizKey(b) {
  return String(b.nome || "") + "|" + String(b.telefone || "") + "|" + String(b.endereco || "");
}

function selectedList() {
  return bizCache.filter(function (b) { return selectedKeys[bizKey(b)]; });
}

function updateBulkBar() {
  const n = Object.keys(selectedKeys).length;
  const bar = $("bulkBar");
  if (!bar) return;
  bar.classList.toggle("hidden", !n);
  $("bulkCount").textContent = n + " selecionada(s)";
  const sel = $("selAll");
  if (sel) {
    const pageKeys = currentPageRows().map(bizKey);
    const all = pageKeys.length > 0 && pageKeys.every(function (k) { return selectedKeys[k]; });
    sel.checked = all;
  }
}

function currentPageRows() {
  const arr = filteredBusinesses();
  const start = (tableState.page - 1) * tableState.perPage;
  return arr.slice(start, start + tableState.perPage);
}

function toggleSelectAll(checked) {
  currentPageRows().forEach(function (b) {
    if (checked) selectedKeys[bizKey(b)] = true;
    else delete selectedKeys[bizKey(b)];
  });
  paintSelection();
}

function paintSelection() {
  document.querySelectorAll("#resultsBody tr[data-key]").forEach(function (tr) {
    tr.classList.toggle("selected", !!selectedKeys[tr.dataset.key]);
    const cb = tr.querySelector("input.row-check");
    if (cb) cb.checked = !!selectedKeys[tr.dataset.key];
  });
  updateBulkBar();
}

function clearSelection() {
  selectedKeys = {};
  paintSelection();
}

function sortArrow(key) {
  if (tableState.sortKey !== key) return "";
  return tableState.sortDir === 1 ? " ▲" : " ▼";
}

window.sortBy = function (key) {
  if (tableState.sortKey === key) {
    tableState.sortDir = tableState.sortDir === 1 ? -1 : 1;
  } else {
    tableState.sortKey = key;
    tableState.sortDir = (key === "nome" || key === "cidade") ? 1 : -1;
  }
  tableState.page = 1;
  renderResults(bizCache);
};

window.gotoPage = function (p) {
  tableState.page = p;
  renderResults(bizCache);
};

function renderPager(total, page, perPage, fnName) {
  const pages = Math.max(1, Math.ceil(total / perPage));
  if (page > pages) page = pages;
  let html = "<span class='hint'>Página " + page + " de " + pages + " · " + total + " itens</span>";
  html += "<div class='btn-row' style='margin:0;'>";
  html += "<button class='btn small' " + (page <= 1 ? "disabled" : "") + " onclick='" + fnName + "(" + (page - 1) + ")'>Anterior</button>";
  html += "<button class='btn small' " + (page >= pages ? "disabled" : "") + " onclick='" + fnName + "(" + (page + 1) + ")'>Próxima</button>";
  html += "</div>";
  return { html: html, page: page, pages: pages };
}

function renderResults(businesses) {
  bizCache = businesses;
  const tb = $("tabResultsBadge");
  if (tb) {
    tb.textContent = businesses.length;
    tb.classList.toggle("hidden", !businesses.length);
  }
  const rc = $("resultsCount");
  if (rc) {
    rc.textContent = businesses.length;
    rc.classList.toggle("hidden", !businesses.length);
  }

  const arr = filteredBusinesses();
  $("filterInfo").textContent = arr.length + " de " + bizCache.length + " exibidos";

  const perPage = tableState.perPage;
  const pages = Math.max(1, Math.ceil(arr.length / perPage));
  if (tableState.page > pages) tableState.page = pages;
  const rows = arr.slice((tableState.page - 1) * perPage, tableState.page * perPage);

  const body = $("resultsBody");
  if (!rows.length) {
    body.innerHTML = "<tr><td colspan='10'><div class='empty-box'>" +
      "<b>Nenhum resultado</b><span>Ajuste os filtros ou rode uma nova busca.</span></div></td></tr>";
  } else {
    body.innerHTML = rows.map(function (b) {
      const i = bizCache.indexOf(b);
      const key = bizKey(b);
      const cidade = [b.cidade, b.estado].filter(Boolean).join(" - ") || "—";
      return (
        "<tr class='biz-row' id='bizRow" + i + "' data-key=\"" + esc(key) + "\" onclick='showDetails(" + i + ")'>" +
        "<td class='col-check' onclick='event.stopPropagation();'><input type='checkbox' class='row-check' data-key=\"" + esc(key) + "\"" + (selectedKeys[key] ? " checked" : "") + "></td>" +
        "<td><div class='cell-main'>" + avatarHtml(b) +
        "<div style='min-width:0;'><div class='cell-name'>" + esc(b.nome) + "</div>" +
        "<div class='cell-sub'>" + esc(b.categoria || "—") + "</div></div></div></td>" +
        "<td>" + (b.nota ? "<span class='star-chip'>★ " + esc(b.nota) + "</span>" : "—") + "</td>" +
        "<td class='num'>" + (esc(b.avaliacoes) || "—") + "</td>" +
        "<td>" + esc(cidade) + "</td>" +
        "<td class='nowrap'>" + (esc(b.telefone) || "—") + "</td>" +
        "<td>" + (b.website ? "<a class='link' href='" + esc(b.website) + "' target='_blank' onclick='event.stopPropagation();'>Site</a>" : "—") + "</td>" +
        "<td>" + (statusPill(b) || "<span class='muted'>—</span>") + "</td>" +
        "<td>" + (scorePill(b) + urgencyPill(b) || "<span class='muted'>—</span>") + "</td>" +
        "<td><div class='row-actions'>" +
        (waPhone(b) ? "<button class='btn small wa' onclick='event.stopPropagation();openWhatsApp(" + i + ")'>WhatsApp</button>" : "") +
        "<button class='btn small primary' onclick='event.stopPropagation();selectBusiness(" + i + ", false);doStrategy()'>Estratégia</button>" +
        "</div></td>" +
        "</tr>"
      );
    }).join("");
  }

  document.querySelectorAll("#resultsBody .row-check").forEach(function (cb) {
    cb.addEventListener("change", function () {
      if (cb.checked) selectedKeys[cb.dataset.key] = true;
      else delete selectedKeys[cb.dataset.key];
      paintSelection();
    });
  });

  document.querySelectorAll("#resultsTable th.sortable").forEach(function (th) {
    const k = th.dataset.sort;
    th.classList.toggle("sorted", tableState.sortKey === k);
    const base = th.textContent.replace(/ [▲▼]/g, "");
    th.textContent = base + sortArrow(k);
    if (!th.dataset.sortBound) {
      th.dataset.sortBound = "1";
      th.addEventListener("click", function () { window.sortBy(k); });
    }
  });

  const pg = renderPager(arr.length, tableState.page, perPage, "gotoPage");
  tableState.page = pg.page;
  $("resultsPager").innerHTML = pg.html;
  updateBulkBar();
}

function renderSkeleton(rows) {
  const body = $("resultsBody");
  if (!body) return;
  let html = "";
  for (let i = 0; i < (rows || 6); i++) {
    html += "<tr class='skel-row'><td></td><td><div class='skel' style='width:70%'></div><div class='skel sm' style='width:45%'></div></td><td><div class='skel sm'></div></td><td><div class='skel sm'></div></td><td><div class='skel sm'></div></td><td><div class='skel sm'></div></td><td><div class='skel sm'></div></td><td><div class='skel sm'></div></td><td><div class='skel sm'></div></td><td><div class='skel sm'></div></td></tr>";
  }
  body.innerHTML = html;
  $("resultsPager").innerHTML = "";
}

function renderTableError(msg) {
  const body = $("resultsBody");
  if (!body) return;
  body.innerHTML = "<tr><td colspan='10'><div class='empty-box'>" +
    "<b>Não foi possível carregar</b><span>" + esc(msg) + "</span>" +
    "<button class='btn small primary' onclick='doSearch()'>Tentar de novo</button></div></td></tr>";
  $("resultsPager").innerHTML = "";
}

async function bulkAnalyze() {
  const list = selectedList();
  if (!list.length) return;
  showLoader("Analisando " + list.length + " selecionadas com IA...");
  const CHUNK = 5;
  try {
    for (let i = 0; i < list.length; i += CHUNK) {
      const chunk = list.slice(i, i + CHUNK);
      const r = await fetch("/api/business/strategy_batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ businesses: chunk })
      });
      const d = await r.json();
      if (r.ok && d.results) {
        d.results.forEach(function (res) {
          const b = bizCache.find(function (x) { return x.nome === res.nome; });
          if (b && res) {
            b.score_oportunidade = res.score;
            b.nivel_ia = res.nivel;
            b.estrategia_resumo = res.resumo;
            b.oportunidades_ia = res.oportunidades;
            b.strategy_engine = res.engine;
          }
        });
      }
      $("loaderText").textContent = "Analisando " + Math.min(i + CHUNK, list.length) + "/" + list.length + "...";
    }
    hideLoader();
    filters.sort = "score";
    const fs = $("fSort");
    if (fs) fs.value = "score";
    tableState.sortKey = "";
    renderResults(bizCache);
    toast(list.length + " leads pontuados pela IA", "ok");
  } catch (e) {
    hideLoader();
    showStatus("searchStatus", "Falha na análise: " + e.message, "error");
  }
}

async function bulkEnqueue() {
  const list = selectedList().filter(function (b) { return waPhone(b); });
  if (!list.length) {
    toast("Nenhuma selecionada com telefone", "error");
    return;
  }
  showLoader("Gerando mensagens 0/" + list.length + "...");
  const itens = [];
  try {
    for (let i = 0; i < list.length; i++) {
      const b = list[i];
      const r = await fetch("/api/business/pitch?rapido=1", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ business: b })
      });
      const d = await r.json();
      if (r.ok && d.whatsapp) itens.push({ nome: b.nome, telefone: b.telefone, mensagem: d.whatsapp, categoria: b.categoria || "" });
      $("loaderText").textContent = "Gerando mensagens " + (i + 1) + "/" + list.length + "...";
    }
    const r2 = await fetch("/api/disparo/enfileirar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ itens: itens, origem: "bulk" })
    });
    const d2 = await r2.json();
    hideLoader();
    if (!r2.ok) throw new Error(d2.detail || "Erro");
    toast(d2.enfileirados + " leads na fila de disparo", "ok");
    switchTab("comercial");
  } catch (e) {
    hideLoader();
    showStatus("searchStatus", "Falha: " + e.message, "error");
  }
}

function bulkExportCsv() {
  const list = selectedList();
  if (!list.length) return;
  const fields = ["nome", "categoria", "nota", "avaliacoes", "endereco", "cidade", "estado", "telefone", "website", "score_oportunidade"];
  const escCsv = function (v) {
    v = v == null ? "" : String(v);
    return /[;"\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
  };
  let csv = "﻿" + fields.join(";") + "\n";
  list.forEach(function (b) {
    csv += fields.map(function (f) { return escCsv(b[f]); }).join(";") + "\n";
  });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  a.download = "leads-selecionados.csv";
  a.click();
  toast(list.length + " leads exportados", "ok");
}
