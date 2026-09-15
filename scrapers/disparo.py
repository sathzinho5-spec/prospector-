"""
Disparador automático de mensagens (nível 3).
- Fila persistente em SQLite (output/disparo.db)
- Worker em thread: delays aleatórios, limite diário, janela de horário
- Provedores: Simulado (teste), Evolution API (QR code), Meta Cloud API (oficial)
"""
import datetime
import os
import random
import re
import sqlite3
import threading
import time

import requests

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
"""

_worker_thread = None
_worker_stop = threading.Event()
_worker_cfg = {}
_worker_state = {"rodando": False, "provider": "simulado", "enviados_hoje": 0,
                 "proximo_em": None, "ultimo_erro": ""}


def _conn():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(_SCHEMA)
    return con


def _norm_phone(raw):
    d = re.sub(r"\D", "", str(raw or ""))
    if 10 <= len(d) <= 11 and not d.startswith("55"):
        d = "55" + d
    return d if len(d) >= 12 else ""


def enfileirar(itens, origem=""):
    """itens: [{nome, telefone, mensagem}]. Retorna qtd enfileirada."""
    con = _conn()
    n = 0
    try:
        for it in itens:
            tel = _norm_phone(it.get("telefone"))
            msg = (it.get("mensagem") or "").strip()
            if not tel or not msg:
                continue
            con.execute(
                "INSERT INTO fila (nome, telefone, mensagem, origem) VALUES (?,?,?,?)",
                (it.get("nome", ""), tel, msg, origem),
            )
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
        con.execute("DELETE FROM fila WHERE status IN ('enviado','falha','cancelado')")
        con.commit()
    finally:
        con.close()


def _enviados_hoje(con):
    row = con.execute(
        "SELECT COUNT(*) FROM fila WHERE status='enviado' AND date(enviado_em)=date('now')"
    ).fetchone()
    return row[0] if row else 0


# ---------------- Provedores ----------------

class SimuladoProvider:
    name = "simulado"

    def send(self, phone, message):
        print(f"[disparo-simulado] para {phone}: {message[:60]}...")
        return True, ""


class EvolutionProvider:
    name = "evolution"

    def __init__(self, base_url, apikey, instance):
        self.base_url = (base_url or "").rstrip("/")
        self.apikey = apikey or ""
        self.instance = instance or ""

    def send(self, phone, message):
        if not self.base_url or not self.apikey or not self.instance:
            return False, "Evolution não configurado (url/key/instance)"
        try:
            r = requests.post(
                f"{self.base_url}/message/sendText/{self.instance}",
                headers={"apikey": self.apikey, "Content-Type": "application/json"},
                json={"number": phone, "text": message},
                timeout=30,
            )
            if r.status_code in (200, 201):
                return True, ""
            return False, f"Evolution HTTP {r.status_code}: {r.text[:200]}"
        except Exception as e:
            return False, str(e)[:200]


class MetaCloudProvider:
    name = "meta"

    def __init__(self, token, phone_id):
        self.token = token or ""
        self.phone_id = phone_id or ""

    def send(self, phone, message):
        if not self.token or not self.phone_id:
            return False, "Meta Cloud não configurado (token/phone_id)"
        try:
            r = requests.post(
                f"https://graph.facebook.com/v21.0/{self.phone_id}/messages",
                headers={"Authorization": f"Bearer {self.token}",
                         "Content-Type": "application/json"},
                json={"messaging_product": "whatsapp", "to": phone,
                      "type": "text", "text": {"body": message}},
                timeout=30,
            )
            if r.status_code in (200, 201):
                return True, ""
            return False, f"Meta HTTP {r.status_code}: {r.text[:200]}"
        except Exception as e:
            return False, str(e)[:200]


def _make_provider(cfg):
    which = (cfg.get("provider") or "simulado").lower()
    if which == "evolution":
        return EvolutionProvider(cfg.get("evo_url"), cfg.get("evo_key"), cfg.get("evo_instance"))
    if which == "meta":
        return MetaCloudProvider(cfg.get("meta_token"), cfg.get("meta_phone_id"))
    return SimuladoProvider()


# ---------------- Worker ----------------

def _in_window(now, ini, fim):
    try:
        h = now.hour + now.minute / 60.0
        hi = int(str(ini).split(":")[0]) + int(str(ini).split(":")[1]) / 60.0
        hf = int(str(fim).split(":")[0]) + int(str(fim).split(":")[1]) / 60.0
        return hi <= h < hf
    except Exception:
        return True


def _worker_loop():
    global _worker_state
    cfg = _worker_cfg
    provider = _make_provider(cfg)
    delay_min = float(cfg.get("delay_min", 45))
    delay_max = float(cfg.get("delay_max", 120))
    limite_dia = int(cfg.get("limite_dia", 50))
    hora_ini = cfg.get("hora_ini", "08:00")
    hora_fim = cfg.get("hora_fim", "20:00")
    optout = bool(cfg.get("optout", True))
    optout_txt = "\n\nResponda SAIR para não receber mais mensagens."

    _worker_state.update({"rodando": True, "provider": provider.name, "ultimo_erro": ""})

    while not _worker_stop.is_set():
        try:
            now = datetime.datetime.now()
            if not _in_window(now, hora_ini, hora_fim):
                _worker_state["proximo_em"] = "fora da janela de horário"
                _worker_stop.wait(60)
                continue

            con = _conn()
            try:
                if _enviados_hoje(con) >= limite_dia:
                    _worker_state["proximo_em"] = "limite diário atingido"
                    con.close()
                    _worker_stop.wait(300)
                    continue
                row = con.execute(
                    "SELECT * FROM fila WHERE status='pendente' "
                    "AND datetime(agendado_para) <= datetime('now') "
                    "ORDER BY id ASC LIMIT 1").fetchone()
                if not row:
                    _worker_state["proximo_em"] = "fila vazia"
                    con.close()
                    _worker_stop.wait(15)
                    continue
                item = dict(row)
            finally:
                try:
                    con.close()
                except Exception:
                    pass

            msg = item["mensagem"] + (optout_txt if optout else "")
            ok, err = provider.send(item["telefone"], msg)

            con = _conn()
            try:
                if ok:
                    con.execute(
                        "UPDATE fila SET status='enviado', enviado_em=CURRENT_TIMESTAMP WHERE id=?",
                        (item["id"],))
                else:
                    tent = item.get("tentativas", 0) + 1
                    status = "falha" if tent >= 3 else "pendente"
                    con.execute(
                        "UPDATE fila SET status=?, tentativas=?, erro=?, "
                        "agendado_para=datetime('now','+10 minutes') WHERE id=?",
                        (status, tent, err, item["id"]))
                    _worker_state["ultimo_erro"] = err
                con.commit()
                _worker_state["enviados_hoje"] = _enviados_hoje(con)
            finally:
                con.close()

            espera = random.uniform(delay_min, delay_max)
            _worker_state["proximo_em"] = (
                datetime.datetime.now() + datetime.timedelta(seconds=espera)
            ).strftime("%H:%M:%S")
            _worker_stop.wait(espera)
        except Exception as e:
            _worker_state["ultimo_erro"] = str(e)[:200]
            _worker_stop.wait(10)

    _worker_state["rodando"] = False
    _worker_state["proximo_em"] = None


def iniciar(cfg):
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return False
    _worker_stop.clear()
    _worker_cfg.clear()
    _worker_cfg.update(cfg or {})
    _worker_thread = threading.Thread(target=_worker_loop, daemon=True)
    _worker_thread.start()
    return True


def pausar():
    _worker_stop.set()
    _worker_state["rodando"] = False


def status():
    con = _conn()
    try:
        pend = con.execute("SELECT COUNT(*) FROM fila WHERE status='pendente'").fetchone()[0]
        env = con.execute("SELECT COUNT(*) FROM fila WHERE status='enviado'").fetchone()[0]
        falha = con.execute("SELECT COUNT(*) FROM fila WHERE status='falha'").fetchone()[0]
        hoje = _enviados_hoje(con)
    finally:
        con.close()
    out = dict(_worker_state)
    out.update({"pendentes": pend, "enviados": env, "falhas": falha, "enviados_hoje": hoje})
    return out
