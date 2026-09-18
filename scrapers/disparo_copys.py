# proposito: a copy de abordagem de cada lead, guardada antes de ele entrar na fila
"""
Onde a copy de um lead espera.

Regra do fundador: lead sem copy pronta nao esta apto pro disparo. Isso exige um
lugar onde a copy exista ANTES da fila, senao "copy pronta" e "na fila" seriam o
mesmo estado e nao haveria como escrever a copy de 30 leads e so depois decidir
quem entra.

Mora fora da fila pelo mesmo motivo do numeros_abordados e do abordagens:
limpar_finalizados() apaga linha de fila, e um lead que ja tem copy escrita nao
pode voltar a aparecer como 'sem copy' porque alguem clicou em limpar.

A fila continua sendo a ordem de servico: ao enfileirar, o texto e copiado pra
linha da fila e e aquele texto que sai. Perguntas diferentes, respostas
diferentes: aqui e "que copy este lead tem", la e "o que vai sair agora".
"""
from scrapers.disparo_db import _conn, _norm_phone


def salvar(telefone, mensagem, nome="", copy_origem="ia", manual=False,
           copy_versao=""):
    """Grava ou troca a copy de um lead. manual=True carimba a edicao a mao.

    copy_versao e a versao do playbook que escreveu o texto. Viaja junto desde
    aqui porque e o unico ponto onde ela ainda e conhecida: da fila pra frente
    so existe o texto pronto.
    """
    tel = _norm_phone(telefone)
    msg = (mensagem or "").strip()
    if not tel or not msg:
        return False
    origem = "manual" if manual else (str(copy_origem or "ia").strip().lower() or "ia")
    versao = str(copy_versao or "").strip()
    con = _conn()
    try:
        con.execute(
            "INSERT INTO copys (telefone, nome, mensagem, copy_origem, copy_versao, editada_em) "
            "VALUES (?,?,?,?,?, CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE NULL END) "
            "ON CONFLICT(telefone) DO UPDATE SET "
            "  nome=COALESCE(NULLIF(excluded.nome,''), copys.nome), "
            "  mensagem=excluded.mensagem, "
            "  copy_origem=excluded.copy_origem, "
            "  copy_versao=excluded.copy_versao, "
            "  editada_em=excluded.editada_em",
            (tel, nome or "", msg, origem, versao, 1 if manual else 0),
        )
        con.commit()
        return True
    finally:
        con.close()


def obter(telefone):
    tel = _norm_phone(telefone)
    if not tel:
        return None
    con = _conn()
    try:
        row = con.execute("SELECT * FROM copys WHERE telefone=?", (tel,)).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def mapa():
    """{telefone: copy}. Uma consulta so, porque a lista de leads cruza centenas."""
    con = _conn()
    try:
        return {r["telefone"]: dict(r) for r in con.execute("SELECT * FROM copys").fetchall()}
    finally:
        con.close()


def remover(telefone):
    tel = _norm_phone(telefone)
    if not tel:
        return False
    con = _conn()
    try:
        con.execute("DELETE FROM copys WHERE telefone=?", (tel,))
        con.commit()
        return True
    finally:
        con.close()
