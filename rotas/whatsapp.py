# proposito: conversas do WhatsApp: chats, mensagens, responder e achar o lead
from fastapi import APIRouter, HTTPException

from nucleo import STATE
from rotas.disparo import _evo_provider
from rotas.modelos import WaResponderRequest

router = APIRouter()


def _wa_jid(jid, telefone):
    jid = (jid or "").strip()
    if jid and "@" in jid:
        return jid
    d = "".join(ch for ch in str(telefone or "") if ch.isdigit())
    if 10 <= len(d) <= 11 and not d.startswith("55"):
        d = "55" + d
    return f"{d}@s.whatsapp.net" if d else ""


@router.get("/api/wa/chats")
def api_wa_chats(instance: str = ""):
    prov = _evo_provider(instance)
    ok, err, chats = prov.listar_chats()
    if not ok:
        raise HTTPException(502, err)
    try:
        est = prov.estado()
    except Exception:
        est = {"conectado": False}
    return {"total": len(chats), "chats": chats,
            "instance": prov.instance,
            "conectado": bool(est.get("conectado"))}


@router.get("/api/wa/mensagens")
def api_wa_mensagens(jid: str = "", telefone: str = "", limite: int = 50, instance: str = ""):
    prov = _evo_provider(instance)
    target = _wa_jid(jid, telefone)
    if not target:
        raise HTTPException(400, "Informe o jid ou telefone.")
    ok, err, msgs = prov.mensagens(target, limite=min(100, max(10, limite)))
    if not ok:
        raise HTTPException(502, err)
    return {"mensagens": msgs}


@router.post("/api/wa/responder")
def api_wa_responder(req: WaResponderRequest):
    prov = _evo_provider(req.instance or "")
    target = _wa_jid(req.jid, req.telefone)
    if not target or not req.texto.strip():
        raise HTTPException(400, "Informe destino e texto.")
    numero = "".join(ch for ch in target.split("@")[0] if ch.isdigit())
    ok, err = prov.send(numero, req.texto.strip())
    if not ok:
        raise HTTPException(502, err)
    return {"ok": True}


@router.get("/api/wa/lead")
def api_wa_lead(telefone: str = ""):
    """Acha o lead da nuvem pelo telefone da conversa."""
    from scrapers import cloud_store, disparo

    d = "".join(ch for ch in str(telefone or "") if ch.isdigit())
    if d.startswith("55"):
        d = d[2:]
    try:
        for b in cloud_store.listar_leads(limite=500):
            if "".join(ch for ch in str(b.get("telefone") or "") if ch.isdigit()).endswith(d[-11:]):
                return {"lead": b}
    except Exception:
        pass
    for b in STATE.get("businesses") or []:
        if "".join(ch for ch in str(b.get("telefone") or "") if ch.isdigit()).endswith(d[-11:]):
            return {"lead": b}
    return {"lead": None}


