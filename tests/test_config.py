# proposito: prova que save_settings nao perde chave sob escrita concorrente
import threading

import config


def test_save_settings_concorrente_nao_perde_chaves(banco_limpo):
    config.save_settings({"disparo_evo_key": "segredo"})

    def gravar(i):
        config.save_settings({"chave_%d" % i: i})

    threads = [threading.Thread(target=gravar, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    atual = config.load_settings()
    assert atual["disparo_evo_key"] == "segredo"
    for i in range(8):
        assert atual["chave_%d" % i] == i
