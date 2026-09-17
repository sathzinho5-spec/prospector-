# proposito: disparo: fila, envio, instancias Evolution, iniciar e pausar
import os

from fastapi import APIRouter, HTTPException

import config
from analysis import analyzer
from nucleo import STATE
from rotas.modelos import (DisparoAgoraRequest, DisparoEnqueueRequest,
                           DisparoMigrarRequest, DisparoRefazerRequest,
                           DisparoStartRequest, DisparoTestRequest)

router = APIRouter()


@router.post("/api/disparo/enfileirar")
def api_disparo_enqueue(req: DisparoEnqueueRequest):
    from scrapers import disparo

    if not req.itens:
        raise HTTPException(400, "Nenhum item recebido.")
    n = disparo.enfileirar(req.itens, origem=req.origem)
    return {"enfileirados": n}


@router.post("/api/disparo/migrar")
def api_disparo_migrar(req: DisparoMigrarRequest):
    """Puxa TODOS os leads já minerados (nuvem, ou sessão) para a fila, sem repetir telefone."""
    from scrapers import cloud_store, disparo

    leads = []
    try:
        leads = cloud_store.listar_leads(limite=500)
    except Exception:
        leads = []
    if not leads:
        leads = STATE.get("businesses") or []
    if not leads:
        raise HTTPException(404, "Nenhum lead minerado encontrado.")

    na_fila = disparo.telefones_na_fila()
    itens = []
    for b in leads:
        tel = disparo._norm_phone(b.get("telefone"))
        if not tel or tel in na_fila:
            continue
        try:
            pitch = analyzer._local_pitch(b)
            msg = pitch.get("whatsapp", "")
        except Exception:
            msg = ""
        if not msg:
            continue
        itens.append({"nome": b.get("nome", ""), "telefone": b.get("telefone", ""), "mensagem": msg})
        na_fila.add(tel)

    n = disparo.enfileirar(itens, origem=req.origem or "minerados")
    return {"enfileirados": n, "total_minerados": len(leads)}


@router.post("/api/disparo/enviar-agora")
def api_disparo_agora(req: DisparoAgoraRequest):
    from scrapers import disparo

    s = config.load_settings()
    prov = disparo._make_provider({
        "provider": s.get("disparo_provider", "simulado"),
        "evo_url": _evo_cfg(s)["url"],
        "evo_key": _evo_cfg(s)["key"],
        "evo_instance": s.get("disparo_evo_instance", ""),
        "meta_token": s.get("disparo_meta_token", ""),
        "meta_phone_id": s.get("disparo_meta_phone_id", ""),
    })
    ok, err = disparo.enviar_agora(req.id, prov)
    try:
        if ok:
            from scrapers import cloud_store
            row = None
            for f in disparo.listar(limite=500):
                if f["id"] == req.id:
                    row = f
                    break
            if row:
                cloud_store.set_contato_status(row.get("nome", ""), "", row.get("telefone", ""), "enviado")
    except Exception:
        pass
    return {"ok": ok, "erro": err, "provider": prov.name}


@router.post("/api/disparo/refazer")
def api_disparo_refazer(req: DisparoRefazerRequest):
    """Regenera a mensagem de um item da fila com IA completa (não o template rápido)."""
    from scrapers import disparo

    item = None
    for f in disparo.listar(limite=1000):
        if f["id"] == req.id:
            item = f
            break
    if not item:
        raise HTTPException(404, "Item não encontrado na fila.")

    business = {"nome": item.get("nome", ""), "telefone": item.get("telefone", "")}
    try:
        from scrapers import cloud_store
        for b in cloud_store.listar_leads(limite=500):
            if disparo._norm_phone(b.get("telefone")) == item.get("telefone"):
                business = dict(b)
                break
        else:
            for b in STATE.get("businesses") or []:
                if disparo._norm_phone(b.get("telefone")) == item.get("telefone"):
                    business = dict(b)
                    break
    except Exception:
        pass

    settings = config.load_settings()
    pitch = analyzer.pitch_message(business, settings)
    msg = (pitch.get("whatsapp") or "").strip()
    if not msg:
        raise HTTPException(502, "A IA não retornou mensagem.")
    disparo.atualizar_mensagem(req.id, msg)
    return {"mensagem": msg, "engine": pitch.get("engine")}


@router.get("/api/disparo/fila")
def api_disparo_fila(status: str = "", limite: int = 200):
    from scrapers import disparo

    return {"fila": disparo.listar(status or None, limite=int(limite))}


@router.get("/api/disparo/item/{item_id}")
def api_disparo_item(item_id: int):
    from scrapers import disparo

    for f in disparo.listar(limite=1000):
        if f["id"] == item_id:
            return f
    raise HTTPException(404, "Item não encontrado na fila.")


@router.post("/api/disparo/iniciar")
def api_disparo_iniciar(req: DisparoStartRequest):
    from scrapers import disparo

    s = config.load_settings()
    if (s.get("disparo_modo") or "auto") == "manual":
        return {"iniciado": False, "motivo": "modo manual ativo — envie item por item", **disparo.status()}
    cfg = {
        "provider": req.provider,
        "delay_min": max(5, req.delay_min),
        "delay_max": max(req.delay_min, req.delay_max),
        "limite_dia": max(1, min(500, req.limite_dia)),
        "hora_ini": req.hora_ini,
        "hora_fim": req.hora_fim,
        "optout": req.optout,
        "evo_url": _evo_cfg(s)["url"],
        "evo_key": _evo_cfg(s)["key"],
        "evo_instance": s.get("disparo_evo_instance", ""),
        "evo_instances": [i.strip() for i in str(s.get("disparo_evo_instances") or "").split(",") if i.strip()],
        "meta_token": s.get("disparo_meta_token", ""),
        "meta_phone_id": s.get("disparo_meta_phone_id", ""),
    }
    ok = disparo.iniciar(cfg)
    return {"iniciado": ok, **disparo.status()}


@router.post("/api/disparo/pausar")
def api_disparo_pausar():
    from scrapers import disparo

    disparo.pausar()
    return disparo.status()


@router.get("/api/disparo/status")
def api_disparo_status():
    from scrapers import disparo

    return disparo.status()


@router.post("/api/disparo/testar")
def api_disparo_testar(req: DisparoTestRequest):
    from scrapers import disparo

    s = config.load_settings()
    prov = disparo._make_provider({
        "provider": s.get("disparo_provider", "simulado"),
        "evo_url": _evo_cfg(s)["url"],
        "evo_key": _evo_cfg(s)["key"],
        "evo_instance": s.get("disparo_evo_instance", ""),
        "meta_token": s.get("disparo_meta_token", ""),
        "meta_phone_id": s.get("disparo_meta_phone_id", ""),
    })
    ok, err = prov.send(disparo._norm_phone(req.phone), req.mensagem)
    return {"ok": ok, "erro": err, "provider": prov.name}


@router.post("/api/disparo/limpar")
def api_disparo_limpar():
    from scrapers import disparo

    disparo.limpar_finalizados()
    return disparo.status()


def _evo_provider(instance=None):
    from scrapers import disparo

    s = config.load_settings()
    inst = (instance or "").strip() or s.get("disparo_evo_instance", "")
    return disparo.EvolutionProvider(
        _evo_cfg(s)["url"],
        _evo_cfg(s)["key"],
        inst,
    )


def _evo_cfg(s=None):
    """URL/key da Evolution: settings primeiro, env da VPS como fallback."""
    s = s if s is not None else config.load_settings()
    return {
        "url": s.get("disparo_evo_url", "") or os.environ.get("DISPARO_EVO_URL", ""),
        "key": s.get("disparo_evo_key", "") or os.environ.get("DISPARO_EVO_KEY", ""),
    }


def _evo_instances():
    from scrapers import disparo  # noqa: F401 (garante módulo carregado)

    s = config.load_settings()
    insts = []
    for v in (s.get("disparo_evo_instance"), s.get("disparo_evo_chip2"),
              s.get("disparo_evo_chip3")):
        v = str(v or "").strip()
        if v and v not in insts:
            insts.append(v)
    for v in str(s.get("disparo_evo_instances") or "").split(","):
        v = v.strip()
        if v and v not in insts:
            insts.append(v)
    return insts[:3]


@router.post("/api/disparo/evolution/qrcode")
def api_evo_qrcode(instance: str = ""):
    prov = _evo_provider(instance)
    ok, err, qr = prov.criar_instancia()
    if not ok:
        raise HTTPException(502, err)
    return {"ok": True, "qrcode": qr, "instance": prov.instance}


@router.get("/api/disparo/evolution/estado")
def api_evo_estado(instance: str = ""):
    return _evo_provider(instance).estado()


@router.get("/api/disparo/instancias")
def api_disparo_instancias():
    provs = []
    for inst in _evo_instances():
        from scrapers import disparo

        s = config.load_settings()
        cfg = _evo_cfg(s)
        p = disparo.EvolutionProvider(cfg["url"], cfg["key"], inst)
        st = p.estado()
        provs.append({"instance": inst, **st})
    if not provs:
        s = config.load_settings()
        provs.append({"instance": s.get("disparo_evo_instance", ""),
                      "conectado": False, "estado": "nao_configurado",
                      "erro": "Cadastre as instâncias nas Configurações."})
    return {"instancias": provs}

