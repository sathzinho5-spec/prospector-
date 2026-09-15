"""
CNPJ Store local (SQLite) - fallback quando o Supabase está fora do ar.
Mesmas tabelas e funções do backend Supabase: empresas_grandes + vistos_cnpj.
Banco fica em output/cnpj.db (pequeno, só gigantes filtrados).
"""
import os
import sqlite3

from config import OUTPUT_DIR

DB_PATH = os.path.join(OUTPUT_DIR, "cnpj.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS empresas_grandes (
  cnpj TEXT PRIMARY KEY,
  razao TEXT,
  fantasia TEXT,
  capital REAL,
  porte TEXT,
  uf TEXT,
  cidade TEXT,
  cnae TEXT,
  situacao TEXT,
  telefone TEXT,
  telefone2 TEXT,
  email TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS vistos_cnpj (
  cnpj TEXT PRIMARY KEY,
  visto_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_local_uf ON empresas_grandes(uf);
CREATE INDEX IF NOT EXISTS idx_local_capital ON empresas_grandes(capital);
CREATE INDEX IF NOT EXISTS idx_local_cidade ON empresas_grandes(cidade);
"""


def _conn():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(_SCHEMA)
    return con


_COLS = ["cnpj", "razao", "fantasia", "capital", "porte", "uf",
         "cidade", "cnae", "situacao", "telefone", "telefone2", "email"]


def subir(dados):
    if not dados:
        return 0
    con = _conn()
    try:
        rows = [tuple(d.get(c) for c in _COLS) for d in dados]
        con.executemany(
            f"INSERT OR REPLACE INTO empresas_grandes ({','.join(_COLS)}) "
            f"VALUES ({','.join('?' * len(_COLS))})",
            rows,
        )
        con.commit()
        return len(rows)
    finally:
        con.close()


def buscar(uf=None, capital_min=500000, cidade=None, limite=50, apenas_nao_vistos=True):
    con = _conn()
    try:
        q = "SELECT * FROM empresas_grandes WHERE capital >= ?"
        params = [capital_min]
        if uf:
            q += " AND uf = ?"
            params.append(uf.upper())
        if cidade:
            q += " AND cidade LIKE ?"
            params.append(f"%{cidade}%")
        if apenas_nao_vistos:
            q += " AND cnpj NOT IN (SELECT cnpj FROM vistos_cnpj)"
        q += " ORDER BY capital DESC LIMIT ?"
        params.append(int(limite))
        return [dict(r) for r in con.execute(q, params).fetchall()]
    finally:
        con.close()


def marcar(cnpjs):
    if not cnpjs:
        return
    con = _conn()
    try:
        con.executemany("INSERT OR IGNORE INTO vistos_cnpj (cnpj) VALUES (?)",
                        [(c,) for c in cnpjs])
        con.commit()
    finally:
        con.close()


def contar():
    con = _conn()
    try:
        return con.execute("SELECT COUNT(*) FROM empresas_grandes").fetchone()[0]
    finally:
        con.close()
