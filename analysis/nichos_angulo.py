# proposito: qual dor e qual promessa cada nicho carrega, e como achar o nicho
"""
Saiu de analysis/copy_sdr.py pela costura que ele ja tinha: de um lado a TABELA
do que cada mercado sente, do outro quem ESCREVE a mensagem. Sao dois ritmos de
mudanca diferentes, e o arquivo passou do teto quando os apelidos entraram.

copy_sdr reexporta NICHE_ANGLES, GENERICO e _angle, entao quem chamava de fora
(inclusive o copy_fechamento) continua chamando igual.
"""

# Angulo de dor/promessa por nicho (base do roteiro)
NICHE_ANGLES = {
    "restaurantes": {"dor": "mesas vazias no meio da semana", "promessa": "movimento no salao e no delivery"},
    "bares": {"dor": "casa vazia nos dias fracos", "promessa": "noites cheias recorrentes"},
    "hamburguerias": {"dor": "depender so do iFood e pagar taxa alta", "promessa": "pedido direto com margem cheia"},
    "pizzarias": {"dor": "depender so do iFood e pagar taxa alta", "promessa": "pedido direto com margem cheia"},
    "cafeterias": {"dor": "cliente que passa na porta e nao entra", "promessa": "fluxo constante de manha e tarde"},
    "acai": {"dor": "vender so no verao e no calor", "promessa": "venda o ano todo"},
    "beleza": {"dor": "cliente novo que gosta do trabalho, não acha os serviços nem como falar, e vai no próximo",
               "promessa": "serviços, fotos dos trabalhos, endereço e WhatsApp num link só"},
    "barbearias": {"dor": "quem descobre a barbearia e não acha preço, horário nem como marcar",
                   "promessa": "serviços, preços, horário e WhatsApp num link só"},
    "estetica": {"dor": "quem pergunta procedimento e preço no direct e desiste antes de marcar avaliação",
                 "promessa": "procedimentos, resultados, endereço e WhatsApp num link só"},
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


# A categoria que vem da mineracao nem sempre e o nome da chave. A carteira da
# Vitrine Rapida grava "Salao", "Barbearia" e "Estetica"; a tabela acima tem
# "beleza", "barbearias" e "estetica". "Salao" nao casava com nada e os 10 saloes
# caiam no angulo generico, que e o pior texto que existe aqui. Apelido resolve
# sem duplicar a tabela: um nome a mais aponta pra mesma entrada.
APELIDOS = {
    "salao": "beleza",
    "saloes": "beleza",
    "cabeleireiro": "beleza",
    "barbearia": "barbearias",
    "barbeiro": "barbearias",
    "esteticista": "estetica",
    "clinica de estetica": "estetica",
    "restaurante": "restaurantes",
    "bar": "bares",
    "hamburgueria": "hamburguerias",
    "pizzaria": "pizzarias",
    "cafeteria": "cafeterias",
    "academia": "academias",
    "padaria": "padarias",
    "advogado": "advocacia",
    "imobiliaria": "imobiliarias",
    "dentista": "odontologia",
    "farmacia": "farmacias",
}


def _sem_acento(texto):
    """'Salão' e 'Salao' tem que cair na mesma chave: a nuvem grava dos dois
    jeitos, dependendo de quem digitou."""
    pares = (("ã", "a"), ("á", "a"), ("â", "a"), ("é", "e"), ("ê", "e"),
             ("í", "i"), ("ó", "o"), ("ô", "o"), ("õ", "o"), ("ú", "u"),
             ("ç", "c"))
    saida = (texto or "").lower()
    for de, para in pares:
        saida = saida.replace(de, para)
    return saida


def _angle(niche_id, categoria):
    if niche_id and niche_id in NICHE_ANGLES:
        return NICHE_ANGLES[niche_id]
    cat = _sem_acento(categoria).strip()
    if cat in APELIDOS:
        return NICHE_ANGLES[APELIDOS[cat]]
    for apelido, nid in APELIDOS.items():
        if apelido in cat:
            return NICHE_ANGLES[nid]
    for nid, a in NICHE_ANGLES.items():
        if nid in cat or cat in nid:
            return a
    return GENERICO
