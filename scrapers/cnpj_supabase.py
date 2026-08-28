"""
CNPJ Supabase - Gigantes Invisíveis
Baixa CSVs da Receita no Temp, filtra capital >= 500k, sobe pro Supabase e apaga Temp.
Deduplicação via tabela vistos_cnpj.
"""
import csv
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

import requests
from config import load_settings

# URLs dos Dados Abertos - atualize o mês se necessário
# Fonte: https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/
BASE_URL = "https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/2025-08"

# Para teste inicial, usamos apenas 1 arquivo de cada para validar o fluxo
# Depois troque para lista completa
ARQUIVOS_EMPRESAS = ["Empresas0.zip", "Empresas1.zip"]
ARQUIVOS_ESTABELECIMENTOS = ["Estabelecimentos0.zip", "Estabelecimentos1.zip"]


def get_supabase():
    from supabase import create_client

    s = load_settings()
    url = s.get("supabase_url")
    key = s.get("supabase_secret") or s.get("supabase_publishable")
    if not url or not key:
        raise RuntimeError("Supabase URL/key não configurados em settings.json")
    return create_client(url, key)


def baixar_e_filtrar(tmpdir, capital_min=500000):
    """
    Baixa ZIPs no tmpdir, extrai e filtra.
    Retorna lista de dicts {cnpj, razao, capital, uf, cidade, cnae}
    """
    import io

    # Mapa cnpj_base -> (razao, capital, porte)
    empresas = {}

    print(f"[CNPJ] Baixando Empresas em {tmpdir}...")
    for zname in ARQUIVOS_EMPRESAS:
        url = f"{BASE_URL}/{zname}"
        print(f"  -> {url}")
        try:
            r = requests.get(url, stream=True, timeout=120)
            r.raise_for_status()
            zpath = os.path.join(tmpdir, zname)
            with open(zpath, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            with zipfile.ZipFile(zpath) as z:
                for name in z.namelist():
                    with z.open(name) as f:
                        reader = csv.reader(io.TextIOWrapper(f, encoding="iso-8859-1"), delimiter=";")
                        for row in reader:
                            try:
                                cnpj_base = row[0]
                                razao = row[1]
                                capital = float(row[5].replace(",", ".")) if row[5] else 0
                                porte = row[6]
                                if capital >= capital_min:
                                    empresas[cnpj_base] = (razao, capital, porte)
                            except Exception:
                                continue
            os.remove(zpath)
        except Exception as e:
            print(f"  [aviso] falha em {zname}: {e}")

    print(f"[CNPJ] {len(empresas)} empresas com capital >= {capital_min}")

    # Filtra estabelecimentos ativos nas UFs desejadas
    filtrados = []
    print("[CNPJ] Baixando Estabelecimentos...")
    for zname in ARQUIVOS_ESTABELECIMENTOS:
        url = f"{BASE_URL}/{zname}"
        print(f"  -> {url}")
        try:
            r = requests.get(url, stream=True, timeout=120)
            r.raise_for_status()
            zpath = os.path.join(tmpdir, zname)
            with open(zpath, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            with zipfile.ZipFile(zpath) as z:
                for name in z.namelist():
                    with z.open(name) as f:
                        reader = csv.reader(io.TextIOWrapper(f, encoding="iso-8859-1"), delimiter=";")
                        for row in reader:
                            try:
                                cnpj_base = row[0]
                                if cnpj_base not in empresas:
                                    continue
                                situacao = row[5]
                                if situacao != "02":  # 02 = Ativa
                                    continue
                                uf = row[19]
                                cidade = row[20]
                                cnae = row[11]
                                razao, capital, porte = empresas[cnpj_base]
                                cnpj_full = row[0] + row[1] + row[2]
                                filtrados.append({
                                    "cnpj": cnpj_full,
                                    "razao": razao,
                                    "fantasia": row[4] or razao,
                                    "capital": capital,
                                    "porte": porte,
                                    "uf": uf,
                                    "cidade": cidade,
                                    "cnae": cnae,
                                    "situacao": situacao,
                                })
                            except Exception:
                                continue
            os.remove(zpath)
        except Exception as e:
            print(f"  [aviso] falha em {zname}: {e}")

    print(f"[CNPJ] Filtrados: {len(filtrados)} estabelecimentos ativos e grandes")
    return filtrados


def subir_para_supabase(dados):
    supabase = get_supabase()
    # upsert em lotes de 500
    for i in range(0, len(dados), 500):
        lote = dados[i:i + 500]
        supabase.table("empresas_grandes").upsert(lote, on_conflict="cnpj").execute()
        print(f"[Supabase] lote {i // 500 + 1}: {len(lote)} linhas")


def buscar_grandes_supabase(uf=None, capital_min=500000, cidade=None, limite=50, apenas_nao_vistos=True):
    supabase = get_supabase()
    q = supabase.table("empresas_grandes").select("*").gte("capital", capital_min)
    if uf:
        q = q.eq("uf", uf.upper())
    if cidade:
        q = q.ilike("cidade", f"%{cidade}%")
    q = q.order("capital", desc=True).limit(limite * 3 if apenas_nao_vistos else limite)
    res = q.execute()
    rows = res.data or []

    if apenas_nao_vistos and rows:
        vistos = supabase.table("vistos_cnpj").select("cnpj").execute()
        vistos_set = set(r["cnpj"] for r in (vistos.data or []))
        rows = [r for r in rows if r["cnpj"] not in vistos_set][:limite]
    else:
        rows = rows[:limite]
    return rows


def marcar_vistos(cnpjs):
    supabase = get_supabase()
    lote = [{"cnpj": c} for c in cnpjs]
    if lote:
        supabase.table("vistos_cnpj").upsert(lote, on_conflict="cnpj").execute()


def sync_completo(capital_min=500000):
    tmpdir = tempfile.mkdtemp(prefix="prospector_cnpj_")
    try:
        dados = baixar_e_filtrar(tmpdir, capital_min=capital_min)
        if dados:
            subir_para_supabase(dados)
            print(f"[OK] {len(dados)} empresas enviadas ao Supabase")
        else:
            print("[aviso] nenhum dado para enviar (verifique capital_min ou UFs)")
        return len(dados)
    finally:
        # Apaga tudo do Temp
        shutil.rmtree(tmpdir, ignore_errors=True)
        print(f"[limpeza] Temp apagado: {tmpdir}")


if __name__ == "__main__":
    import sys

    cap = int(sys.argv[1]) if len(sys.argv) > 1 else 500000
    sync_completo(capital_min=cap)
