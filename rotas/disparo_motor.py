# proposito: ligar, desligar e religar o motor do disparo, lembrando entre reinicios se ele estava ligado
"""
O motor do disparo e uma thread dentro do processo do servidor. Todo deploy
reinicia o container, e o deploy acontece sozinho a cada push em main, do
fundador ou do socio. Enquanto o estado "ligado" vivia so na memoria, um push
de madrugada deixava a fila planejada parada no dia seguinte, sem erro nenhum
na tela.

Por isso ligar grava no settings que o motor esta ligado, desligar grava que
nao esta, e a subida do servidor chama retomar(), que religa com o plano refeito
a partir da hora da volta.
"""
import threading

import config
from rotas.disparo_evolution import _evo_cfg

# Serializa ligar/desligar: um clique duplo em Iniciar, ou Pausar cruzando com
# Iniciar, nao pode deixar duas execucoes mexendo no worker e no settings ao
# mesmo tempo.
_trava = threading.Lock()


def _cfg_do_motor(s, provider):
    """O cfg que o motor recebe. Janela e limite saem do settings, que e onde a
    rota de iniciar acabou de salvar o que veio da tela."""
    return {
        "provider": provider,
        "limite_dia": s.get("disparo_limite_dia") or 30,
        "hora_ini": s.get("disparo_hora_ini") or "08:00",
        "hora_fim": s.get("disparo_hora_fim") or "20:00",
        "evo_url": _evo_cfg(s)["url"],
        "evo_key": _evo_cfg(s)["key"],
        "evo_instance": s.get("disparo_evo_instance", ""),
        "evo_instances": [i.strip() for i in str(s.get("disparo_evo_instances") or "").split(",")
                          if i.strip()],
        "meta_token": s.get("disparo_meta_token", ""),
        "meta_phone_id": s.get("disparo_meta_phone_id", ""),
    }


def ligar(provider):
    """Planeja as pendentes a partir de agora, liga o motor e lembra que ligou.

    Replaneja mesmo com o motor ja rodando, de proposito: plano velho de uma
    sessao anterior nao sobrevive a um clique novo. Clicar Iniciar com o motor
    JA rodando religa ele com a config nova: para a thread velha antes de
    planejar, senao ela segue enviando com o provider, a janela e o limite
    antigos enquanto o settings e a tela ja mostram os novos.
    """
    from scrapers import disparo

    with _trava:
        s = config.load_settings()
        cfg = _cfg_do_motor(s, provider)
        if disparo._worker_thread is not None and disparo._worker_thread.is_alive():
            # Para antes de planejar: planejar_fila olha o que ja saiu hoje, e
            # isso tem que incluir o envio que a thread velha acabou de fazer.
            disparo.pausar()
            disparo._worker_thread.join(timeout=60)
        horarios = disparo.planejar_fila(cfg["hora_ini"], cfg["hora_fim"], cfg["limite_dia"])
        planejados = len(horarios)
        iniciado = disparo.iniciar(cfg)
        config.save_settings({"disparo_motor_ligado": True, "disparo_motor_provider": provider})
        return {"iniciado": iniciado, "planejados": planejados, "horarios": horarios}


def desligar():
    from scrapers import disparo

    with _trava:
        disparo.pausar()
        config.save_settings({"disparo_motor_ligado": False})


def retomar():
    """Chamado na subida do servidor. Religa so o que estava ligado."""
    s = config.load_settings()
    if not s.get("disparo_motor_ligado"):
        return None
    provider = s.get("disparo_motor_provider") or s.get("disparo_provider") or "simulado"
    return ligar(provider)
