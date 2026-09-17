# Arquitetura: prospector

Mapa gerado por `Agente Orquestrador/tools/gerar_arquitetura.py`.
Nao edite a mao: a proxima geracao sobrescreve. Pra mudar uma linha,
mude o `proposito:` no cabecalho do arquivo.

Teto por arquivo: 350 linhas. Arquivos: 57.

## raiz do projeto

```
app.py                          270  sobe o FastAPI, a porta de acesso e as rotas de busca e ajuste
config.py                        68  SEM PROPOSITO DECLARADO
contas.py                       348  SEM PROPOSITO DECLARADO
eslint.config.mjs                47  teto de 350 linhas por arquivo e checagem de erro no JS do painel
niches.py                        63  SEM PROPOSITO DECLARADO
nucleo.py                        44  estado em memoria, porta de acesso e quem esta do outro lado
run.py                           19  SEM PROPOSITO DECLARADO
scheduler.py                    102  SEM PROPOSITO DECLARADO
storage.py                      111  SEM PROPOSITO DECLARADO
```

## analysis/

```
analysis/__init__.py              0  SEM PROPOSITO DECLARADO
analysis/analyzer.py             13  porta de entrada da analise; reexporta pra nenhuma chamada de fora mudar
analysis/copy_comercial.py      212  copy de estrategia e de proposta comercial, com prompt e fallback local
analysis/copy_fechamento.py     184  copy de fechamento: pitch de abordagem e resposta a objecao
analysis/copy_sdr.py            168  SEM PROPOSITO DECLARADO
analysis/instagram_report.py    186  relatorio do perfil de Instagram: metricas, tom, pontos fortes e score
```

## rotas/

```
rotas/__init__.py                 1  marca rotas/ como pacote; os routers vivem nos arquivos ao lado
rotas/acesso.py                 148  telas de acesso e as rotas de conta: entrar, criar, liberar, tirar
rotas/cnpj.py                    40  garimpo de empresas grandes por UF na base de CNPJ
rotas/crm.py                     62  leads na nuvem e o CRM: listar, filtrar e mover de estagio
rotas/disparo.py                279  disparo: fila, envio, instancias Evolution, iniciar e pausar
rotas/modelos.py                145  os contratos de entrada da API, num lugar so
rotas/negocio.py                202  analise e copy de um lead: contato, estrategia, pitch, proposta
rotas/whatsapp.py                74  conversas do WhatsApp: chats, mensagens, responder e achar o lead
```

## scrapers/

```
scrapers/__init__.py              0  SEM PROPOSITO DECLARADO
scrapers/cloud_store.py         224  SEM PROPOSITO DECLARADO
scrapers/cnpj_store.py          105  SEM PROPOSITO DECLARADO
scrapers/cnpj_supabase.py       233  SEM PROPOSITO DECLARADO
scrapers/disparo.py             251  SEM PROPOSITO DECLARADO
scrapers/disparo_fila.py        242  a fila do disparo em SQLite, o bloqueio de telefone e o anti-duplicata
scrapers/disparo_providers.py   293  quem sabe enviar: Simulado, Evolution API e Meta Cloud API
scrapers/gmaps_extrair.py       184  tira o dado de uma pagina aberta do Maps: texto, link, consentimento, ficha
scrapers/gmaps_parse.py          81  funcoes puras que viram texto raspado em dado: nota, cidade, coordenada
scrapers/google_maps.py         142  conduz a busca no Google Maps: abre o navegador, percorre os cartoes
scrapers/google_search.py       140  SEM PROPOSITO DECLARADO
scrapers/instagram.py           137  SEM PROPOSITO DECLARADO
scrapers/site_contacts.py       132  SEM PROPOSITO DECLARADO
```

## scripts/

```
scripts/arquitetura.js           32  acha o gerador de mapa da Dodo e roda; sem ele, avisa e nao quebra o lint
scripts/dev.js                  161  SEM PROPOSITO DECLARADO
```

## tools/

```
tools/criar_dono.py              50  SEM PROPOSITO DECLARADO
tools/importar_carteira.py      152  SEM PROPOSITO DECLARADO
```

## web/

```
web/acesso.js                   296  SEM PROPOSITO DECLARADO
web/app.js                      144  arranque do painel, ligacao de eventos e navegacao entre abas
web/painel.js                   122  SEM PROPOSITO DECLARADO
web/sessao.js                    23  SEM PROPOSITO DECLARADO
```

## web/js/

```
web/js/agenda.js                 40  estado e resultados da busca agendada
web/js/ajustes.js               130  ajustes do painel: ler e salvar as configuracoes
web/js/analise.js               234  analise do lead por IA: score, estrategia, referencia e Instagram
web/js/busca.js                 282  busca de negocios, filtro dos resultados e exportacao
web/js/conexao.js                65  conexao do WhatsApp por QR code das instancias Evolution
web/js/contatos.js              116  quem ja foi contatado e a fila de contato do painel
web/js/conversas.js             178  conversas do WhatsApp: listar chats, ler e responder
web/js/copy.js                  192  geracao de copy de venda: pitch, sequencia, objecao e proposta
web/js/crm.js                   128  CRM: carregar leads, filtrar e montar o quadro por estagio
web/js/crm_cartao.js            216  cartao do lead, acao em massa e KPIs do CRM
web/js/detalhe.js               154  modal de detalhe do lead, screenshot e extracao de contato
web/js/disparo.js               268  disparo automatico: fila, migracao, envio e status
web/js/ui.js                    118  estado compartilhado do painel e as pecas visuais reusadas
```

## Sem proposito declarado

Cada um destes precisa de uma linha `proposito:` no cabecalho.

- `analysis/__init__.py`
- `analysis/copy_sdr.py`
- `config.py`
- `contas.py`
- `niches.py`
- `run.py`
- `scheduler.py`
- `scrapers/__init__.py`
- `scrapers/cloud_store.py`
- `scrapers/cnpj_store.py`
- `scrapers/cnpj_supabase.py`
- `scrapers/disparo.py`
- `scrapers/google_search.py`
- `scrapers/instagram.py`
- `scrapers/site_contacts.py`
- `scripts/dev.js`
- `storage.py`
- `tools/criar_dono.py`
- `tools/importar_carteira.py`
- `web/acesso.js`
- `web/painel.js`
- `web/sessao.js`
