import re

import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
WHATS_RE = re.compile(r"(?:wa\.me/|whatsapp\.com/send\?phone=|api\.whatsapp\.com/send\?phone=)(\d{10,15})")
INSTA_RE = re.compile(r"instagram\.com/([A-Za-z0-9._]+)/?")
FACE_RE = re.compile(r"facebook\.com/([A-Za-z0-9.\-/]+)")
LINKED_RE = re.compile(r"linkedin\.com/(?:company|in)/([A-Za-z0-9\-_%]+)")
TIKTOK_RE = re.compile(r"tiktok\.com/@([A-Za-z0-9._]+)")
PHONE_RE = re.compile(r"(?:\(\d{2}\)\s?|\b\d{2}\s)?9?\s?\d{4}[-\s]\d{4}")

BAD_EMAIL_DOMAINS = ("example.com", "dominio.com", "email.com", "sentry.io", "wixpress.com")
IMG_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")


def _digits(num):
    return re.sub(r"\D", "", num)


def _scan_html(html, result):
    emails = []
    for e in EMAIL_RE.findall(html):
        low = e.lower()
        if any(low.endswith(ext) for ext in IMG_EXT):
            continue
        if any(dom in low for dom in BAD_EMAIL_DOMAINS):
            continue
        if low not in [x.lower() for x in emails]:
            emails.append(e)

    whats = []
    for w in WHATS_RE.findall(html):
        d = _digits(w)
        if d and d not in whats:
            whats.append(d)

    phones = []
    for p in PHONE_RE.findall(html):
        d = _digits(p)
        if len(d) in (10, 11) and d not in whats and d not in phones:
            phones.append(d)

    return emails, whats, phones


def extract_site_contacts(url, timeout=15):
    if not url or not url.startswith("http"):
        url = "https://" + (url or "")

    result = {
        "url": url,
        "titulo": "",
        "descricao": "",
        "emails": [],
        "whatsapps": [],
        "telefones": [],
        "instagram": "",
        "facebook": "",
        "linkedin": "",
        "tiktok": "",
    }

    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9"})

    try:
        resp = session.get(url, timeout=timeout, allow_redirects=True)
    except Exception as e:
        result["erro"] = f"Falha ao acessar o site: {e}"
        return result

    if resp.status_code != 200:
        result["erro"] = f"Site respondeu HTTP {resp.status_code}"
        return result

    html = resp.text

    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    if m:
        result["titulo"] = re.sub(r"\s+", " ", m.group(1)).strip()[:120]

    m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', html, re.I | re.S)
    if not m:
        m = re.search(r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']', html, re.I | re.S)
    if m:
        result["descricao"] = re.sub(r"\s+", " ", m.group(1)).strip()[:200]

    emails, whats, phones = _scan_html(html, result)
    result["emails"] = emails[:5]
    result["whatsapps"] = whats[:3]
    result["telefones"] = phones[:3]

    # contato profundo: se achou pouco, tenta paginas comuns de contato
    if len(result["emails"]) == 0 or len(result["whatsapps"]) == 0:
        base = url.rstrip("/")
        for path in ("/contato", "/fale-conosco", "/sobre", "/contact"):
            try:
                r2 = session.get(base + path, timeout=10, allow_redirects=True)
                if r2.status_code == 200 and len(r2.text) > 200:
                    e2, w2, p2 = _scan_html(r2.text, result)
                    for x in e2:
                        if x.lower() not in [y.lower() for y in result["emails"]] and len(result["emails"]) < 5:
                            result["emails"].append(x)
                    for x in w2:
                        if x not in result["whatsapps"] and len(result["whatsapps"]) < 3:
                            result["whatsapps"].append(x)
                    for x in p2:
                        if x not in result["telefones"] and x not in whats and len(result["telefones"]) < 3:
                            result["telefones"].append(x)
            except Exception:
                continue

    m = INSTA_RE.search(html)
    if m and m.group(1).lower() not in ("p", "reel", "explore", "share"):
        result["instagram"] = m.group(1)
    m = FACE_RE.search(html)
    if m:
        result["facebook"] = ("facebook.com/" + m.group(1)).rstrip("/")
    m = LINKED_RE.search(html)
    if m:
        result["linkedin"] = m.group(1)
    m = TIKTOK_RE.search(html)
    if m:
        result["tiktok"] = m.group(1)

    return result