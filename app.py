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
    apenas_novos: bool = True


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


class DisparoEnqueueRequest(BaseModel):
    itens: list
    origem: str = ""


class DisparoStartRequest(BaseModel):
    provider: str = "simulado"
    delay_min: float = 45
    delay_max: float = 120
    limite_dia: int = 50
    hora_ini: str = "08:00"
    hora_fim: str = "20:00"
    optout: bool = True


class DisparoTestRequest(BaseModel):
    phone: str
    mensagem: str = "Teste do Prospector: mensagem de teste do disparador."


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
    disparo_provider: str = ""
    disparo_evo_url: str = ""
    disparo_evo_key: str = ""
    disparo_evo_instance: str = ""
    disparo_meta_token: str = ""
    disparo_meta_phone_id: str = ""
    disparo_modo: str = ""
    supabase_url: str = ""
    supabase_secret: str = ""


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
    if req.disparo_meta_token:
        new["disparo_meta_token"] = req.disparo_meta_token.strip()
    if req.disparo_meta_phone_id:
        new["disparo_meta_phone_id"] = req.disparo_meta_phone_id.strip()
    if req.disparo_modo in ("auto", "manual"):
        new["disparo_modo"] = req.disparo_modo
    if req.supabase_url:
        new["supabase_url"] = req.supabase_url.strip()
    if req.supabase_secret:
        new["supabase_secret"] = req.supabase_secret.strip()
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
        b["score_oportunidade"] = r.get("score_oportunidade")
        b["nivel"] = r.get("nivel")
        b["oportunidades"] = r.get("oportunidades")

    try:
        from scrapers import cloud_store
        cloud_store.update_analise(req.businesses)
    except Exception:
        pass

    return {"results": out}


@app.post("/api/business/pitch")
async def api_pitch(req: StrategyRequest, rapido: int = 0):
    if not req.business:
        raise HTTPException(400, "Informe o negocio.")
    if rapido:
        return analyzer._local_pitch(req.business)
    settings = config.load_settings()
    result = await asyncio.to_thread(analyzer.pitch_message, req.business, settings)
    try:
        from scrapers import cloud_store
        req.business["_pitch"] = result
        cloud_store.update_analise([req.business])
    except Exception:
        pass
    return result


@app.get("/api/cloud/status")
def api_cloud_status():
    try:
        from scrapers import cloud_store
        online = cloud_store.ping()
    except Exception:
        online = False
    return {"online": online}


@app.get("/api/cloud/leads")
def api_cloud_leads(estado: str = "", min_score: int = 0, apenas_pendentes: bool = False, limite: int = 200):
    from scrapers import cloud_store

    return {"leads": cloud_store.listar_leads(
        estado=estado or None,
        min_score=min_score or None,
        apenas_pendentes=apenas_pendentes,
        limite=min(500, limite),
    )}


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


class SequenciaRequest(BaseModel):
    business: dict
    niche_id: str = ""


@app.post("/api/business/sequencia")
async def api_sequencia(req: SequenciaRequest):
    if not req.business:
        raise HTTPException(400, "Informe o negocio.")
    from analysis import copy_sdr

    settings = config.load_settings()
    return await asyncio.to_thread(copy_sdr.gerar_sequencia, req.business, settings, req.niche_id or None)


# ==================== DISPARADOR ====================

@app.post("/api/disparo/enfileirar")
def api_disparo_enqueue(req: DisparoEnqueueRequest):
    from scrapers import disparo

    if not req.itens:
        raise HTTPException(400, "Nenhum item recebido.")
    n = disparo.enfileirar(req.itens, origem=req.origem)
    return {"enfileirados": n}


class DisparoMigrarRequest(BaseModel):
    origem: str = "minerados"


@app.post("/api/disparo/migrar")
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


class DisparoAgoraRequest(BaseModel):
    id: int


class DisparoRefazerRequest(BaseModel):
    id: int


@app.post("/api/disparo/enviar-agora")
def api_disparo_agora(req: DisparoAgoraRequest):
    from scrapers import disparo

    s = config.load_settings()
    prov = disparo._make_provider({
        "provider": s.get("disparo_provider", "simulado"),
        "evo_url": s.get("disparo_evo_url", ""),
        "evo_key": s.get("disparo_evo_key", ""),
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


@app.post("/api/disparo/refazer")
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


@app.get("/api/disparo/fila")
def api_disparo_fila(status: str = "", limite: int = 200):
    from scrapers import disparo

    return {"fila": disparo.listar(status or None, limite=int(limite))}


@app.post("/api/disparo/iniciar")
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
        "evo_url": s.get("disparo_evo_url", ""),
        "evo_key": s.get("disparo_evo_key", ""),
        "evo_instance": s.get("disparo_evo_instance", ""),
        "meta_token": s.get("disparo_meta_token", ""),
        "meta_phone_id": s.get("disparo_meta_phone_id", ""),
    }
    ok = disparo.iniciar(cfg)
    return {"iniciado": ok, **disparo.status()}


@app.post("/api/disparo/pausar")
def api_disparo_pausar():
    from scrapers import disparo

    disparo.pausar()
    return disparo.status()


@app.get("/api/disparo/status")
def api_disparo_status():
    from scrapers import disparo

    return disparo.status()


@app.post("/api/disparo/testar")
def api_disparo_testar(req: DisparoTestRequest):
    from scrapers import disparo

    s = config.load_settings()
    prov = disparo._make_provider({
        "provider": s.get("disparo_provider", "simulado"),
        "evo_url": s.get("disparo_evo_url", ""),
        "evo_key": s.get("disparo_evo_key", ""),
        "evo_instance": s.get("disparo_evo_instance", ""),
        "meta_token": s.get("disparo_meta_token", ""),
        "meta_phone_id": s.get("disparo_meta_phone_id", ""),
    })
    ok, err = prov.send(disparo._norm_phone(req.phone), req.mensagem)
    return {"ok": ok, "erro": err, "provider": prov.name}


@app.post("/api/disparo/limpar")
def api_disparo_limpar():
    from scrapers import disparo

    disparo.limpar_finalizados()
    return disparo.status()


def _evo_provider():
    from scrapers import disparo

    s = config.load_settings()
    return disparo.EvolutionProvider(
        s.get("disparo_evo_url", ""),
        s.get("disparo_evo_key", ""),
        s.get("disparo_evo_instance", ""),
    )


@app.post("/api/disparo/evolution/qrcode")
def api_evo_qrcode():
    prov = _evo_provider()
    ok, err, qr = prov.criar_instancia()
    if not ok:
        raise HTTPException(502, err)
    if not qr and "base64," in err:
        pass
    return {"ok": True, "qrcode": qr}


@app.get("/api/disparo/evolution/estado")
def api_evo_estado():
    return _evo_provider().estado()


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