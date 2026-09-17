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
    "beleza": {"dor": "agenda com buracos e cliente que some", "promessa": "agenda cheia com retorno garantido"},
    "barbearias": {"dor": "cadeira vazia e cliente que nao volta", "promessa": "cadeira ocupada a semana toda"},
    "estetica": {"dor": "depender de indicacao para fechar pacote", "promessa": "pacotes vendidos no automatico"},
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


def _local_sequencia(business, niche_id=None):
    nome = business.get("nome") or "aí"
    cidade = business.get("cidade") or "sua região"
    nota = business.get("nota")
    av = business.get("avaliacoes")
    site = business.get("website")
    ang = _angle(niche_id, business.get("categoria"))

    dado = f"nota {nota} com {av} avaliações no Google" if nota else "presença no Google Maps"
    sem_site = not site

    abertura = (
        f"Olá, tudo bem? Aqui é do time de marketing para negócios locais. "
        f"Vi {nome} no Google, {dado}, parabéns pelo trabalho. "
        f"Reparei que {('vocês ainda não têm um site próprio, então quem pesquisa acaba caindo no concorrente' if sem_site else 'dá para transformar essas buscas em muito mais contato')}. "
        f"A gente resolve exatamente isso para {ang['dor']}: {ang['promessa']}. "
        f"Posso te mandar uma análise rápida e gratuita do seu perfil?"
    )

    followup = (
        f"Oi, passando rapidinho. Muitos negócios em {cidade} estão perdendo cliente todo dia "
        f"simplesmente porque não aparecem direito quando alguém pesquisa. "
        f"Preparei 3 pontos práticos para {nome} melhorar isso ainda essa semana. "
        f"Quer que eu te envie?"
    )

    fechamento = (
        f"Última mensagem, prometo. Se {ang['dor']} é algo que incomoda aí, "
        f"vale pelo menos olhar a análise gratuita que montei para vocês. "
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

Responda SOMENTE com JSON valido:
{{
  "alavanca": "dor e promessa usadas em 1 linha",
  "abertura": "primeira mensagem",
  "followup": "mensagem de 2 dias depois",
  "fechamento": "ultima mensagem (break-up)"
}}"""


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
            dados = {k: business.get(k) for k in ("nome", "categoria", "nota", "avaliacoes",
                                                   "cidade", "estado", "website", "telefone")}
            prompt = (SEQUENCIA_PROMPT
                      .replace("{dados}", json.dumps(dados, ensure_ascii=False))
                      .replace("{dor}", ang["dor"])
                      .replace("{promessa}", ang["promessa"]))
            if tom_txt:
                prompt += "\n\nTom obrigatório: " + tom_txt
            resp = requests.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model,
                      "messages": [{"role": "user", "content": prompt}],
                      "temperature": 0.7},
                timeout=60,
            )
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                content = re.sub(r"^```(json)?|```$", "", content.strip()).strip()
                data = json.loads(content)
                data["engine"] = "groq/openai"
                for k in ("abertura", "followup", "fechamento"):
                    if data.get(k):
                        data[k] = _sem_travessao(data[k])
                return data
        except Exception:
            pass
    return _local_sequencia(business, niche_id)
