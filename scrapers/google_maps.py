import asyncio
import os
import random
import re
from urllib.parse import quote_plus

from playwright.async_api import async_playwright

from config import BASE_DIR, load_settings

STATE_FILE = os.path.join(BASE_DIR, "user_data", "gmaps_state.json")

UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]


def _ua():
    return random.choice(UA_POOL)


def _jitter(base, spread=0.6):
    return base * (1 + random.uniform(-spread, spread))


async def _is_blocked(page):
    try:
        if "/sorry/" in page.url:
            return True
        content = (await page.content()).lower()
        return "recaptcha" in content or "unusual traffic" in content or "tráfego incomum" in content
    except Exception:
        return False

_SERVICOS = [
    "Entrega em domicílio", "Retirada na loja", "Consumo no local",
    "Drive-thru", "Entrega sem contato", "Retirada externa", "Para levar",
    "Entrada acessível para cadeira de rodas", "Wi-Fi", "Pagamento com cartão",
]

_SCAN_JS = """() => {
  const out = {status: "", preco: "", plus_code: "", atributos: []};
  const servicos = %s;
  document.querySelectorAll('button, div[role="button"], span').forEach(el => {
    const t = (el.textContent || '').trim();
    if (!t || t.length > 45) return;
    if (!out.status && /^(Aberto|Fechado)/.test(t)) { out.status = t; return; }
    if (!out.preco && /^\\$[\\$\\u20ac\\u00a3]{0,3}\\u00b7{0,4}$/.test(t)) { out.preco = t; return; }
    if (!out.plus_code && /^[23456789CFGHJMPQRVWX]{4,8}\\+[23456789CFGHJMPQRVWX]{2,3}$/.test(t)) { out.plus_code = t; return; }
    if (servicos.indexOf(t) !== -1 && out.atributos.indexOf(t) === -1) out.atributos.push(t);
  });
  return out;
}""" % str(_SERVICOS)


def _clean(text):
    if not text:
        return ""
    text = "".join(ch for ch in text if not (0xE000 <= ord(ch) <= 0xF8FF) and not ord(ch) < 32)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


async def _text(page, selectors, timeout=4000):
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if await loc.count() > 0:
                await loc.wait_for(timeout=timeout)
                txt = (await loc.inner_text()).strip()
                if txt:
                    return _clean(txt)
        except Exception:
            continue
    return ""


async def _href(page, selectors, timeout=4000):
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if await loc.count() > 0:
                await loc.wait_for(timeout=timeout)
                href = await loc.get_attribute("href")
                if href:
                    return href
        except Exception:
            continue
    return ""


async def _accept_consent(page):
    try:
        if "consent.google.com" in page.url:
            for sel in [
                'button:has-text("Aceitar tudo")',
                'button:has-text("Accept all")',
                'form[action*="save"] button',
            ]:
                loc = page.locator(sel).first
                if await loc.count() > 0:
                    await loc.click(timeout=3000)
                    await page.wait_for_timeout(1500)
                    return
    except Exception:
        pass


def _parse_rating(rating_text, reviews_text):
    nota, avaliacoes = "", ""
    if rating_text:
        m = re.search(r"([\d]+[.,]\d+|\d+)", rating_text)
        if m:
            nota = m.group(1).replace(".", ",")
    if reviews_text:
        m = re.search(r"([\d.]+)", reviews_text.replace("(", " ").replace(")", " "))
        if m:
            avaliacoes = m.group(1)
    return nota, avaliacoes


def _parse_cidade_estado(endereco):
    cidade, estado = "", ""
    if not endereco:
        return cidade, estado
    m = re.search(r",\s*([^,-]+?)\s*-\s*([A-Z]{2}),\s*\d{5}-?\d{0,3}", endereco)
    if m:
        cidade = m.group(1).strip()
        estado = m.group(2).strip()
        return cidade, estado
    m2 = re.search(r",\s*([^,-]+?)\s*,\s*\d{5}-?\d{0,3}", endereco)
    if m2:
        cidade = m2.group(1).strip()
    return cidade, estado


def _parse_coords(url):
    m = re.search(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", url or "")
    if m:
        return m.group(1), m.group(2)
    m = re.search(r"/@(-?\d+\.\d+),(-?\d+\.\d+)", url or "")
    if m:
        return m.group(1), m.group(2)
    return "", ""


async def _extract_meta(page):
    try:
        return await page.evaluate(
            """() => ({
              image: (document.querySelector('meta[property="og:image"]') || {}).content || "",
              desc: (document.querySelector('meta[property="og:description"]') || {}).content
                    || (document.querySelector('meta[name="description"]') || {}).content || ""
            })"""
        )
    except Exception:
        return {"image": "", "desc": ""}


async def _extract_place(page, fallback):
    info = {
        "nome": "",
        "categoria": "",
        "nota": "",
        "avaliacoes": "",
        "endereco": "",
        "bairro": "",
        "cidade": "",
        "estado": "",
        "telefone": "",
        "website": "",
        "horarios": "",
        "status_funcionamento": "",
        "preco": "",
        "plus_code": "",
        "atributos": [],
        "latitude": "",
        "longitude": "",
        "url": page.url,
    }

    info["nome"] = await _text(
        page,
        [
            "h1.DUwDvf",
            "div.qBF1Pd.fontHeadlineSmall",
            "h1.fontHeadlineSmall",
            "div.fontHeadlineSmall",
            'div[role="main"] h1',
        ],
    )
    if not info["nome"]:
        info["nome"] = fallback

    rating_text = await _text(page, ["div.F7nice span[aria-hidden='true']"])
    reviews_text = await _text(
        page,
        ["span.ceNzKf", "button[aria-label*='avalia']", "span[aria-label*='avalia']"],
    )
    if not rating_text or not reviews_text:
        full = await _text(page, ["div.F7nice"])
        if not rating_text and full:
            rating_text = full
        if not reviews_text and full:
            rev = re.search(r"\(([\d.]+)\)", full)
            if rev:
                reviews_text = rev.group(1)
    info["nota"], info["avaliacoes"] = _parse_rating(rating_text, reviews_text)

    info["categoria"] = await _text(page, ["button.DkEaL", "div.DkEaL"])
    info["endereco"] = await _text(
        page,
        ["button[data-item-id='address']", "a[data-item-id='address']", "button[aria-label*='Endereço']"],
    )
    info["telefone"] = await _text(page, ["button[data-item-id^='phone:']", "button[aria-label*='Telefone']"])

    website_url = await _href(page, ["a[data-item-id='authority']", "a[aria-label*='Website']"])
    if website_url:
        info["website"] = website_url
    else:
        info["website"] = await _text(page, ["a[data-item-id='authority']"])

    # horarios detalhados (clica no botao de horario para expandir)
    try:
        hours_btn = page.locator("button[data-item-id*='ohos'], button[aria-label*='Horário']").first
        if await hours_btn.count() > 0:
            label = _clean(await hours_btn.get_attribute("aria-label") or "")
            if not info["status_funcionamento"] and label:
                info["status_funcionamento"] = label[:60]
            await hours_btn.click(timeout=2500)
            await page.wait_for_timeout(700)
            info["horarios"] = await _text(
                page,
                ["div.G8vxb", "div.t39EBf", "table", "div[aria-label*='Horário de funcionamento']"],
            )
    except Exception:
        pass

    # scan JS: status, preco, plus code, atributos/servicos
    try:
        scan = await page.evaluate(_SCAN_JS)
        if scan:
            if not info["status_funcionamento"]:
                info["status_funcionamento"] = _clean(scan.get("status", ""))
            info["preco"] = _clean(scan.get("preco", ""))
            info["plus_code"] = _clean(scan.get("plus_code", ""))
            info["atributos"] = [_clean(a) for a in scan.get("atributos", [])][:8]
    except Exception:
        pass

    # bairro / cidade / estado a partir do endereco
    try:
        for part in [p.strip() for p in info["endereco"].split(",")]:
            if "-" in part:
                neighborhood = part.split("-")[-1].strip()
                if neighborhood and not re.match(r"^\d{5}", neighborhood) and len(neighborhood) > 2:
                    info["bairro"] = neighborhood
                    break
    except Exception:
        pass
    info["cidade"], info["estado"] = _parse_cidade_estado(info["endereco"])

    info["latitude"], info["longitude"] = _parse_coords(page.url)

    meta = await _extract_meta(page)
    if meta.get("image"):
        info["foto"] = meta["image"]
    if meta.get("desc"):
        desc = _clean(meta["desc"])
        if desc and desc.lower() not in ("google maps", "maps"):
            info["descricao"] = desc[:300]

    return info


async def _collect_cards(page, feed, target):
    cards = feed.locator('a.hfpxzc[href*="/maps/place/"]')
    if await cards.count() == 0:
        cards = feed.locator('a[href*="/maps/place/"]')

    for _ in range(target // 3 + 4):
        count = await cards.count()
        if count >= target:
            break
        try:
            await feed.first.evaluate("el => el.scrollTo(0, el.scrollHeight)")
        except Exception:
            pass
        await page.wait_for_timeout(1200)

    found = []
    seen_urls = set()
    count = await cards.count()
    for i in range(min(target * 2, count)):
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
            await page.goto(card["url"], timeout=60000, wait_until="domcontentloaded")
            if await _is_blocked(page):
                if attempt == 0:
                    await page.wait_for_timeout(4000)
                    continue
                return
            try:
                await page.wait_for_selector("div.F7nice, h1, div[role='main']", timeout=20000)
            except Exception:
                pass
            await page.wait_for_timeout(int(_jitter(2200, 0.3)))
            info = await _extract_place(page, card["nome"])
            if info["nome"] and key not in seen_keys:
                info["consulta"] = location
                businesses.append(info)
                seen_keys.add(key)
            await page.wait_for_timeout(int(_jitter(delay * 600, 0.4)))
            return
        except Exception:
            if attempt == 1:
                return
            await page.wait_for_timeout(2500)


async def search_places(query, locations=None, max_results=15, headless=None, delay=1.5):
    settings = load_settings()
    if headless is None:
        headless = bool(settings.get("headless", True))

    if not locations:
        locations = ["Brasil"]

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
            full_query = f"{query} {location}".strip()
            url = f"https://www.google.com/maps/search/{quote_plus(full_query)}?hl=pt-BR"
            try:
                await page.goto(url, timeout=60000, wait_until="domcontentloaded")
            except Exception:
                continue
            await _accept_consent(page)

            if await _is_blocked(page):
                await page.wait_for_timeout(5000)
                try:
                    await page.goto(url, timeout=60000, wait_until="domcontentloaded")
                except Exception:
                    continue

            feed = page.locator('div[role="feed"]')
            try:
                await feed.first.wait_for(timeout=30000)
            except Exception:
                continue

            cards = await _collect_cards(page, feed, max_results)

            # visitas em paralelo (2 por vez)
            for i in range(0, len(cards), 2):
                chunk = cards[i:i + 2]
                tasks = [
                    _visit_place(worker_pages[j], card, location, seen_keys, businesses, delay)
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