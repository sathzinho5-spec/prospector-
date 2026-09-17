# Comparacao: antes e depois da quebra em arquivos de 350 linhas

**Data:** 17/09/2026
**Branch:** `refactor/quebra-arquivos-350`, oito commits a partir de `ef38771`
**Origem:** processo de quebra de arquivos grandes (vibe-coding-toolkit), traduzido
pra stack real deste projeto, que e Python com frontend em JS classico

---

## 1. Os numeros

|  | No repositorio (`main`) | Com os arquivos quebrados |
|---|---|---|
| Arquivos de codigo | 26 | 57 |
| Linhas totais | 7846 | 8076 (+230) |
| Maior arquivo | 2251 (`web/app.js`) | 349 (`contas.py`) |
| Mediana | 137 | 141 |
| Acima de 350 linhas | 5 | **0** |
| Com proposito declarado | 0 | **57** |
| Lint (ESLint no `web/`) | 17 erros, 1 aviso | **0** |

### A distribuicao, que e onde a mudanca aparece

```
                    ANTES  DEPOIS
0 a 100 linhas          7      18
101 a 200 linhas       10      24
201 a 350 linhas        4      15
351 a 800 linhas        3       0
mais de 800 linhas      2       0
```

As +230 linhas sao o custo honesto da operacao: 57 cabecalhos de proposito, os
imports dos modulos novos e os blocos de reexportacao que mantiveram a interface
publica intacta. Nenhuma linha de logica foi escrita.

---

## 2. Onde cada gigante foi

### `web/app.js`, 2251 linhas, virou 14 arquivos

A costura foi a que o proprio arquivo ja declarava nos comentarios `// ===== X =====`.

| Arquivo | Linhas | Proposito |
|---|---|---|
| `web/js/busca.js` | 282 | busca de negocios, filtro dos resultados e exportacao |
| `web/js/analise.js` | 234 | analise do lead por IA: score, estrategia, referencia, Instagram |
| `web/js/crm_cartao.js` | 216 | cartao do lead, acao em massa e KPIs do CRM |
| `web/js/copy.js` | 192 | copy de venda: pitch, sequencia, objecao e proposta |
| `web/js/conversas.js` | 178 | conversas do WhatsApp: listar chats, ler e responder |
| `web/js/detalhe.js` | 154 | modal de detalhe do lead, screenshot e extracao de contato |
| `web/app.js` | 144 | arranque do painel, ligacao de eventos e navegacao entre abas |
| `web/js/disparo.js` | 268 | disparo automatico: fila, migracao, envio e status |
| `web/js/ajustes.js` | 130 | ajustes do painel: ler e salvar as configuracoes |
| `web/js/crm.js` | 128 | CRM: carregar leads, filtrar e montar o quadro por estagio |
| `web/js/ui.js` | 118 | estado compartilhado e as pecas visuais reusadas |
| `web/js/contatos.js` | 116 | quem ja foi contatado e a fila de contato |
| `web/js/conexao.js` | 65 | conexao do WhatsApp por QR code das instancias Evolution |
| `web/js/agenda.js` | 40 | estado e resultados da busca agendada |

**Continua `<script>` classico, em ordem no `index.html`.** Nao virou ES module de
proposito: existem 26 pontos presos ao escopo global, 2 em `onclick` inline no HTML
e 24 gerados por `innerHTML`, e modulo quebraria os 26 em silencio.

### `app.py`, 1189 linhas, virou 9 arquivos

Cada bloco de rota virou `APIRouter` num modulo, e o `app.py` faz `include_router`.
**Toda URL continua identica.**

| Arquivo | Linhas | Proposito |
|---|---|---|
| `rotas/disparo.py` | 279 | fila, envio, instancias Evolution, iniciar e pausar |
| `app.py` | 270 | sobe o FastAPI, a porta de acesso e as rotas de busca e ajuste |
| `rotas/negocio.py` | 202 | analise e copy de um lead |
| `rotas/acesso.py` | 148 | telas de acesso e rotas de conta |
| `rotas/modelos.py` | 145 | os contratos de entrada da API, num lugar so |
| `rotas/whatsapp.py` | 74 | conversas do WhatsApp |
| `rotas/crm.py` | 62 | leads na nuvem e o CRM |
| `nucleo.py` | 44 | estado em memoria, porta de acesso e quem esta do outro lado |
| `rotas/cnpj.py` | 39 | garimpo de empresas grandes por UF |

**O que NAO saiu do `app.py`, de proposito:** os dois middlewares e as listas
`LIVRES` e `PREFIXOS_LIVRES`. Middleware e do app, nao do router. Mover isso
derrubaria a autenticacao inteira, e sem teste ela cairia calada.

### Os outros tres

| Antes | Depois |
|---|---|
| `scrapers/disparo.py` (771) | `disparo_providers.py` (293), `disparo.py` (251), `disparo_fila.py` (242) |
| `analysis/analyzer.py` (573) | `copy_comercial.py` (212), `instagram_report.py` (186), `copy_fechamento.py` (184), `analyzer.py` (13, so reexportacao) |
| `scrapers/google_maps.py` (408) | `gmaps_extrair.py` (182), `google_maps.py` (142), `gmaps_parse.py` (81) |

No `google_maps.py` o plano previa tirar so os utilitarios de parse, o que deixaria
o arquivo em 347 de 350: um sobrevivente por tres linhas, que volta a estourar no
primeiro ajuste. A costura melhor e por camada.

**Interface publica preservada por reexportacao** nos tres. Quem chamava
`disparo.enfileirar`, `analyzer.build_report` ou `google_maps.search_places`
continua chamando, sem uma linha mudada.

---

## 3. O que passou a existir, e nao existia

### O teto, que agora e conferido por comando

- **`eslint.config.mjs`** com `max-lines` em 350 no `web/` e `scripts/`.
  `sourceType: "script"` e `no-undef` desligado porque o painel usa `<script>`
  classico com escopo global compartilhado.
- **`npm run lint`** e o portao do JS.
- **`npm run mapa -- --check`** e o portao do Python, e sai com codigo 1 quando
  existe arquivo acima do teto ou sem proposito declarado. Hoje sai 0.

### O mapa, que se regenera

**`ARQUITETURA.md`** na raiz, com uma linha por arquivo. Ele nao e escrito a mao:
sai do `proposito:` no cabecalho de cada arquivo, via
`Agente Orquestrador/tools/gerar_arquitetura.py` do workspace da Dodo.

E por isso que ele nao envelhece: nao existe um segundo lugar pra atualizar, e mapa
apontando pra arquivo que sumiu deixa de ser possivel.

`scripts/arquitetura.js` acha a ferramenta e **nao quebra o lint quando ela nao esta
no ambiente**, porque este repositorio tem outro dono, que nao tem o workspace da
Dodo. O `ARQUITETURA.md` ja vem gerado e commitado, entao nada depende de rodar isso.

---

## 4. As provas, porque o projeto nao tem teste

Nao existe teste neste projeto: nenhum `test_*.py`, nenhum `conftest.py`, `pytest`
fora do `requirements.txt`. A Fase 4 do processo original manda rodar typecheck,
testes e lint antes de cada commit, e o passo dos testes nao existia. O que foi
usado no lugar:

1. **Cobertura exata de linha na quebra do `web/app.js`.** Duas provas antes de
   escrever: cada uma das 2251 linhas em exatamente um arquivo, e nenhuma linha
   com conteudo alterado. A quebra moveu fatias, nao redigitou codigo.
2. **Inventario de rotas pelo esquema OpenAPI, antes contra depois:** 60 endpoints,
   zero perdido, zero novo. Contar por `app.routes` engana nesta versao do FastAPI,
   que guarda router incluido como `_IncludedRouter` e nao achata na lista.
3. **Verificador de nome global nao resolvido por AST.** Existe porque import que
   falta no corpo de uma rota nao aparece ao importar o modulo, so quando alguem
   chama a rota. **Pegou 6 imports faltando** que teriam virado erro em producao:
   `asyncio` no cnpj, `os` e `analyzer` no disparo, `asyncio`, `os` e `save_json`
   no negocio, `_evo_provider` no whatsapp, `re` no gmaps_extrair e `_clean` no
   google_maps.
4. **Prova de nenhuma linha em dois modulos** em cada quebra. Pegou dois modelos
   Pydantic (`BatchRequest` e `SequenciaRequest`) dentro de faixas de rota, e pegou
   o estado do worker (`_worker_thread`, `_worker_stop`, `_worker_cfg`,
   `_worker_lock`, `_worker_state`) indo pra fila em vez do motor.
5. **`node --check`** nos 19 arquivos JS.
6. **Conferencia no ar, em cinco boots:** `/api/saude` 200, rotas livres 200, rotas
   protegidas 401 sem cookie, raiz 303, as 13 partes do painel servindo 200, e log
   do uvicorn limpo.

**O que NAO foi verificado:** o caminho autenticado. Entrar com conta exige
credencial, entao nenhuma tela foi vista logada. E o que fica pra conferencia na
tela antes de qualquer merge.

---

## 5. Achados de codigo, nenhum criado por esta operacao

### Bug pre-existente, nao tocado

**`scrapers/instagram.py` usa `os.path.join` e `os.makedirs` nas linhas 110, 111 e
126 e nunca importa `os`.** E `NameError` garantido quando o download de midia do
Instagram roda. Nao foi consertado porque nao tem relacao com esta operacao.

### Possivel feature inacabada, preservada

**`web/js/crm_cartao.js`: o `scoreHtml` e montado e nunca usado.** Parece a pastilha
de score que faltou ser ligada no cartao do CRM. Nao foi apagado: zerar o lint
apagando esconderia a pergunta. Ficou no lugar com `eslint-disable-next-line` e o
motivo escrito ao lado.

---

## 6. O que decide se isso entra no `main`

**O proprio codigo documenta que o `web/app.js` e reescrito toda semana pelo socio.**
Esta escrito no `web/painel.js`, por uma sessao anterior da Dodo:

> *"Tudo aqui vive POR FORA do app.js, de proposito. O app.js e reescrito toda
> semana pelo socio; o que e nosso mora neste arquivo e nao entra em conflito."*

O `web/sessao.js` repete a justificativa. Uma decisao anterior nossa foi justamente
nao tocar no `app.js`, e esta operacao o quebrou em 14 arquivos.

Isso se confirmou durante a sessao: um `pull --ff-only` no meio do trabalho trouxe
tres commits do socio que nao existiam quando o plano foi escrito, e um deles mexeu
no `web/app.js`. Os numeros do plano nasceram velhos e foram refeitos pelo estado
atual (Regra de Ouro 26).

**Consequencia pratica:** a quebra do `web/app.js` conflita de forma dificil com o
proximo push dele, porque o git ve a mudanca pequena dele contra a remocao do
arquivo inteiro. A quebra do Python nao tem a mesma gravidade: ele mexeu em `app.py`
e `analyzer.py`, e ali o conflito e resolvivel.

**Caminho possivel, se o ganho importar mais que a briga:** levar pro `main` a
quebra do Python, o teto, o mapa e os propositos, e deixar o `web/app.js` inteiro
ate combinar com ele. Decisao do fundador e do socio, nao da operacao.

---

## 7. Pendencia conhecida

**`contas.py` esta em 349 de 350.** Passou porque o cabecalho de proposito somou uma
linha. A proxima linha que alguem escrever ali estoura o teto.
