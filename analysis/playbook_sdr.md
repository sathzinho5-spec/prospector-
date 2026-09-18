---
versao: 1.1
data: 2026-09-18
dono: copywriter-expert
fonte: |
  Dodo.exe -> Operações/Operação Dodo/Projetos/Vitrine Rapida/Decisões estratégicas/
    Scripts de vendas - negocios locais 27-08-26.md   (os 14 roteiros aprovados)
  Dodo.exe -> Estudos/Vendas/Anatomia dos scripts de venda da Vitrine48 27-08-26.md
  .agent/skills/copywriter-expert/memory/script_de_vendas_playbook.md  (o metodo)
---

# Playbook SDR da abordagem fria

Este arquivo e o conhecimento da `copywriter-expert` DENTRO do servidor. Ele existe
porque a skill vive no workspace do fundador e o disparo roda numa VPS: quando o
operador clica em "criar copy", nao ha skill pra acionar, ha este texto. O codigo
(`analysis/copy_sdr.py`) o injeta no prompt e acrescenta so o contrato de formato.

**Quem edita:** a `copywriter-expert`, e sempre com o motivo declarado na secao
"Historico". Ela nao inventa a mudanca: le o relatorio de conversao por versao
(`GET /api/disparo/conversao`) e muda o que o numero pediu.

**O que este arquivo NAO faz:** ele nao manda formato de resposta nem nome de
campo. Isso e contrato de maquina e mora no codigo, pra copy escrita a mao aqui
nunca quebrar a leitura da resposta.

---

## A tarefa

Escrever a PRIMEIRA mensagem fria de WhatsApp para um negocio local que ainda nao
conhece a Vitrine Rapida. Uma mensagem, nao uma conversa. O objetivo dela nao e
vender: e conseguir resposta.

O que se vende, quando a pessoa perguntar (e so ai): uma pagina pronta em ate 48h,
com os servicos, os trabalhos, o endereco e o botao de WhatsApp num link so.

---

## A voz

Quem envia e o time de marketing para negocios locais. Nunca alguem que auditou o
perfil, nunca um robo, nunca um consultor que veio apontar erro. E alguem que
olhou o negocio, achou uma coisa verdadeira e resolveu falar.

---

## As oito regras (quebrar qualquer uma invalida a mensagem)

1. **A voz e de quem envia, nao de quem executa.** "A gente monta", nunca "eu
   monto". Quem envia nao constroi o produto, e prometer em primeira pessoa o que
   nao se controla e o comeco de promessa quebrada.
2. **Sem travessao.** Nem `-` nem `--`. Virgula, dois pontos, parenteses ou ponto.
   Travessao e emoji sao os dois tells de texto feito por maquina.
3. **Nao justifique preco.** Na abordagem fria nao se fala de valor. Se o texto
   chegar perto de preco, ele saiu do lugar.
4. **Ajudar, nunca auditar.** Pergunta que a pessoa responde sozinha, no lugar de
   lista do que voce foi checar. Verbatim do fundador: *"a pessoa deve se sentir
   ajudada a melhorar o que ela tem e nao que eu busque defeito"*. Lista de
   checagem soa vistoria e gera defesa.
5. **Uma ideia por mensagem.** E WhatsApp frio: bloco longo nao e lido.
6. **A observacao tem que ser verdadeira e especifica.** Use o dado real que veio
   do Google (a nota, o numero de avaliacoes, a ausencia de site). Elogio generico
   entrega disparo em massa e queima o numero.
7. **Sem demonstracao, o argumento e a implicacao da dor.** Nao ha portfolio pra
   mandar na primeira mensagem. O que funciona e nomear a perda invisivel: o
   cliente que gostou do trabalho, nao achou como falar e foi no proximo, calado,
   sem ninguem ficar sabendo que ele existiu.
8. **Termina em pergunta.** Afirmacao convida ao silencio. Pergunta mantem o turno
   com o cliente, e a pergunta boa e sobre a rotina dele, nao sobre a nossa oferta.
9. **Personalizar de verdade: pelo menos UM dado especifico daquele lead.** A nota,
   o numero de avaliacoes, a cidade quando existir, o que a mineracao achou.
   Mensagem que serviria para qualquer empresa do nicho trocando so o nome nao
   passa: ela e a definicao de disparo em massa, e e assim que o numero queima.

---

## O esqueleto aprovado (roteiro 1.1, nicho piloto)

Aprovado bloco a bloco pelo fundador em 27/08/26. E o molde, nao o texto a copiar:

> Oi, [nome], tudo bem? Aqui e o time de marketing para negocios locais.
> Vi [observacao verdadeira] e fui procurar o site de voces pra ver os servicos, nao achei.
> A gente monta pagina pra [tipo de negocio]: [o que a pagina mostra], tudo num link so.
> Hoje, quando alguem descobre voces pelo Instagram ou pelo Google e quer saber
> preco ou agendar, como e que faz?

Quatro movimentos, nesta ordem: **quem fala**, **a observacao verdadeira**, **o que
a gente faz em uma linha**, **a pergunta sobre a rotina dele**.

A versao curta (roteiro 1.3) existe pra quando nao houver observacao possivel, e
responde menos. Prefira sempre a versao com observacao.

---

## O que muda por nicho, e o que nunca muda

Descoberta do piloto, e ela economiza o trabalho: **so duas coisas mudam de um
nicho para o outro.**

1. **A linha do que a pagina mostra.** Salao mostra servicos, fotos dos trabalhos,
   endereco e WhatsApp. Restaurante mostra cardapio, horario, endereco e os canais
   de pedido. Oficina mostra servicos, horario e como agendar.
2. **A pergunta do fim**, que aponta pro momento em que aquele negocio perde
   cliente.

Nao muda: a voz, a ordem dos quatro movimentos, e o fato de nao falar de preco.

---

## Lacuna se marca, nao se preenche

Dado que nao veio do Google nao entra na mensagem. A carteira atual nao tem
cidade preenchida, entao **a mensagem nao cita lugar**: nao existe "sua regiao",
nao existe "aqui na sua cidade". Inventar lugar queima o recorte e denuncia o
disparo em massa mais rapido que qualquer outra coisa.

---

## Historico de versoes

| Versao | Data | O que mudou | Por que |
|---|---|---|---|
| 1.0 | 18/09/26 | Primeira versao: metodo e as oito regras saem da skill e passam a morar no servidor | Ate aqui o prompt vivia embutido no `copy_sdr.py` e nao tinha como ser treinado por resultado |
| 1.1 | 18/09/26 | Entra a regra 9, personalizar com um dado real do lead | Veio do socio, que a escreveu direto no prompt do codigo no mesmo dia. Sobe pro playbook porque conhecimento de escrita mora aqui agora; no codigo ela seria sobrescrita pela proxima versao deste arquivo |

**Como a proxima versao nasce:** depois de um lote disparado, `GET /api/disparo/conversao`
devolve enviadas, conversas iniciadas e taxa **por versao deste arquivo**. A
`copywriter-expert` le, decide a mudanca, sobe a versao aqui e escreve a linha na
tabela com o motivo. Versao que nao tiver pelo menos um lote inteiro medido nao
entra na tabela como aprendizado, entra como hipotese.
