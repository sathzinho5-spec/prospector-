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
    delay_min: float = 45
    delay_max: float = 120
    limite_dia: int = 50
    hora_ini: str = "08:00"
    hora_fim: str = "20:00"
    optout: bool = True


class DisparoTestRequest(BaseModel):
    phone: str
    mensagem: str = "Teste do Prospector: mensagem de teste do disparador."


class InstagramRequest(BaseModel):
    name: str
    username: str = ""
    download: bool = True
    max_posts: int = 12


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
    disparo_modo: str = ""
    supabase_url: str = ""
    supabase_secret: str = ""
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

