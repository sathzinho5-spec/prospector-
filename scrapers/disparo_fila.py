# proposito: a fila do disparo em SQLite, o bloqueio de telefone e o anti-duplicata
# Reexportado de proposito: o esquema e a conexao mudaram de arquivo quando o
# disparo ganhou copy de lead e registro de abordagem, e estes quatro nomes
# seguem alcancaveis como disparo_fila._conn, como sempre foram.
from scrapers.disparo_abordagens import enviadas_hoje as _enviados_hoje  # noqa: F401
from scrapers.disparo_db import DB_PATH, _SCHEMA, _conn, _norm_phone  # noqa: F401


def enfileirar(itens, origem=""):
    """itens: [{nome, telefone, mensagem, copy_origem, categoria}]. Retorna qtd enfileirada.
    Pula duplicata exata (mesmo telefone + mesma mensagem já pendente/enviando).
    Cada item ganha agendado_para = melhor momento do nicho (analysis/timing):
    a fila anda sozinha em ordem de horario, sem travar ninguem."""
    import config
    from analysis import timing

    settings = config.load_settings()
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
            agendado, motivo = timing.proximo_envio_em(it.get("categoria", ""), settings)
            con.execute(
                "INSERT INTO fila (nome, telefone, mensagem, origem, copy_origem, agendado_para, timing_motivo) "
                "VALUES (?,?,?,?,?,?,?)",
                (it.get("nome", ""), tel, msg, origem,
                 str(it.get("copy_origem") or "ia").strip().lower(),
                 agendado, motivo),
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


def telefones_bloqueados():
    con = _conn()
    try:
        return set(r[0] for r in con.execute(
            "SELECT telefone FROM numeros_bloqueados").fetchall())
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
            con.execute("UPDATE fila SET mensagem=?, editada_em=CURRENT_TIMESTAMP, "
                        "copy_origem='manual' WHERE id=?", (mensagem, item_id))
        else:
            con.execute("UPDATE fila SET mensagem=?, editada_em=NULL, "
                        "copy_origem='ia' WHERE id=?", (mensagem, item_id))
        con.commit()
        return True
    finally:
        con.close()
