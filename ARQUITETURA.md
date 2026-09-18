# Arquitetura: prospector

Mapa gerado por `Agente Orquestrador/tools/gerar_arquitetura.py`.
Nao edite a mao: a proxima geracao sobrescreve. Pra mudar uma linha,
mude o `proposito:` no cabecalho do arquivo.

Teto por arquivo: 350 linhas. Arquivos: 69.

## raiz do projeto

```
app.py                           287  sobe o FastAPI, a porta de acesso e as rotas de busca e ajuste
config.py                         80  caminhos do projeto e leitura das configuracoes, com volume de dados na VPS
contas.py                        349  porta de entrada: cadastro pendente, aprovacao do dono e cookie de sessao
eslint.config.mjs                 47  teto de 350 linhas por arquivo e checagem de erro no JS do painel
niches.py                        121  a lista de nichos que a busca oferece
nucleo.py                         44  estado em memoria, porta de acesso e quem esta do outro lado
run.py                            20  sobe o uvicorn, com os cabecalhos do proxy quando roda na VPS
scheduler.py                     103  agendador da busca recorrente e a comparacao com a rodada anterior
storage.py                       112  grava e exporta os negocios achados: JSON, CSV e Excel
```

## analysis/

```
analysis/__init__.py               1  marca analysis/ como pacote; a analise vive nos arquivos ao lado
analysis/analyzer.py              13  porta de entrada da analise; reexporta pra nenhuma chamada de fora mudar
analysis/copy_comercial.py       212  copy de estrategia e de proposta comercial, com prompt e fallback local
analysis/copy_fechamento.py      184  copy de fechamento: pitch de abordagem e resposta a objecao
analysis/copy_sdr.py             189  copy do SDR pro disparador: mensagem por nicho, na voz de quem envia
analysis/instagram_report.py     186  relatorio do perfil de Instagram: metricas, tom, pontos fortes e score
analysis/timing.py               128  melhor momento de envio por nicho: janela preferida e proximo slot
analysis/aprendizado.py          108  score que aprende: conversao por perfil vira ajuste do score
```

## rotas/

```
rotas/__init__.py                  1  marca rotas/ como pacote; os routers vivem nos arquivos ao lado
rotas/acesso.py                  148  telas de acesso e as rotas de conta: entrar, criar, liberar, tirar
rotas/cnpj.py                     40  garimpo de empresas grandes por UF na base de CNPJ
rotas/crm.py                      75  leads na nuvem e o CRM: listar, filtrar e mover de estagio
rotas/disparo.py                 278  disparo: fila, envio da mensagem, cadencia, iniciar e pausar o motor
rotas/disparo_conversas.py        73  conversa iniciada: marcar, desmarcar e ler qual copy converteu
rotas/disparo_copy.py            235  a copy de abordagem dos leads: criar quem esta sem, e migrar pra fila
rotas/disparo_evolution.py        84  instancias da Evolution: qrcode, estado do chip e o numero pareado
rotas/disparo_leads.py           130  a lista de leads do disparo com o estado de copy e de envio de cada um
rotas/modelos.py                 203  os contratos de entrada da API, num lugar so
rotas/negocio.py                 163  analise e copy de um lead: contato, estrategia, pitch, proposta
rotas/negocio_instagram.py       239  prospeccao e analise de perfis do Instagram
rotas/whatsapp.py                 74  conversas do WhatsApp: chats, mensagens, responder e achar o lead
```

## scrapers/

```
scrapers/__init__.py               1  marca scrapers/ como pacote; os raspadores vivem nos arquivos ao lado
scrapers/cloud_store.py          261  leads e fila no Supabase, best-effort: cai pro local sem quebrar
scrapers/cnpj_store.py           106  espelho local em SQLite do CNPJ, pra quando o Supabase esta fora
scrapers/cnpj_supabase.py        234  baixa o CNPJ da Receita, filtra capital alto e sobe pro Supabase
scrapers/disparo.py              274  o motor do disparo: janela de horario, worker em thread, iniciar e pausar
scrapers/disparo_abordagens.py   160  o que saiu por lead e a conversa iniciada, fora do alcance da limpeza
scrapers/disparo_cadencia.py     106  o ritmo do disparo derivado da janela de horario e do limite do dia
scrapers/disparo_copys.py         77  a copy de abordagem de cada lead, guardada antes de ele entrar na fila
scrapers/disparo_db.py           147  o banco do disparo: caminho, esquema das tabelas e migracao defensiva
scrapers/disparo_fila.py         198  a fila do disparo em SQLite, o bloqueio de telefone e o anti-duplicata
scrapers/disparo_providers.py    336  quem sabe enviar: Simulado, Evolution API e Meta Cloud API
scrapers/gmaps_extrair.py        184  tira o dado de uma pagina aberta do Maps: texto, link, consentimento, ficha
scrapers/gmaps_parse.py           81  funcoes puras que viram texto raspado em dado: nota, cidade, coordenada
scrapers/google_maps.py          160  conduz a busca no Google Maps: abre o navegador, percorre os cartoes
scrapers/google_search.py        232  busca no Google pra achar site e referencia do negocio
scrapers/instagram.py            138  le o perfil publico do Instagram: dados, posts e midia
scrapers/site_contacts.py        133  varre o site do negocio atras de email, telefone e rede social
```

## scripts/

```
scripts/arquitetura.js            32  acha o gerador de mapa da Dodo e roda; sem ele, avisa e nao quebra o lint
scripts/dev.js                   162  npm run dev: sobe o Prospector em Python pelo comando padrao do ecossistema
```

## tools/

```
tools/criar_dono.py               51  cria ou promove conta de dono, quando a regra da primeira conta nao basta
tools/importar_carteira.py       153  importa a carteira de leads da planilha do Drive pro Prospector
```

## web/

```
web/acesso.js                    297  decide qual das quatro telas de acesso aparece, pelo endereco e pela sessao
web/app.js                       201  arranque do painel, ligacao de eventos e navegacao entre abas
web/painel.js                    130  aba de conexao do numero, faixa de estado e quem esta logado
web/sessao.js                     24  link de Acessos pra quem e dono, e o Sair que sai de verdade
```

## web/js/

```
web/js/agenda.js                  40  estado e resultados da busca agendada
web/js/ajustes.js                151  ajustes do painel: ler e salvar as configuracoes
web/js/analise.js                327  analise do lead por IA: score, estrategia, referencia e Instagram
web/js/busca.js                  330  busca de negocios, filtro dos resultados e exportacao
web/js/conexao.js                 76  conexao do WhatsApp por QR code das instancias Evolution
web/js/contatos.js               116  quem ja foi contatado e a fila de contato do painel
web/js/conversas.js              178  conversas do WhatsApp: listar chats, ler e responder
web/js/copy.js                   192  geracao de copy de venda: pitch, sequencia, objecao e proposta
web/js/crm.js                    128  CRM: carregar leads, filtrar e montar o quadro por estagio
web/js/crm_cartao.js             288  cartao do lead, acao em massa e KPIs do CRM
web/js/detalhe.js                157  modal de detalhe do lead, screenshot e extracao de contato
web/js/disparo.js                313  disparo automatico: fila, migracao, envio e status
web/js/disparo_aba.js            210  aba Disparo: os KPIs, a cadencia mostrada e a lista de leads
web/js/disparo_gaveta.js         160  a gaveta de detalhe do lead na aba Disparo: ficha, copy e resposta
web/js/tabela.js                 280  tabela de resultados: ordenacao, selecao, paginacao e acoes em lote
web/js/ui.js                     132  estado compartilhado do painel e as pecas visuais reusadas
```
