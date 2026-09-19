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

from analysis import playbook_sdr

# Reexportado de proposito: a tabela de nichos mudou de arquivo, e estes quatro
# nomes seguem alcancaveis como copy_sdr._angle, como sempre foram.
from analysis.nichos_angulo import (APELIDOS, GENERICO,  # noqa: F401
                                    NICHE_ANGLES, _angle, _sem_acento)

def _sem_travessao(texto):
    return texto.replace("—", ",").replace("–", ",")


def _numero_legivel(campo, valor):
    """A nuvem guarda nota e avaliacoes como texto com decimal: '4.9' e '109.0'.
    Mandado assim pra IA, sai 'nota 4.9 com 109.0 avaliacoes' na mensagem, que e
    a cara de dado colado por robo. Avaliacao e contagem e nao tem casa decimal;
    nota tem, e no Brasil se escreve com virgula."""
    try:
        n = float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        return valor
    if campo == "avaliacoes":
        return str(int(round(n)))
    texto = ("%.1f" % n).rstrip("0").rstrip(".")
    return texto.replace(".", ",")


def _dados_ricos(business):
    """Tudo que a mineracao ja sabe e o copywriter precisa pra personalizar.
    Antes iam so 8 campos rasos; score, estrategia e oportunidades ficavam de
    fora e toda mensagem saia generica."""
    dados = {k: business.get(k) for k in ("nome", "categoria", "nota", "avaliacoes",
                                          "cidade", "estado", "website", "telefone")}
    for k in ("nota", "avaliacoes"):
        if dados.get(k) not in (None, ""):
            dados[k] = _numero_legivel(k, dados[k])
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

    # Frase pronta pra entrar depois de "Vi que voces tem", pra nao precisar de
    # emenda no meio do texto.
    dado = f"{nota} com {av} avaliações no Google" if nota else "uma presença boa no Google"
    sem_site = not site
    # Cidade vem vazia na carteira. Sem ela a frase perde o trecho, nunca vira "sua região".
    onde = f" em {cidade}" if cidade else ""

    # Sem apresentacao: a mensagem abre no nome da pessoa e num fato sobre o
    # negocio dela. Decisao do fundador em 18/09, e e a regra da versao 1.3 do
    # playbook. Quem abre se apresentando avisa que e abordagem comercial antes
    # de a pessoa chegar na parte que interessa.
    achou = ("fui procurar o site de vocês pra ver os serviços, não achei"
             if sem_site else "dei uma olhada em como vocês aparecem pra quem pesquisa")
    abertura = (
        f"Oi, {nome}, tudo bem? "
        f"Vi que vocês têm {dado} e {achou}. "
        f"A gente monta página com {ang['promessa']}. "
        f"Hoje, quando alguém descobre vocês e quer saber preço ou agendar, como é que faz?"
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
        "copy_versao": "local",
        "alavanca": f"dor: {ang['dor']} / promessa: {ang['promessa']}",
        "abertura": _sem_travessao(abertura),
        "followup": _sem_travessao(followup),
        "fechamento": _sem_travessao(fechamento),
    }


# O conhecimento minimo, pra quando o playbook nao chegou junto com a imagem.
# Nao e copia do playbook de proposito: e o resumo curto que impede a copy de sair
# errada, e nada alem disso. Playbook fora do ar deve doer um pouco na qualidade e
# aparecer na metrica como versao 'embutido', nunca passar despercebido.
REGRAS_MINIMAS = """Voce escreve a primeira mensagem fria de WhatsApp para um negocio local.
A mensagem NAO se apresenta: nada de "aqui e o time de marketing", nada de dizer
de qual empresa se fala. Ela abre no nome da pessoa e num fato sobre o negocio
dela, e quem faz aparece depois, como "a gente".

REGRAS OBRIGATORIAS:
1. Voz de quem envia, nunca dizer que auditou o perfil
2. PROIBIDO travessao (- ou --). Use virgula ou dois pontos
3. Nao falar de preco nem de valores
4. Ajudar, nao auditar: apontar UM caminho, nao listar defeitos
5. Terminar em pergunta sobre a rotina do negocio
6. Implicar a dor (o cliente que some calado), sem demonstracao
7. Maximo 90 palavras por mensagem
8. Nao citar cidade nem regiao quando o dado nao vier nos dados do negocio
9. PERSONALIZAR DE VERDADE: citar pelo menos UM dado especifico do lead
   (nota, avaliacoes, cidade, score, estrategia). Texto que serviria para
   qualquer empresa do nicho trocando so o nome nao vale"""

# O contrato de maquina: a tarefa, os dados e o formato da resposta. Mora no codigo
# e NUNCA no playbook, porque quem edita o playbook e a copywriter-expert, e copy
# escrita a mao nao pode quebrar a leitura do JSON.
CONTRATO = """Escreva a sequencia de abordagem para o negocio abaixo.

Dados do negocio: {dados}
Angulo do nicho: dor = "{dor}", promessa = "{promessa}".

Responda SOMENTE com JSON valido, sem cerca de codigo:
{
  "alavanca": "dor e promessa usadas em 1 linha",
  "abertura": "primeira mensagem, a unica que sera enviada no disparo frio",
  "followup": "mensagem de 2 dias depois",
  "fechamento": "ultima mensagem (break-up)"
}"""

# Nome antigo preservado: era o prompt inteiro antes do playbook existir, e ainda
# e o que alguem procura ao abrir este arquivo atras do texto padrao.
SEQUENCIA_PROMPT = REGRAS_MINIMAS + "\n\n" + CONTRATO


def _conhecimento(settings):
    """De onde saem as regras de escrita, e o carimbo de qual versao saiu.

    A ordem e deliberada: o que o operador colou na tela vence, porque a tela
    promete isso ("vazio = prompt da skill"); apagar o campo devolve o playbook.
    """
    colado = (settings.get("abordagem_prompt") or "").strip()
    if colado:
        return colado, "custom"
    do_disco = playbook_sdr.texto()
    if do_disco:
        return do_disco, playbook_sdr.versao()
    return REGRAS_MINIMAS, "embutido"


def _montar_prompt_sequencia(settings):
    """Devolve (prompt, versao). O contrato de formato e SEMPRE acrescentado.

    Antes o texto colado substituia o prompt inteiro, contrato de JSON incluido:
    quem colasse instrucao em prosa recebia resposta em prosa, o json.loads
    falhava e a copy caia no template local sem nada na tela dizer por que. Agora
    o colado troca so o conhecimento, e o formato continua garantido pelo codigo.
    """
    base, versao = _conhecimento(settings)
    return base.rstrip() + "\n\n" + CONTRATO, versao


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
            bruto, versao = _montar_prompt_sequencia(settings)
            prompt = (bruto
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
                # Carimbo da versao do conhecimento que escreveu este texto. E o
                # que liga a copy ao relatorio de conversao depois.
                data["copy_versao"] = versao
                for k in ("abertura", "followup", "fechamento"):
                    if data.get(k):
                        data[k] = _sem_travessao(data[k])
                if data.get("abertura"):
                    return data
        except Exception:
            pass
    return _local_sequencia(business, niche_id)
