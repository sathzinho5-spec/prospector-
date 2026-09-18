# proposito: o banco do disparo: caminho, esquema das tabelas e migracao defensiva
"""
Saiu de scrapers/disparo_fila.py quando o disparo ganhou historico de abordagem
e copy de lead: as tres coisas moram no mesmo arquivo .db e precisavam do mesmo
_conn(), mas a fila nao e dona do esquema das outras duas. disparo_fila.py
reexporta DB_PATH, _SCHEMA, _conn e _norm_phone, entao nenhuma chamada de fora
mudou.
"""
import os
import re
import sqlite3

from config import OUTPUT_DIR

DB_PATH = os.path.join(OUTPUT_DIR, "disparo.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS fila (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nome TEXT,
  telefone TEXT NOT NULL,
  mensagem TEXT NOT NULL,
  status TEXT DEFAULT 'pendente',
  tentativas INTEGER DEFAULT 0,
  agendado_para TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  enviado_em TIMESTAMP,
  erro TEXT,
  origem TEXT
);
CREATE INDEX IF NOT EXISTS idx_fila_status ON fila(status);

-- Numero que ja recebeu abordagem, para nunca receber uma segunda.
-- Vive FORA da fila de proposito: limpar a fila apaga o historico dela, e se a
-- protecao dependesse dele, a primeira limpeza reabriria o disparo duplicado
-- sem ninguem perceber.
CREATE TABLE IF NOT EXISTS numeros_abordados (
  telefone TEXT PRIMARY KEY,
  primeiro_envio TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Numero desativado pro disparo por decisao de quem opera. Diferente do
-- abordado: aqui nao houve envio nenhum, e a pessoa escolheu que nao ha de
-- haver. Mora fora da fila pelo mesmo motivo: limpar a fila nao pode reabrir
-- o envio pra quem foi desativado de proposito.
CREATE TABLE IF NOT EXISTS numeros_bloqueados (
  telefone TEXT PRIMARY KEY,
  motivo TEXT,
  bloqueado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- A copy de abordagem de um lead, escrita ANTES de ele entrar na fila. Mora
-- fora da fila pelo mesmo motivo das duas de cima: limpar a fila nao pode
-- fazer um lead que ja tem copy voltar a aparecer como 'sem copy' na tela.
CREATE TABLE IF NOT EXISTS copys (
  telefone TEXT PRIMARY KEY,
  nome TEXT,
  mensagem TEXT NOT NULL,
  copy_origem TEXT DEFAULT 'ia',
  criada_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  editada_em TIMESTAMP
);

-- O texto que DE FATO saiu, por envio, e quando aquela conversa comecou.
-- Este e o registro da conversao e ele NAO pode morar na fila: a fila perde as
-- linhas 'enviado' na primeira limpeza, e com elas iria embora a unica resposta
-- para "qual copy converteu". Mesmo precedente do numeros_abordados.
CREATE TABLE IF NOT EXISTS abordagens (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  telefone TEXT NOT NULL,
  nome TEXT,
  mensagem TEXT NOT NULL,
  copy_origem TEXT,
  instancia TEXT,
  origem TEXT,
  enviado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  respondido_em TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_abordagens_telefone ON abordagens(telefone);
CREATE INDEX IF NOT EXISTS idx_abordagens_enviado ON abordagens(enviado_em);
"""

# Colunas que nasceram depois do banco. ALTER defensivo: banco que ja existe
# ganha o que falta sozinho, sem apagar nada.
_COLUNAS_NOVAS = (
    ("fila", "instancia", "TEXT"),
    ("fila", "editada_em", "TIMESTAMP"),
    ("fila", "copy_origem", "TEXT"),
)

_migrado = False


def _norm_phone(raw):
    d = re.sub(r"\D", "", str(raw or ""))
    if 10 <= len(d) <= 11 and not d.startswith("55"):
        d = "55" + d
    return d if len(d) >= 12 else ""


def _semear_abordagens(con):
    """Banco que ja rodava tem envio na fila e nenhuma abordagem registrada.

    Sem esta semeadura o contador de hoje nasceria zerado na primeira subida da
    versao nova e o motor estouraria o limite diario; e o historico de quem ja
    foi abordado comecaria mentindo que ninguem recebeu nada. Casa por telefone
    porque o anti-duplicata garante uma abordagem por numero.
    """
    con.execute(
        "INSERT INTO abordagens "
        "  (telefone, nome, mensagem, copy_origem, instancia, origem, enviado_em) "
        "SELECT f.telefone, f.nome, f.mensagem, "
        "       CASE WHEN f.editada_em IS NOT NULL THEN 'manual' "
        "            ELSE COALESCE(f.copy_origem, 'desconhecida') END, "
        "       f.instancia, f.origem, COALESCE(f.enviado_em, CURRENT_TIMESTAMP) "
        "  FROM fila f "
        " WHERE f.status='enviado' "
        "   AND NOT EXISTS (SELECT 1 FROM abordagens a WHERE a.telefone = f.telefone)"
    )
    con.commit()


def _migrar(con):
    """Roda uma vez por processo, na primeira conexao."""
    for tabela, coluna, tipo in _COLUNAS_NOVAS:
        try:
            cols = [r[1] for r in con.execute("PRAGMA table_info(%s)" % tabela).fetchall()]
            if coluna not in cols:
                con.execute("ALTER TABLE %s ADD COLUMN %s %s" % (tabela, coluna, tipo))
                con.commit()
        except Exception:
            pass
    try:
        _semear_abordagens(con)
    except Exception:
        pass


def _conn():
    global _migrado
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(_SCHEMA)
    if not _migrado:
        _migrar(con)
        _migrado = True
    return con
