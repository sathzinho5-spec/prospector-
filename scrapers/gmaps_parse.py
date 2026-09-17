# proposito: funcoes puras que viram texto raspado em dado: nota, cidade, coordenada
import random
import re

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

