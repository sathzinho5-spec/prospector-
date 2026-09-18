# proposito: o ritmo do disparo derivado da janela de horario e do limite do dia
"""
Regra fixa de cadencia. Quem opera nao escolhe mais a pausa entre um envio e
outro: ela SAI da janela e do limite do dia, porque esses dois numeros e que
descrevem a intencao ("30 por dia, das 8 as 20"). Pausa digitada a mao vive
divergindo do limite e o operador so descobre no fim do dia, com a fila parada
ou com o chip queimado.

    intervalo base = tamanho da janela / limite do dia
    08:00-20:00 com limite 30  ->  720min / 30  ->  1 envio a cada ~24 min

Em cima do intervalo base entra variacao aleatoria, para o envio nao virar
relogio. Duas travas fecham o desenho: nunca dois envios no mesmo minuto, e
segundo nunca :00 (segundo redondo e a assinatura mais barata de robo).
"""
import datetime
import random

# Variacao em cima do intervalo base. Simetrica de proposito: a media continua
# sendo o intervalo base, entao o limite do dia segue de pe.
VARIACAO = 0.25

# Piso que garante a trava do minuto. Limite alto numa janela curta pediria
# intervalo de segundos; ai o limite do dia nao e alcancado, e esse e o
# tradeoff certo, porque dois envios no mesmo minuto queimam o chip.
MIN_INTERVALO_SEG = 60.0

PADRAO_HORA_INI = "08:00"
PADRAO_HORA_FIM = "20:00"


def _hora_em_minutos(valor, padrao):
    try:
        partes = str(valor).split(":")
        total = int(partes[0]) * 60 + int(partes[1])
    except (AttributeError, IndexError, TypeError, ValueError):
        return padrao
    return total if 0 <= total <= 24 * 60 else padrao


def janela_minutos(hora_ini=PADRAO_HORA_INI, hora_fim=PADRAO_HORA_FIM):
    """Tamanho da janela, em minutos.

    Janela invertida (fim antes do inicio) nao envia nada: quem barra o envio e
    o _in_window do motor. Aqui ela vira o dia inteiro so para a conta nao
    dividir por zero, e a tela mostra o intervalo teorico.
    """
    dur = _hora_em_minutos(hora_fim, 20 * 60) - _hora_em_minutos(hora_ini, 8 * 60)
    return dur if dur > 0 else 24 * 60


def calcular(hora_ini=PADRAO_HORA_INI, hora_fim=PADRAO_HORA_FIM, limite_dia=30):
    """A cadencia inteira num dicionario. Unica fonte do numero que a tela mostra."""
    minutos = janela_minutos(hora_ini, hora_fim)
    try:
        limite = int(limite_dia)
    except (TypeError, ValueError):
        limite = 30
    limite = max(1, min(500, limite))
    intervalo = max(MIN_INTERVALO_SEG, (minutos * 60.0) / limite)
    em_minutos = int(round(intervalo / 60.0))
    return {
        "hora_ini": str(hora_ini or PADRAO_HORA_INI),
        "hora_fim": str(hora_fim or PADRAO_HORA_FIM),
        "limite_dia": limite,
        "janela_min": minutos,
        "intervalo_seg": round(intervalo, 1),
        "intervalo_min": em_minutos,
        "variacao": VARIACAO,
        "resumo": "1 disparo a cada ~%d min" % em_minutos,
    }


def _minuto(quando):
    return quando.replace(second=0, microsecond=0)


def _quebrar_segundo(quando, sorteio):
    """Segundo :00 e assinatura de robo. Sorteia um segundo do mesmo minuto."""
    if quando.second == 0:
        return quando.replace(second=max(1, min(59, int(sorteio(1, 59)))))
    return quando


def proximo_envio(intervalo_seg, ultimo_envio=None, agora=None, sorteio=random.uniform):
    """Instante do proximo envio, ja com as tres regras aplicadas.

    sorteio e injetavel para o comportamento poder ser exercitado sem depender
    do acaso. Devolve sempre um datetime no futuro, em outro minuto que o do
    ultimo envio, com segundo diferente de zero.
    """
    agora = (agora or datetime.datetime.now()).replace(microsecond=0)
    base = max(MIN_INTERVALO_SEG, float(intervalo_seg or MIN_INTERVALO_SEG))
    espera = sorteio(base * (1.0 - VARIACAO), base * (1.0 + VARIACAO))
    alvo = (agora + datetime.timedelta(seconds=espera)).replace(microsecond=0)
    if ultimo_envio is not None and _minuto(alvo) <= _minuto(ultimo_envio):
        alvo = _minuto(ultimo_envio) + datetime.timedelta(minutes=1)
    if _minuto(alvo) <= _minuto(agora):
        alvo = _minuto(agora) + datetime.timedelta(minutes=1)
    return _quebrar_segundo(alvo, sorteio)


def espera_segundos(alvo, agora=None):
    """Quanto o motor dorme ate o alvo. Nunca negativo, nunca zero."""
    agora = agora or datetime.datetime.now()
    return max(1.0, (alvo - agora).total_seconds())
