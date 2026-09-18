# proposito: leads e fila no Supabase, best-effort: cai pro local sem quebrar
"""
Cloud store (Supabase) para leads + fila de disparo.
Tudo best-effort: se o Supabase estiver fora do ar, retorna None/False
e o sistema segue no modo local (SQLite/memória) sem quebrar.
"""
import hashlib

from config import load_settings

_leads_cols = ["id", "nome", "categoria", "nota", "avaliacoes", "endereco",
               "bairro", "cidade", "estado", "telefone", "website", "horarios",
               "status_funcionamento", "preco", "plus_code", "atributos",
               "latitude", "longitude", "foto", "descricao", "consulta", "url",
               "score_oportunidade", "nivel", "oportunidades", "pitch_whatsapp",
               "contato_status", "observacao", "score_ajustado", "score_motivo"]

CRM_STAGES = ["novo", "enviado", "contatado", "respondido", "negociando", "fechado", "perdido"]


def _client():
    from supabase import create_client

    s = load_settings()
    url = (s.get("supabase_url") or "").strip()
    key = (s.get("supabase_secret") or "").strip()
    if not url or not key:
        return None
    return create_client(url, key)


def _with_timeout(fn, timeout=8):
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

    with ThreadPoolExecutor(max_workers=1) as ex:
        try:
            return ex.submit(fn).result(timeout=timeout)
        except FuturesTimeout:
            raise TimeoutError("Supabase sem resposta (timeout)")


def ping():
    """Retorna True se a nuvem responde."""
    def _do():
        sb = _client()
        if not sb:
            return False
        sb.table("leads").select("id").limit(1).execute()
        return True
    try:
        return _with_timeout(_do)
    except Exception:
        return False


def lead_id(b):
    base = f"{b.get('nome', '')}|{b.get('endereco', '')}|{b.get('telefone', '')}"
    return hashlib.md5(base.encode("utf-8", "ignore")).hexdigest()[:16]


def _row(b):
    atr = b.get("atributos")
    if isinstance(atr, list):
        atr = "; ".join(str(x) for x in atr)
    opps = b.get("oportunidades") or b.get("oportunidades_ia")
    if isinstance(opps, list):
        opps = "; ".join(str(x) for x in opps)
    row = {
        "id": lead_id(b),
        "nome": b.get("nome"),
        "categoria": b.get("categoria"),
        "nota": b.get("nota"),
        "avaliacoes": b.get("avaliacoes"),
        "endereco": b.get("endereco"),
        "bairro": b.get("bairro"),
        "cidade": b.get("cidade"),
        "estado": b.get("estado"),
        "telefone": b.get("telefone"),
        "website": b.get("website"),
        "horarios": b.get("horarios"),
        "status_funcionamento": b.get("status_funcionamento"),
        "preco": b.get("preco"),
        "plus_code": b.get("plus_code"),
        "atributos": atr,
        "latitude": b.get("latitude"),
        "longitude": b.get("longitude"),
        "foto": b.get("foto"),
        "descricao": b.get("descricao"),
        "consulta": b.get("consulta"),
        "url": b.get("url"),
        "score_oportunidade": b.get("score_oportunidade"),
        "nivel": b.get("nivel") or b.get("nivel_ia"),
        "oportunidades": opps,
        "pitch_whatsapp": (b.get("_pitch") or {}).get("whatsapp") if isinstance(b.get("_pitch"), dict) else b.get("pitch_whatsapp"),
        "contato_status": b.get("contato_status") or "novo",
    }
    return {k: v for k, v in row.items() if v is not None}


def save_leads(businesses):
    """Upsert em lote. Retorna qtd salva ou 0 se nuvem fora."""
    if not businesses:
        return 0

    def _do():
        sb = _client()
        if not sb:
            return 0
        rows = [_row(b) for b in businesses]
        for i in range(0, len(rows), 200):
            sb.table("leads").upsert(rows[i:i + 200], on_conflict="id").execute()
        return len(rows)

    try:
        return _with_timeout(_do, timeout=20)
    except Exception as e:
        print(f"[cloud] save_leads falhou, segue local: {e}")
        return 0


def update_analise(businesses):
    """Atualiza score/nivel/oportunidades/pitch dos leads já salvos."""
    def _do():
        sb = _client()
        if not sb:
            return 0
        n = 0
        for b in businesses:
            patch = {}
            if b.get("score_oportunidade") is not None:
                patch["score_oportunidade"] = b["score_oportunidade"]
            if b.get("nivel") or b.get("nivel_ia"):
                patch["nivel"] = b.get("nivel") or b.get("nivel_ia")
            opps = b.get("oportunidades") or b.get("oportunidades_ia")
            if opps:
                patch["oportunidades"] = "; ".join(opps) if isinstance(opps, list) else opps
            pitch = b.get("_pitch")
            if isinstance(pitch, dict) and pitch.get("whatsapp"):
                patch["pitch_whatsapp"] = pitch["whatsapp"]
            if patch:
                sb.table("leads").update(patch).eq("id", lead_id(b)).execute()
                n += 1
        return n
    try:
        return _with_timeout(_do, timeout=25)
    except Exception as e:
        print(f"[cloud] update_analise falhou: {e}")
        return 0


def set_contato_status_by_id(_id, status, observacao=None):
    def _do():
        sb = _client()
        if not sb:
            return False
        patch = {"contato_status": status}
        if observacao is not None:
            patch["observacao"] = observacao
        sb.table("leads").update(patch).eq("id", _id).execute()
        return True
    try:
        return _with_timeout(_do, timeout=10)
    except Exception:
        return False


def set_contato_status(nome, endereco, telefone, status, observacao=None):
    def _do():
        sb = _client()
        if not sb:
            return False
        _id = lead_id({"nome": nome, "endereco": endereco, "telefone": telefone})
        patch = {"contato_status": status}
        if observacao is not None:
            patch["observacao"] = observacao
        sb.table("leads").update(patch).eq("id", _id).execute()
        return True
    try:
        return _with_timeout(_do, timeout=10)
    except Exception:
        return False


def existing_ids(ids):
    """Retorna o subconjunto de ids que já existem na tabela leads."""
    if not ids:
        return set()
    found = set()

    def _do():
        sb = _client()
        if not sb:
            return set()
        out = set()
        ids_list = list(ids)
        for i in range(0, len(ids_list), 100):
            chunk = ids_list[i:i + 100]
            res = sb.table("leads").select("id").in_("id", chunk).execute()
            for r in res.data or []:
                out.add(r["id"])
        return out

    try:
        return _with_timeout(_do, timeout=15)
    except Exception:
        return set()


def disparo_liberado(lead):
    """So barra quem foi EXPLICITAMENTE desativado para disparo. Campo ausente
    (lead da sessao) ou nulo (linha anterior a coluna existir) conta como
    liberado: barrar todos quebraria o fluxo normal da fila."""
    if not isinstance(lead, dict):
        return True
    valor = lead.get("disparo_ativo")
    return True if valor is None else bool(valor)


def set_disparo_ativo(ids, ativo):
    """Liga ou desliga o disparo dos leads informados. Devolve quantos foram
    gravados, 0 com a nuvem fora. Ligar e sempre acao consciente de quem usa:
    nada aqui roda sozinho."""
    alvos = [str(i).strip() for i in (ids or []) if str(i or "").strip()]
    if not alvos:
        return 0

    def _do():
        sb = _client()
        if not sb:
            return 0
        n = 0
        for i in range(0, len(alvos), 100):
            chunk = alvos[i:i + 100]
            sb.table("leads").update({"disparo_ativo": bool(ativo)}).in_("id", chunk).execute()
            n += len(chunk)
        return n

    try:
        return _with_timeout(_do, timeout=20)
    except Exception as e:
        print(f"[cloud] set_disparo_ativo falhou: {e}")
        return 0


def listar_leads(estado=None, min_score=None, apenas_pendentes=False, limite=200):
    def _do():
        sb = _client()
        if not sb:
            return []
        q = sb.table("leads").select("*").order("score_oportunidade", desc=True, nullsfirst=False).limit(limite)
        if estado:
            q = q.eq("estado", estado.upper())
        if min_score is not None:
            q = q.gte("score_oportunidade", int(min_score))
        if apenas_pendentes:
            q = q.eq("contato_status", "novo")
        return q.execute().data or []
    try:
        return _with_timeout(_do, timeout=15)
    except Exception:
        return []


def obter_lead(_id):
    """Um lead pelo id, ou None. Leitura leve pra quem precisa do antes."""
    def _do():
        sb = _client()
        if not sb:
            return None
        r = sb.table("leads").select("*").eq("id", str(_id)).limit(1).execute()
        return (r.data or [None])[0]

    try:
        return _with_timeout(_do, timeout=8)
    except Exception:
        return None


def set_aprendizado(ajustes):
    """Grava score_ajustado + score_motivo por lead_id. Devolve quantos foram.
    Tolera banco anterior ao schema novo: sem as colunas, avisa uma vez e
    devolve 0 em vez de quebrar o recalculado (rode supabase_schema.sql)."""
    alvos = [(str(i), dict(v)) for i, v in (ajustes or {}).items() if str(i or "").strip()]

    def _do():
        sb = _client()
        if not sb:
            return 0
        n = 0
        for lid, aj in alvos:
            try:
                sb.table("leads").update({
                    "score_ajustado": int(aj.get("score_ajustado")),
                    "score_motivo": str(aj.get("motivo") or "")[:200],
                }).eq("id", lid).execute()
                n += 1
            except Exception as e:
                print(f"[cloud] set_aprendizado pulou {lid}: {e}")
                break
        return n

    try:
        return _with_timeout(_do, timeout=25)
    except Exception as e:
        print(f"[cloud] set_aprendizado falhou: {e}")
        return 0


def log_evento(lead_id, evento, de=None, para=None):
    """Historico fino pra v2 e pro radar do follow-up. Tabela pode nao existir
    ainda: nesse caso registra em silencio (o retrato da v1 nao depende dele)."""
    def _do():
        sb = _client()
        if not sb:
            return False
        sb.table("eventos_lead").insert({
            "lead_id": str(lead_id),
            "evento": str(evento),
            "de": str(de or "") or None,
            "para": str(para or "") or None,
        }).execute()
        return True

    try:
        return _with_timeout(_do, timeout=8)
    except Exception:
        return False
