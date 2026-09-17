import base64
import re
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

from playwright.async_api import async_playwright

from config import load_settings

UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
]

UA = UA_POOL[0]


def _ua_random():
    import random
    return random.choice(UA_POOL)


def _clean(url):
    if "bing.com/ck/a" in url:
        m = re.search(r"[?&]u=([^&]+)", url)
        if m:
            try:
                enc = unquote(m.group(1))
                if enc[:2] in ("a1", "a9"):
                    enc = enc[2:]
                decoded = base64.urlsafe_b64decode(enc + "==").decode("utf-8")
                if decoded.startswith("http"):
                    return decoded
            except Exception:
                pass
    if "google.com/url" in url:
        q = parse_qs(urlparse(url).query).get("q")
        if q:
            return q[0]
    return url


def extract_instagram_handle(results):
    skip = {"explore", "p", "reel", "accounts", "share", "login", "stories", "reels", "home", "direct", "create", "session"}
    for r in results:
        m = re.search(r"instagram\.com/([A-Za-z0-9._]+)/?", r["url"])
        if m:
            handle = m.group(1)
            if handle.lower() not in skip and not handle.startswith("@"):
                return handle
    return None


async def _dedupe(results):
    seen, out = set(), []
    for r in results:
        if r["url"] in seen:
            continue
        seen.add(r["url"])
        out.append(r)
    return out


async def _ddg_bloqueado(page):
    """Detecta página de erro/bloqueio do DuckDuckGo."""
    try:
        txt = await page.locator("body").inner_text(timeout=3000)
        baixo = txt.lower()
        return ("anonymized error code" in baixo or "email us" in baixo) and len(txt) < 2000
    except Exception:
        return False


async def _search_duckduckgo(page, query, max_results):
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    await page.goto(url, timeout=45000, wait_until="domcontentloaded")
    await page.wait_for_timeout(1200)
    if await _ddg_bloqueado(page):
        return []
    out = []
    links = page.locator("a.result__a")
    n = await links.count()
    for i in range(min(n, max_results)):
        try:
            href = await links.nth(i).get_attribute("href")
            title = (await links.nth(i).inner_text()).strip()
            if not href or not title:
                continue
            if "duckduckgo.com/y.js" in href:
                m = re.search(r"uddg=([^&]+)", href)
                href = unquote(m.group(1)) if m else href
            out.append({"title": title, "url": _clean(href)})
        except Exception:
            continue
    return out[:max_results]


async def _bing_bloqueado(page):
    try:
        if "/sorry/" in page.url:
            return True
        txt = await page.locator("body").inner_text(timeout=3000)
        baixo = txt.lower()
        return ("unusual traffic" in baixo or "captcha" in baixo) and len(txt) < 3000
    except Exception:
        return False


async def _search_bing(page, query, max_results):
    url = f"https://www.bing.com/search?q={quote_plus(query)}&setlang=pt-BR"
    await page.goto(url, timeout=45000, wait_until="domcontentloaded")
    await page.wait_for_timeout(2000)
    if await _bing_bloqueado(page):
        return []
    out = []
    links = page.locator("li.b_algo h2 a")
    n = await links.count()
    for i in range(min(n, max_results)):
        try:
            href = await links.nth(i).get_attribute("href")
            title = (await links.nth(i).inner_text()).strip()
            if not href or not title:
                continue
            out.append({"title": title, "url": _clean(href)})
        except Exception:
            continue
    return out[:max_results]


async def google_search(query, max_results=8, headless=None):
    settings = load_settings()
    if headless is None:
        headless = bool(settings.get("headless", True))

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless, args=["--disable-blink-features=AutomationControlled"])
        page = await browser.new_page(
            user_agent=_ua_random(),
            locale="pt-BR",
            viewport={"width": 1366, "height": 900},
            extra_http_headers={"Accept-Language": "pt-BR,pt;q=0.9"},
        )
        # Bing primeiro (mais estável no momento); DDG como fallback
        results = []
        try:
            results = await _search_bing(page, query, max_results)
        except Exception:
            results = []
        if not results:
            try:
                results = await _search_duckduckgo(page, query, max_results)
            except Exception:
                results = []
        if not results:
            # última tentativa: Bing de novo após pausa (pode ser rate-limit momentâneo)
            try:
                await page.wait_for_timeout(3000)
                results = await _search_bing(page, query, max_results)
            except Exception:
                results = []
        await browser.close()
    return await _dedupe(results)


async def find_business_reference(name, location=""):
    query = f'{name} {location}'.strip()
    web_results = await google_search(query, max_results=8)
    ig_results = await google_search(f"{name} instagram", max_results=8)
    handle = extract_instagram_handle(ig_results)
    if not handle:
        for r in web_results:
            m = re.search(r"instagram\.com/([A-Za-z0-9._]+)/?", r["url"])
            if m and m.group(1).lower() not in {"explore", "p", "reel"}:
                handle = m.group(1)
                break
    return {
        "nome": name,
        "web_results": web_results,
        "instagram_handle": handle,
        "instagram_search": ig_results,
    }


_PULAR_HANDLES = {"explore", "p", "reel", "reels", "stories", "accounts",
                  "share", "login", "home", "direct", "create", "session",
                  "about", "developer", "legal", "privacy"}


def _handle_de_url(url):
    m = re.search(r"instagram\.com/([A-Za-z0-9._]+)/?", url or "")
    if not m:
        return ""
    handle = m.group(1)
    if handle.lower() in _PULAR_HANDLES or handle.startswith("@"):
        return ""
    return handle


async def prospectar_instagram(nicho, local="", max_results=20):
    """Descobre perfis de empresas no Instagram via busca indexada (sem login).
    Retorna [{username, url, titulo, contexto}]."""
    consultas = [
        f'site:instagram.com "{nicho}"',
        f'site:instagram.com "{nicho}" "{local}"' if local else "",
        f'instagram.com "{nicho}" "{local}" perfil' if local else "",
        f'"{nicho}" instagram "{local}" agende orçamento' if local else f'"{nicho}" instagram perfil',
    ]
    consultas = [c for c in consultas if c]

    achados = []
    vistos = set()
    for q in consultas:
        try:
            resultados = await google_search(q, max_results=12)
        except Exception:
            continue
        for r in resultados:
            handle = _handle_de_url(r["url"])
            if not handle or handle in vistos:
                continue
            vistos.add(handle)
            achados.append({
                "username": handle,
                "url": f"https://www.instagram.com/{handle}/",
                "titulo": r["title"],
                "contexto": local,
            })
            if len(achados) >= max_results:
                return achados
    return achados