# proposito: disparo: fila, envio da mensagem, cadencia, iniciar e pausar o motor
from fastapi import APIRouter, HTTPException

import config
from analysis import analyzer
from nucleo import STATE
# Reexportado de proposito: o bloco da Evolution e o bloco da copy mudaram de
# arquivo, e estes nomes seguem alcancaveis como rotas.disparo._evo_cfg e
# rotas.disparo._mensagem_abordagem, como sempre foram. rotas/whatsapp.py
# depende do primeiro.
from rotas.disparo_copy import (_mensagem_abordagem, _teto_ia,  # noqa: F401
                                api_disparo_migrar)
from rotas.disparo_evolution import _evo_cfg, _evo_instances, _evo_provider  # noqa: F401
from rotas.modelos import (DisparoAgoraRequest, DisparoEnqueueRequest,
                           DisparoMensagemRequest, DisparoRefazerRequest,
                           DisparoStartRequest, DisparoTestRequest)

router = APIRouter()


@router.post("/api/disparo/enfileirar")
def api_disparo_enqueue(req: DisparoEnqueueRequest):
    from scrapers import disparo

    if not req.itens:
        raise HTTPException(400, "Nenhum item recebido.")
    n = disparo.enfileirar(req.itens, origem=req.origem)
    return {"enfileirados": n}


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


def _janela_e_limite(req=None):
    """Os dois numeros de onde a cadencia sai. Fonte: as configuracoes. Valor
    vindo no pedido sobrescreve E fica salvo, senao o /cadencia responderia uma
    coisa e o motor rodaria outra, que e exatamente a divergencia a evitar."""
    s = config.load_settings()
    novo = {}
    if req is not None:
        if req.hora_ini:
            novo["disparo_hora_ini"] = str(req.hora_ini)
        if req.hora_fim:
            novo["disparo_hora_fim"] = str(req.hora_fim)
        if req.limite_dia is not None:
            novo["disparo_limite_dia"] = max(1, min(500, int(req.limite_dia)))
    if novo:
        s = config.save_settings(novo)
    return (s, s.get("disparo_hora_ini") or "08:00",
            s.get("disparo_hora_fim") or "20:00",
            s.get("disparo_limite_dia") or 30)


@router.get("/api/disparo/cadencia")
def api_disparo_cadencia(hora_ini: str = "", hora_fim: str = "", limite_dia: int = 0):
    """O intervalo que o motor usa, calculado aqui e em lugar nenhum mais.

    A tela mostra este numero; ela nao o recalcula. Se recalculasse, bastaria
    uma regra mudar de um lado pro operador passar a ler um ritmo que o motor
    nao esta praticando. Os parametros existem so pra previa: a tela pode
    perguntar 'e se fosse 50 por dia?' sem salvar nada.
    """
    from scrapers import disparo, disparo_cadencia

    _, ini, fim, limite = _janela_e_limite()
    cad = disparo_cadencia.calcular(hora_ini or ini, hora_fim or fim,
                                    limite_dia or limite)
    st = disparo.status()
    cad["rodando"] = bool(st.get("rodando"))
    cad["proximo_em"] = st.get("proximo_em")
    cad["previa"] = bool(hora_ini or hora_fim or limite_dia)
    return cad


@router.get("/api/timing/janelas")
def api_timing_janelas():
    """Padrao por nicho + o que o operador ajustou. A tela monta o editor com
    isso: ela nao duplica a tabela, senao padrao e tela divergem."""
    import niches
    from analysis import timing

    s = config.load_settings()
    salvas = s.get("timing_janelas") or {}
    return {
        "nichos": [{"id": n["id"], "label": n["label"]} for n in niches.NICHES],
        "padrao": timing.JANELAS_PADRAO,
        "salvas": salvas,
    }


@router.get("/api/disparo/kpis")
def api_disparo_kpis():
    """Os quatro numeros da aba. Todos vem de quem ja os contava: nenhum
    caminho paralelo de calculo, senao a tela e o motor discordam."""
    from scrapers import disparo
    from rotas.disparo_leads import montar_linhas

    st = disparo.status()
    novos = sum(1 for linha in montar_linhas() if linha["estado"] in ("sem_copy", "copy_pronta"))
    return {
        "leads_novos": novos,
        "enviadas_hoje": st.get("enviados_hoje", 0),
        "na_fila": st.get("pendentes", 0),
        "conversas_iniciadas": st.get("conversas_iniciadas", 0),
    }


@router.post("/api/disparo/iniciar")
def api_disparo_iniciar(req: DisparoStartRequest):
    """Liga o motor. delay_min/delay_max sao aceitos e ignorados: a pausa entre
    envios virou regra fixa. O envio avulso NAO e mais barrado pelo modo manual,
    porque os dois caminhos convivem pela trava atomica da fila."""
    from scrapers import disparo

    s, ini, fim, limite = _janela_e_limite(req)
    cfg = {
        "provider": req.provider,
        "limite_dia": limite,
        "hora_ini": ini,
        "hora_fim": fim,
        "optout": req.optout,
        "evo_url": _evo_cfg(s)["url"],
        "evo_key": _evo_cfg(s)["key"],
        "evo_instance": s.get("disparo_evo_instance", ""),
        "evo_instances": [i.strip() for i in str(s.get("disparo_evo_instances") or "").split(",") if i.strip()],
        "meta_token": s.get("disparo_meta_token", ""),
        "meta_phone_id": s.get("disparo_meta_phone_id", ""),
    }
    # A FILA NASCE AQUI. Antes ela so era carregada pelo botao "enfileirar", que
    # saiu da tela quando a aba virou Disparo: o motor passou a ligar em cima de
    # fila vazia e a nao mandar nada, sem erro nenhum. Agora "iniciar" faz o que
    # o nome promete, e quem entra e so quem a propria lista mostra como apto.
    from rotas.disparo_leads import enfileirar_aptos

    carga = enfileirar_aptos(origem="iniciar")

    ok = disparo.iniciar(cfg)
    avisos = []
    if req.delay_min is not None or req.delay_max is not None:
        avisos.append("delay_min e delay_max foram ignorados: a cadencia agora "
                      "sai da janela e do limite do dia.")
    if (req.provider or "").lower() == "simulado":
        avisos.append("Modo ensaio: o provedor esta em 'simulado', nada sai de "
                      "verdade e nenhum lead e consumido. Troque o provedor em "
                      "Ajustes para disparar pra valer.")
    if not carga["aptos"]:
        fora = carga["fora"]
        detalhe = ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in fora.items() if v)
        avisos.append("Nenhum lead apto entrou na fila" +
                      (f" ({detalhe})." if detalhe else "."))
    # A cadencia sai do status e NAO de uma conta refeita aqui. O recalculo que
    # existia nesta linha era apagado pelo **status() logo abaixo, que tem a
    # mesma chave: a rota prometia um objeto e entregava a string do motor, sem
    # ninguem perceber. Ficou a do motor de proposito, que e a que ele pratica.
    return {"iniciado": ok, "avisos": avisos, "carga": carga,
            **disparo.status()}


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
