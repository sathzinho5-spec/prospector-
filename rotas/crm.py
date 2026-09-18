# proposito: leads na nuvem e o CRM: listar, filtrar e mover de estagio
from fastapi import APIRouter, HTTPException

from rotas.modelos import CrmStatusRequest, DisparoAtivoRequest

router = APIRouter()


@router.get("/api/cloud/status")
def api_cloud_status():
    try:
        from scrapers import cloud_store
        online = cloud_store.ping()
    except Exception:
        online = False
    return {"online": online}


@router.get("/api/cloud/leads")
def api_cloud_leads(estado: str = "", min_score: int = 0, apenas_pendentes: bool = False, limite: int = 200):
    from scrapers import cloud_store

    return {"leads": cloud_store.listar_leads(
        estado=estado or None,
        min_score=min_score or None,
        apenas_pendentes=apenas_pendentes,
        limite=min(500, limite),
    )}


@router.get("/api/crm/leads")
def api_crm_leads(busca: str = "", uf: str = "", status: str = "", min_score: int = 0, limite: int = 500):
    from scrapers import cloud_store

    leads = cloud_store.listar_leads(limite=min(500, limite))
    q = (busca or "").strip().lower()
    if q:
        leads = [l for l in leads if q in str(l.get("nome", "")).lower()
                 or q in str(l.get("cidade", "")).lower()
                 or q in str(l.get("categoria", "")).lower()]
    if uf:
        leads = [l for l in leads if str(l.get("estado", "")).upper() == uf.upper()]
    if status:
        leads = [l for l in leads if str(l.get("contato_status") or "novo") == status]
    if min_score:
        leads = [l for l in leads if (l.get("score_oportunidade") or 0) >= min_score]
    return {"total": len(leads), "leads": leads}


@router.post("/api/crm/disparo-ativo")
def api_crm_disparo_ativo(req: DisparoAtivoRequest):
    """Liga ou desliga o disparo de um lead ou de varios de uma vez."""
    from scrapers import cloud_store

    if not req.ids:
        raise HTTPException(400, "Informe pelo menos um lead.")
    n = cloud_store.set_disparo_ativo(req.ids, req.ativo)
    if not n:
        raise HTTPException(502, "Nao deu pra gravar na nuvem. Tente de novo.")
    return {"ok": True, "atualizados": n, "ativo": bool(req.ativo)}


@router.post("/api/crm/status")
def api_crm_status(req: CrmStatusRequest):
    from scrapers import cloud_store

    if not req.id and not req.nome:
        raise HTTPException(400, "Informe o lead.")
    _id = req.id
    if not _id:
        _id = cloud_store.lead_id({"nome": req.nome, "endereco": req.endereco, "telefone": req.telefone})
    anterior = None
    try:
        lead = cloud_store.obter_lead(_id)
        anterior = (lead or {}).get("contato_status")
    except Exception:
        pass
    ok = cloud_store.set_contato_status_by_id(_id, req.status, req.observacao)
    if ok and anterior != req.status:
        try:
            cloud_store.log_evento(_id, req.status, anterior, req.status)
        except Exception:
            pass
    return {"ok": ok}


@router.get("/api/crm/aprendizado")
def api_crm_aprendizado():
    """Previa do aprendizado: calcula sem gravar. A tela mostra e quem decide
    se aplica e o botao Recalcular (POST)."""
    from analysis import aprendizado
    from scrapers import cloud_store

    leads = cloud_store.listar_leads(limite=500)
    return aprendizado.recalcular(leads)


@router.post("/api/crm/aprendizado/recalcular")
def api_crm_aprendizado_recalcular():
    """Recalcula e grava score_ajustado + motivo na nuvem. Best-effort como o
    resto da nuvem: sem colunas novas no banco, calcula e devolve sem gravar."""
    from analysis import aprendizado
    from scrapers import cloud_store

    leads = cloud_store.listar_leads(limite=500)
    r = aprendizado.recalcular(leads)
    gravados = cloud_store.set_aprendizado(r.get("ajustes") or {}) if r.get("ok") else 0
    r["gravados"] = gravados
    return r


