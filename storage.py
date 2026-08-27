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
    return csv_path


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