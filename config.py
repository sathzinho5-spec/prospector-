# proposito: caminhos do projeto e leitura das configuracoes, com volume de dados na VPS
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# No servidor os dados vivem num volume, fora da imagem: sem isso cada
# publicacao apagaria as configuracoes e as contas. Na maquina local a
# variavel nao existe e tudo continua ao lado do codigo, como sempre foi.
DADOS_DIR = os.environ.get("PROSPECTOR_DADOS") or BASE_DIR
os.makedirs(DADOS_DIR, exist_ok=True)

SETTINGS_FILE = os.path.join(DADOS_DIR, "settings.json")
DOWNLOADS_DIR = os.path.join(DADOS_DIR, "downloads")
OUTPUT_DIR = os.path.join(DADOS_DIR, "output")

DEFAULT_SETTINGS = {
    "openai_api_key": "",
    "openai_base_url": "https://api.openai.com/v1",
    "openai_model": "gpt-4o-mini",
    "instagram_sessionid": "",
    "headless": True,
    "request_delay": 1.5,
    "max_results": 15,
    "schedule_enabled": False,
    "schedule_time": "08:00",
    "schedule_niche": "restaurantes",
    "schedule_states": [],
    "schedule_max": 10,
    "schedule_last_run": "",
    "schedule_new_count": 0,
    "schedule_total_count": 0,
    "disparo_provider": "simulado",
    "disparo_evo_url": "",
    "disparo_evo_key": "",
    "disparo_evo_instance": "",
    "disparo_evo_instances": "",
    "disparo_evo_chip2": "",
    "disparo_evo_chip3": "",
    "disparo_prompt": "",
    "abordagem_prompt": "",
    # Trave de custo: quantos leads da migracao podem sair da IA por vez.
    # 30 porque a carteira tem 30 e o objetivo e carregar todos num clique.
    # Acima disso o lead fica de fora e a tela avisa. Zero desliga a IA.
    "abordagem_ia_max": 30,
    # Janela e limite do dia: os dois unicos numeros que descrevem o ritmo do
    # disparo. A pausa entre um envio e outro NAO se configura mais, ela e
    # derivada destes dois (scrapers/disparo_cadencia.py).
    "disparo_hora_ini": "08:00",
    "disparo_hora_fim": "20:00",
    "disparo_limite_dia": 30,
    # Janelas preferidas por nicho: {nicho_id: {ini, fim, dias}}. Vazio usa o
    # padrao de analysis/timing.py. Edita na tela de Configuracoes.
    "timing_janelas": {},
    "disparo_tom": "direto",
    "disparo_meta_token": "",
    "disparo_meta_phone_id": "",
    "supabase_url": "",
    "supabase_secret": "",
    "supabase_publishable": "",
}


def load_settings():
    merged = dict(DEFAULT_SETTINGS)
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                merged.update(saved)
        except Exception:
            pass
    return merged


def save_settings(new_settings):
    current = load_settings()
    current.update(new_settings)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)
    return current