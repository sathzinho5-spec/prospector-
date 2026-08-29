import csv
import json
import os

from config import OUTPUT_DIR

BUSINESS_FIELDS = [
    "nome", "categoria", "nota", "avaliacoes", "endereco", "bairro",
    "cidade", "estado", "telefone", "website", "horarios",
    "status_funcionamento", "preco", "plus_code", "atributos",
    "latitude", "longitude", "foto", "descricao", "consulta", "url",
]

INITIAL_BUSINESS_FIELDS = ["nome", "categoria", "nota", "avaliacoes", "endereco", "telefone", "website", "url"]


def ensure_dirs():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def save_json(name, data):
    ensure_dirs()
    path = os.path.join(OUTPUT_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def save_businesses(businesses, name="negocios"):
    save_json(f"{name}.json", businesses)
    csv_path = export_csv(businesses, name)
    # Também salva no Supabase (tabela leads) quando o scraping roda
    try:
        _save_supabase_leads(businesses)
    except Exception:
        pass
    return csv_path


def _save_supabase_leads(businesses):
    import hashlib

    from config import load_settings

    s = load_settings()
    url = s.get("supabase_url")
    key = s.get("supabase_secret") or s.get("supabase_publishable")
    if not url or not key:
        return
    try:
        from supabase import create_client

        supabase = create_client(url, key)
        rows = []
        for b in businesses:
            _id = hashlib.md5(f"{b.get('nome','')}|{b.get('endereco','')}".encode()).hexdigest()[:16]
            rows.append({
                "id": _id,
                "nome": b.get("nome"),
                "categoria": b.get("categoria"),
                "nota": b.get("nota"),
                "avaliacoes": b.get("avaliacoes"),
                "endereco": b.get("endereco"),
                "bairro": b.get("bairro"),
                "cidade": b.get("cidade"),
                "estado": b.get("estado"),
                "telefone": b.get("telefone"),
                "website": b.get("website"),
                "horarios": b.get("horarios"),
                "status_funcionamento": b.get("status_funcionamento"),
                "preco": b.get("preco"),
                "plus_code": b.get("plus_code"),
                "atributos": "; ".join(b.get("atributos") or []),
                "latitude": b.get("latitude"),
                "longitude": b.get("longitude"),
                "foto": b.get("foto"),
                "descricao": b.get("descricao"),
                "consulta": b.get("consulta"),
                "url": b.get("url"),
            })
        for i in range(0, len(rows), 200):
            supabase.table("leads").upsert(rows[i:i + 200], on_conflict="id").execute()
    except Exception:
        pass


def export_csv(businesses, name="negocios"):
    ensure_dirs()
    path = os.path.join(OUTPUT_DIR, f"{name}.csv")
    fields = [f for f in BUSINESS_FIELDS if any(b.get(f) for b in businesses)] or INITIAL_BUSINESS_FIELDS
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for b in businesses:
            row = {}
            for k, v in b.items():
                if isinstance(v, list):
                    v = "; ".join(str(x) for x in v)
                row[k] = "" if v is None else v
            writer.writerow(row)
    return path


def export_excel(businesses, name="negocios"):
    ensure_dirs()
    path = os.path.join(OUTPUT_DIR, f"{name}.xlsx")
    import pandas as pd

    df = pd.DataFrame(businesses)
    df.to_excel(path, index=False, engine="openpyxl")
    return path