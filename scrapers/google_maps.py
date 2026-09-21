# proposito: conduz a busca no Google Maps: abre o navegador, percorre os cartoes
import asyncio
import os
import random
from urllib.parse import quote_plus

from playwright.async_api import async_playwright

from config import BASE_DIR, load_settings
from scrapers.gmaps_extrair import _accept_consent, _extract_place, _is_blocked
from scrapers.gmaps_parse import _clean, _jitter, _ua

STATE_FILE = os.path.join(BASE_DIR, "user_data", "gmaps_state.json")
async def _collect_cards(page, feed, target):
    cards = feed.locator('a.hfpxzc[href*="/maps/place/"]')
    if await cards.count() == 0:
        cards = feed.locator('a[href*="/maps/place/"]')

    # rolagem profunda: tenta carregar bem além do alvo (o Maps pagina aos poucos)
    # teto com folga pequena: antes era 2x (40 cards pra visitar 10), e cada
    # rolagem extra custa 0,8s sem trazer nada util.
    teto = max(target + 8, 15)
    ultima_contagem = -1
    repeticoes_iguais = 0
    for _ in range(22):
        count = await cards.count()
        if count >= teto:
            break
        # se 3 rolagens seguidas não trouxerem nada novo, acabou a lista
        if count == ultima_contagem:
            repeticoes_iguais += 1
            if repeticoes_iguais >= 3:
                break
        else:
            repeticoes_iguais = 0
        ultima_contagem = count
        try:
            await feed.first.evaluate("el => el.scrollTo(0, el.scrollHeight)")
        except Exception:
            pass
        await page.wait_for_timeout(800)

    found = []
    seen_urls = set()
    count = await cards.count()
    for i in range(min(teto, count)):
        try:
            href = await cards.nth(i).get_attribute("href")
            name = _clean(await cards.nth(i).get_attribute("aria-label") or "")
            if href and "/maps/place/" in href and name:
                if name.lower() in ("resultados", "results"):
                    continue
                key = href.split("?")[0]
                if key not in seen_urls:
                    seen_urls.add(key)
                    found.append({"nome": name, "url": href})
                if len(found) >= target:
                    break
        except Exception:
            continue
    return found


async def _visit_place(page, card, location, seen_keys, businesses, delay):
    key = card["url"].split("?")[0]
    for attempt in range(2):
        try:
            await page.goto(card["url"], timeout=45000, wait_until="domcontentloaded")
            if await _is_blocked(page):
                if attempt == 0:
                    await page.wait_for_timeout(2500)
                    continue
                return
            try:
                await page.wait_for_selector("div.F7nice, h1, div[role='main']", timeout=12000)
            except Exception:
                pass
            await page.wait_for_timeout(int(_jitter(1000, 0.3)))
            info = await _extract_place(page, card["nome"])
            if info["nome"] and key not in seen_keys:
                info["consulta"] = location
                businesses.append(info)
                seen_keys.add(key)
            await page.wait_for_timeout(int(_jitter(delay * 400, 0.4)))
            return
        except Exception:
            if attempt == 1:
                return
            await page.wait_for_timeout(1500)


async def search_places(query, locations=None, max_results=15, headless=None, delay=1.5, termos=None):
    settings = load_settings()
    if headless is None:
        headless = bool(settings.get("headless", True))

    if not locations:
        locations = ["Brasil"]
    if not termos:
        termos = [query]
    # limite de segurança: evita varreduras de horas
    termos = termos[:8]
    locations = locations[:10]

    businesses = []
    seen_keys = set()
    ua = _ua()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless, args=["--disable-blink-features=AutomationControlled"])
        context = await browser.new_context(
            user_agent=ua,
            locale="pt-BR",
            viewport={"width": 1366, "height": 900},
            extra_http_headers={"Accept-Language": "pt-BR,pt;q=0.9"},
            storage_state=STATE_FILE if os.path.exists(STATE_FILE) else None,
        )
        page = await context.new_page()
        worker_pages = [page, await context.new_page()]

        for location in locations:
            for termo in termos:
                full_query = f"{termo} {location}".strip()
                url = f"https://www.google.com/maps/search/{quote_plus(full_query)}?hl=pt-BR"
                try:
                    await page.goto(url, timeout=60000, wait_until="domcontentloaded")
                except Exception:
                    continue
                await _accept_consent(page)

                if await _is_blocked(page):
                    await page.wait_for_timeout(2500)
                    try:
                        await page.goto(url, timeout=60000, wait_until="domcontentloaded")
                    except Exception:
                        continue

                feed = page.locator('div[role="feed"]')
                try:
                    await feed.first.wait_for(timeout=20000)
                except Exception:
                    continue

                cards = await _collect_cards(page, feed, max_results)

                # visitas em paralelo (2 por vez)
                for i in range(0, len(cards), 2):
                    chunk = cards[i:i + 2]
                    tasks = [
                        _visit_place(worker_pages[j], card, f"{termo} | {location}", seen_keys, businesses, delay)
                        for j, card in enumerate(chunk)
                    ]
                    await asyncio.gather(*tasks)

        try:
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            await context.storage_state(path=STATE_FILE)
        except Exception:
            pass

        await browser.close()

    return businesses

