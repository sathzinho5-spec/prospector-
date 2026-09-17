# proposito: copy de estrategia e de proposta comercial, com prompt e fallback local
import json
import re

import requests

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
