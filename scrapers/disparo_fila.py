# proposito: a fila do disparo em SQLite, o bloqueio de telefone e o anti-duplicata
# Reexportado de proposito: o esquema e a conexao mudaram de arquivo quando o
# disparo ganhou copy de lead e registro de abordagem, e estes quatro nomes
# seguem alcancaveis como disparo_fila._conn, como sempre foram.
import datetime

from scrapers import disparo_cadencia
from scrapers.disparo_abordagens import enviadas_hoje as _enviados_hoje  # noqa: F401
from scrapers.disparo_db import DB_PATH, _SCHEMA, _conn, _norm_phone  # noqa: F401


def enfileirar(itens, origem=""):
    """itens: [{nome, telefone, mensagem, copy_origem, categoria}]. Retorna qtd enfileirada.
    Pula duplicata exata (mesmo telefone + mesma mensagem já pendente/enviando).
    NAO define horario: quem planeja e disparo_cadencia.planejar(), chamado no
    clique de iniciar. Aqui a linha nasce com o agendado_para padrao (agora) e o
    plano reescreve logo em seguida. Um lugar so decide o ritmo."""
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
        for it in itens:
            tel = _norm_phone(it.get("telefone"))
            msg = (it.get("mensagem") or "").strip()
            if not tel or not msg:
                continue
            if tel in existentes:
                continue
            con.execute(
                "INSERT INTO fila (nome, telefone, mensagem, origem, copy_origem, "
                "                  copy_versao) "
                "VALUES (?,?,?,?,?,?)",
                (it.get("nome", ""), tel, msg, origem,
                 str(it.get("copy_origem") or "ia").strip().lower(),
                 str(it.get("copy_versao") or "").strip()),
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
        # quem ja foi abordado, a copy do lead e o registro do que saiu nao
        # moram na fila, entao limpar nao reabre o disparo repetido nem apaga
        # a medida de qual copy converteu.
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
            "UPDATE fila SET status='enviando', agendado_para=datetime('now','localtime') "
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
            "AND datetime(agendado_para) < datetime('now','localtime', ?)",
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


def replanejar(horarios):
    """Reescreve o agendado_para das linhas PENDENTES, na ordem da fila.

    Roda no clique de iniciar, com os horarios que disparo_cadencia.planejar()
    acabou de calcular. Reescrever e de proposito: o fundador pediu que a conta
    comece no momento do clique, entao plano velho de uma sessao anterior nao
    pode sobreviver a um clique novo.
    """
    con = _conn()
    try:
        ids = [r[0] for r in con.execute(
            "SELECT id FROM fila WHERE status='pendente' ORDER BY id ASC").fetchall()]
        n = 0
        for item_id, quando in zip(ids, horarios or []):
            con.execute("UPDATE fila SET agendado_para=? WHERE id=?",
                        (quando.strftime("%Y-%m-%d %H:%M:%S"), item_id))
            n += 1
        con.commit()
        return n
    finally:
        con.close()


def pendentes():
    """Quantas linhas esperam a vez. E o tamanho do plano a calcular."""
    con = _conn()
    try:
        return con.execute(
            "SELECT COUNT(*) FROM fila WHERE status='pendente'").fetchone()[0]
    finally:
        con.close()


def planejar_fila(hora_ini, hora_fim, limite_dia, agora=None):
    """Planeja as linhas pendentes a partir de agora, grava e devolve o plano.

    Junta as duas coisas que so o banco sabe e que o planejador precisa:
    quantas sairam hoje, porque o limite e do dia e nao do clique, e quando
    saiu a ultima. Depois de um reinicio o motor volta e replaneja; sem o piso
    abaixo, o primeiro envio da volta podia colar no ultimo que saiu antes.
    """
    agora = (agora or datetime.datetime.now()).replace(microsecond=0)
    cad = disparo_cadencia.calcular(hora_ini, hora_fim, limite_dia)
    con = _conn()
    try:
        ja_hoje = _enviados_hoje(con)
        ultimo = con.execute("SELECT MAX(enviado_em) FROM abordagens").fetchone()[0]
    finally:
        con.close()
    inicio = agora
    if ultimo:
        try:
            quando = datetime.datetime.strptime(str(ultimo)[:19], "%Y-%m-%d %H:%M:%S")
            piso = quando + datetime.timedelta(
                seconds=cad["intervalo_seg"] * (1.0 - disparo_cadencia.VARIACAO))
            inicio = max(agora, piso)
        except ValueError:
            pass
    horarios = disparo_cadencia.planejar(pendentes(), hora_ini, hora_fim, limite_dia,
                                         inicio=inicio, enviados_hoje=ja_hoje)
    replanejar(horarios)
    return horarios


def remover_pendentes(telefones):
    """Tira da fila as linhas PENDENTES desses numeros. Retorna quantas sairam.

    E o que substitui a lista de bloqueio: desligar um lead deixou de escrever
    numa lista paralela e passou a fazer a coisa obvia, tirar ele da fila. A
    decisao passa a morar num lugar so, e quem esta na fila e, por definicao,
    quem foi liberado. So mexe em 'pendente': linha 'enviando' ja foi
    reivindicada por um processo, e ja enviada e historico.
    """
    alvos = [t for t in (_norm_phone(x) for x in (telefones or [])) if t]
    if not alvos:
        return 0
    con = _conn()
    try:
        marcas = ",".join("?" for _ in alvos)
        cur = con.execute(
            "DELETE FROM fila WHERE status='pendente' AND telefone IN (%s)" % marcas,
            alvos)
        con.commit()
        return cur.rowcount or 0
    finally:
        con.close()


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
    dizendo que aquele texto e dela. O carimbo de origem anda junto: e ele que
    responde, la na frente, qual copy converteu."""
    con = _conn()
    try:
        if manual:
            con.execute("UPDATE fila SET mensagem=?, editada_em=datetime('now','localtime'), "
                        "copy_origem='manual' WHERE id=?", (mensagem, item_id))
        else:
            con.execute("UPDATE fila SET mensagem=?, editada_em=NULL, "
                        "copy_origem='ia' WHERE id=?", (mensagem, item_id))
        con.commit()
        return True
    finally:
        con.close()
