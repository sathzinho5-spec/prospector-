# proposito: analise e copy de um lead: contato, estrategia, pitch, proposta
import asyncio
import os

from fastapi import APIRouter, HTTPException

from analysis import analyzer
from storage import save_json
from scrapers import google_search
import config
from rotas.modelos import (BatchRequest, ContactRequest,
                           ObjectionRequest, ReferenceRequest, ScreenshotRequest,
                           SequenciaRequest, StrategyRequest)

router = APIRouter()


@router.post("/api/business/contacts")
async def api_contacts(req: ContactRequest):
    if not req.url.strip():
        raise HTTPException(400, "Informe a URL do site.")
    from scrapers import site_contacts

    result = await asyncio.to_thread(site_contacts.extract_site_contacts, req.url.strip())
    return result


@router.post("/api/business/strategy")
async def api_strategy(req: StrategyRequest):
    if not req.business:
        raise HTTPException(400, "Informe o negocio.")
    settings = config.load_settings()
    report = await asyncio.to_thread(analyzer.business_strategy, req.business, settings)
    save_json("estrategia_ultima.json", report)
    return report



@router.post("/api/business/strategy_batch")
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


@router.post("/api/business/pitch")
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


@router.post("/api/business/proposal")
async def api_proposal(req: StrategyRequest):
    if not req.business:
        raise HTTPException(400, "Informe o negocio.")
    settings = config.load_settings()
    return await asyncio.to_thread(analyzer.proposal, req.business, settings)


@router.post("/api/business/objection")
async def api_objection(req: ObjectionRequest):
    if not req.business or not req.objection.strip():
        raise HTTPException(400, "Informe o negocio e a objecao.")
    settings = config.load_settings()
    return await asyncio.to_thread(analyzer.handle_objection, req.business, req.objection.strip(), settings)



@router.post("/api/business/sequencia")
async def api_sequencia(req: SequenciaRequest):
    if not req.business:
        raise HTTPException(400, "Informe o negocio.")
    from analysis import copy_sdr

    settings = config.load_settings()
    return await asyncio.to_thread(copy_sdr.gerar_sequencia, req.business, settings, req.niche_id or None)


# ==================== DISPARADOR ====================

@router.post("/api/business/screenshot")
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


@router.post("/api/google/reference")
async def api_reference(req: ReferenceRequest):
    try:
        ref = await google_search.find_business_reference(req.name, req.location)
    except Exception as e:
        raise HTTPException(502, f"Falha na busca de referência: {e}")
    return ref
