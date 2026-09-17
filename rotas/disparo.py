# proposito: disparo: fila, envio da mensagem, iniciar e pausar o motor
from fastapi import APIRouter, HTTPException

import config
from analysis import analyzer
from nucleo import STATE
# Reexportado de proposito: o bloco da Evolution mudou de arquivo e estas tres
# funcoes seguem alcancaveis como rotas.disparo._evo_cfg, como sempre foram.
from rotas.disparo_evolution import _evo_cfg, _evo_instances, _evo_provider  # noqa: F401
from rotas.modelos import (DisparoAgoraRequest, DisparoEnqueueRequest,
                           DisparoMensagemRequest, DisparoMigrarRequest,
                           DisparoRefazerRequest, DisparoStartRequest,
                           DisparoTestRequest)

router = APIRouter()


@router.post("/api/disparo/enfileirar")
def api_disparo_enqueue(req: DisparoEnqueueRequest):
    from scrapers import disparo

    if not req.itens:
        raise HTTPException(400, "Nenhum item recebido.")
    n = disparo.enfileirar(req.itens, origem=req.origem)
    return {"enfileirados": n}


def _teto_ia(settings):
    """Trave de custo: quantas mensagens da migracao podem sair da IA. A
    migracao puxa ate 500 leads; sem teto seriam 500 chamadas pagas num
    clique. Sem chave de IA o teto e zero e tudo cai no template local."""
    if not str(settings.get("openai_api_key") or "").strip():
        return 0
    padrao = config.DEFAULT_SETTINGS.get("abordagem_ia_max", 30)
    try:
        teto = int(settings.get("abordagem_ia_max", padrao))
    except (TypeError, ValueError):
        teto = padrao
    return max(0, min(100, teto))


def _mensagem_abordagem(business, settings, usar_ia, exigir_ia):
    """Mensagem de um lead da fila. Devolve (texto, engine).

    Com IA configurada (exigir_ia), texto de template local NAO entra na fila:
    o fallback local carrega copy que o fundador reprovou, e uma queda da IA
    mandaria ela pro cliente sem aviso. Melhor o lead ficar de fora e a tela
    dizer quantos ficaram. Sem chave de IA nada muda: tudo sai do template.
    """
    if usar_ia:
        try:
            from analysis import copy_sdr
            seq = copy_sdr.gerar_sequencia(business, settings)
            msg = (seq.get("abertura") or "").strip()
            engine = seq.get("engine") or "local"
            if msg and engine != "local":
                return msg, engine
        except Exception:
            pass
    if exigir_ia:
        return "", "local"
    try:
        return (analyzer._local_pitch(business).get("whatsapp") or "").strip(), "local"
    except Exception:
        return "", "local"


@router.post("/api/disparo/migrar")
def api_disparo_migrar(req: DisparoMigrarRequest):
    """Puxa TODOS os leads já minerados (nuvem, ou sessão) para a fila, sem repetir telefone."""
    from scrapers import cloud_store, disparo

    leads = []
    try:
        leads = cloud_store.listar_leads(limite=500)
    except Exception:
        leads = []
    if not leads:
        leads = STATE.get("businesses") or []
    if not leads:
        raise HTTPException(404, "Nenhum lead minerado encontrado.")

    settings = config.load_settings()
    teto_ia = _teto_ia(settings)
    exigir_ia = teto_ia > 0
    na_fila = disparo.telefones_na_fila()
    itens = []
    desativados = 0
    tentativas_ia = 0
    com_ia = 0
    sem_mensagem = 0
    for b in leads:
        if not cloud_store.disparo_liberado(b):
            desativados += 1
            continue
        tel = disparo._norm_phone(b.get("telefone"))
        if not tel or tel in na_fila:
            continue
        usar_ia = tentativas_ia < teto_ia
        if usar_ia:
            tentativas_ia += 1
        msg, engine = _mensagem_abordagem(b, settings, usar_ia, exigir_ia)
        if not msg:
            sem_mensagem += 1
            continue
        if engine != "local":
            com_ia += 1
        itens.append({"nome": b.get("nome", ""), "telefone": b.get("telefone", ""), "mensagem": msg})
        na_fila.add(tel)

    n = disparo.enfileirar(itens, origem=req.origem or "minerados")
    return {"enfileirados": n, "total_minerados": len(leads),
            "desativados": desativados, "teto_ia": teto_ia,
            "com_ia": com_ia, "com_template": len(itens) - com_ia,
            "sem_mensagem": sem_mensagem}


@router.post("/api/disparo/enviar-agora")
def api_disparo_agora(req: DisparoAgoraRequest):
    from scrapers import disparo

    s = config.load_settings()
    prov = disparo._make_provider({
        "provider": s.get("disparo_provider", "simulado"),
        "evo_url": _evo_cfg(s)["url"],
        "evo_key": _evo_cfg(s)["key"],
        "evo_instance": s.get("disparo_evo_instance", ""),
        "meta_token": s.get("disparo_meta_token", ""),
        "meta_phone_id": s.get("disparo_meta_phone_id", ""),
    })
    ok, err = disparo.enviar_agora(req.id, prov)
    try:
        if ok:
            from scrapers import cloud_store
            row = None
            for f in disparo.listar(limite=500):
                if f["id"] == req.id:
                    row = f
                    break
            if row:
                cloud_store.set_contato_status(row.get("nome", ""), "", row.get("telefone", ""), "enviado")
    except Exception:
        pass
    return {"ok": ok, "erro": err, "provider": prov.name}


@router.post("/api/disparo/refazer")
def api_disparo_refazer(req: DisparoRefazerRequest):
    """Regenera a mensagem de um item da fila com IA completa (não o template rápido)."""
    from scrapers import disparo

    item = None
    for f in disparo.listar(limite=1000):
        if f["id"] == req.id:
            item = f
            break
    if not item:
        raise HTTPException(404, "Item não encontrado na fila.")

    # Mesma regra da edicao a mao: o texto do que JA SAIU nao se reescreve, porque
    # o registro do que foi enviado e a metrica da operacao. 'falha' continua
    # aberto de proposito: regenerar e o caminho de recuperar item que nao saiu.
    status_item = (item.get("status") or "").strip()
    if status_item not in ("pendente", "falha"):
        raise HTTPException(
            409,
            f"Esta mensagem está como '{status_item}' e não pode mais ser regenerada. "
            "Só item pendente ou com falha aceita regeneração.",
        )

    business = {"nome": item.get("nome", ""), "telefone": item.get("telefone", "")}
    try:
        from scrapers import cloud_store
        for b in cloud_store.listar_leads(limite=500):
            if disparo._norm_phone(b.get("telefone")) == item.get("telefone"):
                business = dict(b)
                break
        else:
            for b in STATE.get("businesses") or []:
                if disparo._norm_phone(b.get("telefone")) == item.get("telefone"):
                    business = dict(b)
                    break
    except Exception:
        pass

    settings = config.load_settings()
    pitch = analyzer.pitch_message(business, settings)
    msg = (pitch.get("whatsapp") or "").strip()
    if not msg:
        raise HTTPException(502, "A IA não retornou mensagem.")
    disparo.atualizar_mensagem(req.id, msg)
    return {"mensagem": msg, "engine": pitch.get("engine")}


@router.post("/api/disparo/mensagem")
def api_disparo_mensagem(req: DisparoMensagemRequest):
    """Salva o texto que a pessoa escreveu a mao, antes do envio.

    So item pendente aceita edicao: mexer no texto de algo ja enviado seria
    mentir sobre o que saiu, e o que saiu e a metrica do dia.
    """
    from scrapers import disparo

    msg = (req.mensagem or "").strip()
    if not msg:
        raise HTTPException(400, "A mensagem nao pode ficar vazia.")
    item = None
    for f in disparo.listar(limite=1000):
        if f["id"] == req.id:
            item = f
            break
    if not item:
        raise HTTPException(404, "Item nao encontrado na fila.")
    status = str(item.get("status") or "")
    if status != "pendente":
        raise HTTPException(409, f"Esta mensagem esta como '{status}' e nao pode mais ser "
                                 "editada. So item pendente aceita edicao.")
    disparo.atualizar_mensagem(req.id, msg, manual=True)
    return {"ok": True, "id": req.id, "mensagem": msg, "editada": True}


@router.get("/api/disparo/fila")
def api_disparo_fila(status: str = "", limite: int = 200):
    from scrapers import disparo

    return {"fila": disparo.listar(status or None, limite=int(limite))}


@router.get("/api/disparo/item/{item_id}")
def api_disparo_item(item_id: int):
    from scrapers import disparo

    for f in disparo.listar(limite=1000):
        if f["id"] == item_id:
            return f
    raise HTTPException(404, "Item não encontrado na fila.")


@router.post("/api/disparo/iniciar")
def api_disparo_iniciar(req: DisparoStartRequest):
    from scrapers import disparo

    s = config.load_settings()
    if (s.get("disparo_modo") or "auto") == "manual":
        return {"iniciado": False, "motivo": "modo manual ativo — envie item por item", **disparo.status()}
    cfg = {
        "provider": req.provider,
        "delay_min": max(5, req.delay_min),
        "delay_max": max(req.delay_min, req.delay_max),
        "limite_dia": max(1, min(500, req.limite_dia)),
        "hora_ini": req.hora_ini,
        "hora_fim": req.hora_fim,
        "optout": req.optout,
        "evo_url": _evo_cfg(s)["url"],
        "evo_key": _evo_cfg(s)["key"],
        "evo_instance": s.get("disparo_evo_instance", ""),
        "evo_instances": [i.strip() for i in str(s.get("disparo_evo_instances") or "").split(",") if i.strip()],
        "meta_token": s.get("disparo_meta_token", ""),
        "meta_phone_id": s.get("disparo_meta_phone_id", ""),
    }
    ok = disparo.iniciar(cfg)
    return {"iniciado": ok, **disparo.status()}


@router.post("/api/disparo/pausar")
def api_disparo_pausar():
    from scrapers import disparo

    disparo.pausar()
    return disparo.status()


@router.get("/api/disparo/status")
def api_disparo_status():
    from scrapers import disparo

    return disparo.status()


@router.post("/api/disparo/testar")
def api_disparo_testar(req: DisparoTestRequest):
    from scrapers import disparo

    s = config.load_settings()
    prov = disparo._make_provider({
        "provider": s.get("disparo_provider", "simulado"),
        "evo_url": _evo_cfg(s)["url"],
        "evo_key": _evo_cfg(s)["key"],
        "evo_instance": s.get("disparo_evo_instance", ""),
        "meta_token": s.get("disparo_meta_token", ""),
        "meta_phone_id": s.get("disparo_meta_phone_id", ""),
    })
    ok, err = prov.send(disparo._norm_phone(req.phone), req.mensagem)
    return {"ok": ok, "erro": err, "provider": prov.name}


@router.post("/api/disparo/limpar")
def api_disparo_limpar():
    from scrapers import disparo

    disparo.limpar_finalizados()
    return disparo.status()
