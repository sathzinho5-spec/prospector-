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


def _hora_no_dia(dia, hora, padrao):
    m = _hora_em_minutos(hora, padrao)
    return dia.replace(hour=m // 60, minute=m % 60, second=0, microsecond=0)


def _abre(dia, hora_ini):
    return _hora_no_dia(dia, hora_ini, 8 * 60)


def _fecha(dia, hora_ini, hora_fim):
    fim = _hora_no_dia(dia, hora_fim, 20 * 60)
    abre = _abre(dia, hora_ini)
    # Janela invertida (fim antes do inicio) vira "ate o fim do dia", pra o
    # planejamento nao devolver lista vazia e o operador achar que sumiu.
    return fim if fim > abre else abre.replace(hour=23, minute=59, second=59)


def planejar(quantidade, hora_ini=PADRAO_HORA_INI, hora_fim=PADRAO_HORA_FIM,
             limite_dia=30, inicio=None, sorteio=random.uniform):
    """O horario de CADA envio da fila, do primeiro ao ultimo.

    Esta funcao e a unica dona do ritmo. Antes ele nascia em dois lugares: a
    fila carimbava um "melhor momento do nicho" na entrada e o motor espacava os
    envios por conta, entao o horario que a tela mostrava nao era o que
    acontecia. Agora o plano e calculado no clique de iniciar, gravado na fila e
    apenas SEGUIDO pelo motor.

    As regras, na ordem em que valem:

    1. O primeiro sai AGORA, se agora estiver dentro da janela. Fora dela, na
       proxima abertura. E o que "comecar quando eu clico" quer dizer.
    2. Os seguintes espacam pelo intervalo base com variacao, nunca caem no
       mesmo minuto do anterior e nunca terminam em segundo redondo.
    3. Passou do fim da janela, ou bateu o limite do dia: o resto vai pra
       abertura do dia seguinte, e a contagem do dia recomeca.
    """
    agora = (inicio or datetime.datetime.now()).replace(microsecond=0)
    cad = calcular(hora_ini, hora_fim, limite_dia)
    base = cad["intervalo_seg"]
    limite = cad["limite_dia"]

    abre_hoje = _abre(agora, hora_ini)
    fecha_hoje = _fecha(agora, hora_ini, hora_fim)
    if agora < abre_hoje:
        cursor = abre_hoje
    elif agora <= fecha_hoje:
        cursor = agora
    else:
        cursor = _abre(agora + datetime.timedelta(days=1), hora_ini)

    saida, anterior, no_dia = [], None, 0
    for i in range(max(0, int(quantidade or 0))):
        if anterior is None:
            alvo = cursor
        else:
            espera = sorteio(base * (1.0 - VARIACAO), base * (1.0 + VARIACAO))
            alvo = (anterior + datetime.timedelta(seconds=espera)).replace(microsecond=0)
            if _minuto(alvo) <= _minuto(anterior):
                alvo = _minuto(anterior) + datetime.timedelta(minutes=1)
        referencia = anterior or alvo
        if no_dia >= limite or alvo > _fecha(referencia, hora_ini, hora_fim):
            alvo = _abre(referencia + datetime.timedelta(days=1), hora_ini)
            no_dia = 0
        alvo = _quebrar_segundo(alvo, sorteio)
        saida.append(alvo)
        anterior = alvo
        no_dia += 1
    return saida


def espera_segundos(alvo, agora=None):
    """Quanto o motor dorme ate o alvo. Nunca negativo, nunca zero."""
    agora = agora or datetime.datetime.now()
    return max(1.0, (alvo - agora).total_seconds())
