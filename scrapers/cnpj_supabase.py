"""
CNPJ Supabase - Gigantes Invisíveis
Baixa CSVs da Receita no Temp, filtra capital >= 500k, sobe pro Supabase e apaga Temp.
Deduplicação via tabela vistos_cnpj.
Suporta múltiplos espelhos da Receita (tenta até achar um que responde).
"""
import csv
import io
import os
import shutil
import tempfile
import zipfile

import requests
from config import load_settings

# Tenta vários espelhos/meses até achar um que responde
BASE_CANDIDATOS = [
    "https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/2025-08",
    "https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/2025-07",
    "https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/2025-06",
    "https://dadosabertos.rfb.gov.br/CNPJ",
]

ARQUIVOS_EMPRESAS = [f"Empresas{i}.zip" for i in range(10)]
ARQUIVOS_ESTABELECIMENTOS = [f"Estabelecimentos{i}.zip" for i in range(10)]


def get_supabase():
    from supabase import create_client

    s = load_settings()
    url = s.get("supabase_url")
    key = s.get("supabase_secret") or s.get("supabase_publishable")
    if not url or not key:
        raise RuntimeError("Supabase URL/key não configurados em settings.json")
    return create_client(url, key)


def _descobrir_base():
    for base in BASE_CANDIDATOS:
        try:
            # tenta HEAD num arquivo pequeno
            test = f"{base}/Empresas0.zip"
            r = requests.head(test, timeout=15, allow_redirects=True)
            if r.status_code == 200:
                print(f"[CNPJ] Base encontrada: {base}")
                return base
        except Exception:
            continue
    # fallback: usa primeira mesmo e deixa falhar com aviso
    return BASE_CANDIDATOS[0]


def baixar_e_filtrar(tmpdir, capital_min=500000, max_arquivos=2):
    """
    Baixa ZIPs no tmpdir, extrai e filtra.
    max_arquivos = quantos ZIPs baixar de cada tipo (2 = teste rápido ~400MB, 10 = completo ~2GB)
    """
    base = _descobrir_base()
    empresas = {}

    print(f"[CNPJ] Baixando {max_arquivos} arquivos de Empresas em {tmpdir}...")
    for zname in ARQUIVOS_EMPRESAS[:max_arquivos]:
        url = f"{base}/{zname}"
        print(f"  -> {url}")
        try:
            r = requests.get(url, stream=True, timeout=120)
            if r.status_code != 200:
                print(f"  [aviso] HTTP {r.status_code} para {zname}, pulando")
                continue
            zpath = os.path.join(tmpdir, zname)
            with open(zpath, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            print(f"  [ok] {zname} baixado, extraindo...")
            with zipfile.ZipFile(zpath) as z:
                for name in z.namelist():
                    with z.open(name) as f:
                        reader = csv.reader(io.TextIOWrapper(f, encoding="iso-8859-1"), delimiter=";")
                        for row in reader:
                            try:
                                cnpj_base = row[0]
                                razao = row[1]
                                capital = float(row[5].replace(",", ".")) if len(row) > 5 and row[5] else 0
                                porte = row[6] if len(row) > 6 else ""
                                if capital >= capital_min:
                                    empresas[cnpj_base] = (razao, capital, porte)
                            except Exception:
                                continue
            os.remove(zpath)
            print(f"  [CNPJ] {len(empresas)} empresas grandes até agora")
        except Exception as e:
            print(f"  [aviso] falha em {zname}: {e}")

    print(f"[CNPJ] Total: {len(empresas)} empresas com capital >= {capital_min}")

    filtrados = []
    print(f"[CNPJ] Baixando {max_arquivos} arquivos de Estabelecimentos...")
    for zname in ARQUIVOS_ESTABELECIMENTOS[:max_arquivos]:
        url = f"{base}/{zname}"
        print(f"  -> {url}")
        try:
            r = requests.get(url, stream=True, timeout=120)
            if r.status_code != 200:
                print(f"  [aviso] HTTP {r.status_code} para {zname}, pulando")
                continue
            zpath = os.path.join(tmpdir, zname)
            with open(zpath, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            print(f"  [ok] {zname} baixado, extraindo...")
            with zipfile.ZipFile(zpath) as z:
                for name in z.namelist():
                    with z.open(name) as f:
                        reader = csv.reader(io.TextIOWrapper(f, encoding="iso-8859-1"), delimiter=";")
                        for row in reader:
                            try:
                                cnpj_base = row[0]
                                if cnpj_base not in empresas:
                                    continue
                                situacao = row[5] if len(row) > 5 else ""
                                if situacao != "02":
                                    continue
                                uf = row[19] if len(row) > 19 else ""
                                cidade = row[20] if len(row) > 20 else ""
                                cnae = row[11] if len(row) > 11 else ""
                                razao, capital, porte = empresas[cnpj_base]
                                cnpj_full = row[0] + row[1] + row[2] if len(row) > 2 else cnpj_base
                                filtrados.append({
                                    "cnpj": cnpj_full,
                                    "razao": razao,
                                    "fantasia": row[4] if len(row) > 4 and row[4] else razao,
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


def sync_completo(capital_min=500000, max_arquivos=2):
    tmpdir = tempfile.mkdtemp(prefix="prospector_cnpj_")
    try:
        dados = baixar_e_filtrar(tmpdir, capital_min=capital_min, max_arquivos=max_arquivos)
        if dados:
            subir_para_supabase(dados)
            print(f"[OK] {len(dados)} empresas enviadas ao Supabase")
        else:
            print("[aviso] nenhum dado para enviar (verifique capital_min ou conexão)")
        return len(dados)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        print(f"[limpeza] Temp apagado: {tmpdir}")


if __name__ == "__main__":
    import sys
    cap = int(sys.argv[1]) if len(sys.argv) > 1 else 500000
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    print(sync_completo(capital_min=cap, max_arquivos=n))
