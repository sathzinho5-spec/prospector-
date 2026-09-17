# proposito: instancias da Evolution: qrcode, estado do chip e o numero pareado
#
# Saiu de rotas/disparo.py pela costura que o proprio arquivo ja tinha: fila e
# envio de um lado, o chip do outro. rotas/disparo.py reexporta os tres helpers,
# entao nenhuma chamada de fora mudou.
import os

from fastapi import APIRouter, HTTPException

import config

router = APIRouter()


def _evo_provider(instance=None):
    from scrapers import disparo

    s = config.load_settings()
    inst = (instance or "").strip() or s.get("disparo_evo_instance", "")
    return disparo.EvolutionProvider(
        _evo_cfg(s)["url"],
        _evo_cfg(s)["key"],
        inst,
    )


def _evo_cfg(s=None):
    """URL/key da Evolution: settings primeiro, env da VPS como fallback."""
    s = s if s is not None else config.load_settings()
    return {
        "url": s.get("disparo_evo_url", "") or os.environ.get("DISPARO_EVO_URL", ""),
        "key": s.get("disparo_evo_key", "") or os.environ.get("DISPARO_EVO_KEY", ""),
    }


def _evo_instances():
    from scrapers import disparo  # noqa: F401 (garante módulo carregado)

    s = config.load_settings()
    insts = []
    for v in (s.get("disparo_evo_instance"), s.get("disparo_evo_chip2"),
              s.get("disparo_evo_chip3")):
        v = str(v or "").strip()
        if v and v not in insts:
            insts.append(v)
    for v in str(s.get("disparo_evo_instances") or "").split(","):
        v = v.strip()
        if v and v not in insts:
            insts.append(v)
    return insts[:3]


@router.post("/api/disparo/evolution/qrcode")
def api_evo_qrcode(instance: str = ""):
    prov = _evo_provider(instance)
    ok, err, qr = prov.criar_instancia()
    if not ok:
        raise HTTPException(502, err)
    return {"ok": True, "qrcode": qr, "instance": prov.instance}


@router.get("/api/disparo/evolution/estado")
def api_evo_estado(instance: str = ""):
    return _evo_provider(instance).estado()


@router.get("/api/disparo/instancias")
def api_disparo_instancias():
    provs = []
    for inst in _evo_instances():
        from scrapers import disparo

        s = config.load_settings()
        cfg = _evo_cfg(s)
        p = disparo.EvolutionProvider(cfg["url"], cfg["key"], inst)
        st = p.estado()
        provs.append({"instance": inst, **st})
    if not provs:
        s = config.load_settings()
        provs.append({"instance": s.get("disparo_evo_instance", ""),
                      "conectado": False, "estado": "nao_configurado",
                      "erro": "Cadastre as instâncias nas Configurações."})
    return {"instancias": provs}

