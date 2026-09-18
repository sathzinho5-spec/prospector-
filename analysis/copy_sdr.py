# proposito: copy do SDR pro disparador: mensagem por nicho, na voz de quem envia
"""
SDR Copywriter - motor de mensagens do disparador.
Base: skill copywriter-expert (resposta direta, roteiro por nicho).

Regras aplicadas (sempre, IA ou local):
1. Voz de quem envia (time de marketing, nunca "eu analisei seu perfil")
2. Sem travessao - usar virgula ou dois-pontos
3. Nunca justificar preco baixo
4. Ajudar, nao auditar (apontar caminho, nao listar defeitos)
5. Terminar em pergunta
6. Implicacao da dor (o que ele perde), sem demonstracao longa
7. Uma ideia por mensagem, curta para WhatsApp
"""
import json
import re

import requests

# Angulo de dor/promessa por nicho (base do roteiro)
NICHE_ANGLES = {
    "restaurantes": {"dor": "mesas vazias no meio da semana", "promessa": "movimento no salao e no delivery"},
    "bares": {"dor": "casa vazia nos dias fracos", "promessa": "noites cheias recorrentes"},
    "hamburguerias": {"dor": "depender so do iFood e pagar taxa alta", "promessa": "pedido direto com margem cheia"},
    "pizzarias": {"dor": "depender so do iFood e pagar taxa alta", "promessa": "pedido direto com margem cheia"},
    "cafeterias": {"dor": "cliente que passa na porta e nao entra", "promessa": "fluxo constante de manha e tarde"},
    "acai": {"dor": "vender so no verao e no calor", "promessa": "venda o ano todo"},
    "beleza": {"dor": "cliente novo que gosta do trabalho, nao acha os servicos nem como falar, e vai no proximo",
               "promessa": "servicos, fotos dos trabalhos, endereco e WhatsApp num link so"},
    "barbearias": {"dor": "quem descobre a barbearia e nao acha preco, horario nem como marcar",
                   "promessa": "servicos, precos, horario e WhatsApp num link so"},
    "estetica": {"dor": "quem pergunta procedimento e preco no direct e desiste antes de marcar avaliacao",
                 "promessa": "procedimentos, resultados, endereco e WhatsApp num link so"},
    "academias": {"dor": "aluno que cancela em 3 meses", "promessa": "matricula e retencao constantes"},
    "padarias": {"dor": "concorrer so por preco com mercado", "promessa": "cliente fiel do bairro que paga mais"},
    "petshop": {"dor": "tutor que compra racao no mercado", "promessa": "tutor fiel com compra recorrente"},
    "advocacia": {"dor": "depender de indicacao para fechar caso", "promessa": "casos qualificados todo mes"},
    "imobiliarias": {"dor": "lead frio que nao responde", "promessa": "visitas agendadas com comprador pronto"},
    "odontologia": {"dor": "orcamento que o paciente nao fecha", "promessa": "agenda de avaliacoes cheia"},
    "moda": {"dor": "estoque parado e promocao que come a margem", "promessa": "giro de estoque com margem"},
    "mecanica": {"dor": "oficina vazia fora de epoca de revisao", "promessa": "carro na rampa o mes todo"},
    "moveis": {"dor": "orcamento que esfria e nunca fecha", "promessa": "projetos fechados com entrada"},
    "cursos": {"dor": "turma que nao enche", "promessa": "turmas cheias todo ciclo"},
    "farmacias": {"dor": "concorrer com rede grande no preco", "promessa": "cliente do bairro comprando todo mes"},
    "reformas": {"dor": "orcamento que vira so comparacao de preco", "promessa": "obras fechadas com sinal"},
    "limpeza": {"dor": "cliente que contrata uma vez e some", "promessa": "contratos recorrentes mensais"},
    "floricultura": {"dor": "vender so em datas comemorativas", "promessa": "pedidos toda semana"},
    "fotografia": {"dor": "depender de indicacao para fechar ensaio", "promessa": "ensaios agendados com entrada"},
}

GENERICO = {"dor": "cliente que pesquisa e escolhe o concorrente", "promessa": "ser encontrado primeiro e fechar mais"}


def _angle(niche_id, categoria):
    if niche_id and niche_id in NICHE_ANGLES:
        return NICHE_ANGLES[niche_id]
    cat = (categoria or "").lower()
    for nid, a in NICHE_ANGLES.items():
        if nid in cat or cat in nid:
            return a
    return GENERICO


def _sem_travessao(texto):
    return texto.replace("—", ",").replace("–", ",")


def _dados_ricos(business):
    """Tudo que a mineracao ja sabe e o copywriter precisa pra personalizar.
    Antes iam so 8 campos rasos; score, estrategia e oportunidades ficavam de
    fora e toda mensagem saia generica."""
    dados = {k: business.get(k) for k in ("nome", "categoria", "nota", "avaliacoes",
                                          "cidade", "estado", "website", "telefone")}
    for k in ("score_oportunidade", "score_ajustado", "score_motivo", "nivel_ia",
              "nivel", "estrategia_resumo", "descricao", "horarios", "endereco"):
        v = business.get(k)
        if v not in (None, ""):
            dados[k] = v
    for k in ("oportunidades_ia", "oportunidades", "atributos"):
        v = business.get(k)
        if isinstance(v, list) and v:
            dados[k] = v[:4]
        elif v:
            dados[k] = v
    return {k: v for k, v in dados.items() if v not in (None, "")}


def _violacoes(msg):
    """Regras da skill que da pra checar por codigo. Modelo pequeno viola direto;
    sem isso a validacao era so promessa no prompt."""
    problemas = []
    t = (msg or "").strip()
    if not t:
        return ["vazia"]
    if "—" in t or "–" in t:
        problemas.append("travessao proibido")
    if len(t.split()) > 95:
        problemas.append("passou de 90 palavras")
    if not t.rstrip().endswith("?"):
        problemas.append("nao termina em pergunta")
    return problemas


def _local_sequencia(business, niche_id=None):
    nome = business.get("nome") or "aí"
    cidade = (business.get("cidade") or "").strip()
    nota = business.get("nota")
    av = business.get("avaliacoes")
    site = business.get("website")
    ang = _angle(niche_id, business.get("categoria"))

    dado = f"nota {nota} com {av} avaliações no Google" if nota else "presença no Google Maps"
    sem_site = not site
    # Cidade vem vazia na carteira. Sem ela a frase perde o trecho, nunca vira "sua região".
    onde = f" em {cidade}" if cidade else ""

    abertura = (
        f"Olá, tudo bem? Aqui é do time de marketing para negócios locais. "
        f"Vi {nome} no Google, {dado}, parabéns pelo trabalho. "
        f"Reparei que {('vocês ainda não têm um site próprio, então quem pesquisa acaba caindo no concorrente' if sem_site else 'dá para transformar essas buscas em muito mais contato')}. "
        f"A gente resolve exatamente isso para {ang['dor']}: {ang['promessa']}. "
        f"Quer ver um exemplo de como isso ficaria para vocês?"
    )

    followup = (
        f"Oi, passando rapidinho. Muitos negócios{onde} perdem cliente todo dia "
        f"simplesmente porque não aparecem direito quando alguém pesquisa. "
        f"Montei um exemplo de como isso ficaria para {nome}. "
        f"Quer que eu te envie?"
    )

    fechamento = (
        f"Última mensagem, prometo. Se {ang['dor']} é algo que incomoda aí, "
        f"vale pelo menos olhar o exemplo que montei para vocês. "
        f"Se não fizer sentido, te deixo em paz. Topa receber?"
    )

    return {
        "engine": "local",
        "alavanca": f"dor: {ang['dor']} / promessa: {ang['promessa']}",
        "abertura": _sem_travessao(abertura),
        "followup": _sem_travessao(followup),
        "fechamento": _sem_travessao(fechamento),
    }


SEQUENCIA_PROMPT = """Voce e um copywriter de resposta direta e um closer B2B de marketing digital no Brasil.
Monte uma sequencia de abordagem WhatsApp para o negocio abaixo.

Dados do negocio: {dados}
Nichos e angulo: dor = "{dor}", promessa = "{promessa}".

REGRAS OBRIGATORIAS (se violar, a resposta e invalida):
1. Voz de quem envia (time de marketing), nunca dizer que auditou o perfil
2. PROIBIDO usar travessao (— ou –). Use virgula ou dois-pontos
3. Nunca justificar preco nem falar de valores
4. Ajudar, nao auditar: apontar UM caminho, nao listar defeitos
5. Cada mensagem TERMINA em pergunta
6. Implicar a dor (o que ele perde se nao agir), sem demonstracao longa
7. Maximo 90 palavras por mensagem
8. PERSONALIZAR DE VERDADE: citar pelo menos UM dado especifico do lead
   (nota, avaliacoes, cidade, score, estrategia). Proibido texto que serviria
   para qualquer empresa do nicho trocando so o nome.

Responda SOMENTE com JSON valido:
{
  "alavanca": "dor e promessa usadas em 1 linha",
  "abertura": "primeira mensagem",
  "followup": "mensagem de 2 dias depois",
  "fechamento": "ultima mensagem (break-up)"
}"""


def _montar_prompt_sequencia(settings):
    """Prompt da abordagem: customizado pelo usuario ou padrao da skill.

    Espelha analysis.copy_fechamento._montar_prompt: se o prompt colado nao
    trouxer os marcadores, eles sao acrescentados no fim, senao a IA receberia
    o pedido sem os dados do lead e sem o angulo do nicho.
    """
    base = (settings.get("abordagem_prompt") or "").strip() or SEQUENCIA_PROMPT
    if "{dados}" not in base:
        base += "\n\nDados do negocio: {dados}"
    if "{dor}" not in base or "{promessa}" not in base:
        base += '\n\nAngulo do nicho: dor = "{dor}", promessa = "{promessa}".'
    return base


def gerar_sequencia(business, settings, niche_id=None):
    api_key = (settings.get("openai_api_key") or "").strip()
    ang = _angle(niche_id, business.get("categoria"))
    try:
        from analysis.analyzer import TONS
        tom_txt = TONS.get((settings.get("disparo_tom") or "direto").lower(), "")
    except Exception:
        tom_txt = ""
    if api_key:
        try:
            base_url = settings.get("openai_base_url", "https://api.openai.com/v1").rstrip("/")
            model = settings.get("openai_model", "gpt-4o-mini")
            dados = _dados_ricos(business)
            prompt = (_montar_prompt_sequencia(settings)
                      .replace("{dados}", json.dumps(dados, ensure_ascii=False))
                      .replace("{dor}", ang["dor"])
                      .replace("{promessa}", ang["promessa"]))
            if tom_txt:
                prompt += "\n\nTom obrigatório: " + tom_txt

            def _chamar(prompt_txt):
                resp = requests.post(
                    f"{base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"model": model,
                          "messages": [{"role": "user", "content": prompt_txt}],
                          "temperature": 0.7},
                    timeout=60,
                )
                if resp.status_code != 200:
                    return None
                content = resp.json()["choices"][0]["message"]["content"]
                content = re.sub(r"^```(json)?|```$", "", content.strip()).strip()
                return json.loads(content)

            data = _chamar(prompt)
            # Uma chance de conserto: devolve SO as regras violadas, nao o
            # prompt todo. Resolve travessao, tamanho e pergunta sem pagar
            # outra geracao do zero.
            if data:
                ruins = [k for k in ("abertura", "followup", "fechamento")
                         if data.get(k) and _violacoes(data[k])]
                if ruins and len(str(prompt)) < 12000:
                    fix = (prompt + "\n\nSua resposta violou estas regras: " +
                           "; ".join(sorted({v for k in ruins for v in _violacoes(data[k])})) +
                           ". Reescreva SOMENTE o mesmo JSON corrigido.")
                    try:
                        data2 = _chamar(fix)
                        if data2 and all(data2.get(k) for k in ("abertura", "followup", "fechamento")):
                            data = data2
                    except Exception:
                        pass
            if data:
                data["engine"] = "groq/openai"
                for k in ("abertura", "followup", "fechamento"):
                    if data.get(k):
                        data[k] = _sem_travessao(data[k])
                if data.get("abertura"):
                    return data
        except Exception:
            pass
    return _local_sequencia(business, niche_id)
