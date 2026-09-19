# proposito: prova o plano gravado na fila: desconta o que saiu hoje, respeita o ultimo envio e refaz atraso
import datetime

from scrapers import disparo
from scrapers.disparo_db import _conn


def _enfileirar(n):
    disparo.enfileirar([{"nome": "L%d" % i, "telefone": "2199999%04d" % i,
                         "mensagem": "Oi %d" % i} for i in range(n)], origem="teste")


def _registrar_envios(qtd, quando):
    con = _conn()
    try:
        for i in range(qtd):
            con.execute("INSERT INTO abordagens (telefone, nome, mensagem, enviado_em) "
                        "VALUES (?,?,?,?)", ("2188888%04d" % i, "X", "m",
                                              quando.strftime("%Y-%m-%d %H:%M:%S")))
        con.commit()
    finally:
        con.close()


def _agendados():
    con = _conn()
    try:
        return [r[0] for r in con.execute(
            "SELECT agendado_para FROM fila WHERE status='pendente' ORDER BY id")]
    finally:
        con.close()


def test_planejar_fila_grava_o_plano_nas_pendentes(banco_limpo):
    _enfileirar(3)
    agora = datetime.datetime.now().replace(hour=1, minute=5, second=0, microsecond=0)
    horarios = disparo.planejar_fila("08:00", "14:00", 30, agora=agora)
    assert len(horarios) == 3
    assert _agendados() == [h.strftime("%Y-%m-%d %H:%M:%S") for h in horarios]
    assert horarios[0] >= agora.replace(hour=8, minute=1)


def test_primeiro_envio_espera_o_intervalo_minimo_desde_o_ultimo(banco_limpo):
    _enfileirar(2)
    agora = datetime.datetime.now().replace(microsecond=0)
    _registrar_envios(1, agora - datetime.timedelta(minutes=2))
    horarios = disparo.planejar_fila("00:00", "23:59", 30, agora=agora)
    # base = 1439 min / 30 = 47,97 min; piso = base * (1 - 0.25) = 35,98 min depois do ultimo.
    ultimo = agora - datetime.timedelta(minutes=2)
    assert horarios[0] >= ultimo + datetime.timedelta(minutes=35)


def test_limite_batido_hoje_manda_as_pendentes_pra_amanha(banco_limpo):
    _enfileirar(4)
    agora = datetime.datetime.now().replace(microsecond=0)
    # Meia-noite e cinco segundos, e nao "3h atras": rodando de madrugada, 3h
    # atras e ontem e o limite de hoje nao estaria batido.
    _registrar_envios(30, agora.replace(hour=0, minute=0, second=5))
    horarios = disparo.planejar_fila("00:00", "23:59", 30, agora=agora)
    assert all(h.date() > agora.date() for h in horarios)


def test_atrasada_so_depois_da_tolerancia():
    agora = datetime.datetime(2026, 9, 19, 10, 0, 0)
    assert disparo._atrasada("2026-09-19 09:54:59", agora) is True
    assert disparo._atrasada("2026-09-19 09:56:00", agora) is False
    assert disparo._atrasada("2026-09-19 10:30:00", agora) is False
    assert disparo._atrasada(None, agora) is False
    assert disparo._atrasada("lixo", agora) is False


def test_falta_piso_pura():
    agora = datetime.datetime(2026, 9, 19, 10, 0, 0)
    assert disparo._falta_piso(None, agora, 60.0) == 0.0
    assert disparo._falta_piso(agora - datetime.timedelta(seconds=10), agora, 60.0) == 50.0
    assert disparo._falta_piso(agora - datetime.timedelta(seconds=70), agora, 60.0) == 0.0


def test_replanejar_pula_linha_em_espera_de_retentativa(banco_limpo):
    _enfileirar(3)
    con = _conn()
    try:
        primeiro = con.execute("SELECT id FROM fila ORDER BY id ASC").fetchone()[0]
        agendado = (datetime.datetime.now()
                    + datetime.timedelta(minutes=10)).replace(microsecond=0)
        con.execute("UPDATE fila SET tentativas=1, agendado_para=? WHERE id=?",
                    (agendado.strftime("%Y-%m-%d %H:%M:%S"), primeiro))
        con.commit()
    finally:
        con.close()
    agora = datetime.datetime.now().replace(hour=1, minute=5, second=0, microsecond=0)
    horarios = disparo.planejar_fila("08:00", "14:00", 30, agora=agora)
    assert len(horarios) == 2
    con = _conn()
    try:
        row = con.execute("SELECT agendado_para FROM fila WHERE id=?", (primeiro,)).fetchone()
    finally:
        con.close()
    assert row[0] == agendado.strftime("%Y-%m-%d %H:%M:%S")
