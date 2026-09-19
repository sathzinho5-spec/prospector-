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


def _cabem(partida, fecha, base):
    """Quantos envios cabem de partida ate fecha, na grade da cadencia.

    O envio k mira partida + k*base e pode escorregar ate VARIACAO*base pra
    frente. Ele so entra no dia se couber antes do fechamento ate no pior
    sorteio: e isso que impede a variacao de empurrar alguem pro dia seguinte.
    """
    folga = (fecha - partida).total_seconds()
    if folga < 0:
        return 0
    return 1 + max(0, int((folga - VARIACAO * base) // base))


def planejar(quantidade, hora_ini=PADRAO_HORA_INI, hora_fim=PADRAO_HORA_FIM,
             limite_dia=30, inicio=None, sorteio=random.uniform, enviados_hoje=0):
    """O horario de CADA envio da fila, do primeiro ao ultimo.

    Esta funcao e a unica dona do ritmo. O plano e calculado no clique de
    iniciar (e na volta do motor depois de um reinicio), gravado na fila e
    apenas SEGUIDO pelo motor.

    As regras, na ordem em que valem:

    1. Janela aberta: o primeiro sai AGORA. Antes da abertura: sai alguns
       minutos depois dela, nunca no minuto exato, porque "08:00" cravado em
       todo dia e assinatura de robo. Depois do fechamento, ou com o limite do
       dia ja batido: tudo vai pra abertura seguinte.
    2. Cada envio seguinte mira um ponto FIXO da grade (partida + k * base) e
       varia em torno dele. A variacao nao se soma de um envio pro outro:
       somada, ela empurrava o ultimo lead pro dia seguinte em 1 de cada 10
       planos, mesmo quando a carteira cabia inteira na janela.
    3. So entra no dia quem cabe antes do fechamento ate no pior sorteio, e
       so ate o limite do dia, descontado o que ja saiu hoje. O resto vai pra
       abertura do dia seguinte, com a contagem zerada.
    4. Nunca dois envios no mesmo minuto, nunca segundo redondo.
    """
    agora = (inicio or datetime.datetime.now()).replace(microsecond=0)
    cad = calcular(hora_ini, hora_fim, limite_dia)
    base = cad["intervalo_seg"]
    limite = cad["limite_dia"]
    restantes = max(0, int(quantidade or 0))
    ja_no_dia = max(0, int(enviados_hoje or 0))

    abre_hoje = _abre(agora, hora_ini)
    # O primeiro minuto apos a abertura conta como "antes dela": sobra do dia
    # anterior que acorda o worker em 08:00:0x nao pode sair no minuto exato.
    limiar = abre_hoje + datetime.timedelta(seconds=60)
    if agora < limiar and ja_no_dia < limite:
        partida, na_abertura = abre_hoje, True
    elif limiar <= agora <= _fecha(agora, hora_ini, hora_fim) and ja_no_dia < limite:
        partida, na_abertura = agora, False
    else:
        partida, na_abertura = _abre(agora + datetime.timedelta(days=1), hora_ini), True
        ja_no_dia = 0

    saida = []
    while restantes > 0:
        fecha = _fecha(partida, hora_ini, hora_fim)
        vagas = min(restantes, limite - ja_no_dia, _cabem(partida, fecha, base))
        anterior = None
        for k in range(max(1, vagas)):
            if k == 0:
                folga = sorteio(60.0, max(60.0, VARIACAO * base)) if na_abertura else 0.0
                alvo = partida + datetime.timedelta(seconds=folga)
            else:
                desvio = sorteio(-VARIACAO * base, VARIACAO * base)
                alvo = partida + datetime.timedelta(seconds=k * base + desvio)
            alvo = alvo.replace(microsecond=0)
            if anterior is not None and _minuto(alvo) <= _minuto(anterior):
                alvo = _minuto(anterior) + datetime.timedelta(minutes=1)
            alvo = _quebrar_segundo(alvo, sorteio)
            # Trava de seguranca: o empurrao de minuto acima pode, em janela
            # minuscula, passar do fechamento. O primeiro do dia sempre entra,
            # senao um dia sem vaga nenhuma viraria laco infinito.
            if k > 0 and alvo > fecha:
                break
            saida.append(alvo)
            anterior = alvo
            restantes -= 1
        partida = _abre(partida + datetime.timedelta(days=1), hora_ini)
        na_abertura = True
        ja_no_dia = 0
    return saida


def espera_segundos(alvo, agora=None):
    """Quanto o motor dorme ate o alvo. Nunca negativo, nunca zero."""
    agora = agora or datetime.datetime.now()
    return max(1.0, (alvo - agora).total_seconds())
