# proposito: prova que o registro de envio grava a hora local mesmo em banco antigo com padrao em UTC
import datetime

import pytest

from scrapers import disparo_db
from scrapers.disparo_abordagens import registrar
from scrapers.disparo_db import _conn


def _banco_com_padrao_utc(con):
    """Recria abordagens como ela nasceu em producao, antes do e7ef021: DEFAULT
    CURRENT_TIMESTAMP, que e UTC. O CREATE TABLE IF NOT EXISTS nunca corrige isso."""
    con.execute("DROP TABLE abordagens")
    con.execute(
        "CREATE TABLE abordagens (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "telefone TEXT NOT NULL, nome TEXT, mensagem TEXT NOT NULL, copy_origem TEXT, "
        "copy_versao TEXT, instancia TEXT, origem TEXT, "
        "enviado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP, respondido_em TIMESTAMP)")
    con.commit()


@pytest.fixture(autouse=True)
def _devolve_esquema_atual():
    """Os testes daqui trocam a tabela pela versao antiga; o proximo teste do
    pacote precisa receber a atual, recriada pelo _SCHEMA no _conn()."""
    yield
    con = _conn()
    try:
        con.execute("DROP TABLE abordagens")
        con.commit()
    finally:
        con.close()


def test_registrar_grava_hora_local_em_banco_antigo(banco_limpo):
    con = _conn()
    try:
        _banco_com_padrao_utc(con)
        antes = datetime.datetime.now().replace(microsecond=0)
        assert registrar(con, {"telefone": "21999990000", "nome": "X"}, "Oi")
        con.commit()
        gravado = con.execute("SELECT enviado_em FROM abordagens").fetchone()[0]
    finally:
        con.close()
    gravado = datetime.datetime.strptime(gravado, "%Y-%m-%d %H:%M:%S")
    assert abs((gravado - antes).total_seconds()) < 60


def test_migracao_corrige_envio_gravado_em_utc(banco_limpo):
    con = _conn()
    try:
        _banco_com_padrao_utc(con)
        con.execute("INSERT INTO fila (nome, telefone, mensagem, status, enviado_em) "
                    "VALUES ('A', '5521999990001', 'm', 'enviado', '2026-09-19 08:01:22')")
        con.execute("INSERT INTO fila (nome, telefone, mensagem, status, enviado_em) "
                    "VALUES ('B', '5521999990002', 'm', 'enviado', '2026-09-19 09:10:05')")
        # A: gravado em UTC (3h adiantado). B: ja certo, nao pode ser tocado.
        con.execute("INSERT INTO abordagens (telefone, mensagem, enviado_em) "
                    "VALUES ('5521999990001', 'm', '2026-09-19 11:01:22')")
        con.execute("INSERT INTO abordagens (telefone, mensagem, enviado_em) "
                    "VALUES ('5521999990002', 'm', '2026-09-19 09:10:05')")
        con.commit()
        disparo_db._corrigir_fuso_abordagens(con)
        disparo_db._corrigir_fuso_abordagens(con)  # idempotente
        linhas = dict(con.execute("SELECT telefone, enviado_em FROM abordagens"))
    finally:
        con.close()
    assert linhas == {"5521999990001": "2026-09-19 08:01:22",
                      "5521999990002": "2026-09-19 09:10:05"}


def test_migracao_sem_fila_nao_mexe(banco_limpo):
    con = _conn()
    try:
        con.execute("INSERT INTO abordagens (telefone, mensagem, enviado_em) "
                    "VALUES ('5521999990003', 'm', '2026-09-19 11:01:22')")
        con.commit()
        disparo_db._corrigir_fuso_abordagens(con)
        valor = con.execute("SELECT enviado_em FROM abordagens").fetchone()[0]
    finally:
        con.close()
    assert valor == "2026-09-19 11:01:22"
