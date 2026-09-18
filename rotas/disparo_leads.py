# proposito: a lista de leads do disparo com o estado de copy e de envio de cada um
"""
A rota que alimenta a tabela da aba Disparo.

Ela existe porque a pergunta do operador nao e respondida por nenhuma tabela
sozinha: "este lead ja tem copy?" mora em copys, "ja esta na fila?" mora na
fila, "ja saiu e respondeu?" mora em abordagens, e "pode disparar?" mora na
nuvem (disparo_liberado) e no bloqueio local. O cruzamento acontece aqui, uma
vez, em vez de a tela fazer quatro chamadas e montar a verdade por conta.
"""
from fastapi import APIRouter

from nucleo import STATE

router = APIRouter()

# Ordem de leitura, do fim da vida pro comeco: quem ja respondeu nao volta a
# ser "na fila" so porque sobrou linha antiga.
ESTADOS = ("respondeu", "enviado", "falha", "duplicado", "bloqueado",
           "na_fila", "copy_pronta", "sem_copy")


def leads_do_disparo(limite=500):
    """Os leads que a aba Disparo enxerga: a nuvem, e a sessao quando ela esta
    fora. Mesma fonte que a migracao ja usava, pra tela e fila nao divergirem."""
    from scrapers import cloud_store

    try:
        leads = cloud_store.listar_leads(limite=limite)
    except Exception:
        leads = []
    return leads or (STATE.get("businesses") or [])


def _estado_do_lead(fila_row, copy_row, abordagem):
    if abordagem:
        return "respondeu" if abordagem.get("respondido_em") else "enviado"
    status = str((fila_row or {}).get("status") or "")
    if status in ("pendente", "enviando"):
        return "na_fila"
    if status in ("falha", "duplicado", "bloqueado"):
        return status
    if status == "enviado":
        # Fila diz enviado e nao ha abordagem: banco anterior a semeadura, ou
        # linha gravada antes desta versao. Enviado continua sendo a verdade.
        return "enviado"
    return "copy_pronta" if copy_row else "sem_copy"


def _linha(lead, tel, fila_row, copy_row, abordagem, bloqueado, liberado):
    from scrapers import cloud_store

    estado = _estado_do_lead(fila_row, copy_row, abordagem)
    fonte = fila_row or copy_row or {}
    mensagem = (fonte.get("mensagem") or "").strip() or None
    if abordagem:
        # O que saiu manda sobre o que esta guardado: e o texto que o lead leu.
        mensagem = abordagem.get("mensagem") or mensagem
    return {
        "id": lead.get("id") or cloud_store.lead_id(lead),
        "nome": lead.get("nome") or "",
        "telefone": tel,
        "telefone_bruto": lead.get("telefone") or "",
        "cidade": lead.get("cidade") or "",
        "uf": lead.get("estado") or "",
        "categoria": lead.get("categoria") or "",
        "score": lead.get("score_oportunidade"),
        "estado": estado,
        "mensagem": mensagem,
        "copy_origem": (fonte.get("copy_origem") or (abordagem or {}).get("copy_origem")),
        "copy_versao": (fonte.get("copy_versao") or (abordagem or {}).get("copy_versao")),
        "editada": bool(fonte.get("editada_em")),
        "disparo_ativo": liberado,
        "bloqueado": bloqueado,
        "apto": bool(estado == "copy_pronta" and liberado and not bloqueado),
        "fila_id": (fila_row or {}).get("id"),
        "melhor_envio": (fila_row or {}).get("agendado_para"),
        "timing_motivo": (fila_row or {}).get("timing_motivo") or "",
        "abordagem_id": (abordagem or {}).get("id"),
        "enviado_em": (abordagem or {}).get("enviado_em"),
        "respondido_em": (abordagem or {}).get("respondido_em"),
        "erro": (fila_row or {}).get("erro"),
    }


def montar_linhas(limite=500):
    """Cruza leads x copy x fila x abordagem. Quatro consultas, nao uma por lead."""
    from scrapers import cloud_store, disparo, disparo_abordagens, disparo_copys

    leads = leads_do_disparo(limite=limite)
    copys = disparo_copys.mapa()
    abordagens = disparo_abordagens.mapa_por_telefone()
    bloqueados = disparo.telefones_bloqueados()
    fila = {}
    for row in disparo.listar(limite=2000):
        # Da mais nova pra mais velha: listar() ja vem por id DESC, entao a
        # primeira que aparece por telefone e a linha que vale.
        fila.setdefault(row["telefone"], row)

    linhas = []
    vistos = set()
    for lead in leads:
        tel = disparo._norm_phone(lead.get("telefone"))
        if not tel or tel in vistos:
            continue
        vistos.add(tel)
        linhas.append(_linha(lead, tel, fila.get(tel), copys.get(tel),
                             abordagens.get(tel), tel in bloqueados,
                             cloud_store.disparo_liberado(lead)))
    return linhas


@router.get("/api/disparo/leads")
def api_disparo_leads(estado: str = "", busca: str = "", limite: int = 500):
    """A tabela da aba Disparo. estado aceita varios separados por virgula."""
    linhas = montar_linhas(limite=min(500, max(1, int(limite))))

    totais = {e: 0 for e in ESTADOS}
    for linha in linhas:
        totais[linha["estado"]] = totais.get(linha["estado"], 0) + 1

    filtros = [e.strip() for e in (estado or "").split(",") if e.strip()]
    if filtros:
        linhas = [linha for linha in linhas if linha["estado"] in filtros]
    q = (busca or "").strip().lower()
    if q:
        linhas = [linha for linha in linhas
                  if q in linha["nome"].lower() or q in linha["telefone"]
                  or q in linha["cidade"].lower()]

    return {"total": len(linhas), "totais": totais,
            "aptos": sum(1 for linha in linhas if linha["apto"]),
            "leads": linhas}


# Ordem em que um motivo ganha do outro quando o lead cai em mais de um. E de
# ciclo de vida, do fim pro comeco: quem ja recebeu nao volta a ser "sem copy".
_MOTIVOS = ("ja_abordado", "ja_na_fila", "bloqueado", "desligado", "sem_copy")


def _motivo_de_fora(linha):
    if linha["estado"] in ("enviado", "respondeu"):
        return "ja_abordado"
    if linha["estado"] in ("na_fila", "falha", "duplicado"):
        return "ja_na_fila"
    if linha["bloqueado"] or linha["estado"] == "bloqueado":
        return "bloqueado"
    if not linha["disparo_ativo"]:
        return "desligado"
    return "sem_copy"


def enfileirar_aptos(origem="iniciar"):
    """Carrega a fila com os leads aptos, e diz quem ficou de fora e por que.

    Este e o passo que faltava entre "criar copy" e "iniciar disparo": o botao
    de enfileirar a mao saiu da tela por decisao do fundador, e com ele foi
    embora o unico caminho de um lead com copy pronta chegar na fila. O motor
    passou a ligar em cima de fila vazia e a nao mandar nada, sem erro nenhum.

    Quem decide o que e apto NAO e este arquivo duas vezes: a definicao mora em
    _linha() ("apto") e a tela consome a mesma. Se divergissem, a lista diria
    que 29 estao prontos e a fila receberia outro numero.

    A fila e a tabela `fila` que ja existia. Ela continua sendo a ordem de
    servico, e o anti-duplicata dela (numero na fila, numero ja abordado,
    numero bloqueado) segue valendo por cima do que for mandado daqui.
    """
    from scrapers import disparo

    linhas = montar_linhas()
    itens, fora = [], {m: 0 for m in _MOTIVOS}
    for linha in linhas:
        if linha["apto"]:
            itens.append({"nome": linha["nome"], "telefone": linha["telefone"],
                          "mensagem": linha["mensagem"],
                          "copy_origem": linha["copy_origem"] or "ia",
                          "copy_versao": linha["copy_versao"] or "",
                          # A categoria alimenta o agendamento por nicho que o
                          # socio pos no enfileirar: sem ela todo lead cairia
                          # no horario generico.
                          "categoria": linha["categoria"] or ""})
        else:
            fora[_motivo_de_fora(linha)] += 1
    enfileirados = disparo.enfileirar(itens, origem=origem) if itens else 0
    return {"enfileirados": enfileirados, "aptos": len(itens),
            "total": len(linhas), "fora": fora}
