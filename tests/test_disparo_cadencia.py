# proposito: prova o plano de horarios do disparo: grade da janela, mesmo dia e limite
import datetime
import random

from scrapers import disparo_cadencia as cad

DIA = datetime.datetime(2026, 9, 19)


def _em(hora, minuto=0, segundo=0, dias=0):
    return DIA + datetime.timedelta(days=dias, hours=hora, minutes=minuto, seconds=segundo)


def _plano(qtd, ini="08:00", fim="14:00", limite=30, inicio=None, semente=1, ja=0):
    sorteio = random.Random(semente).uniform
    return cad.planejar(qtd, ini, fim, limite, inicio=inicio, sorteio=sorteio, enviados_hoje=ja)


def _conferir_forma(plano):
    for anterior, atual in zip(plano, plano[1:]):
        assert atual > anterior
        assert atual.replace(second=0) > anterior.replace(second=0), "dois no mesmo minuto"
    for quando in plano:
        assert quando.second != 0, "segundo redondo"


def test_trinta_na_janela_da_manha_cabem_todos_no_mesmo_dia_em_qualquer_sorteio():
    for semente in range(500):
        plano = _plano(30, inicio=_em(1, 5), semente=semente)
        assert len(plano) == 30
        assert all(q.date() == DIA.date() for q in plano), semente
        assert plano[0] >= _em(8, 1)
        assert plano[-1] <= _em(14)
        _conferir_forma(plano)


def test_trinta_na_janela_longa_tambem_cabem_no_mesmo_dia():
    # Era o defeito: a variacao somada envio a envio empurrava o ultimo pro dia
    # seguinte em cerca de 1 a cada 10 planos da janela 08:00-22:00.
    for semente in range(500):
        plano = _plano(30, fim="22:00", inicio=_em(1, 5), semente=semente)
        assert all(q.date() == DIA.date() for q in plano), semente
        assert plano[-1] <= _em(22)


def test_primeiro_da_manha_nunca_cai_no_minuto_da_abertura():
    for semente in range(300):
        plano = _plano(3, inicio=_em(1, 5), semente=semente)
        assert _em(8, 1) <= plano[0] <= _em(8, 4), plano[0]


def test_o_ritmo_ocupa_a_janela_sem_estourar():
    plano = _plano(30, inicio=_em(1, 5), semente=7)
    assert plano[-1] >= _em(13, 30)
    lacunas = [(b - a).total_seconds() / 60 for a, b in zip(plano, plano[1:])]
    assert 10 <= sum(lacunas) / len(lacunas) <= 14


def test_janela_aberta_no_clique_o_primeiro_sai_agora():
    agora = _em(10, 0, 17)
    plano = _plano(5, inicio=agora)
    assert plano[0] == agora


def test_clique_no_meio_da_janela_manda_pro_dia_seguinte_so_o_que_nao_cabe():
    plano = _plano(30, inicio=_em(10, 0, 17))
    hoje = [q for q in plano if q.date() == DIA.date()]
    amanha = [q for q in plano if q.date() == (DIA + datetime.timedelta(days=1)).date()]
    # 4 horas de janela / 12 min: 20 cabem hoje ate no pior sorteio.
    assert len(hoje) == 20
    assert len(amanha) == 10
    assert amanha[0] >= _em(8, 1, dias=1)
    _conferir_forma(plano)


def test_depois_do_fechamento_vai_tudo_pra_abertura_seguinte():
    plano = _plano(5, inicio=_em(15))
    assert all(q.date() == (DIA + datetime.timedelta(days=1)).date() for q in plano)
    assert plano[0] >= _em(8, 1, dias=1)


def test_limite_do_dia_desconta_o_que_ja_saiu_hoje():
    plano = _plano(10, inicio=_em(9), ja=25)
    hoje = [q for q in plano if q.date() == DIA.date()]
    assert len(hoje) == 5
    assert len(plano) == 10


def test_limite_ja_batido_manda_tudo_pro_dia_seguinte():
    plano = _plano(4, inicio=_em(9), ja=30)
    assert all(q.date() == (DIA + datetime.timedelta(days=1)).date() for q in plano)


def test_limite_divide_a_carteira_em_dias():
    plano = _plano(45, inicio=_em(1, 5))
    primeiro_dia = [q for q in plano if q.date() == DIA.date()]
    segundo_dia = [q for q in plano if q.date() == (DIA + datetime.timedelta(days=1)).date()]
    assert len(primeiro_dia) == 30
    assert len(segundo_dia) == 15
    _conferir_forma(plano)


def test_fila_vazia_nao_planeja_nada():
    assert _plano(0, inicio=_em(9)) == []


def test_minutos_quebrados_e_distintos_na_manha():
    plano = _plano(30, inicio=_em(1, 5), semente=3)
    minutos = [q.strftime("%H:%M") for q in plano]
    assert len(set(minutos)) == 30
    assert "08:00" not in minutos


def test_limite_batido_antes_da_abertura_manda_tudo_pro_dia_seguinte():
    plano = _plano(5, inicio=_em(7), ja=30)
    assert all(q.date() == (DIA + datetime.timedelta(days=1)).date() for q in plano)
    assert plano[0] >= _em(8, 1, dias=1)


def test_sobra_do_dia_anterior_no_primeiro_minuto_da_abertura_nao_sai_na_abertura():
    # Worker acorda em 08:00:0x com fila de ontem: o primeiro minuto apos a
    # abertura conta como "antes dela", senao um lead sai no minuto exato.
    plano = _plano(3, inicio=_em(8, 0, 30))
    assert plano[0] >= _em(8, 1)
