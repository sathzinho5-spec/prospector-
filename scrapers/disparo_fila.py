# proposito: a fila do disparo em SQLite, o bloqueio de telefone e o anti-duplicata
import datetime
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
"""
def _conn():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(_SCHEMA)
    try:
        cols = [r[1] for r in con.execute("PRAGMA table_info(fila)").fetchall()]
        if "instancia" not in cols:
            con.execute("ALTER TABLE fila ADD COLUMN instancia TEXT")
            con.commit()
        if "editada_em" not in cols:
            con.execute("ALTER TABLE fila ADD COLUMN editada_em TIMESTAMP")
            con.commit()
    except Exception:
        pass
    return con


def _norm_phone(raw):
    d = re.sub(r"\D", "", str(raw or ""))
    if 10 <= len(d) <= 11 and not d.startswith("55"):
        d = "55" + d
    return d if len(d) >= 12 else ""


def enfileirar(itens, origem=""):
    """itens: [{nome, telefone, mensagem}]. Retorna qtd enfileirada.
    Pula duplicata exata (mesmo telefone + mesma mensagem já pendente/enviando)."""
    con = _conn()
    n = 0
    try:
        # Por NUMERO, nao por telefone+mensagem: mesma pessoa com dois textos
        # diferentes continua sendo duas abordagens pra mesma pessoa.
        existentes = set(
            r[0] for r in con.execute(
                "SELECT telefone FROM fila WHERE status IN ('pendente','enviando')"
            ).fetchall()
        )
        existentes.update(
            r[0] for r in con.execute("SELECT telefone FROM numeros_abordados").fetchall()
        )
        existentes.update(
            r[0] for r in con.execute("SELECT telefone FROM numeros_bloqueados").fetchall()
        )
        for it in itens:
            tel = _norm_phone(it.get("telefone"))
            msg = (it.get("mensagem") or "").strip()
            if not tel or not msg:
                continue
            if tel in existentes:
                continue
            con.execute(
                "INSERT INTO fila (nome, telefone, mensagem, origem) VALUES (?,?,?,?)",
                (it.get("nome", ""), tel, msg, origem),
            )
            existentes.add(tel)
            n += 1
        con.commit()
    finally:
        con.close()
    return n


def listar(status=None, limite=200):
    con = _conn()
    try:
        if status:
            rows = con.execute(
                "SELECT * FROM fila WHERE status=? ORDER BY id DESC LIMIT ?",
                (status, limite)).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM fila ORDER BY id DESC LIMIT ?", (limite,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def limpar_finalizados():
    con = _conn()
    try:
        # 'duplicado' entra aqui porque tambem e estado final. O historico de
        # quem ja foi abordado nao mora na fila, entao limpar nao reabre o
        # disparo repetido.
        con.execute("DELETE FROM fila WHERE status IN ('enviado','falha','cancelado','duplicado','bloqueado')")
        con.commit()
    finally:
        con.close()


def _reivindicar(item_id):
    """Marca o item como 'enviando' de forma atômica.
    Retorna True só para quem conseguiu a trava (impede 2 robôs no mesmo item)."""
    con = _conn()
    try:
        cur = con.execute(
            "UPDATE fila SET status='enviando', agendado_para=CURRENT_TIMESTAMP "
            "WHERE id=? AND status='pendente'",
            (item_id,))
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()


def _devolver_travados(minutos=15):
    """Devolve para pendente os 'enviando' travados (robô morreu no meio)."""
    con = _conn()
    try:
        con.execute(
            "UPDATE fila SET status='pendente' WHERE status='enviando' "
            "AND datetime(agendado_para) < datetime('now', ?)",
            (f"-{int(minutos)} minutes",))
        con.commit()
    except Exception:
        pass
    finally:
        con.close()


def ja_recebeu(con, telefone, item_id=-1):
    """Aquele NUMERO ja recebeu abordagem? A pergunta e por numero e nunca por
    linha da fila: duas linhas com textos diferentes pro mesmo telefone sao duas
    abordagens pra mesma pessoa, e a segunda e contato queimado."""
    tel = _norm_phone(telefone)
    if not tel:
        return False
    if con.execute("SELECT 1 FROM numeros_abordados WHERE telefone=?", (tel,)).fetchone():
        return True
    row = con.execute(
        "SELECT 1 FROM fila WHERE telefone=? AND status='enviado' AND id<>?",
        (tel, item_id)).fetchone()
    return bool(row)


def bloquear(telefone, motivo=""):
    """Desativa um numero pro disparo. Idempotente."""
    tel = _norm_phone(telefone)
    if not tel:
        return False
    con = _conn()
    try:
        con.execute("INSERT OR IGNORE INTO numeros_bloqueados (telefone, motivo) VALUES (?,?)",
                    (tel, motivo))
        con.commit()
    finally:
        con.close()
    return True


def desbloquear(telefone):
    tel = _norm_phone(telefone)
    con = _conn()
    try:
        con.execute("DELETE FROM numeros_bloqueados WHERE telefone=?", (tel,))
        con.commit()
    finally:
        con.close()
    return True


def bloqueado(con, telefone):
    tel = _norm_phone(telefone)
    if not tel:
        return False
    return bool(con.execute(
        "SELECT 1 FROM numeros_bloqueados WHERE telefone=?", (tel,)).fetchone())


def registrar_abordado(con, telefone):
    """Grava o numero no historico que a limpeza da fila nao alcanca."""
    tel = _norm_phone(telefone)
    if tel:
        con.execute(
            "INSERT OR IGNORE INTO numeros_abordados (telefone) VALUES (?)", (tel,))


def telefones_na_fila():
    con = _conn()
    try:
        return set(r[0] for r in con.execute("SELECT DISTINCT telefone FROM fila").fetchall())
    finally:
        con.close()


def atualizar_mensagem(item_id, mensagem, manual=False):
    """Troca o texto de um item da fila. manual=True carimba a edicao a mao;
    manual=False (o padrao, que e o refazer com IA) LIMPA o carimbo, porque
    regenerar sobrescreve o que a pessoa escreveu e a tela nao pode seguir
    dizendo que aquele texto e dela."""
    con = _conn()
    try:
        if manual:
            con.execute("UPDATE fila SET mensagem=?, editada_em=CURRENT_TIMESTAMP WHERE id=?",
                        (mensagem, item_id))
        else:
            con.execute("UPDATE fila SET mensagem=?, editada_em=NULL WHERE id=?",
                        (mensagem, item_id))
        con.commit()
        return True
    finally:
        con.close()

def _enviados_hoje(con):
    row = con.execute(
        "SELECT COUNT(*) FROM fila WHERE status='enviado' AND date(enviado_em)=date('now')"
    ).fetchone()
    return row[0] if row else 0


# ---------------- Provedores ----------------
