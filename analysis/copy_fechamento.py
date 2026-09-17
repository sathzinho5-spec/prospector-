# proposito: copy de fechamento: pitch de abordagem e resposta a objecao
import json
import re

import requests

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

TONS = {
    "direto": "Tom DIRETO e objetivo: frases curtas, sem rodeios, vá ao ponto e feche com pergunta.",
    "consultivo": "Tom CONSULTIVO e parceiro: faça perguntas que façam o dono refletir, eduque sem vender.",
    "agressivo": "Tom AGRESSIVO de resposta direta: urgência, dor amplificada, prova e CTA forte. Sem ser desrespeitoso.",
    "amigavel": "Tom AMIGÁVEL e caloroso: conversa de bairro, empatia, leveza, como indicação de amigo.",
}


def _montar_prompt(settings):
    """Prompt do disparador: customizado pelo usuário ou padrão da skill + tom."""
    base = (settings.get("disparo_prompt") or "").strip() or PITCH_PROMPT
    tom = (settings.get("disparo_tom") or "direto").lower()
    instrucao = TONS.get(tom, TONS["direto"])
    if "{dados}" not in base:
        base += "\n\nDados do negocio:\n{dados}"
    return base + "\n\nTom obrigatório: " + instrucao


def _local_pitch(business):
    from analysis.copy_sdr import _angle

    nome = business.get("nome") or "aí"
    cidade = business.get("cidade") or "sua região"
    nota = business.get("nota")
    av = business.get("avaliacoes")
    site = business.get("website")
    ang = _angle(None, business.get("categoria"))

    dado = f"nota {nota} com {av} avaliações no Google" if nota else "presença no Google Maps"
    ponto = (
        "vocês ainda não têm um site próprio, então quem pesquisa acaba escolhendo o concorrente"
        if not site else "dá para transformar essas buscas em muito mais contato"
    )

    whatsapp = (
        f"Olá, tudo bem? Aqui é do time de marketing para negócios locais. "
        f"Vi {nome} no Google, {dado}, parabéns pelo trabalho. "
        f"Reparei que {ponto}. "
        f"A gente resolve exatamente isso para casos de {ang['dor']}: {ang['promessa']}. "
        f"Posso te mandar uma análise rápida e gratuita?"
    )

    assunto = f"{nome}: {ang['promessa']} em {cidade}?"
    corpo = (
        f"Olá!\n\nPesquisando {nome} no Google, encontrei {dado}. "
        f"Notei que {ponto}.\n\n"
        f"Trabalhamos com negócios que sofrem com {ang['dor']}, e o caminho costuma ser: {ang['promessa']}.\n\n"
        f"Posso te enviar uma análise gratuita do perfil, sem compromisso?\n\n"
        f"Abraços!"
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
            prompt = _montar_prompt(settings).replace("{dados}", json.dumps(dados, ensure_ascii=False, indent=2))
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

