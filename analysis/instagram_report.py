# proposito: relatorio do perfil de Instagram: metricas, tom, pontos fortes e score
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
