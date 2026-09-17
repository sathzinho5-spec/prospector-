# Arquitetura: prospector

Mapa gerado por `Agente Orquestrador/tools/gerar_arquitetura.py`.
Nao edite a mao: a proxima geracao sobrescreve. Pra mudar uma linha,
mude o `proposito:` no cabecalho do arquivo.

Teto por arquivo: 350 linhas. Arquivos: 57.

## raiz do projeto

```
app.py                          270  sobe o FastAPI, a porta de acesso e as rotas de busca e ajuste
config.py                        69  caminhos do projeto e leitura das configuracoes, com volume de dados na VPS
contas.py                       349  porta de entrada: cadastro pendente, aprovacao do dono e cookie de sessao
eslint.config.mjs                47  teto de 350 linhas por arquivo e checagem de erro no JS do painel
niches.py                        64  a lista de nichos que a busca oferece
nucleo.py                        44  estado em memoria, porta de acesso e quem esta do outro lado
run.py                           20  sobe o uvicorn, com os cabecalhos do proxy quando roda na VPS
scheduler.py                    103  agendador da busca recorrente e a comparacao com a rodada anterior
storage.py                      112  grava e exporta os negocios achados: JSON, CSV e Excel
```

## analysis/

```
analysis/__init__.py              1  marca analysis/ como pacote; a analise vive nos arquivos ao lado
analysis/analyzer.py             13  porta de entrada da analise; reexporta pra nenhuma chamada de fora mudar
analysis/copy_comercial.py      212  copy de estrategia e de proposta comercial, com prompt e fallback local
analysis/copy_fechamento.py     184  copy de fechamento: pitch de abordagem e resposta a objecao
analysis/copy_sdr.py            169  copy do SDR pro disparador: mensagem por nicho, na voz de quem envia
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
scrapers/__init__.py              1  marca scrapers/ como pacote; os raspadores vivem nos arquivos ao lado
scrapers/cloud_store.py         225  leads e fila no Supabase, best-effort: cai pro local sem quebrar
scrapers/cnpj_store.py          106  espelho local em SQLite do CNPJ, pra quando o Supabase esta fora
scrapers/cnpj_supabase.py       234  baixa o CNPJ da Receita, filtra capital alto e sobe pro Supabase
scrapers/disparo.py             251  o motor do disparo: janela de horario, worker em thread, iniciar e pausar
scrapers/disparo_fila.py        242  a fila do disparo em SQLite, o bloqueio de telefone e o anti-duplicata
scrapers/disparo_providers.py   293  quem sabe enviar: Simulado, Evolution API e Meta Cloud API
scrapers/gmaps_extrair.py       184  tira o dado de uma pagina aberta do Maps: texto, link, consentimento, ficha
scrapers/gmaps_parse.py          81  funcoes puras que viram texto raspado em dado: nota, cidade, coordenada
scrapers/google_maps.py         142  conduz a busca no Google Maps: abre o navegador, percorre os cartoes
scrapers/google_search.py       141  busca no Google pra achar site e referencia do negocio
scrapers/instagram.py           138  le o perfil publico do Instagram: dados, posts e midia
scrapers/site_contacts.py       133  varre o site do negocio atras de email, telefone e rede social
```

## scripts/

```
scripts/arquitetura.js           32  acha o gerador de mapa da Dodo e roda; sem ele, avisa e nao quebra o lint
scripts/dev.js                  162  npm run dev: sobe o Prospector em Python pelo comando padrao do ecossistema
```

## tools/

```
tools/criar_dono.py              51  cria ou promove conta de dono, quando a regra da primeira conta nao basta
tools/importar_carteira.py      153  importa a carteira de leads da planilha do Drive pro Prospector
```

## web/

```
web/acesso.js                   297  decide qual das quatro telas de acesso aparece, pelo endereco e pela sessao
web/app.js                      144  arranque do painel, ligacao de eventos e navegacao entre abas
web/painel.js                   123  aba de conexao do numero, faixa de estado e quem esta logado
web/sessao.js                    24  link de Acessos pra quem e dono, e o Sair que sai de verdade
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
