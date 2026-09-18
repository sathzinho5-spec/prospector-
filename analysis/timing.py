# proposito: melhor momento de envio por nicho: janela preferida e proximo slot
"""
Fase 1 da inteligencia de timing: tabela de janelas por nicho (quando o dono
atende) + calculo do proximo slot valido. Sem parser de horario e sem
aprendizado ainda: isso vem nas fases 2 e 3, que usam os campos que este
modulo ja grava (timing_motivo) e os eventos que o follow-up vai gerar.

dias usa dois valores de proposito: "uteis" (seg-sex) ou "todos". Janela
personalizada por dia da semana e fase 2.
"""
import datetime
import unicodedata

UTEIS = (0, 1, 2, 3, 4)
TODOS = (0, 1, 2, 3, 4, 5, 6)

# id do nicho -> janela preferida. ini/fim em "HH:MM", dias "uteis"|"todos".
# A regra e sempre a mesma: falar com o dono fora do rush dele.
JANELAS_PADRAO = {
    # Alimentacao fora de casa: dono some no almoco e no jantar.
    "restaurantes": {"ini": "14:30", "fim": "17:30", "dias": "todos", "motivo": "entre turnos"},
    "pizzarias": {"ini": "14:30", "fim": "17:30", "dias": "todos", "motivo": "entre turnos"},
    "hamburguerias": {"ini": "14:30", "fim": "17:30", "dias": "todos", "motivo": "entre turnos"},
    "bares": {"ini": "15:00", "fim": "18:00", "dias": "todos", "motivo": "antes do movimento"},
    "acai": {"ini": "14:30", "fim": "17:30", "dias": "todos", "motivo": "entre turnos"},
    "distribuidora": {"ini": "09:00", "fim": "11:00", "dias": "uteis", "motivo": "horario comercial"},
    # Manha: dono de padaria e cafeteria atende depois do rush das 7h-9h.
    "padarias": {"ini": "10:00", "fim": "12:00", "dias": "todos", "motivo": "depois do rush da manha"},
    "cafeterias": {"ini": "13:00", "fim": "16:00", "dias": "uteis", "motivo": "fora do pico"},
    # Escritorio e clinica: manha, antes do almoco e da agenda cheia.
    "advocacia": {"ini": "09:00", "fim": "11:00", "dias": "uteis", "motivo": "horario comercial"},
    "contabilidade": {"ini": "09:00", "fim": "11:00", "dias": "uteis", "motivo": "horario comercial"},
    "seguros": {"ini": "09:00", "fim": "11:00", "dias": "uteis", "motivo": "horario comercial"},
    "imobiliarias": {"ini": "09:00", "fim": "11:00", "dias": "uteis", "motivo": "horario comercial"},
    "odontologia": {"ini": "09:00", "fim": "11:00", "dias": "uteis", "motivo": "antes da agenda encher"},
    "estetica": {"ini": "09:00", "fim": "11:00", "dias": "uteis", "motivo": "antes da agenda encher"},
    "cursos": {"ini": "09:00", "fim": "11:00", "dias": "uteis", "motivo": "horario comercial"},
    "grafica": {"ini": "09:00", "fim": "11:00", "dias": "uteis", "motivo": "horario comercial"},
    "fotografia": {"ini": "10:00", "fim": "12:00", "dias": "uteis", "motivo": "horario comercial"},
    "reformas": {"ini": "09:00", "fim": "11:00", "dias": "uteis", "motivo": "antes de ir pra obra"},
    "limpeza": {"ini": "09:00", "fim": "11:00", "dias": "uteis", "motivo": "horario comercial"},
    # Varejo e servico de balcao: depois de abrir, antes do movimento.
    "moda": {"ini": "10:00", "fim": "12:00", "dias": "uteis", "motivo": "antes do movimento"},
    "moveis": {"ini": "10:00", "fim": "12:00", "dias": "uteis", "motivo": "antes do movimento"},
    "otica": {"ini": "10:00", "fim": "12:00", "dias": "uteis", "motivo": "antes do movimento"},
    "celular": {"ini": "10:00", "fim": "12:00", "dias": "uteis", "motivo": "antes do movimento"},
    "suplementos": {"ini": "10:00", "fim": "12:00", "dias": "uteis", "motivo": "antes do movimento"},
    "floricultura": {"ini": "10:00", "fim": "12:00", "dias": "uteis", "motivo": "antes do movimento"},
    "vidracaria": {"ini": "10:00", "fim": "12:00", "dias": "uteis", "motivo": "antes do movimento"},
    "mecanica": {"ini": "09:00", "fim": "11:00", "dias": "uteis", "motivo": "inicio do expediente"},
    "lavajato": {"ini": "09:00", "fim": "11:00", "dias": "uteis", "motivo": "inicio do expediente"},
    "farmacias": {"ini": "10:00", "fim": "12:00", "dias": "todos", "motivo": "antes do movimento"},
    "chaveiro": {"ini": "10:00", "fim": "12:00", "dias": "todos", "motivo": "horario calmo"},
    # Corpo e pet: entre os picos da manha e do fim de tarde.
    "academias": {"ini": "10:00", "fim": "12:00", "dias": "uteis", "motivo": "entre picos"},
    "petshop": {"ini": "10:00", "fim": "12:00", "dias": "uteis", "motivo": "entre picos"},
    # Hospedagem e festa: depois do check-out, antes do evento.
    "pousadas": {"ini": "10:00", "fim": "12:00", "dias": "todos", "motivo": "apos o check-out"},
    "buffet": {"ini": "10:00", "fim": "12:00", "dias": "uteis", "motivo": "horario comercial"},
}


def _norm(t):
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", str(t or ""))
        if unicodedata.category(c) != "Mn")
    return sem_acento.lower().strip()


def nicho_de(categoria):
    """categoria livre ('Padaria', 'Mecânica de Automóveis') -> id do nicho ou ''."""
    cat = _norm(categoria)
    if not cat:
        return ""
    from niches import NICHES

    for n in NICHES:
        if _norm(n["id"]) == cat:
            return n["id"]
    for n in NICHES:
        textos = [_norm(n["id"]), _norm(n["label"])]
        textos += [_norm(v) for v in n.get("variacoes", [])]
        for t in textos:
            if t and (t in cat or cat in t):
                return n["id"]
    return ""


def janela_para(categoria, settings):
    """(ini, fim, dias, motivo, origem). Origem: config, nicho ou geral."""
    settings = settings or {}
    nicho = nicho_de(categoria)
    salvas = settings.get("timing_janelas") or {}
    if nicho and isinstance(salvas.get(nicho), dict):
        s = salvas[nicho]
        ini = str(s.get("ini") or "").strip() or "09:00"
        fim = str(s.get("fim") or "").strip() or "18:00"
        dias = s.get("dias") if s.get("dias") in ("uteis", "todos") else "uteis"
        return ini, fim, dias, "janela que voce ajustou", "config"
    if nicho and nicho in JANELAS_PADRAO:
        j = JANELAS_PADRAO[nicho]
        return j["ini"], j["fim"], j["dias"], j["motivo"], "nicho"
    ini = str(settings.get("disparo_hora_ini") or "08:00")
    fim = str(settings.get("disparo_hora_fim") or "20:00")
    return ini, fim, "todos", "janela geral", "geral"


def _dias_permitidos(dias):
    return UTEIS if dias == "uteis" else TODOS


def proximo_envio_em(categoria, settings, agora=None):
    """'YYYY-MM-DD HH:MM:SS' do proximo slot valido + motivo curto pra tela.

    Nunca volta vazio: no pior caso, o comeco da janela geral de amanha."""
    agora = agora or datetime.datetime.now()
    ini, fim, dias, motivo, _origem = janela_para(categoria, settings)
    permitidos = _dias_permitidos(dias)

    def hm(hora):
        try:
            h, m = hora.split(":")
            return int(h), int(m)
        except Exception:
            return 9, 0

    h_ini, m_ini = hm(ini)
    h_fim, m_fim = hm(fim)
    for salto in range(9):
        dia = agora + datetime.timedelta(days=salto)
        if dia.weekday() not in permitidos:
            continue
        abre = dia.replace(hour=h_ini, minute=m_ini, second=0, microsecond=0)
        fecha = dia.replace(hour=h_fim, minute=m_fim, second=0, microsecond=0)
        if salto == 0:
            if agora < abre:
                return abre.strftime("%Y-%m-%d %H:%M:%S"), motivo
            if agora <= fecha:
                slot = agora.replace(second=0, microsecond=0)
                return slot.strftime("%Y-%m-%d %H:%M:%S"), motivo
            continue
        return abre.strftime("%Y-%m-%d %H:%M:%S"), motivo
    amanha = (agora + datetime.timedelta(days=1)).replace(
        hour=9, minute=0, second=0, microsecond=0)
    return amanha.strftime("%Y-%m-%d %H:%M:%S"), "janela geral"
