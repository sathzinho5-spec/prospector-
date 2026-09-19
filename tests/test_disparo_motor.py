# proposito: prova o ciclo de vida do motor: ligar, desligar, religar depois do reinicio e texto sem opt-out
import datetime
import time

import config
from rotas import disparo_motor
from scrapers import disparo


def _janela_fechada():
    """Uma janela que nao contem o agora, pro motor ligar sem enviar nada."""
    agora = datetime.datetime.now()
    if agora.hour < 20:
        return "22:00", "23:00"
    return "02:00", "03:00"


def _esperar_rodando(segundos=3):
    """A thread marca rodando=True logo que comeca, nao no retorno de iniciar()."""
    limite = time.time() + segundos
    while time.time() < limite:
        if disparo.status()["rodando"]:
            return True
        time.sleep(0.05)
    return False


def _preparar(provider="simulado", janela=None):
    ini, fim = janela or _janela_fechada()
    config.save_settings({"disparo_hora_ini": ini, "disparo_hora_fim": fim,
                          "disparo_limite_dia": 30, "disparo_provider": provider})
    disparo.enfileirar([
        {"nome": "Lead A", "telefone": "21999990001", "mensagem": "Oi A"},
        {"nome": "Lead B", "telefone": "21999990002", "mensagem": "Oi B"},
    ], origem="teste")


def test_ligar_planeja_liga_e_lembra(banco_limpo):
    _preparar()
    r = disparo_motor.ligar("simulado")
    assert r["iniciado"] is True
    assert r["planejados"] == 2
    assert len(r["horarios"]) == 2
    s = config.load_settings()
    assert s["disparo_motor_ligado"] is True
    assert s["disparo_motor_provider"] == "simulado"
    assert _esperar_rodando()


def test_desligar_para_e_esquece(banco_limpo):
    _preparar()
    disparo_motor.ligar("simulado")
    disparo_motor.desligar()
    assert config.load_settings()["disparo_motor_ligado"] is False
    assert disparo.status()["rodando"] is False


def test_retomar_religa_o_motor_que_estava_ligado(banco_limpo):
    _preparar()
    config.save_settings({"disparo_motor_ligado": True, "disparo_motor_provider": "simulado"})
    assert disparo.status()["rodando"] is False
    r = disparo_motor.retomar()
    assert r is not None and r["iniciado"] is True
    assert r["planejados"] == 2
    assert _esperar_rodando()


def test_retomar_nao_liga_o_que_estava_desligado(banco_limpo):
    _preparar()
    assert disparo_motor.retomar() is None
    assert disparo.status()["rodando"] is False


def test_cfg_do_motor_le_janela_e_limite_do_settings(banco_limpo):
    cfg = disparo_motor._cfg_do_motor(
        {"disparo_hora_ini": "08:00", "disparo_hora_fim": "14:00",
         "disparo_limite_dia": 30, "disparo_evo_instance": "vr-2934"}, "evolution")
    assert cfg["provider"] == "evolution"
    assert (cfg["hora_ini"], cfg["hora_fim"], cfg["limite_dia"]) == ("08:00", "14:00", 30)
    assert cfg["evo_instance"] == "vr-2934"
    assert "optout" not in cfg


class _Espiao:
    name = "espiao"
    instance = "espiao"

    def __init__(self):
        self.enviadas = []

    def send(self, phone, message):
        self.enviadas.append((phone, message))
        return True, ""


def test_motor_envia_o_texto_da_copy_sem_a_frase_sair(banco_limpo, monkeypatch):
    espiao = _Espiao()
    monkeypatch.setattr(disparo, "_build_providers", lambda cfg: [espiao])
    _preparar(janela=("00:00", "23:59"))
    disparo_motor.ligar("simulado")
    limite = time.time() + 10
    while not espiao.enviadas and time.time() < limite:
        time.sleep(0.2)
    assert espiao.enviadas, "o motor nao enviou nada em 10s"
    _, mensagem = espiao.enviadas[0]
    assert mensagem in ("Oi A", "Oi B")
    assert "SAIR" not in mensagem


def test_piso_entre_envios_evita_rajada_de_atrasadas(banco_limpo, monkeypatch):
    """Duas linhas nascem vencidas (agendado_para=now, sem passar por planejar_fila).
    Limite 500 numa janela de quase 24h da um piso de ~86s entre envios: a
    segunda nao pode sair 1s depois da primeira so porque ambas ja venceram."""
    espiao = _Espiao()
    monkeypatch.setattr(disparo, "_build_providers", lambda cfg: [espiao])
    config.save_settings({"disparo_hora_ini": "00:00", "disparo_hora_fim": "23:59",
                          "disparo_limite_dia": 500, "disparo_provider": "simulado"})
    disparo.enfileirar([
        {"nome": "Lead A", "telefone": "21999990001", "mensagem": "Oi A"},
        {"nome": "Lead B", "telefone": "21999990002", "mensagem": "Oi B"},
    ], origem="teste")
    cfg = disparo_motor._cfg_do_motor(config.load_settings(), "simulado")
    disparo.iniciar(cfg)
    limite = time.time() + 10
    while not espiao.enviadas and time.time() < limite:
        time.sleep(0.2)
    assert espiao.enviadas, "o motor nao enviou nada em 10s"
    time.sleep(3)
    assert len(espiao.enviadas) == 1


def _mais_30min(hhmm):
    """Desloca um horario HH:MM em 30 minutos, virando o dia se precisar."""
    h, m = (int(p) for p in hhmm.split(":"))
    total = (h * 60 + m + 30) % (24 * 60)
    return "%02d:%02d" % (total // 60, total % 60)


def test_ligar_com_motor_rodando_religa_com_a_config_nova(banco_limpo):
    ini_a, fim_a = _janela_fechada()
    _preparar(janela=(ini_a, fim_a))
    disparo_motor.ligar("simulado")
    assert _esperar_rodando()
    # Janela B: a mesma A deslocada 30min, continua fechada no horario do teste.
    ini_b, fim_b = _mais_30min(ini_a), _mais_30min(fim_a)
    config.save_settings({"disparo_hora_ini": ini_b, "disparo_hora_fim": fim_b,
                          "disparo_limite_dia": 50, "disparo_provider": "simulado"})
    r = disparo_motor.ligar("simulado")
    assert r["iniciado"] is True
    assert _esperar_rodando()
    assert disparo._worker_cfg["hora_fim"] == fim_b
    assert disparo._worker_cfg["limite_dia"] == 50


class _EspiaoFalha:
    name = "espiao"
    instance = "espiao"

    def send(self, phone, message):
        return False, "erro x"


def test_enviar_agora_com_falha_reagenda_para_daqui_a_10_minutos(banco_limpo):
    disparo.enfileirar([{"nome": "Lead A", "telefone": "21999990001", "mensagem": "Oi A"}],
                       origem="teste")
    item_id = disparo.listar(status="pendente")[0]["id"]
    ok, err = disparo.enviar_agora(item_id, _EspiaoFalha())
    assert ok is False and err == "erro x"
    linha = disparo.listar()[0]
    assert linha["status"] == "pendente"
    assert linha["tentativas"] == 1
    agendado = datetime.datetime.strptime(str(linha["agendado_para"])[:19], "%Y-%m-%d %H:%M:%S")
    assert agendado > datetime.datetime.now() + datetime.timedelta(minutes=9)


def test_rotas_iniciar_e_pausar_passam_pelo_motor(banco_limpo, monkeypatch):
    from rotas import disparo as rota
    from rotas import disparo_leads
    from rotas.modelos import DisparoStartRequest

    _preparar()
    monkeypatch.setattr(disparo_leads, "enfileirar_aptos",
                        lambda origem="iniciar": {"enfileirados": 0, "aptos": 2,
                                                  "total": 2, "fora": {}})
    ini, fim = _janela_fechada()
    r = rota.api_disparo_iniciar(DisparoStartRequest(provider="simulado", hora_ini=ini,
                                                     hora_fim=fim, limite_dia=30))
    assert r["iniciado"] is True
    assert r["carga"]["planejados"] == 2
    assert r["carga"]["primeiro_envio"] is not None
    assert config.load_settings()["disparo_motor_ligado"] is True
    rota.api_disparo_pausar()
    assert config.load_settings()["disparo_motor_ligado"] is False
