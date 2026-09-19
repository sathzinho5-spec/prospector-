# proposito: conversa iniciada: marcar, desmarcar e ler qual copy converteu
"""
O coracao da medicao do disparo.

A pergunta que a empresa nao respondia: quantas conversas a abordagem iniciou, e
qual copy puxou cada uma. O dado vive em scrapers/disparo_abordagens.py, FORA da
fila, porque limpar_finalizados() apaga as linhas 'enviado' e levaria a metrica
junto. Estas rotas so leem e escrevem aquele registro.
"""
from fastapi import APIRouter, HTTPException

from rotas.modelos import DisparoRespostaRequest

router = APIRouter()


def _espelhar_no_crm(lead_id, estagio):
    """Best-effort, igual ao resto da integracao com a nuvem: o CRM nao pode
    seguir dizendo 'enviado' depois de a conversa comecar, mas nuvem fora do ar
    tambem nao pode impedir o operador de marcar a resposta."""
    if not lead_id:
        return False
    try:
        from scrapers import cloud_store
        return bool(cloud_store.set_contato_status_by_id(str(lead_id), estagio))
    except Exception:
        return False


@router.post("/api/disparo/respondido")
def api_disparo_respondido(req: DisparoRespostaRequest):
    """O lead respondeu. Idempotente: repetir mantem o horario da primeira
    resposta, que e o que mede quanto a copy demorou pra puxar conversa."""
    from scrapers import disparo_abordagens

    if not req.id and not str(req.telefone or "").strip():
        raise HTTPException(400, "Informe o id da abordagem ou o telefone.")
    ok, linha = disparo_abordagens.marcar_respondido(req.id, req.telefone)
    if not ok:
        raise HTTPException(404, "Nao ha abordagem registrada para este lead.")
    return {"ok": True, "abordagem": linha,
            "crm": _espelhar_no_crm(req.lead_id, "respondido"),
            "conversas_iniciadas": disparo_abordagens.conversas_iniciadas()}


@router.post("/api/disparo/nao-respondido")
def api_disparo_nao_respondido(req: DisparoRespostaRequest):
    """Desfaz a marcacao. Existe porque quem opera erra de linha, e metrica que
    nao se corrige vira metrica em que ninguem confia."""
    from scrapers import disparo_abordagens

    if not req.id and not str(req.telefone or "").strip():
        raise HTTPException(400, "Informe o id da abordagem ou o telefone.")
    ok, linha = disparo_abordagens.desmarcar_respondido(req.id, req.telefone)
    if not ok:
        raise HTTPException(404, "Nao ha abordagem registrada para este lead.")
    return {"ok": True, "abordagem": linha,
            "crm": _espelhar_no_crm(req.lead_id, "enviado"),
            "conversas_iniciadas": disparo_abordagens.conversas_iniciadas()}


@router.get("/api/disparo/conversas")
def api_disparo_conversas(apenas_respondidas: bool = False, limite: int = 200):
    """O que saiu, o que virou conversa, e a taxa por origem da copy."""
    from scrapers import disparo_abordagens

    return {
        "conversas_iniciadas": disparo_abordagens.conversas_iniciadas(),
        "por_copy": disparo_abordagens.resumo_por_copy(),
        "abordagens": disparo_abordagens.listar(
            limite=min(1000, max(1, int(limite))),
            apenas_respondidas=bool(apenas_respondidas)),
    }


@router.get("/api/disparo/conversao")
def api_disparo_conversao():
    """O relatorio que treina o playbook: taxa por VERSAO do conhecimento.

    Separado de /api/disparo/conversas de proposito. Aquele responde "o que
    aconteceu com cada lead" e carrega a lista inteira; este responde "qual
    versao do playbook converte melhor" e cabe numa tela. Quem le este aqui e a
    copywriter-expert, antes de escrever a versao seguinte.
    """
    from analysis import playbook_sdr
    from scrapers import disparo_abordagens

    por_versao = disparo_abordagens.resumo_por_versao()
    enviadas = sum(l["enviadas"] for l in por_versao)
    respondidas = sum(l["respondidas"] for l in por_versao)
    return {
        "versao_no_ar": playbook_sdr.versao(),
        "playbook_disponivel": playbook_sdr.disponivel(),
        "enviadas": enviadas,
        "conversas_iniciadas": respondidas,
        "taxa": round(100.0 * respondidas / enviadas, 1) if enviadas else 0.0,
        "por_versao": por_versao,
        "por_origem": disparo_abordagens.resumo_por_copy(),
    }
