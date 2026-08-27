import json
import re
from collections import Counter

import requests

POSITIVE = [
    "ótimo", "otimo", "excelente", "incrível", "maravilhoso", "perfeito", "amor", "amei",
    "adorei", "delicioso", "top", "melhor", "recomendo", "lindo", "linda", "bonito", "bonita",
    "qualidade", "atendimento", "parabéns", "sucesso", "gratidão", "agradecido", "espetacular",
    "fantástico", "impressionante", "premium", "exclusivo", "lançamento", "novidade",
    "encantadora", "encantador", "charme", "estilo",
]

NEGATIVE = [
    "ruim", "péssimo", "horrível", "demora", "caro", "não recomendo", "decepcionado",
    "decepcionada", "problema", "falha", "erro", "lamentável", "triste", "nunca mais",
    "atraso", "reclamação", "frustrante",
]


def _build_metrics(posts):
    likes = [p.get("curtidas", 0) for p in posts]
    comments = [p.get("comentarios", 0) for p in posts]
    return {
        "posts_analisados": len(posts),
        "media_curtidas": round(sum(likes) / len(likes)) if likes else 0,
        "media_comentarios": round(sum(comments) / len(comments)) if comments else 0,
        "total_curtidas": sum(likes),
        "total_comentarios": sum(comments),
    }


def _top_hashtags(captions, limit=10):
    counter = Counter(re.findall(r"#([\wÀ-ú]+)", captions, re.UNICODE))
    return [{"hashtag": f"#{h}", "qtd": c} for h, c in counter.most_common(limit)]


def local_analysis(nome, profile, posts, saved):
    captions = " ".join(p.get("legenda", "") for p in posts).lower()
    pos = sum(captions.count(w) for w in POSITIVE)
    neg = sum(captions.count(w) for w in NEGATIVE)
    total = pos + neg
    score = round(pos / total * 100) if total else 50

    hashtags = _top_hashtags(captions)
    metrics = _build_metrics(posts)

    if not posts:
        resumo = f"Nenhuma postagem pública disponível para análise de {nome}."
        sugestoes = ["Verifique se o perfil é público ou forneça o @ correto."]
    else:
        resumo = (
            f"Análise local de {nome} ({profile.get('username')}): {len(posts)} postagens avaliadas, "
            f"média de {metrics['media_curtidas']} curtidas e {metrics['media_comentarios']} comentários por post. "
            f"Índice de positividade nas legendas: {score}%."
        )
        sugestoes = [
            "Manter frequência consistente de posts para engajamento contínuo.",
            "Usar as hashtags de maior alcance identificadas em todas as publicações.",
            "Responder comentários para aumentar a taxa de interação.",
            "Criar conteúdo de bastidores para humanizar a marca.",
        ]

    return {
        "engine": "local",
        "nome": nome,
        "resumo": resumo,
        "score_positividade": score,
        "tom_de_voz": _detect_tone(captions),
        "hashtags": hashtags,
        "pontos_fortes": _strong_points(score, metrics),
        "sugestoes": sugestoes,
        "metricas": metrics,
        "conteudos_baixados": saved,
    }


def _detect_tone(captions):
    if not captions:
        return "Não identificado (sem legendas disponíveis)."
    lower = captions
    if any(w in lower for w in ["promo", "oferta", "desconto", "frete", "compre", "garanta"]):
        return "Comercial/promocional"
    if any(w in lower for w in ["dica", "tutorial", "aprenda", "passo a passo", "como fazer"]):
        return "Educativo/informativo"
    if any(w in lower for w in ["amor", "gratidão", "obrigado", "cliente", "time", "familia"]):
        return "Emocional/relacionamento"
    return "Institucional"


def _strong_points(score, metrics):
    points = []
    if score >= 70:
        points.append("Legendas com forte sentimento positivo e boa reputação.")
    elif score >= 45:
        points.append("Sentimento majoritariamente neutro/positivo nas legendas.")
    else:
        points.append("Muitos termos negativos nas legendas — atenção à reputação.")
    if metrics.get("media_comentarios", 0) > 0:
        points.append("Público comenta e interage (taxa de resposta no feed).")
    if metrics.get("posts_analisados", 0) >= 8:
        points.append("Volume saudável de conteúdo recente para análise.")
    return points


def ai_analysis(nome, profile, posts, settings):
    api_key = settings.get("openai_api_key", "").strip()
    if not api_key:
        raise ValueError("Sem chave de API configurada.")

    base_url = settings.get("openai_base_url", "https://api.openai.com/v1").rstrip("/")
    model = settings.get("openai_model", "gpt-4o-mini")

    posts_for_prompt = [
        {"legenda": p.get("legenda", "")[:600], "curtidas": p.get("curtidas", 0), "comentarios": p.get("comentarios", 0)}
        for p in posts[:15]
    ]

    prompt = f"""
Você é um analista de marketing digital especialista em Instagram.
Analise o perfil abaixo e produza um relatório estratégico completo.

Empresa analisada: {nome}
Perfil do Instagram: @{profile.get('username', '')}
Biografia: {profile.get('biografia', '')}
Seguidores: {profile.get('seguidores', 0)}
Total de posts: {profile.get('total_posts', 0)}
Verificado: {profile.get('verificado', False)} | Conta de negócio: {profile.get('conta_negocio', False)} | Categoria: {profile.get('categoria', '')}

Postagens recentes:
{json.dumps(posts_for_prompt, ensure_ascii=False, indent=2)}

Responda SOMENTE com JSON válido no formato:
{{
  "resumo": "resumo geral de 2-4 frases sobre a presença digital da empresa",
  "score_positividade": 0 a 100,
  "tom_de_voz": "descrição do tom",
  "pontos_fortes": ["lista"],
  "sugestoes": ["lista de melhorias concretas"],
  "conteudo_recomendado": ["3-5 ideias de conteúdo"],
  "hashtags_recomendadas": ["5 hashtags"]
}}
"""

    resp = requests.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.4,
        },
        timeout=60,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"IA retornou HTTP {resp.status_code}: {resp.text[:300]}")

    content = resp.json()["choices"][0]["message"]["content"]
    content = re.sub(r"^```(json)?|```$", "", content.strip()).strip()
    data = json.loads(content)

    return {
        "engine": "openai",
        "modelo": model,
        "nome": nome,
        **data,
        "metricas": _build_metrics(posts),
        "hashtags": _top_hashtags(" ".join(p.get("legenda", "") for p in posts)),
    }


def build_report(nome, profile, posts, saved, settings):
    try:
        return ai_analysis(nome, profile, posts, settings)
    except Exception as local_fallback_exc:
        report = local_analysis(nome, profile, posts, saved)
        if settings.get("openai_api_key"):
            report["erro_ia"] = str(local_fallback_exc)
        return report


# ==================== ANALISE ESTRATEGICA DO NEGOCIO ====================

STRATEGY_PROMPT = """Voce e um consultor estrategico de marketing digital B2B no Brasil.
Analise o negocio abaixo (dados coletados do Google Maps e do site dele) e produza um
relatorio de PROSPECCAO: o objetivo e avaliar se esse negocio e um bom cliente para
servicos de marketing digital e como abordá-lo.

Dados do negocio:
{dados}

Responda SOMENTE com JSON valido no formato:
{{
  "resumo": "2-3 frases sobre a situacao do negocio",
  "score_oportunidade": 0 a 100,
  "nivel": "Alto" | "Medio" | "Baixo",
  "presenca_digital": ["constatos curtos: site, redes sociais, reputacao"],
  "oportunidades": ["3-6 oportunidades concretas de servico para oferecer"],
  "abordagem": "como abordar esse dono na primeira conversa (2-3 frases)",
  "acoes_imediatas": ["3-5 acoes praticas"]
}}"""


def _local_strategy(business):
    score = 35
    oportunidades = []
    presenca = []

    reviews = 0
    try:
        reviews = int(str(business.get("avaliacoes") or "0").replace(".", "").replace(",", ""))
    except Exception:
        pass
    nota = 0.0
    try:
        nota = float(str(business.get("nota") or "0").replace(",", "."))
    except Exception:
        pass

    if not business.get("website"):
        oportunidades.append("Nao tem site proprio — oferta de criacao de site / landing page.")
        score += 20
    else:
        presenca.append("Possui site propio cadastrado no Google.")

    if reviews < 30:
        oportunidades.append(f"Poucas avaliacoes ({reviews}) — campanha de reputacao e captação de reviews.")
        score += 15
    else:
        presenca.append(f"{reviews} avaliacoes no Google (reputacao ativa).")

    if nota and nota < 4.3:
        oportunidades.append(f"Nota {str(business.get('nota'))} — trabalho de gestao de reputacao e resposta a clientes.")
        score += 10

    if business.get("telefone"):
        presenca.append("Telefone visivel no Google (canal direto de contato).")

    servicos = business.get("atributos") or []
    if not servicos:
        oportunidades.append("Sem servicos preenchidos no perfil (delivery/retirada) — otimizacao de ficha no Google.")
        score += 8

    if business.get("horarios"):
        presenca.append("Horarios configurados no perfil.")

    if not oportunidades:
        oportunidades.append("Perfil bem cuidado — focar em trafego pago e conteudo para escalar.")

    score = max(10, min(95, score))
    nivel = "Alto" if score >= 70 else ("Medio" if score >= 45 else "Baixo")

    return {
        "engine": "local",
        "resumo": f"{business.get('nome')} ({business.get('categoria') or 'negocio local'}) em "
                  f"{business.get('cidade') or business.get('estado') or 'Brasil'} — nota {business.get('nota') or 'N/A'} "
                  f"com {reviews} avaliacoes.",
        "score_oportunidade": score,
        "nivel": nivel,
        "presenca_digital": presenca or ["Presenca digital limitada."],
        "oportunidades": oportunidades,
        "abordagem": "Apresente-se mostrando um ponto especifico do perfil deles (ex: numero de avaliacoes ou ausencia de site) "
                     "e ofereca uma analise gratuita de 10 minutos.",
        "acoes_imediatas": [
            "Ligar/WhatsApp apresentando-se com um dado concreto do perfil deles.",
            "Montar mini-auditoria gratuita do Google Maps do concorrente mais bem avaliado.",
            "Oferecer pacote inicial: otimizacao de ficha + captura de reviews.",
        ],
    }


def business_strategy(business, settings):
    api_key = (settings.get("openai_api_key") or "").strip()
    if api_key:
        try:
            base_url = settings.get("openai_base_url", "https://api.openai.com/v1").rstrip("/")
            model = settings.get("openai_model", "gpt-4o-mini")

            dados = {
                k: business.get(k)
                for k in ("nome", "categoria", "nota", "avaliacoes", "endereco", "cidade",
                          "estado", "telefone", "website", "status_funcionamento",
                          "preco", "atributos", "consulta")
            }
            resp = requests.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": STRATEGY_PROMPT.replace("{dados}", json.dumps(dados, ensure_ascii=False, indent=2))}],
                    "temperature": 0.4,
                },
                timeout=60,
            )
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                content = re.sub(r"^```(json)?|```$", "", content.strip()).strip()
                data = json.loads(content)
                data["engine"] = "groq/openai"
                data["modelo"] = model
                return data
        except Exception:
            pass

    return _local_strategy(business)


# ==================== PROPOSTA COMERCIAL ====================

PROPOSAL_PROMPT = """Voce e um consultor de marketing digital montando uma proposta comercial
para o negocio abaixo (dados do Google Maps e site).

Dados:
{dados}

Gere uma proposta objetiva e persuasiva. Responda SOMENTE com JSON valido:
{{
  "diagnostico": ["3-4 problemas/oportunidades especificas detectadas"],
  "solucao": ["3-4 servicos recomendados, cada um em 1 linha"],
  "plano": [
    {{"fase": "Fase 1 (0-30 dias)", "itens": ["..."]}},
    {{"fase": "Fase 2 (30-60 dias)", "itens": ["..."]}},
    {{"fase": "Fase 3 (60-90 dias)", "itens": ["..."]}}
  ],
  "resultado_esperado": "1-2 frases sobre o resultado esperado em 90 dias",
  "cta": "frase final de fechamento com chamada para acao"
}}"""


def _local_proposal(business):
    nome = business.get("nome") or "seu negócio"
    strategy = _local_strategy(business)

    diagnostico = strategy.get("oportunidades", [])[:4]
    if not diagnostico:
        diagnostico = ["Presença digital pode ser expandida."]

    solucao = [
        "Otimização completa do perfil no Google Maps (fotos, descrição, serviços).",
        "Rotina de captação de avaliações para subir a nota e a confiança.",
        "Criação de site/landing page focada em converter buscas locais.",
        "Conteúdo semanal no Instagram com abordagem local.",
    ]

    plano = [
        {"fase": "Fase 1 (0-30 dias)", "itens": ["Auditoria e correção do perfil no Google", "Configuração de canais de contato (WhatsApp)"]},
        {"fase": "Fase 2 (30-60 dias)", "itens": ["Lançamento do site/landing page", "Início da rotina de avaliações e conteúdo"]},
        {"fase": "Fase 3 (60-90 dias)", "itens": ["Campanhas locais de tráfego", "Relatório de resultados e ajustes"]},
    ]

    return {
        "engine": "local",
        "diagnostico": diagnostico,
        "solucao": solucao,
        "plano": plano,
        "resultado_esperado": f"Em 90 dias, {nome} com perfil otimizado, site no ar e rotina de avaliações ativa — mais ligações, mensagens e visitas.",
        "cta": "Podemos começar essa semana. Vamos ao primeiro passo?",
    }


def proposal(business, settings):
    api_key = (settings.get("openai_api_key") or "").strip()
    if api_key:
        try:
            base_url = settings.get("openai_base_url", "https://api.openai.com/v1").rstrip("/")
            model = settings.get("openai_model", "gpt-4o-mini")
            dados = {k: business.get(k) for k in ("nome", "categoria", "nota", "avaliacoes",
                                                   "cidade", "estado", "website", "telefone",
                                                   "status_funcionamento", "atributos")}
            resp = requests.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": PROPOSAL_PROMPT.replace("{dados}", json.dumps(dados, ensure_ascii=False, indent=2))}],
                    "temperature": 0.5,
                },
                timeout=60,
            )
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                content = re.sub(r"^```(json)?|```$", "", content.strip()).strip()
                data = json.loads(content)
                data["engine"] = "groq/openai"
                return data
        except Exception:
            pass

    return _local_proposal(business)

PITCH_PROMPT = """Voce e um closer de vendas B2B especializado em servicos de marketing digital no Brasil.
Com base nos dados do negocio abaixo, escreva uma abordagem de vendas personalizada.

Dados do negocio:
{dados}

Regras:
- Mensagem de WhatsApp: maximo 90 palavras, tom humano, citar 1 dado especifico do negocio
  (nota, ausencia de site, numero de avaliacoes etc) e terminar com pergunta leve.
- E-mail: assunto curto chamativo e corpo de no maximo 150 palavras.

Responda SOMENTE com JSON valido:
{{
  "whatsapp": "texto da mensagem",
  "email_assunto": "assunto",
  "email_corpo": "corpo do e-mail"
}}"""


def _local_pitch(business):
    nome = business.get("nome") or "aí"
    nota = business.get("nota")
    av = business.get("avaliacoes")
    site = business.get("website")

    dado = f"nota {nota} com {av} avaliações no Google" if nota else "presença no Google Maps"
    gancho = (
        "notei que vocês ainda não têm um site próprio — isso está deixando clientes irem pros concorrentes"
        if not site else "vi que vocês já têm site, mas dá pra extrair muito mais clientes dele"
    )

    whatsapp = (
        f"Olá, tudo bem? Falo do time de marketing digital. "
        f"Pesquisei {nome} no Google e {dado} — parabéns! "
        f"Mas {gancho}. "
        f"Trabalho colocando negócios como o seu na frente de quem está procurando agora. "
        f"Posso te mandar uma análise rápida e gratuita de como melhorar?"
    )

    assunto = f"{nome}: {av or 'vários'} clientes procurando você no Google (dica dentro)"
    corpo = (
        f"Olá!\n\nPesquisando {nome} no Google, encontrei {dado}. "
        f"{gancho.capitalize()}.\n\n"
        "Ajudo negócios locais a aparecerem primeiro no Google e transformarem buscas em clientes.\n\n"
        "Posso te enviar uma análise gratuita do seu perfil (sem compromisso)?\n\n"
        "Abraços!"
    )

    return {
        "engine": "local",
        "whatsapp": whatsapp,
        "email_assunto": assunto,
        "email_corpo": corpo,
    }


def pitch_message(business, settings):
    api_key = (settings.get("openai_api_key") or "").strip()
    if api_key:
        try:
            base_url = settings.get("openai_base_url", "https://api.openai.com/v1").rstrip("/")
            model = settings.get("openai_model", "gpt-4o-mini")
            dados = {k: business.get(k) for k in ("nome", "categoria", "nota", "avaliacoes",
                                                   "cidade", "estado", "website", "telefone")}
            resp = requests.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": PITCH_PROMPT.replace("{dados}", json.dumps(dados, ensure_ascii=False, indent=2))}],
                    "temperature": 0.7,
                },
                timeout=60,
            )
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                content = re.sub(r"^```(json)?|```$", "", content.strip()).strip()
                data = json.loads(content)
                data["engine"] = "groq/openai"
                return data
        except Exception:
            pass

    return _local_pitch(business)


# ==================== TREINADOR DE OBJECOES ====================

OBJECTION_PROMPT = """Voce e um closer de vendas B2B de marketing digital no Brasil.
O cliente disse a seguinte objecao durante a abordagem:

"{objecao}"

Dados do negocio: {dados}

Escreva uma resposta de 3-5 frases que: valide a preocupacao, desarma a objecao com
logica pratica, e termine com uma pergunta que reabre a conversa. Tom humano, sem jargoes.

Responda SOMENTE com JSON: {{"resposta": "..."}}"""


def _local_objection(objecao):
    o = objecao.lower()
    if "caro" in o or "preço" in o or "preco" in o or "verba" in o:
        return ("Entendo totalmente a preocupação com investimento. Só pra contextualizar: "
                "o custo de continuar invisível no Google costuma ser maior — cada cliente que "
                "busca e não encontra você vai pro concorrente. E o plano inicial é leve, pensado "
                "pra se pagar com os primeiros resultados. Se eu te mostrar o potencial com dados "
                "do seu próprio perfil, faz sentido dar uma olhada?")
    if "já tenho" in o or "ja tenho" in o or "outra agência" in o or "outra agencia" in o:
        return ("Que bom, então você já entendeu o valor do marketing! Justamente por isso: "
                "não vim substituir ninguém, vim complementar. Meu foco é uma coisa específica — "
                "transformar buscas locais em contato real. Posso fazer uma auditoria gratuita do "
                "que já existe? Se estiver ótimo, eu mesmo te digo.")
    if "tempo" in o or "ocupado" in o:
        return ("Sei como é a rotina puxada. Justamente por isso o processo é quase zero esforço "
                "pro seu lado: eu e minha equipe cuidamos de tudo e você só aprova o que for "
                "publicado. Te mando um resumo de 2 minutos pra você olhar quando der?")
    if "não" in o and ("interesse" in o or "quero" in o):
        return ("Fechado, respeito total! Vou deixar uma análise gratuita do seu perfil guardada "
                "aqui — é sua, sem compromisso. Posso te enviar pra você olhar com calma quando "
                "fizer sentido?")
    return ("Entendo seu ponto. Posso te fazer uma pergunta rápida? Se hoje um cliente busca pelo "
            "serviço que você oferece na sua região, ele te encontra em qual posição? Se a resposta "
            "não for 'o primeiro', é exatamente isso que eu resolvo. Quer ver como isso funciona "
            "na prática com dados do seu perfil?")


def handle_objection(business, objecao, settings):
    api_key = (settings.get("openai_api_key") or "").strip()
    if api_key:
        try:
            base_url = settings.get("openai_base_url", "https://api.openai.com/v1").rstrip("/")
            model = settings.get("openai_model", "gpt-4o-mini")
            dados = {k: business.get(k) for k in ("nome", "categoria", "nota", "avaliacoes", "cidade")}
            prompt = OBJECTION_PROMPT.replace("{objecao}", objecao) \
                                     .replace("{dados}", json.dumps(dados, ensure_ascii=False))
            resp = requests.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                },
                timeout=60,
            )
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                content = re.sub(r"^```(json)?|```$", "", content.strip()).strip()
                data = json.loads(content)
                data["engine"] = "groq/openai"
                return data
        except Exception:
            pass

    return {"engine": "local", "resposta": _local_objection(objecao)}