# proposito: a copy de abordagem dos leads: criar quem esta sem, e migrar pra fila
"""
Saiu de rotas/disparo.py pela costura que o arquivo ja tinha: de um lado a fila
e o motor, do outro quem ESCREVE o texto. rotas/disparo.py reexporta _teto_ia,
_mensagem_abordagem e api_disparo_migrar, entao nenhuma chamada de fora mudou.

As duas rotas daqui compartilham o mesmo gerador, e e de proposito: se "criar
copy" e "migrar" escrevessem por caminhos diferentes, o texto que a tela mostra
como pronto poderia nao ser o texto que entra na fila.
"""
from fastapi import APIRouter, HTTPException

import config
from analysis import analyzer
from nucleo import STATE
from rotas.disparo_leads import leads_do_disparo
from rotas.modelos import (DisparoCopyRequest, DisparoCriarCopyRequest,
                           DisparoMigrarRequest)

router = APIRouter()


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


def _origem(engine):
    """Carimbo que segue o texto ate o registro de conversao. 'template' e
    separado de 'ia' de proposito: juntar os dois faria o relatorio de qual
    copy converteu responder uma pergunta que ninguem fez."""
    return "ia" if engine and engine != "local" else "template"


def _lead_id(business):
    from scrapers import cloud_store

    return str(business.get("id") or cloud_store.lead_id(business))


def _selecionado(business, tel, ids, telefones):
    """Sem selecao, vale todo mundo. E o que faz 'criar copy de todos' e
    'criar copy destes tres' serem a mesma rota."""
    if not ids and not telefones:
        return True
    return _lead_id(business) in ids or tel in telefones


@router.post("/api/disparo/criar-copy")
def api_disparo_criar_copy(req: DisparoCriarCopyRequest):
    """Escreve a copy dos leads que estao sem ela. Nao enfileira nada: quem
    decide o que entra na fila e a migracao, depois de quem opera conferir."""
    from scrapers import cloud_store, disparo, disparo_copys

    leads = leads_do_disparo()
    if not leads:
        raise HTTPException(404, "Nenhum lead minerado encontrado.")

    settings = config.load_settings()
    teto_ia = _teto_ia(settings)
    exigir_ia = teto_ia > 0
    ids = set(str(i).strip() for i in (req.ids or []) if str(i or "").strip())
    telefones = set(t for t in (disparo._norm_phone(x) for x in (req.telefones or [])) if t)
    existentes = disparo_copys.mapa()

    criados, ja_tinham, desativados, sem_mensagem, com_ia = [], 0, 0, 0, 0
    tentativas_ia = 0
    for b in leads:
        tel = disparo._norm_phone(b.get("telefone"))
        if not tel or not _selecionado(b, tel, ids, telefones):
            continue
        if not cloud_store.disparo_liberado(b):
            desativados += 1
            continue
        if tel in existentes and not req.refazer:
            ja_tinham += 1
            continue
        usar_ia = tentativas_ia < teto_ia
        if usar_ia:
            tentativas_ia += 1
        msg, engine = _mensagem_abordagem(b, settings, usar_ia, exigir_ia)
        if not msg:
            sem_mensagem += 1
            continue
        origem = _origem(engine)
        if origem == "ia":
            com_ia += 1
        disparo_copys.salvar(tel, msg, b.get("nome", ""), origem)
        criados.append({"telefone": tel, "nome": b.get("nome", ""),
                        "mensagem": msg, "copy_origem": origem})

    return {"criados": len(criados), "ja_tinham": ja_tinham,
            "desativados": desativados, "sem_mensagem": sem_mensagem,
            "teto_ia": teto_ia, "com_ia": com_ia,
            "com_template": len(criados) - com_ia, "itens": criados}


@router.post("/api/disparo/migrar")
def api_disparo_migrar(req: DisparoMigrarRequest):
    """Puxa TODOS os leads já minerados (nuvem, ou sessão) para a fila, sem repetir telefone."""
    from scrapers import cloud_store, disparo, disparo_copys

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
    copys = disparo_copys.mapa()
    itens = []
    desativados = 0
    tentativas_ia = 0
    com_ia = 0
    da_copy = 0
    sem_mensagem = 0
    for b in leads:
        if not cloud_store.disparo_liberado(b):
            desativados += 1
            continue
        tel = disparo._norm_phone(b.get("telefone"))
        if not tel or tel in na_fila:
            continue
        # Copy ja escrita vem primeiro: gerar de novo pagaria a IA duas vezes e,
        # pior, trocaria por outro texto o que quem opera ja leu e aprovou.
        pronta = copys.get(tel)
        if pronta:
            msg, origem = pronta["mensagem"], (pronta.get("copy_origem") or "ia")
            da_copy += 1
        else:
            usar_ia = tentativas_ia < teto_ia
            if usar_ia:
                tentativas_ia += 1
            msg, engine = _mensagem_abordagem(b, settings, usar_ia, exigir_ia)
            origem = _origem(engine)
            if msg:
                disparo_copys.salvar(tel, msg, b.get("nome", ""), origem)
        if not msg:
            sem_mensagem += 1
            continue
        if origem == "ia":
            com_ia += 1
        itens.append({"nome": b.get("nome", ""), "telefone": b.get("telefone", ""),
                      "mensagem": msg, "copy_origem": origem,
                      "categoria": b.get("categoria", "")})
        na_fila.add(tel)

    n = disparo.enfileirar(itens, origem=req.origem or "minerados")
    return {"enfileirados": n, "total_minerados": len(leads),
            "desativados": desativados, "teto_ia": teto_ia,
            "com_ia": com_ia, "com_template": len(itens) - com_ia,
            "da_copy_pronta": da_copy, "sem_mensagem": sem_mensagem}


@router.post("/api/disparo/copy")
def api_disparo_copy(req: DisparoCopyRequest):
    """Salva a copy que o operador escreveu a mao, pelo TELEFONE do lead.

    Existe porque a edicao pela fila (/api/disparo/mensagem) so alcanca lead que
    ja foi enfileirado, e o operador revisa o texto ANTES disso. Grava nos dois
    lugares quando os dois existem: se gravasse so num, a tela mostraria o texto
    revisado e a fila mandaria o antigo.

    Lead que ja recebeu a abordagem nao aceita edicao, pela mesma razao das
    outras duas rotas: reescrever o texto do que saiu falsifica a metrica.
    """
    from scrapers import disparo, disparo_abordagens, disparo_copys

    tel = disparo._norm_phone(req.telefone)
    if not tel:
        raise HTTPException(400, "Telefone invalido.")
    msg = (req.mensagem or "").strip()
    if not msg:
        raise HTTPException(400, "A mensagem nao pode ficar vazia.")

    if disparo_abordagens.mapa_por_telefone().get(tel):
        raise HTTPException(409, "Este lead ja recebeu a abordagem e o texto nao "
                                 "pode mais ser alterado.")

    anterior = disparo_copys.obter(tel) or {}
    disparo_copys.salvar(tel, msg, nome=anterior.get("nome", ""),
                         copy_origem="manual", manual=True)

    # A fila so e tocada quando o item ainda esta pendente: item em voo ou ja
    # finalizado nao se reescreve.
    fila_id = None
    for f in disparo.listar(limite=1000):
        if f.get("telefone") == tel and str(f.get("status") or "") == "pendente":
            disparo.atualizar_mensagem(f["id"], msg, manual=True)
            fila_id = f["id"]
            break

    return {"ok": True, "telefone": tel, "mensagem": msg,
            "editada": True, "fila_id": fila_id}
