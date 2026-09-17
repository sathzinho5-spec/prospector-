# Evolution API - como ligar o disparo real
# ============================================================
# A Evolution API conecta seu WhatsApp via QR code e o Prospector
# envia as mensagens sozinho. Sem ela, o disparo fica no modo Simulado.
#
# ------------------------------------------------------------
# OPÇÃO A — LOCAL (seu PC, para testar)
# ------------------------------------------------------------
#   cd evolution
#   docker compose up -d
#
# ------------------------------------------------------------
# OPÇÃO B — VPS (produção, 24h no ar) ⭐ RECOMENDADO
# ------------------------------------------------------------
# 1. Copie a pasta evolution para a VPS (ou git pull, ela já está no repo).
# 2. Na VPS, crie a API key forte e suba:
#
#      export EVO_APIKEY='troque-por-uma-chave-longa-e-aleatoria'
#      export DB_PASSWORD='outra-senha-forte'
#      docker compose -f docker-compose.vps.yml up -d
#
# 3. No Prospector (site), vá em Configurações IA > Disparo:
#      URL base ...: http://evolution:8080
#      API key .....: a mesma EVO_APIKEY de cima
#      Instância ...: prospector (ou chip2, chip3 para os extras)
#    Salve. (Também aceita env DISPARO_EVO_URL / DISPARO_EVO_KEY no container.)
# 4. Aba Comercial > Disparo > Conectar WhatsApp > escaneie o QR com o
#    CHIP SECUNDÁRIO (WhatsApp > Aparelhos conectados).
# 5. Teste no meu número > Iniciar disparo.
#
# NOTAS DE PRODUÇÃO
# - A API NÃO tem porta pública: só o Prospector (mesma rede Docker) a alcança.
# - Sessões/QR ficam nos volumes (evo_instances, evo_pgdata): sobrevivem a restart.
# - Para trocar a key depois: atualize EVO_APIKEY, recrie o container
#   (docker compose -f docker-compose.vps.yml up -d --force-recreate evolution)
#   e atualize a mesma key nas Configurações do Prospector.
#
# DICAS DE SEGURANÇA (importante)
# ------------------------------------------------------------
# - Use um CHIP SECUNDÁRIO, nunca seu número principal
# - Comece com 20-30 envios/dia na 1ª semana (aquecimento)
# - Mantenha pausas 45-120s e janela 08h-20h (padrão do sistema)
# - Mensagens sempre com SAIR no final (o sistema já adiciona)
# - Disparo em massa viola os Termos do WhatsApp: existe risco de
#   banimento do número. Para zero risco, use a Meta Cloud API.
EVO_APIKEY=prospector123
DB_PASSWORD=evolution123
