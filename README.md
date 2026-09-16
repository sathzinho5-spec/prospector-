# Prospector — Máquina de Prospecção B2B

Sistema completo para **encontrar, qualificar, analisar e contatar** negócios locais:
Google Maps + IA (Groq/Gemini/OpenAI) + Instagram + WhatsApp + CRM + Supabase.

## Início rápido

```bash
pip install -r requirements.txt
python -m playwright install chromium
python run.py
# Abrir http://127.0.0.1:8000 (ou duplo clique em start_prospector.bat)
```

## Abas do sistema

| Aba | O que faz |
|---|---|
| **Início** | Busca rápida, última busca, status (IA, nuvem, agendador) |
| **Resultados** | Grade de leads com foto, filtros (site/nota/avaliações), ordenação (score, urgência), análise em lote por IA |
| **CRM** | KPIs, kanban por estágio (novo → fechado), filtros, anotações, seleção em massa, detalhes completos |
| **Comercial** | Fila de contato, disparo automático, performance do funil |

## Fluxo de trabalho

1. **Buscar** — nicho ou termo livre + 1 ou mais estados (nunca repete: compara com a nuvem)
2. **Analisar todos (IA)** — score de oportunidade 0-100% em lote, tabela ordenada
3. **Detalhes** — endereço, horários, foto, contatos do site (e-mail/WhatsApp/redes), screenshot do Maps
4. **Estratégia (IA)** — oportunidades de serviço, abordagem e plano por lead
5. **Mensagem/Proposta** — WhatsApp e e-mail personalizados prontos p/ copiar; proposta em PDF
6. **Disparo** — fila automática (Evolution/Meta) ou assistida via WhatsApp Web, com modo auto/manual
7. **CRM** — pipeline completo com 7 estágios, tudo persistido no Supabase

## Recursos principais

- **Nunca repetir**: cada busca oculta leads já coletados (hash na nuvem)
- **Score de urgência**: nota baixa + muitas avaliações = URGENTE
- **Busca agendada**: roda sozinha todo dia e avisa sobre leads novos
- **Sequência SDR**: abertura + follow-up + fechamento por nicho (skill copywriter)
- **Treinador de objeções**: "tá caro", "já tenho agência" → resposta na hora
- **Gigantes invisíveis (CNPJ)**: grandes empresas sem site/Maps via Supabase
- **Export**: CSV, Excel, JSON

## Configuração (tudo em Configurações IA, no app)

| Item | Onde obter | Obrigatório? |
|---|---|---|
| Chave IA (Groq/Gemini/OpenAI) | [Groq](https://console.groq.com) ou [AI Studio](https://aistudio.google.com) | Não (usa análise local) |
| Cookie `sessionid` Instagram | DevTools → Application → Cookies | Só p/ análise do Instagram |
| Supabase URL + secret | Seu projeto → Settings → Data API | Não (usa banco local) |
| Evolution API | `cd evolution && docker compose up -d` | Só p/ disparo real |

Para a nuvem, rode `supabase_schema.sql` no SQL Editor do seu projeto (cria `leads`, `fila_disparo`, `empresas_grandes`, `vistos_cnpj`).

## Estrutura

```
app.py              # API FastAPI (busca, análise, disparo, CRM, CNPJ, agendador)
config.py           # settings.json local (chaves — fora do git)
niches.py           # 24 nichos + 27 UFs
storage.py          # CSV/Excel/JSON + upsert Supabase
scheduler.py        # buscas agendadas (thread)
analysis/           # analyzer.py (estratégia/pitch/proposta/objeção) + copy_sdr.py (roteiros por nicho)
scrapers/           # google_maps, google_search, instagram, site_contacts, disparo, cloud_store, cnpj_*
web/                # index.html + app.js + styles.css (interface única, sem versões)
evolution/          # docker-compose da Evolution API + guia
supabase_schema.sql # schema completo (arquivo único)
```

## Avisos

- Scraping pode sofrer bloqueio/CAPTCHA; o sistema tem retry, sessão persistente e delays humanizados.
- Disparo em massa no WhatsApp pessoal pode derrubar o número — use chip secundário, limite baixo e mensagem com SAIR. Para zero risco, use a Meta Cloud API.
- Instagram exige seu próprio `sessionid`.
- Uso para prospecção: observe a LGPD.
