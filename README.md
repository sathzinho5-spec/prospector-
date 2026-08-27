# Prospector - Scraping de Negócios

Ferramenta web para **prospecção de negócios** a partir de **Google Maps**, **Google** e **Instagram**, com base de IA para análise.

## Como usar

1. Instalar dependências:
   ```
   pip install -r requirements.txt
   playwright install chromium
   ```

2. Iniciar o servidor:
   ```
   python run.py
   ```

3. Abrir o navegador em **http://127.0.0.1:8000**

## Fluxo de trabalho

1. **Escolha um nicho** (restaurantes, barbearias, academias, etc.) e um **filtro** (cidade/bairro).
2. A ferramenta coleta do Google Maps a lista completa de negócios: nome, categoria, nota, nº de avaliações, endereço, telefone, site e horários.
3. Para cada negócio você pode:
   - **Buscar referência no Google** — encontra o site e o @ do Instagram do negócio (usa DuckDuckGo/Bing como mecanismo de busca porque o Google bloqueia scraping automatizado com CAPTCHA).
   - **Analisar Instagram + IA** — baixa conteúdo, mostra postagens recentes e gera um **relatório estratégico** (pontos fortes, sugestões, tom de voz, hashtags, conteúdo recomendado).
4. **Exportar** a lista em CSV, Excel ou JSON (arquivos ficam em `output/`).

## Instagram — importante

O Instagram **bloqueia o acesso anônimo (sem login)** desde 2025/2026. Para usar a análise do Instagram:

1. Faça login no Instagram no seu navegador.
2. Abra Dev Tools (`F12`) → Application → Cookies → `https://www.instagram.com` → copie o valor do cookie **`sessionid`**.
3. Cole em **Configurações da IA** → "Cookie de sessão do Instagram (sessionid)" e salve.

O cookie fica salvo apenas localmente (em `settings.json`, fora do repositório). Sem ele, a ferramenta informa claramente que o acesso foi bloqueado.

## Base de IA

- **Sem configuração**: usa a análise local gratuita (sentimento, hashtags, métricas).
- **Com chave OpenAI-compatível** (botão "Configurações da IA"): gera relatório estratégico avançado via LLM.

## Avisos

- Scraping de Google Maps/Google/Instagram pode ser bloqueado ou violar termos de uso.
- O Google Maps pode exibir CAPTCHA em volume alto; use atraso entre requisições.
- O Instagram exige o cookie de sessão do próprio usuário para acessar dados (ver acima).
- Use em volume moderado (a ferramenta respeita um atraso configurável entre requisições).
- Esta ferramenta é para fins de prospecção de leads; verifique a legislação de proteção de dados (LGPD) antes de usar os dados.