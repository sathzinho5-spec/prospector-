NICHES = [
    {"id": "restaurantes", "label": "Restaurantes", "keywords": ["restaurantes", "restaurante"]},
    {"id": "bares", "label": "Bares e Lanchonetes", "keywords": ["bares", "lanchonetes"]},
    {"id": "hamburguerias", "label": "Hamburguerias", "keywords": ["hamburguerias", "hamburguer"]},
    {"id": "pizzarias", "label": "Pizzarias", "keywords": ["pizzarias"]},
    {"id": "cafeterias", "label": "Cafeterias", "keywords": ["cafeterias", "café"]},
    {"id": "acai", "label": "Açaí e Sorveterias", "keywords": ["açaí", "sorveterias"]},
    {"id": "beleza", "label": "Salões de Beleza", "keywords": ["salão de beleza"]},
    {"id": "barbearias", "label": "Barbearias", "keywords": ["barbearias", "barbeiro"]},
    {"id": "estetica", "label": "Clínicas de Estética", "keywords": ["clínica de estética", "estética"]},
    {"id": "academias", "label": "Academias", "keywords": ["academias", "musculação"]},
    {"id": "padarias", "label": "Padarias e Confeitarias", "keywords": ["padarias", "confeitarias"]},
    {"id": "petshop", "label": "Petshops e Veterinárias", "keywords": ["petshops", "veterinária"]},
    {"id": "advocacia", "label": "Escritórios de Advocacia", "keywords": ["advocacia", "advogados"]},
    {"id": "imobiliarias", "label": "Imobiliárias", "keywords": ["imobiliárias", "corretores"]},
    {"id": "odontologia", "label": "Clínicas Odontológicas", "keywords": ["dentista", "clínica odontológica"]},
    {"id": "moda", "label": "Lojas de Roupas", "keywords": ["lojas de roupas", "boutique"]},
    {"id": "mecanica", "label": "Mecânicas de Automóveis", "keywords": ["oficina mecânica", "mecânica de automóveis"]},
    {"id": "moveis", "label": "Lojas de Móveis", "keywords": ["lojas de móveis", "móveis planejados"]},
    {"id": "cursos", "label": "Escolas e Cursos", "keywords": ["cursos", "escolas de idiomas"]},
    {"id": "farmacias", "label": "Farmácias", "keywords": ["farmácias"]},
    {"id": "reformas", "label": "Reformas e Construção", "keywords": ["reformas", "construção civil"]},
    {"id": "limpeza", "label": "Serviços de Limpeza", "keywords": ["serviços de limpeza", "dedetização"]},
    {"id": "floricultura", "label": "Floriculturas", "keywords": ["floriculturas", "flores"]},
    {"id": "fotografia", "label": "Fotógrafos", "keywords": ["fotógrafos", "fotografia"]},
]

ESTADOS = [
    {"uf": "AC", "nome": "Acre"},
    {"uf": "AL", "nome": "Alagoas"},
    {"uf": "AP", "nome": "Amapá"},
    {"uf": "AM", "nome": "Amazonas"},
    {"uf": "BA", "nome": "Bahia"},
    {"uf": "CE", "nome": "Ceará"},
    {"uf": "DF", "nome": "Distrito Federal"},
    {"uf": "ES", "nome": "Espírito Santo"},
    {"uf": "GO", "nome": "Goiás"},
    {"uf": "MA", "nome": "Maranhão"},
    {"uf": "MT", "nome": "Mato Grosso"},
    {"uf": "MS", "nome": "Mato Grosso do Sul"},
    {"uf": "MG", "nome": "Minas Gerais"},
    {"uf": "PA", "nome": "Pará"},
    {"uf": "PB", "nome": "Paraíba"},
    {"uf": "PR", "nome": "Paraná"},
    {"uf": "PE", "nome": "Pernambuco"},
    {"uf": "PI", "nome": "Piauí"},
    {"uf": "RJ", "nome": "Rio de Janeiro"},
    {"uf": "RN", "nome": "Rio Grande do Norte"},
    {"uf": "RS", "nome": "Rio Grande do Sul"},
    {"uf": "RO", "nome": "Rondônia"},
    {"uf": "RR", "nome": "Roraima"},
    {"uf": "SC", "nome": "Santa Catarina"},
    {"uf": "SP", "nome": "São Paulo"},
    {"uf": "SE", "nome": "Sergipe"},
    {"uf": "TO", "nome": "Tocantins"},
]


def get_public():
    return {
        "nichos": [{"id": n["id"], "label": n["label"]} for n in NICHES],
        "estados": ESTADOS,
    }


def keyword_for(niche_id):
    for n in NICHES:
        if n["id"] == niche_id:
            return n["keywords"][0]
    return niche_id