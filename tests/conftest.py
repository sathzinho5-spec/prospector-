# proposito: prepara os testes: raiz do projeto no caminho, dados em pasta temporaria e banco limpo
import os
import sys
import tempfile

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

# Antes de qualquer import do projeto: config.py le PROSPECTOR_DADOS na hora do
# import. Sem isto o teste escreveria no settings.json e no disparo.db de verdade.
os.environ["PROSPECTOR_DADOS"] = tempfile.mkdtemp(prefix="prospector-testes-")


@pytest.fixture
def banco_limpo(monkeypatch):
    """Banco do disparo vazio, settings apagado e a nuvem desligada.

    A nuvem sai de proposito: o motor chama cloud_store depois de cada envio, e
    teste nenhum pode depender de rede nem escrever no Supabase de verdade.
    """
    import config
    from scrapers import cloud_store, disparo
    from scrapers.disparo_db import _conn

    monkeypatch.setattr(cloud_store, "set_contato_status", lambda *a, **k: False)
    con = _conn()
    try:
        for tabela in ("fila", "abordagens", "numeros_abordados", "copys"):
            con.execute("DELETE FROM %s" % tabela)
        con.commit()
    finally:
        con.close()
    if os.path.exists(config.SETTINGS_FILE):
        os.remove(config.SETTINGS_FILE)
    yield
    disparo.pausar()
    if disparo._worker_thread is not None:
        disparo._worker_thread.join(timeout=10)
