# proposito: score que aprende: conversao por perfil vira ajuste do score
"""
Fase 1 do loop fechado: estatistica por bucket, sem ML. Cada lead tocado
(status diferente de "novo") vota; quem converteu (respondeu, negociando,
fechado) pesa. O lift de cada bucket passa por shrinkage: bucket pequeno
encolhe pra media, pra 2 fechamentos nao transformarem um nicho em ouro.

O historico fino mora em eventos_lead (log_evento no cloud_store). Este modulo
usa o retrato atual pra v1; os eventos acumulam pra v2 e pra deteccao de
resposta do follow-up.
"""
from analysis import timing

# Status que contam como "tocado" e como "converteu". Mesmos nomes do CRM.
CONVERTEU = ("respondido", "negociando", "fechado")
MIN_TOTAL = 15
MIN_BUCKET = 5
SHRINK_K = 20


def _num(x):
    try:
        return float(str(x).replace(".", "").replace(",", ".")) if "," in str(x) else float(str(x))
    except Exception:
        return 0.0


def faixa_nota(b):
    n = _num(b.get("nota"))
    if n <= 0:
        return "sem nota"
    if n < 4.0:
        return "nota < 4,0"
    if n < 4.5:
        return "nota 4,0–4,5"
    return "nota 4,5+"


def faixa_av(b):
    try:
        av = int(float(str(b.get("avaliacoes") or "0").replace(".", "").replace(",", ".")))
    except Exception:
        av = 0
    if av < 30:
        return "poucas avaliações"
    if av < 150:
        return "30–150 avaliações"
    return "150+ avaliações"


def tem_site(b):
    return "com site" if (b.get("website") or "").strip() else "sem site"


def nicho(b):
    nid = timing.nicho_de(b.get("categoria") or "")
    return nid or "outros"


def _buckets(b):
    return (
        ("nota", faixa_nota(b)),
        ("avaliacoes", faixa_av(b)),
        ("site", tem_site(b)),
        ("nicho", nicho(b)),
    )


def recalcular(leads):
    """leads: lista de dicts com contato_status + atributos. Retorna o pacote
    completo: ajustes por lead_id (ou None) + tabela pra tela + estado."""
    tocados = [b for b in (leads or []) if str(b.get("contato_status") or "novo") != "novo"]
    conv = [b for b in tocados if str(b.get("contato_status") or "") in CONVERTEU]
    n_total = len(tocados)
    if n_total < MIN_TOTAL:
        return {"ok": False, "motivo": "aprendendo",
                "eventos": n_total, "minimo": MIN_TOTAL,
                "ajustes": {}, "tabela": []}
    base = len(conv) / n_total

    stats = {}
    for b in tocados:
        c = str(b.get("contato_status") or "") in CONVERTEU
        for dim, val in _buckets(b):
            s = stats.setdefault((dim, val), [0, 0])
            s[0] += 1
            if c:
                s[1] += 1

    lifts = {}
    tabela = []
    for (dim, val), (n, k) in stats.items():
        if n < MIN_BUCKET:
            continue
        taxa = k / n
        lift_raw = (taxa / base) if base > 0 else 1.0
        lift = (n * lift_raw + SHRINK_K * 1.0) / (n + SHRINK_K)
        lifts[(dim, val)] = lift
        tabela.append({"dim": dim, "valor": val, "n": n,
                       "taxa": round(100.0 * taxa, 1), "lift": round(lift, 2)})
    tabela.sort(key=lambda r: r["lift"], reverse=True)

    ajustes = {}
    for b in tocados:
        score = b.get("score_oportunidade")
        if score is None:
            continue
        vals = [lifts[k] for k in _buckets(b) if k in lifts]
        if not vals:
            continue
        lift_medio = sum(vals) / len(vals)
        ajustado = max(5, min(99, round(float(score) * lift_medio)))
        if ajustado == int(score):
            continue
        # Motivo: o bucket mais forte com amostra decente, em linguagem de dono.
        cand = [(lifts[k], k) for k in _buckets(b) if k in lifts]
        cand.sort(reverse=True)
        dim, val = cand[0][1]
        quanto = cand[0][0]
        motivo = "Leads %s fecham %.1fx mais" % (val, quanto) if quanto >= 1 \
            else "Leads %s fecham %.0f%% menos" % (val, (1 - quanto) * 100)
        lid = b.get("id")
        if lid:
            ajustes[str(lid)] = {"score_ajustado": ajustado, "motivo": motivo}
    return {"ok": True, "eventos": n_total,
            "base": round(100.0 * base, 1),
            "ajustes": ajustes, "tabela": tabela}
