# proposito: tira o dado de uma pagina aberta do Maps: texto, link, consentimento, ficha
import re

from scrapers.gmaps_parse import (_SCAN_JS, _clean, _parse_cidade_estado, _parse_coords,
                                  _parse_rating)

async def _is_blocked(page):
    try:
        if "/sorry/" in page.url:
            return True
        content = (await page.content()).lower()
        return "recaptcha" in content or "unusual traffic" in content or "tráfego incomum" in content
    except Exception:
        return False
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
