# proposito: o que saiu por lead e a conversa iniciada, fora do alcance da limpeza
"""
O registro de conversao do disparo.

Ele NAO mora na fila, e essa e a decisao central deste arquivo: a fila perde as
linhas 'enviado' na primeira limpar_finalizados(), e se o historico morasse la,
a metrica de "qual copy converteu" seria apagada por um clique de faxina. Mesmo
precedente do numeros_abordados, que vive fora da fila desde sempre pelo mesmo
motivo.

Guarda, por envio: telefone, nome, o texto EXATO que saiu (com opt-out quando
houve), se a copy veio da IA ou da mao do operador, quando saiu e quando a
conversa comecou.
"""
from scrapers.disparo_db import _conn, _norm_phone

ORIGENS = ("ia", "manual", "template", "desconhecida")


def _origem_da_copy(item):
    """De onde veio o texto daquela linha da fila.

    Prefere o carimbo gravado no enfileiramento. Sem ele (linha anterior a
    coluna existir), cai na unica evidencia que a fila sempre teve: edicao a
    mao carimbada em editada_em.
    """
    origem = str((item or {}).get("copy_origem") or "").strip().lower()
    if origem in ORIGENS:
        return origem
    return "manual" if (item or {}).get("editada_em") else "desconhecida"


def registrar(con, item, texto_enviado, instancia=""):
    """Grava o envio que acabou de dar certo. Recebe a conexao aberta de fora
    para entrar na MESMA transacao do UPDATE da fila: ou as duas coisas valem,
    ou nenhuma vale, e o contador do dia nunca fica torto."""
    tel = _norm_phone((item or {}).get("telefone"))
    texto = (texto_enviado or "").strip()
    if not tel or not texto:
        return False
    # enviado_em explicito, nunca o DEFAULT: o banco de producao nasceu com
    # DEFAULT CURRENT_TIMESTAMP (UTC) e o CREATE TABLE IF NOT EXISTS nao corrige
    # tabela existente. Pelo DEFAULT, o envio saia gravado 3h adiantado.
    con.execute(
        "INSERT INTO abordagens "
        "  (telefone, nome, mensagem, copy_origem, copy_versao, instancia, origem, enviado_em) "
        "VALUES (?,?,?,?,?,?,?, datetime('now','localtime'))",
        (tel, (item or {}).get("nome", ""), texto, _origem_da_copy(item),
         str((item or {}).get("copy_versao") or ""),
         str(instancia or ""), (item or {}).get("origem", "")),
    )
    return True


def enviadas_hoje(con):
    """Quantas sairam hoje. Le o registro, nao a fila: a fila zera na limpeza e
    o motor passaria a achar que o limite do dia foi reiniciado."""
    row = con.execute(
        "SELECT COUNT(*) FROM abordagens "
        "WHERE date(enviado_em)=date('now','localtime')"
    ).fetchone()
    return row[0] if row else 0


def _alvo(con, abordagem_id=0, telefone=""):
    """A linha que a marcacao atinge: por id, ou a abordagem mais recente do
    numero. Mais recente porque o anti-duplicata ja garante uma por numero, e
    se houver duas, a conversa em curso e a da ultima."""
    if abordagem_id:
        return con.execute("SELECT * FROM abordagens WHERE id=?", (int(abordagem_id),)).fetchone()
    tel = _norm_phone(telefone)
    if not tel:
        return None
    return con.execute(
        "SELECT * FROM abordagens WHERE telefone=? ORDER BY id DESC LIMIT 1", (tel,)
    ).fetchone()


def marcar_respondido(abordagem_id=0, telefone=""):
    """O lead respondeu. Idempotente: chamar de novo NAO move o horario da
    primeira resposta, porque e ele que mede quanto tempo a copy levou para
    puxar conversa. Devolve (ok, linha)."""
    con = _conn()
    try:
        row = _alvo(con, abordagem_id, telefone)
        if not row:
            return False, None
        if not row["respondido_em"]:
            con.execute(
                "UPDATE abordagens SET respondido_em=datetime('now','localtime') WHERE id=?",
                (row["id"],))
            con.commit()
            row = con.execute("SELECT * FROM abordagens WHERE id=?", (row["id"],)).fetchone()
        return True, dict(row)
    finally:
        con.close()


def desmarcar_respondido(abordagem_id=0, telefone=""):
    """Operador errou a linha. Devolve (ok, linha)."""
    con = _conn()
    try:
        row = _alvo(con, abordagem_id, telefone)
        if not row:
            return False, None
        con.execute("UPDATE abordagens SET respondido_em=NULL WHERE id=?", (row["id"],))
        con.commit()
        row = con.execute("SELECT * FROM abordagens WHERE id=?", (row["id"],)).fetchone()
        return True, dict(row)
    finally:
        con.close()


def listar(limite=200, apenas_respondidas=False):
    con = _conn()
    try:
        sql = "SELECT * FROM abordagens"
        if apenas_respondidas:
            sql += " WHERE respondido_em IS NOT NULL"
        sql += " ORDER BY id DESC LIMIT ?"
        return [dict(r) for r in con.execute(sql, (int(limite),)).fetchall()]
    finally:
        con.close()


def mapa_por_telefone():
    """{telefone: ultima abordagem}. E a forma que a lista de leads consome."""
    saida = {}
    for row in listar(limite=2000):
        saida.setdefault(row["telefone"], row)
    return saida


def conversas_iniciadas():
    con = _conn()
    try:
        row = con.execute(
            "SELECT COUNT(*) FROM abordagens WHERE respondido_em IS NOT NULL").fetchone()
        return row[0] if row else 0
    finally:
        con.close()


def _taxa(enviadas, respondidas):
    return round(100.0 * respondidas / enviadas, 1) if enviadas else 0.0


def _agrupar(colunas):
    """enviadas, respondidas e taxa agrupadas pelas colunas pedidas."""
    campos = ", ".join(colunas)
    con = _conn()
    try:
        rows = con.execute(
            "SELECT " + campos + ", "
            "       COUNT(*) AS enviadas, "
            "       SUM(CASE WHEN respondido_em IS NOT NULL THEN 1 ELSE 0 END) AS respondidas "
            "  FROM abordagens GROUP BY " +
            ", ".join(str(i + 1) for i in range(len(colunas))) +
            " ORDER BY enviadas DESC").fetchall()
    finally:
        con.close()
    saida = []
    for r in rows:
        d = dict(r)
        d["enviadas"] = d.get("enviadas") or 0
        d["respondidas"] = d.get("respondidas") or 0
        d["taxa"] = _taxa(d["enviadas"], d["respondidas"])
        saida.append(d)
    return saida


_ORIGEM = "COALESCE(copy_origem,'desconhecida') AS copy_origem"
_VERSAO = "COALESCE(NULLIF(copy_versao,''),'sem_versao') AS copy_versao"


def resumo_por_copy():
    """Qual copy converteu: enviadas, respondidas e taxa, por origem do texto."""
    return _agrupar([_ORIGEM])


def resumo_por_versao():
    """A mesma conta, por VERSAO do playbook que escreveu o texto.

    E este numero, e nao o de cima, que treina a copywriter-expert: 'ia' diz
    que a maquina escreveu, a versao diz QUAL conhecimento escreveu. Sem ele,
    trocar o playbook seria mudar no escuro e comparar com nada.

    Cruza com a origem de proposito: copy editada a mao pelo operador carrega a
    versao do texto que ele recebeu pra editar, e misturar as duas faria a
    versao levar credito pela reescrita de outra pessoa.
    """
    return _agrupar([_VERSAO, _ORIGEM])
