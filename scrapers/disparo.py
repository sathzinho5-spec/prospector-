"""
Disparador automático de mensagens (nível 3).
- Fila persistente em SQLite (output/disparo.db)
- Worker em thread: cadência derivada da janela e do limite, janela de horário
- Provedores: Simulado (teste), Evolution API (QR code), Meta Cloud API (oficial)

proposito: o motor do disparo: janela de horario, worker em thread, iniciar e pausar
"""
import datetime
import threading
import time

from scrapers import disparo_abordagens, disparo_cadencia
# Reexportado de proposito: quem chama continua fazendo disparo.enfileirar,
# disparo.listar, disparo._make_provider. Nenhuma chamada de fora muda.
from scrapers.disparo_fila import (DB_PATH, _SCHEMA, _conn, _devolver_travados,
                                   _enviados_hoje, _norm_phone, _reivindicar,
                                   atualizar_mensagem, bloquear, bloqueado,
                                   desbloquear, enfileirar, ja_recebeu,
                                   limpar_finalizados, listar, registrar_abordado,
                                   telefones_bloqueados, telefones_na_fila)
from scrapers.disparo_providers import (EvolutionProvider, MetaCloudProvider,
                                        SimuladoProvider, _build_providers,
                                        _eh_falha_conexao, _erro_amigavel,
                                        _make_provider)

_worker_thread = None
_worker_stop = threading.Event()
_worker_cfg = {}
_worker_lock = threading.Lock()
_worker_state = {"rodando": False, "provider": "simulado", "enviados_hoje": 0,
                 "proximo_em": None, "ultimo_erro": "",
                 "cadencia": "", "intervalo_seg": 0}
def enviar_agora(item_id, provider):
    """Envia um item específico na hora, a qualquer momento. Retorna (ok, err).

    Convive com o motor automático em vez de pausá-lo: quem impede os dois de
    brigarem pelo mesmo item é a trava atômica _reivindicar, a mesma que o
    worker usa. Quem chegar primeiro leva o item; o outro recebe False e segue.
    """
    if not _reivindicar(item_id):
        return False, "Item já está sendo enviado por outro processo"
    con = _conn()
    try:
        row = con.execute("SELECT * FROM fila WHERE id=?", (item_id,)).fetchone()
        if not row:
            return False, "Item não encontrado na fila"
        item = dict(row)
        if bloqueado(con, item["telefone"]):
            erro = "Este numero esta desativado pro disparo."
            con.execute("UPDATE fila SET status='bloqueado', erro=? WHERE id=?",
                        (erro, item_id))
            con.commit()
            return False, erro
        if ja_recebeu(con, item["telefone"], item_id):
            erro = "Este numero ja recebeu uma abordagem."
            con.execute("UPDATE fila SET status='duplicado', erro=? WHERE id=?",
                        (erro, item_id))
            con.commit()
            return False, erro
        msg = item["mensagem"]
        ok, err = provider.send(item["telefone"], msg)
        nome_chip = getattr(provider, "instance", provider.name)
        if ok:
            con.execute(
                "UPDATE fila SET status='enviado', enviado_em=CURRENT_TIMESTAMP, "
                "instancia=? WHERE id=?",
                (nome_chip, item_id,))
            registrar_abordado(con, item["telefone"])
            # Mesma transacao do UPDATE de proposito: o registro do que saiu e a
            # metrica de conversao, e ele nao pode divergir da fila nem por uma
            # falha no meio. O envio avulso nao acrescenta opt-out, entao o
            # texto gravado e exatamente o que o provedor recebeu.
            disparo_abordagens.registrar(con, item, msg, nome_chip)
        else:
            tent = item.get("tentativas", 0) + 1
            status = "falha" if tent >= 3 else "pendente"
            con.execute(
                "UPDATE fila SET status=?, tentativas=?, erro=? WHERE id=?",
                (status, tent, err, item_id))
        con.commit()
        return ok, err
    finally:
        con.close()

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
    providers = _build_providers(cfg)
    prov_idx = 0
    ruim_ate = {}
    nomes = ",".join(getattr(p, "instance", p.name) for p in providers)
    hora_ini = cfg.get("hora_ini", disparo_cadencia.PADRAO_HORA_INI)
    hora_fim = cfg.get("hora_fim", disparo_cadencia.PADRAO_HORA_FIM)
    # A pausa entre envios nao vem mais da tela: ela e derivada da janela e do
    # limite do dia, pela regra fixa de cadencia. Um numero so, calculado num
    # lugar so, entao o que o operador le e o que o motor faz.
    cadencia = disparo_cadencia.calcular(hora_ini, hora_fim, cfg.get("limite_dia", 30))
    limite_dia = cadencia["limite_dia"]
    intervalo_seg = cadencia["intervalo_seg"]
    ultimo_envio = None
    optout = bool(cfg.get("optout", True))
    optout_txt = "\n\nResponda SAIR para não receber mais mensagens."

    def _escolher():
        nonlocal prov_idx
        agora = time.time()
        for _ in range(len(providers)):
            i = prov_idx % len(providers)
            prov_idx += 1
            if ruim_ate.get(i, 0) < agora:
                return i, providers[i]
        return None, None

    _worker_state.update({"rodando": True, "provider": nomes, "ultimo_erro": "",
                          "cadencia": cadencia["resumo"],
                          "intervalo_seg": intervalo_seg})
    _devolver_travados(15)

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

            # trava atômica: se outro robô pegou primeiro, pula
            if not _reivindicar(item["id"]):
                continue

            # Trava por NUMERO, antes de escolher o chip: linha que nao vai ser
            # enviada nao pode gastar a vez de um chip no rodizio.
            con = _conn()
            try:
                if bloqueado(con, item["telefone"]):
                    con.execute(
                        "UPDATE fila SET status='bloqueado', erro=? WHERE id=?",
                        ("Este numero esta desativado pro disparo.", item["id"]))
                    con.commit()
                    continue
                if ja_recebeu(con, item["telefone"], item["id"]):
                    con.execute(
                        "UPDATE fila SET status='duplicado', erro=? WHERE id=?",
                        ("Este numero ja recebeu uma abordagem.", item["id"]))
                    con.commit()
                    continue
            finally:
                con.close()

            pi, provider = _escolher()
            if provider is None:
                _worker_state["proximo_em"] = "chips indisponíveis, tentando de novo"
                _worker_stop.wait(60)
                continue
            nome_chip = getattr(provider, "instance", provider.name)

            msg = item["mensagem"] + (optout_txt if optout else "")
            ok, err = provider.send(item["telefone"], msg)
            if not ok and _eh_falha_conexao(err):
                ruim_ate[pi] = time.time() + 600

            con = _conn()
            try:
                if ok:
                    con.execute(
                        "UPDATE fila SET status='enviado', enviado_em=CURRENT_TIMESTAMP, "
                        "instancia=? WHERE id=?",
                        (nome_chip, item["id"]))
                    registrar_abordado(con, item["telefone"])
                    # msg, e nao item["mensagem"]: o texto gravado tem que ser o
                    # que o provedor recebeu, opt-out incluido. Medir conversao
                    # por um texto diferente do que o lead leu nao mede nada.
                    disparo_abordagens.registrar(con, item, msg, nome_chip)
                    ultimo_envio = datetime.datetime.now()
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

            if ok:
                try:
                    from scrapers import cloud_store
                    cloud_store.set_contato_status(
                        item.get("nome", ""), "", item.get("telefone", ""), "enviado")
                except Exception:
                    pass

            alvo = disparo_cadencia.proximo_envio(intervalo_seg, ultimo_envio)
            _worker_state["proximo_em"] = alvo.strftime("%H:%M:%S")
            _worker_stop.wait(disparo_cadencia.espera_segundos(alvo))
        except Exception as e:
            _worker_state["ultimo_erro"] = str(e)[:200]
            _worker_stop.wait(10)

    _worker_state["rodando"] = False
    _worker_state["proximo_em"] = None


def iniciar(cfg):
    global _worker_thread
    with _worker_lock:
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
        pend = con.execute("SELECT COUNT(*) FROM fila WHERE status IN ('pendente','enviando')").fetchone()[0]
        env = con.execute("SELECT COUNT(*) FROM fila WHERE status='enviado'").fetchone()[0]
        falha = con.execute("SELECT COUNT(*) FROM fila WHERE status='falha'").fetchone()[0]
        hoje = _enviados_hoje(con)
        # Fora da fila de proposito: e o unico numero que sobrevive a limpeza.
        conversas = con.execute(
            "SELECT COUNT(*) FROM abordagens WHERE respondido_em IS NOT NULL").fetchone()[0]
    finally:
        con.close()
    out = dict(_worker_state)
    out.update({"pendentes": pend, "enviados": env, "falhas": falha,
                "enviados_hoje": hoje, "conversas_iniciadas": conversas})
    return out
