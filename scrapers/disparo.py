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
                                   atualizar_mensagem, enfileirar, ja_recebeu,
                                   limpar_finalizados, listar, pendentes,
                                   registrar_abordado, remover_pendentes,
                                   replanejar, telefones_na_fila)
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
def _gravar_sucesso(con, item, msg, provider):
    """O que acontece com a linha depois que o provedor aceitou a mensagem.

    O corte que este arquivo nao tinha: **ensaio nao consome lead.** O provedor
    Simulado devolve sucesso sem mandar nada, e ate aqui o sucesso dele era
    gravado igual ao de verdade: a linha virava 'enviado', o numero entrava no
    numeros_abordados (que e permanente, de proposito) e uma abordagem falsa
    entrava na metrica de conversao. Resultado: um clique em Iniciar disparo com
    o interruptor desarmado queimava a carteira inteira para o envio real e
    sujava a unica medida de qual copy converteu.

    Agora o ensaio apaga a propria linha. O lead volta a 'copy pronta', volta a
    ser apto e pode ser ensaiado de novo, sem deixar rastro que minta.
    """
    nome_chip = getattr(provider, "instance", provider.name)
    if getattr(provider, "name", "") == "simulado":
        con.execute("DELETE FROM fila WHERE id=?", (item["id"],))
        return False
    con.execute(
        "UPDATE fila SET status='enviado', enviado_em=datetime('now','localtime'), "
        "instancia=? WHERE id=?",
        (nome_chip, item["id"]))
    registrar_abordado(con, item["telefone"])
    # Mesma transacao do UPDATE de proposito: o registro do que saiu e a metrica
    # de conversao, e ele nao pode divergir da fila nem por uma falha no meio.
    disparo_abordagens.registrar(con, item, msg, nome_chip)
    return True


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
        # A conferencia contra a lista de bloqueio saiu com a lista. Quem esta na
        # fila e, por definicao, quem foi liberado: desligar um lead agora tira
        # ele daqui (disparo_fila.remover_pendentes), em vez de deixar a linha
        # parada esperando uma segunda lista dizer que ela nao vale.
        if ja_recebeu(con, item["telefone"], item_id):
            erro = "Este numero ja recebeu uma abordagem."
            con.execute("UPDATE fila SET status='duplicado', erro=? WHERE id=?",
                        (erro, item_id))
            con.commit()
            return False, erro
        msg = item["mensagem"]
        ok, err = provider.send(item["telefone"], msg)
        if ok:
            # O envio avulso nao acrescenta opt-out, entao o texto gravado e
            # exatamente o que o provedor recebeu.
            _gravar_sucesso(con, item, msg, provider)
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

def _proximo_agendado():
    """Quando sai a proxima linha pendente, segundo o plano gravado na fila."""
    con = _conn()
    try:
        row = con.execute(
            "SELECT agendado_para FROM fila WHERE status='pendente' "
            "ORDER BY datetime(agendado_para) ASC, id ASC LIMIT 1").fetchone()
    finally:
        con.close()
    if not row or not row[0]:
        return None
    try:
        return datetime.datetime.strptime(str(row[0])[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


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
                    "AND datetime(agendado_para) <= datetime('now','localtime') "
                    "ORDER BY datetime(agendado_para) ASC, id ASC LIMIT 1").fetchone()
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

            msg = item["mensagem"] + (optout_txt if optout else "")
            ok, err = provider.send(item["telefone"], msg)
            if not ok and _eh_falha_conexao(err):
                ruim_ate[pi] = time.time() + 600

            con = _conn()
            try:
                if ok:
                    # msg, e nao item["mensagem"]: o texto gravado tem que ser o
                    # que o provedor recebeu, opt-out incluido. Medir conversao
                    # por um texto diferente do que o lead leu nao mede nada.
                    _gravar_sucesso(con, item, msg, provider)
                    ultimo_envio = datetime.datetime.now()
                else:
                    tent = item.get("tentativas", 0) + 1
                    status = "falha" if tent >= 3 else "pendente"
                    con.execute(
                        "UPDATE fila SET status=?, tentativas=?, erro=?, "
                        "agendado_para=datetime('now','localtime','+10 minutes') WHERE id=?",
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

            # O motor NAO espaca mais por conta: ele le o horario que o plano
            # gravou na proxima linha e dorme ate la. Enquanto ele calculava o
            # proprio intervalo, o horario que a tela mostrava e o que acontecia
            # eram duas contas diferentes, e so coincidiam por sorte.
            proximo = _proximo_agendado()
            if proximo:
                _worker_state["proximo_em"] = proximo.strftime("%d/%m %H:%M")
                # Teto de 5 min por espera pra um replanejamento feito no meio
                # do caminho valer sem precisar parar e iniciar de novo.
                _worker_stop.wait(min(300.0, disparo_cadencia.espera_segundos(proximo)))
            else:
                _worker_state["proximo_em"] = "fila vazia"
                _worker_stop.wait(15)
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
