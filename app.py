# proposito: sobe o FastAPI, a porta de acesso e as rotas de busca e ajuste
import asyncio
import json
import os

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

import config
import contas
import niches
import scheduler
from analysis import analyzer
from nucleo import LIVRES, PREFIXOS_LIVRES, STATE, WEB_DIR, _quem
from scrapers import google_maps
from storage import export_csv, export_excel, save_businesses, save_json

from rotas import (acesso, cnpj, crm, disparo, disparo_conversas, disparo_copy,
                   disparo_evolution, disparo_leads, negocio, negocio_instagram,
                   whatsapp)
from rotas.modelos import ScheduleRequest, SearchRequest, SettingsRequest

app = FastAPI(title="Prospector - Scraping de Negócios")

scheduler.start_scheduler()


@app.middleware("http")
async def no_cache_static(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static") or request.url.path == "/":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
@app.middleware("http")
async def porta_de_acesso(request: Request, call_next):
    caminho = request.url.path
    if caminho in LIVRES or caminho.startswith(PREFIXOS_LIVRES):
        return await call_next(request)

    if _quem(request):
        return await call_next(request)

    # Quem tem cookie valido mas ainda espera aprovacao vai pra tela de espera,
    # nao pra de entrar: mandar de volta pro login faria a pessoa tentar entrar
    # de novo sem entender que o problema nao e a senha.
    pendente = contas.conta_do_cookie_mesmo_pendente(
        request.cookies.get(contas.NOME_COOKIE))

    if caminho.startswith("/api/"):
        return JSONResponse(
            {"erro": "Sua conta ainda nao foi liberada." if pendente
                     else "Entre para usar o Prospector."},
            status_code=401)

    return RedirectResponse("/aguardando" if pendente else "/entrar", status_code=303)
@app.get("/")
def index():
    return FileResponse(os.path.join(WEB_DIR, "index.html"))


@app.get("/api/saude")
def api_saude():
    """Usado pela publicacao automatica pra saber se a versao nova respondeu."""
    return {"ok": True}
@app.get("/api/niches")
def api_niches():
    return niches.get_public()


@app.get("/api/settings")
def api_get_settings():
    s = config.load_settings()
    return {
        **s,
        "openai_api_key": ("*" * 8) if s.get("openai_api_key") else "",
        "instagram_sessionid": ("*" * 8) if s.get("instagram_sessionid") else "",
        "disparo_evo_key": ("*" * 8) if s.get("disparo_evo_key") else "",
        "disparo_meta_token": ("*" * 8) if s.get("disparo_meta_token") else "",
        "supabase_secret": ("*" * 8) if s.get("supabase_secret") else "",
    }


@app.post("/api/settings")
def api_save_settings(req: SettingsRequest):
    new = {}
    if req.openai_api_key:
        new["openai_api_key"] = req.openai_api_key.strip()
    if req.openai_base_url:
        new["openai_base_url"] = req.openai_base_url.strip()
    if req.openai_model:
        new["openai_model"] = req.openai_model.strip()
    if req.instagram_sessionid:
        new["instagram_sessionid"] = req.instagram_sessionid.strip()
    if req.headless is not None:
        new["headless"] = req.headless
    if req.request_delay is not None:
        new["request_delay"] = max(0.0, req.request_delay)
    if req.disparo_provider:
        new["disparo_provider"] = req.disparo_provider.strip()
    if req.disparo_evo_url:
        new["disparo_evo_url"] = req.disparo_evo_url.strip()
    if req.disparo_evo_key:
        new["disparo_evo_key"] = req.disparo_evo_key.strip()
    if req.disparo_evo_instance:
        new["disparo_evo_instance"] = req.disparo_evo_instance.strip()
    if req.disparo_evo_instances:
        new["disparo_evo_instances"] = req.disparo_evo_instances.strip()
    for _f in ("disparo_evo_chip2", "disparo_evo_chip3"):
        _v = getattr(req, _f, "")
        if _v:
            new[_f] = _v.strip()
    if req.disparo_prompt is not None:
        new["disparo_prompt"] = req.disparo_prompt.strip()
    if req.abordagem_prompt is not None:
        new["abordagem_prompt"] = req.abordagem_prompt.strip()
    if req.abordagem_ia_max is not None:
        new["abordagem_ia_max"] = max(0, min(100, int(req.abordagem_ia_max)))
    if req.disparo_tom in ("direto", "consultivo", "agressivo", "amigavel"):
        new["disparo_tom"] = req.disparo_tom
    if req.disparo_meta_token:
        new["disparo_meta_token"] = req.disparo_meta_token.strip()
    if req.disparo_meta_phone_id:
        new["disparo_meta_phone_id"] = req.disparo_meta_phone_id.strip()
    if req.disparo_hora_ini:
        new["disparo_hora_ini"] = req.disparo_hora_ini.strip()
    if req.disparo_hora_fim:
        new["disparo_hora_fim"] = req.disparo_hora_fim.strip()
    if req.disparo_limite_dia is not None:
        new["disparo_limite_dia"] = max(1, min(500, int(req.disparo_limite_dia)))
    if req.supabase_url:
        new["supabase_url"] = req.supabase_url.strip()
    if req.supabase_secret:
        new["supabase_secret"] = req.supabase_secret.strip()
    if req.timing_janelas is not None:
        limpas = {}
        for nid, j in (req.timing_janelas or {}).items():
            if not isinstance(j, dict):
                continue
            ini = str(j.get("ini") or "").strip()
            fim = str(j.get("fim") or "").strip()
            dias = j.get("dias") if j.get("dias") in ("uteis", "todos") else "uteis"
            if len(ini) == 5 and len(fim) == 5 and ini[2] == ":" and fim[2] == ":":
                limpas[str(nid)] = {"ini": ini, "fim": fim, "dias": dias}
        new["timing_janelas"] = limpas
    saved = config.save_settings(new)
    return {
        **saved,
        "openai_api_key": ("*" * 8) if saved.get("openai_api_key") else "",
        "instagram_sessionid": ("*" * 8) if saved.get("instagram_sessionid") else "",
    }


@app.post("/api/search")
async def api_search(req: SearchRequest):
    if not req.query.strip():
        raise HTTPException(400, "Informe o nicho.")

    locations = [l.strip() for l in (req.locations or []) if l and l.strip()]
    if not locations:
        if req.filter.strip():
            locations = [req.filter.strip()]
        else:
            raise HTTPException(400, "Selecione pelo menos um estado ou informe um filtro.")

    try:
        businesses = await google_maps.search_places(
            req.query.strip(),
            locations=locations,
            max_results=req.max_results,
            delay=config.load_settings().get("request_delay", 1.5),
        )
    except RuntimeError as e:
        raise HTTPException(502, str(e))

    if not businesses:
        raise HTTPException(404, "Nenhum negócio encontrado para essa busca.")

    repetidos_ocultos = 0
    try:
        from scrapers import cloud_store
        # 1. checa quem JÁ estava salvo ANTES desta busca
        if req.apenas_novos:
            ids = [cloud_store.lead_id(b) for b in businesses]
            vistos = cloud_store.existing_ids(ids)
            if vistos:
                repetidos_ocultos = sum(1 for b in businesses if cloud_store.lead_id(b) in vistos)
                businesses = [b for b in businesses if cloud_store.lead_id(b) not in vistos]
        # 2. salva tudo (upsert) para as próximas buscas saberem
        cloud_store.save_leads(businesses)
    except Exception:
        pass

    STATE["businesses"] = businesses
    STATE["last_search"] = f"{req.query.strip()} | {', '.join(locations)}"
    path = save_businesses(businesses, "negocios")

    por_local = {}
    for b in businesses:
        loc = b.get("consulta") or "N/A"
        por_local[loc] = por_local.get(loc, 0) + 1

    return {
        "query": req.query.strip(),
        "locations": locations,
        "total": len(businesses),
        "por_local": por_local,
        "repetidos_ocultos": repetidos_ocultos,
        "businesses": businesses,
        "csv": path,
    }


@app.get("/api/results")
def api_results():
    return {"businesses": STATE.get("businesses") or [], "last_search": STATE.get("last_search") or ""}


@app.get("/api/schedule")
def api_schedule_status():
    s = config.load_settings()
    return {
        "enabled": s.get("schedule_enabled", False),
        "time": s.get("schedule_time", "08:00"),
        "niche": s.get("schedule_niche", "restaurantes"),
        "states": s.get("schedule_states", []),
        "max": s.get("schedule_max", 10),
        "last_run": s.get("schedule_last_run", ""),
        "new_count": s.get("schedule_new_count", 0),
        "total_count": s.get("schedule_total_count", 0),
    }


@app.post("/api/schedule")
def api_schedule_save(req: ScheduleRequest):
    config.save_settings({
        "schedule_enabled": req.enabled,
        "schedule_time": req.time.strip() or "08:00",
        "schedule_niche": req.niche.strip() or "restaurantes",
        "schedule_states": [x.strip() for x in (req.states or []) if x.strip()],
        "schedule_max": max(1, min(60, req.max)),
    })
    return api_schedule_status()


@app.get("/api/schedule/results")
def api_schedule_results():
    path = os.path.join(config.BASE_DIR, "output", "agendadas", "busca_"
                        + (config.load_settings().get("schedule_last_run") or "none") + ".json")
    if not os.path.exists(path):
        raise HTTPException(404, "Nenhuma busca agendada salva ainda.")
    with open(path, "r", encoding="utf-8") as f:
        businesses = json.load(f)
    prev = []
    prev_file = os.path.join(config.BASE_DIR, "output", "agendadas", "anterior.json")
    if os.path.exists(prev_file):
        with open(prev_file, "r", encoding="utf-8") as f:
            prev = json.load(f)
    prev_keys = set((b.get("nome") or "").lower().strip() for b in prev)
    new = [b for b in businesses if (b.get("nome") or "").lower().strip() not in prev_keys]
    return {"total": len(businesses), "novos": new}


@app.get("/api/export")
def api_export(format: str = "csv"):
    businesses = STATE.get("businesses") or []
    if not businesses:
        raise HTTPException(404, "Nenhuma busca realizada ainda.")
    if format == "json":
        path = save_json("negocios.json", businesses)
        return FileResponse(path, filename="negocios.json", media_type="application/json")
    if format == "xlsx":
        path = export_excel(businesses, "negocios")
        return FileResponse(path, filename="negocios.xlsx", media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    path = export_csv(businesses, "negocios")
    return FileResponse(path, filename="negocios.csv", media_type="text/csv; charset=utf-8")


# ==================== CNPJ GIGANTES INVISIVEIS (Supabase) ====================



app.include_router(acesso.router)
app.include_router(negocio.router)
app.include_router(negocio_instagram.router)
app.include_router(crm.router)
app.include_router(disparo.router)
app.include_router(disparo_copy.router)
app.include_router(disparo_leads.router)
app.include_router(disparo_conversas.router)
app.include_router(disparo_evolution.router)
app.include_router(whatsapp.router)
app.include_router(cnpj.router)
