# proposito: os contratos de entrada da API, num lugar so
from pydantic import BaseModel


class SearchRequest(BaseModel):
    query: str
    locations: list = []
    filter: str = ""
    max_results: int = 15
    apenas_novos: bool = True


class ReferenceRequest(BaseModel):
    name: str
    location: str = ""


class ContactRequest(BaseModel):
    url: str


class StrategyRequest(BaseModel):
    business: dict


class ScreenshotRequest(BaseModel):
    url: str
    name: str = "negocio"


class ScheduleRequest(BaseModel):
    enabled: bool = False
    time: str = "08:00"
    niche: str = "restaurantes"
    states: list = []
    max: int = 10


class ObjectionRequest(BaseModel):
    business: dict
    objection: str


class DisparoEnqueueRequest(BaseModel):
    itens: list
    origem: str = ""


class DisparoStartRequest(BaseModel):
    provider: str = "simulado"
    # DEPRECADOS: a pausa entre envios deixou de ser escolhida na tela e passou
    # a ser derivada da janela e do limite do dia (regra fixa de cadencia, em
    # scrapers/disparo_cadencia.py). Continuam aqui, aceitos e IGNORADOS, so
    # para nao quebrar chamador antigo; a resposta do /iniciar avisa.
    delay_min: float | None = None
    delay_max: float | None = None
    # None = nao veio no pedido, entao vale o que esta salvo nas configuracoes.
    # Valor presente sobrescreve E fica salvo, senao a cadencia que a tela
    # mostra divergiria da que o motor esta rodando.
    limite_dia: int | None = None
    hora_ini: str | None = None
    hora_fim: str | None = None
    # DEPRECADO: aceito e IGNORADO. A frase de descadastro saiu das mensagens a
    # pedido do fundador em 19/09/2026; o campo fica pra chamador antigo nao quebrar.
    optout: bool = True


class DisparoTestRequest(BaseModel):
    phone: str
    mensagem: str = "Teste do Prospector: mensagem de teste do disparador."


class InstagramRequest(BaseModel):
    name: str
    username: str = ""
    download: bool = True
    max_posts: int = 12


class InstagramProspectRequest(BaseModel):
    nicho: str
    local: str = ""
    max_results: int = 20
    enriquecer: bool = True
    apenas_novos: bool = True


class InstagramSitesRequest(BaseModel):
    businesses: list = []
    apenas_novos: bool = True


class SettingsRequest(BaseModel):
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = ""
    instagram_sessionid: str = ""
    headless: bool | None = None
    request_delay: float | None = None
    disparo_provider: str = ""
    disparo_evo_url: str = ""
    disparo_evo_key: str = ""
    disparo_evo_instance: str = ""
    disparo_evo_instances: str = ""
    disparo_evo_chip2: str = ""
    disparo_evo_chip3: str = ""
    # None = o campo nao veio no pedido. "" = a pessoa apagou e quer o padrao.
    disparo_prompt: str | None = None
    abordagem_prompt: str | None = None
    abordagem_ia_max: int | None = None
    disparo_tom: str = ""
    disparo_meta_token: str = ""
    disparo_meta_phone_id: str = ""
    # Janela e limite: os dois numeros de onde a cadencia e derivada.
    disparo_hora_ini: str = ""
    disparo_hora_fim: str = ""
    disparo_limite_dia: int | None = None
    supabase_url: str = ""
    supabase_secret: str = ""
    # Janelas preferidas por nicho: {nicho_id: {ini, fim, dias}}. None = nao veio.

class EntrarRequest(BaseModel):
    email: str = ""
    senha: str = ""


class ContaRequest(BaseModel):
    email: str = ""


class SenhaRequest(BaseModel):
    senha_atual: str = ""
    senha_nova: str = ""

class BatchRequest(BaseModel):
    businesses: list

class CrmStatusRequest(BaseModel):
    id: str = ""
    nome: str = ""
    endereco: str = ""
    telefone: str = ""
    status: str = "novo"
    observacao: str | None = None

class SequenciaRequest(BaseModel):
    business: dict
    niche_id: str = ""

class DisparoAtivoRequest(BaseModel):
    ids: list = []
    ativo: bool = False


class DisparoMigrarRequest(BaseModel):
    origem: str = "minerados"

class DisparoAgoraRequest(BaseModel):
    id: int


class DisparoRefazerRequest(BaseModel):
    id: int


class DisparoMensagemRequest(BaseModel):
    id: int
    mensagem: str = ""


class DisparoCriarCopyRequest(BaseModel):
    # Selecao vazia = todos os leads sem copy. Com ids ou telefones, so eles.
    ids: list = []
    telefones: list = []
    refazer: bool = False


class DisparoRespostaRequest(BaseModel):
    # id da abordagem, ou o telefone do lead. lead_id so serve para espelhar o
    # estagio no CRM da nuvem, e e opcional.
    id: int = 0
    telefone: str = ""
    lead_id: str = ""

class WaResponderRequest(BaseModel):
    jid: str = ""
    telefone: str = ""
    texto: str = ""

class CnpjGrandesRequest(BaseModel):
    uf: str = ""
    cidade: str = ""
    capital_min: int = 500000
    limite: int = 20
    apenas_nao_vistos: bool = True


class CnpjMarcarRequest(BaseModel):
    cnpjs: list



class DisparoCopyRequest(BaseModel):
    # A copy escrita a mao pelo operador, antes de o lead entrar na fila.
    telefone: str = ""
    mensagem: str = ""
