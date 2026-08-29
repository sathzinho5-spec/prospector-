import asyncio
import json
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config
import niches
from analysis import analyzer
from scrapers import google_maps, google_search, instagram
from storage import export_csv, export_excel, save_businesses, save_json
import scheduler

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

STATE = {"businesses": [], "last_search": ""}

WEB_DIR = os.path.join(config.BASE_DIR, "web")
os.makedirs(WEB_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


class SearchRequest(BaseModel):
    query: str
    locations: list = []
    filter: str = ""
    max_results: int = 15


class ReferenceRequest(BaseModel):
    name: str
    location: str = ""


class ContactRequest(BaseModel):
    url: str


class StrategyRequest(BaseModel):
    business: dict


class ScreenshotRequest(BaseModel):
    url: str
    name: str = "negocio"


class ScheduleRequest(BaseModel):
    enabled: bool = False
    time: str = "08:00"
    niche: str = "restaurantes"
    states: list = []
    max: int = 10


class ObjectionRequest(BaseModel):
    business: dict
    objection: str


class InstagramRequest(BaseModel):
    name: str
    username: str = ""
    download: bool = True
    max_posts: int = 12


class SettingsRequest(BaseModel):
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = ""
    instagram_sessionid: str = ""
    headless: bool | None = None
    request_delay: float | None = None


@app.get("/")
def index():
    return FileResponse(os.path.join(WEB_DIR, "index.html"))


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
        "businesses": businesses,
        "csv": path,
    }


@app.get("/api/results")
def api_results():
    return {"businesses": STATE.get("businesses") or [], "last_search": STATE.get("last_search") or ""}


@app.post("/api/business/contacts")
async def api_contacts(req: ContactRequest):
    if not req.url.strip():
        raise HTTPException(400, "Informe a URL do site.")
    from scrapers import site_contacts

    result = await asyncio.to_thread(site_contacts.extract_site_contacts, req.url.strip())
    return result


@app.post("/api/business/strategy")
async def api_strategy(req: StrategyRequest):
    if not req.business:
        raise HTTPException(400, "Informe o negocio.")
    settings = config.load_settings()
    report = await asyncio.to_thread(analyzer.business_strategy, req.business, settings)
    save_json("estrategia_ultima.json", report)
    return report


class BatchRequest(BaseModel):
    businesses: list


@app.post("/api/business/strategy_batch")
async def api_strategy_batch(req: BatchRequest):
    if not req.businesses:
        raise HTTPException(400, "Nenhum negocio recebido.")
    settings = config.load_settings()

    from concurrent.futures import ThreadPoolExecutor

    def work(b):
        try:
            return analyzer.business_strategy(b, settings)
        except Exception:
            return analyzer._local_strategy(b)

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=6) as ex:
        reports = await loop.run_in_executor(ex, lambda: [work(b) for b in req.businesses])

    out = []
    for b, r in zip(req.businesses, reports):
        out.append({
            "nome": b.get("nome"),
            "score": r.get("score_oportunidade"),
            "nivel": r.get("nivel"),
            "resumo": r.get("resumo"),
            "oportunidades": (r.get("oportunidades") or [])[:3],
            "engine": r.get("engine"),
        })
    return {"results": out}


@app.post("/api/business/pitch")
async def api_pitch(req: StrategyRequest):
    if not req.business:
        raise HTTPException(400, "Informe o negocio.")
    settings = config.load_settings()
    return await asyncio.to_thread(analyzer.pitch_message, req.business, settings)


@app.post("/api/business/proposal")
async def api_proposal(req: StrategyRequest):
    if not req.business:
        raise HTTPException(400, "Informe o negocio.")
    settings = config.load_settings()
    return await asyncio.to_thread(analyzer.proposal, req.business, settings)


@app.post("/api/business/objection")
async def api_objection(req: ObjectionRequest):
    if not req.business or not req.objection.strip():
        raise HTTPException(400, "Informe o negocio e a objecao.")
    settings = config.load_settings()
    return await asyncio.to_thread(analyzer.handle_objection, req.business, req.objection.strip(), settings)


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


@app.post("/api/business/screenshot")
async def api_screenshot(req: ScreenshotRequest):
    if not req.url.strip():
        raise HTTPException(400, "Informe a URL do Maps.")

    import re as _re
    from playwright.async_api import async_playwright

    slug = _re.sub(r"[^A-Za-z0-9]+", "_", req.name)[:40] or "negocio"
    folder = os.path.join(config.DOWNLOADS_DIR, "screenshots")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{slug}.png")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            viewport={"width": 1280, "height": 900},
            locale="pt-BR",
        )
        try:
            await page.goto(req.url.strip(), timeout=60000, wait_until="domcontentloaded")
            await page.wait_for_timeout(3500)
            await page.screenshot(path=path, full_page=False)
        finally:
            await browser.close()

    return {"arquivo": path}


@app.post("/api/google/reference")
async def api_reference(req: ReferenceRequest):
    try:
        ref = await google_search.find_business_reference(req.name, req.location)
    except Exception as e:
        raise HTTPException(502, f"Falha na busca de referência: {e}")
    return ref


@app.post("/api/instagram/analyze")
async def api_instagram(req: InstagramRequest):
    username = req.username.strip().lstrip("@")
    searched = False
    if not username:
        try:
            ref = await google_search.find_business_reference(req.name, "")
            username = ref.get("instagram_handle") or ""
            searched = True
        except Exception:
            username = ""
        if not username:
            raise HTTPException(400, "Não foi possível encontrar o @ do Instagram. Informe o @ do perfil manualmente.")

    try:
        profile, posts = await asyncio.to_thread(instagram.get_profile_and_posts, username, req.max_posts)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))

    saved = []
    if req.download and posts:
        saved = await asyncio.to_thread(instagram.download_media, username, posts, 6)

    settings = config.load_settings()
    report = analyzer.build_report(req.name, profile, posts, saved, settings)

    payload = {
        "nome": req.name,
        "username": username,
        "auto_descoberto": searched,
        "perfil": profile,
        "posts": posts,
        "conteudos_baixados": saved,
        "relatorio": report,
    }
    save_json(f"analise_{username}.json", payload)
    STATE["report"] = payload
    return payload


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

class CnpjGrandesRequest(BaseModel):
    uf: str = ""
    cidade: str = ""
    capital_min: int = 500000
    limite: int = 20
    apenas_nao_vistos: bool = True


class CnpjMarcarRequest(BaseModel):
    cnpjs: list


@app.get("/api/cnpj/grandes")
def api_cnpj_grandes(uf: str = "", cidade: str = "", capital_min: int = 500000, limite: int = 20, apenas_nao_vistos: bool = True):
    from scrapers import cnpj_supabase

    try:
        rows = cnpj_supabase.buscar_grandes_supabase(
            uf=uf or None, cidade=cidade or None, capital_min=capital_min, limite=limite, apenas_nao_vistos=apenas_nao_vistos
        )
        return {"total": len(rows), "empresas": rows}
    except Exception as e:
        raise HTTPException(502, f"Erro ao consultar Supabase: {e}")


@app.post("/api/cnpj/marcar-vistos")
def api_cnpj_marcar(req: CnpjMarcarRequest):
    from scrapers import cnpj_supabase

    try:
        cnpj_supabase.marcar_vistos(req.cnpjs)
        return {"vistos": len(req.cnpjs)}
    except Exception as e:
        raise HTTPException(502, str(e))


@app.post("/api/cnpj/sync")
async def api_cnpj_sync(capital_min: int = 500000, max_arquivos: int = 2):
    from scrapers import cnpj_supabase

    loop = asyncio.get_event_loop()
    count = await loop.run_in_executor(None, lambda: cnpj_supabase.sync_completo(capital_min=capital_min, max_arquivos=max_arquivos))
    return {"sincronizadas": count, "capital_min": capital_min, "max_arquivos": max_arquivos}