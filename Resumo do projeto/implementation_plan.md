# Plano: quebra dos arquivos grandes do Prospector

**Data:** 17/09/2026
**Origem:** `Promps/Prompt Quebra Arquivos Grandes` (3 prompts do vibe-coding-toolkit)
**Conduz:** dodo-ia | **Executa:** dev-expert | **Confere:** fundador, na tela
**Status:** aguardando aprovacao do fundador (Regra de Ouro 10)

---

## 1. O problema, e por que o processo original nao roda como esta

Os tres prompts sao inteiramente ESLint. O Prospector e um backend Python (FastAPI) com
frontend em JS vanilla. Conferido no projeto:

- `package.json` tem um unico script, `dev`. Nasceu so pra cumprir a Regra de Ouro 23.
- Nao existe `node_modules`, nao existe config de ESLint, nao existe TypeScript.
- Nao existe teste nenhum: nenhum `test_*.py`, nenhum `conftest.py`, `pytest` fora do
  `requirements.txt`.

Rodando o processo como escrito, o ESLint enxergaria 1 dos 7 arquivos acima de 350 linhas.

**Decisao do fundador (17/09/2026):** traduzir o teto pro Python e usar ESLint no `web/`. A
logica dos tres prompts (medir, lote de 3, cortar por responsabilidade e nao por contagem,
preservar a interface publica, validar antes de commitar) vale igual nas duas pontas.

**Segunda decisao do fundador:** sem escrever teste antes. O trabalho acontece em branch
separada, sem merge, e ele confere na tela antes de qualquer publicacao.

### O risco que essa decisao aceita, dito com todas as letras

O remote e `sathzinho5-spec/prospector-`, do socio, com publicacao automatica ligada (decisao
registrada em 16/09/2026). A Fase 4 do prompt 09 manda rodar typecheck, testes e lint antes de
cada commit. Sem teste, o passo dos testes nao existe, e o que sobra e a conferencia na tela.
Por isso a branch separada nao e detalhe: e a unica trava.

---

## 2. A medicao de base (Fase 0 do prompt 09)

Contado agora com `wc -l`, sem chute:

| # | Arquivo | Linhas | Quem mede |
|---|---|---|---|
| 1 | `web/app.js` | 2243 | ESLint |
| 2 | `app.py` | 1164 | script de contagem |
| 3 | `scrapers/disparo.py` | 771 | script de contagem |
| 4 | `analysis/analyzer.py` | 554 | script de contagem |
| 5 | `scrapers/google_maps.py` | 407 | script de contagem |

Logo abaixo do teto, fora do lote e sem acao: `contas.py` (348).

### O que fica fora do gate, e por que

`web/styles.css` (1479) e `web/index.html` (638) passam de 350 e **nenhum linter enxerga**.
Cobrir CSS exigiria stylelint, uma terceira ferramenta que nao foi pedida. Fica registrado
como buraco conhecido, nao como tarefa.

### Os lotes (BATCH_SIZE=3)

- **Lote 1:** `web/app.js`, `app.py`, `scrapers/disparo.py`
- **Lote 2:** `analysis/analyzer.py`, `scrapers/google_maps.py`

Entre um lote e outro, para e relata (Fase 5). O lote 2 so comeca com o seu aval.

---

## 3. Etapa 1: instalar os tetos (equivalente ao prompt 08)

**Responsavel:** dev-expert

### Lado JS: ESLint 9

- Instalar `eslint@^9` e `@eslint/js@^9` como devDependencies.
- Config em `eslint.config.mjs` (flat config). **Nao pode ser `.eslintrc.json`**: o
  `.gitignore` do projeto tem `*.json` com excecao so pro `package.json`, entao um config JSON
  nasceria invisivel pro Git.
- A regra do teto: `"max-lines": ["warn", {"max": 350, "skipBlankLines": false,
  "skipComments": false}]`. Esse e o `RULE_ID` do lado JS.
- **Ajuste obrigatorio:** `languageOptions.sourceType` tem que ser `"script"`, nao `"module"`,
  e `globals` tem que declarar o browser. Os arquivos de `web/` sao carregados como script
  classico, compartilhando escopo global. Com o default `module`, o ESLint acusaria `no-undef`
  em tudo e o relatorio viraria ruido.

### Lado Python: o gerador de arquitetura, em modo `--check`

Conferido na documentacao do Ruff em 17/09/2026: **o Ruff nao tem regra de numero maximo de
linhas por arquivo**. Nao existe equivalente ao `C0302` do Pylint.

Quem faz o papel do `RULE_ID` no lado Python e
`Agente Orquestrador/tools/gerar_arquitetura.py --check`, ja escrito e testado neste projeto em
17/09/2026. Ele varre o projeto, conta as linhas, le o `proposito:` do cabecalho de cada
arquivo e sai com codigo 1 quando existe arquivo acima do teto **ou** sem proposito declarado.

**Uma ferramenta, nao duas** (Regra de Ouro 6): o mesmo script que mede o teto e o que gera o
mapa, porque le exatamente os mesmos dados. Um `scripts/tamanho.py` separado seria a mesma
varredura escrita duas vezes.

Ele mora nas tools do workspace, nao dentro do projeto. Isso importa aqui: o repositorio e do
socio, e assim o unico arquivo nosso que aterrissa la e o `ARQUITETURA.md` gerado.

Ruff fica fora desta etapa: resolve qualidade geral, que e assunto da etapa 4, e so entra la se
voce quiser.

### Scripts no `package.json`

```
"lint"      -> roda os dois
"lint:js"   -> eslint web scripts
"lint:py"   -> python "<workspace>/Agente Orquestrador/tools/gerar_arquitetura.py" . --check
"mapa"      -> python "<workspace>/Agente Orquestrador/tools/gerar_arquitetura.py" .
```

Nao entram `test` nem `typecheck`: nao existem, e inventar script que nao faz nada e pior que
nao ter. Onde o prompt 09 pede esses dois passos, o substituto e a conferencia na tela.

**Verificacao da etapa 1:** ja feita em 17/09/2026. O `--check` rodou no prospector e apontou
os mesmos 5 arquivos acima do teto da tabela da secao 2, achados por caminho independente. Ele
tambem contou 26 arquivos sem `proposito:` declarado, que e o trabalho da secao 3.5.

Uma diferenca de uma linha para a tabela da secao 2: o script conta 1165 no `app.py` e o
`wc -l` contou 1164. O `wc` conta quebras de linha, entao arquivo que termina sem quebra final
fica um a menos. O numero do script e o certo. Nao muda nada no plano.

---

## 3.5 O cabecalho de proposito e o mapa (pedido do fundador, 17/09/2026)

Esta secao existe porque o ganho da quebra nao e ter arquivos menores, e ter visao do projeto
inteiro sem ler o projeto inteiro. Arquivo pequeno sem nome que se explique nao entrega isso.

**Cada arquivo criado ou tocado nesta operacao nasce com o proposito no cabecalho:**

```python
# proposito: fila de envio, bloqueio de telefone e anti-duplicata
```

```javascript
// proposito: conversas do WhatsApp: listar chats, ler e responder
```

Uma linha, dizendo o trabalho daquele arquivo. Se precisar de duas frases pra caber, o corte da
secao 4 foi no lugar errado e se volta pra costura.

**O `ARQUITETURA.md` na raiz e gerado, nunca escrito a mao.** Ele sai do `proposito:` de cada
arquivo. E por isso que ele nao envelhece: nao existe um segundo lugar pra atualizar, e mapa
que aponta pra arquivo que sumiu deixa de ser possivel. Um cabecalho ainda pode mentir, mas a
superficie de mentira caiu de vinte rodapes pra uma linha por arquivo.

**Quando regenera:** ao fim de cada arquivo quebrado, junto do `npm run lint`. O `ARQUITETURA.md`
entra no mesmo commit do arquivo, entao o mapa nunca fica uma versao atras do codigo.

**O que ja existe:** o mapa do estado ATUAL do prospector foi gerado em 17/09/2026 e esta em
`ARQUITETURA.md`, na raiz do projeto, com os 26 arquivos e os 5 estouros. Ele nasce util mesmo
antes da quebra, porque ja diz onde nao ha proposito declarado.

---

## 4. Etapa 2, lote 1: onde cortar (Fases 2 e 3 do prompt 09)

Corte por responsabilidade, nunca por contagem. Interface publica preservada por reexportacao.

### 4.1 `web/app.js` (2243 linhas)

**O achado que muda a estrategia:** existem 26 pontos que dependem do escopo global, 2 em
`onclick` inline no `index.html` (`crmBulkMove()`, `crmBulkClear()`) e 24 gerados dentro do
proprio `app.js` por `innerHTML` com `onclick=`. Converter para ES modules quebraria os 26 de
uma vez, em silencio, sem teste pra pegar.

**Portanto: continua script classico.** A quebra e em varios arquivos carregados em ordem no
`index.html`, dividindo o mesmo escopo global. Zero mudanca de comportamento, e casa com o
estilo que ja esta la (Regra 7 §3).

O arquivo ja declara as proprias costuras com os comentarios `// ===== X =====`. As costuras
seguem elas:

| Novo arquivo | O que leva | Funcoes (linha atual) |
|---|---|---|
| `web/js/ui.js` | utilitarios e pedacos de UI | `$` (1), `esc` (9), `showStatus` (15), `clearStatus` (22), `showLoader` (27), `hideLoader` (41), `initials` (46), `computeUrgency` (70), `urgencyPill` (86), `avatarHtml` (599), `statusPill` (606), `scorePill` (648), `copyToClipboard` (799) |
| `web/js/busca.js` | busca e resultados | `renderQuickNiches` (211), `renderQuickStates` (232), `toggleState` (245), `loadLastSearch` (254), `loadNiches` (318), `selectedStates` (350), `updateStateCount` (356), `reloadLast` (524), `doSearch` (544), `filteredBusinesses` (613), `renderResults` (655) |
| `web/js/analise.js` | analise e copy por IA | `generatePitchFor` (113), `analyzeAll` (703), `doPitch` (744), `doSequencia` (808), `doObjection` (847), `doProposal` (871), `openProposalWindow` (899), `detailHtmlFor` (988), `openDetailModal` (1035), `doStrategy` (1141), `doReference` (1184), `doInstagram` (1218), `renderInstagram` (1239) |
| `web/js/disparo.js` | conexao e disparo | `refreshInstances` (1397), `connectWhatsApp` (1420), `checkWaState` (1445), `paintModo` (1462), `setModo` (1471), `migrarMinerados` (1483), `enqueueAll` (1570), `refreshDisparo` (1617), `startDisp` (1661), `pauseDisp` (1691), `testDisp` (1697), `clearDisp` (1720) |
| `web/js/conversas.js` | conversas do WhatsApp | `tempoRel` (1731), `renderWaChats` (1749), `loadWaChats` (1778), `diaKey` (1840), `loadWaMsgs` (1848), `sendWaReply` (1884) |
| `web/js/crm.js` | CRM | `loadCrm` (1915), `crmFiltered` (1973), `renderCrmBoard` (1989) e o bloco de selecao a partir de 2026 |
| `web/app.js` (fica) | estado, arranque e ligacao de eventos | os `let` do topo (3 a 7), `PROVIDERS` (53), `init` (59), `bindEvents` (398) |

`index.html` passa a carregar, nesta ordem: `ui.js`, `busca.js`, `analise.js`, `disparo.js`,
`conversas.js`, `crm.js`, `app.js`. O `app.js` por ultimo porque e quem chama `init()`.

Estimativa: nenhum dos sete passa de 350 linhas.

### 4.2 `app.py` (1164 linhas)

Costura: dominio de rota. Cada bloco vira um `APIRouter` num modulo, e o `app.py` faz
`include_router`. **Toda URL continua identica**, que e a preservacao de interface da Fase 3.

| Novo arquivo | Rotas que leva | Linhas atuais |
|---|---|---|
| `rotas/acesso.py` | telas e API de conta: `_tela_de_acesso` (191), `tela_entrar` (196), `tela_criar_conta` (201), `tela_aguardando` (206), `tela_acessos` (211), `tela_senha` (216), `_por_o_cookie` (234), `api_acesso_eu` (248), `api_acesso_entrar` (264), `api_acesso_criar` (273), `api_acesso_trocar_senha` (284), `api_acesso_sair` (302), `_so_dono` (308), `api_acesso_contas` (316), `api_acesso_liberar` (322), `api_acesso_recusar` (330), `api_acesso_tirar` (338) | 191 a 343 |
| `rotas/negocio.py` | contatos, estrategia, pitch, proposta, objecao, sequencia, screenshot, referencia, instagram | 471 a 648, 1029 a 1105 |
| `rotas/crm.py` | `api_cloud_status` (554), `api_cloud_leads` (564), `api_crm_leads` (585), `api_crm_status` (604) | 553 a 615 |
| `rotas/disparo.py` | todas as `/api/disparo/*` e `/api/disparo/evolution/*`, mais `_evo_provider` (855) e `_evo_instances` (867) | 649 a 912 |
| `rotas/whatsapp.py` | `_wa_jid` (920), `api_wa_chats` (931), `api_wa_mensagens` (940), `api_wa_responder` (952), `api_wa_lead` (965) | 914 a 982 |
| `rotas/cnpj.py` | `api_cnpj_grandes` (1136), `api_cnpj_marcar` (1149), `api_cnpj_sync` (1159) | 1123 a 1164 |
| `rotas/modelos.py` | os modelos Pydantic compartilhados entre mais de uma rota | 90 a 173 |
| `app.py` (fica) | `app = FastAPI()`, os dois middlewares, `STATE`, `WEB_DIR`, montagem do estatico, busca, resultados, settings, niches, schedule, export | 1 a 90, 175 a 190, 345 a 470, 984 a 1028, 1106 a 1122 |

**Trava que nao pode passar batido:** os dois middlewares (`@app.middleware("http")` nas linhas
23 e 66) e as listas `LIVRES` (45) e `PREFIXOS_LIVRES` (46) **ficam no `app.py`**. Middleware e
do app, nao do router. Mover isso derruba a autenticacao inteira, e como nao ha teste, ela
cairia calada.

### 4.3 `scrapers/disparo.py` (771 linhas)

| Novo arquivo | O que leva | Linhas atuais |
|---|---|---|
| `scrapers/disparo_providers.py` | `SimuladoProvider` (309), `_erro_amigavel` (317), `EvolutionProvider` (331), `MetaCloudProvider` (538), `_eh_falha_conexao` (564), `_build_providers` (573), `_make_provider` (588) | 309 a 595 |
| `scrapers/disparo_fila.py` | `_SCHEMA` (21), `_conn` (64), `_norm_phone` (79), `enfileirar` (86), `listar` (124), `limpar_finalizados` (139), `_reivindicar` (151), `_devolver_travados` (166), `ja_recebeu` (181), `bloquear` (196), `desbloquear` (211), `bloqueado` (222), `registrar_abordado` (230), `telefones_na_fila` (238), `atualizar_mensagem` (246), `_enviados_hoje` (300) | 7 a 308 |
| `scrapers/disparo.py` (fica) | o motor: `enviar_agora` (256), `_in_window` (596), `_worker_loop` (606), `_escolher` (621), `iniciar` (742), `pausar` (755), `status` (760) | resto |

**Preservacao de interface:** o `app.py` chama `disparo.enfileirar`, `disparo.listar`,
`disparo.bloquear` e outras por atributo do modulo. O `disparo.py` reexporta tudo que saiu
(`from .disparo_fila import enfileirar, listar, ...`), entao nenhuma chamada em `app.py` muda.
Isso e a Fase 3 literal: reexportar em vez de reescrever imports.

---

## 5. Etapa 3, lote 2 (so apos o seu aval do lote 1)

- `analysis/analyzer.py` (554): costura e o par relatorio de Instagram contra copy comercial.
  `_build_metrics` (22), `_top_hashtags` (34), `local_analysis` (39), `_detect_tone` (79),
  `_strong_points` (92), `ai_analysis` (107) e `build_report` (176) saem para
  `analysis/instagram_report.py`; os quatro blocos de copy (`STRATEGY_PROMPT` 188 em diante,
  `PROPOSAL_PROMPT` 314, `PITCH_PROMPT` 395, `OBJECTION_PROMPT` 487) saem para
  `analysis/copy_comercial.py`. O `analyzer.py` reexporta.
- `scrapers/google_maps.py` (407): passa so 57 linhas do teto. Costura candidata: os
  utilitarios de parse (`_clean` 59, `_parse_rating` 112, `_parse_cidade_estado` 125,
  `_parse_coords` 140) para `scrapers/gmaps_parse.py`. Se na hora nao houver costura natural,
  **relata "sem costura natural" e pula**, conforme a Fase 2 do prompt manda. Nao se corta por
  contagem.

---

## 6. Etapa 4: zerar o resto (equivalente ao prompt 03)

So depois dos dois lotes. Roda `npm run lint` e trata o que sobrar de aviso do ESLint no
`web/`, em lotes, sem misturar com a quebra de arquivo. Se voce quiser o mesmo do lado Python,
e aqui que o Ruff entra, como decisao separada.

---

## 7. Plano de verificacao

Como nao ha teste, cada passo tem uma checagem concreta no lugar:

| Passo | Verificacao |
|---|---|
| Etapa 1 | feita: o `--check` apontou os mesmos 5 arquivos da secao 2 |
| Cada arquivo quebrado | `npm run lint` roda de novo: o arquivo sumiu da lista, nenhuma violacao nova, e nenhum arquivo novo sem `proposito:` |
| Cada arquivo quebrado | `npm run mapa` regenera o `ARQUITETURA.md`, que entra no mesmo commit |
| `app.py` | `python run.py` sobe e `GET /api/saude` responde. Depois: entrar com conta, conferir que `/entrar` continua livre e que uma rota protegida barra sem cookie |
| `web/app.js` | abrir o painel e percorrer as seis areas: busca, analise, disparo, conversas, CRM, e as duas acoes em massa do CRM (`crmBulkMove`, `crmBulkClear`), que sao os `onclick` inline do HTML |
| `scrapers/disparo.py` | `GET /api/disparo/status` e `GET /api/disparo/fila` respondem, e o modo simulado envia sem erro. **Nao disparar de verdade** |
| Fechamento | `git diff --stat` na branch, e voce confere na tela antes de qualquer merge |

**Commit por arquivo**, nomeando o arquivo e a costura, como a Fase 4 pede. Branch
`refactor/quebra-arquivos-350`. Sem merge e sem push pra `main`, porque a publicacao e
automatica no repositorio do socio.

---

## 8. Pendencias que este plano abre

1. **Regra de Ouro 20:** este processo se repete. Nao existe skill dona dele hoje. Proposta:
   `help` para a `skill-expert` pedindo treinamento da `dev-expert`, nao contratacao nova,
   porque o escopo ja e dela.
2. **Regra de Ouro 22:** nao existe nota deste processo em `Dodo Company/Processos/Dev/`. E a
   primeira vez. No encerramento, a `assistente-expert` escreve.
3. **Buraco conhecido:** `web/styles.css` (1479) e `web/index.html` (638) ficam fora de
   qualquer teto. O gerador so le `.py`, `.js`, `.mjs`, `.cjs`, `.ts`, `.jsx` e `.tsx`. Decisao
   sua se CSS e HTML entram depois.
4. **Regra de Ouro 27:** o fundador determinou em 17/09/2026 que o cabecalho de proposito e o
   `ARQUITETURA.md` valem pra TODO projeto que a Dodo tocar, nosso ou de socio. O texto da
   regra esta redigido e aguardando o aval dele. Pela Regra de Ouro 8, quem grava em
   `regras_de_ouro.md` e a `skill-expert` ou o fundador, nunca a dodo-ia.
