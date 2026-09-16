# Evolution API - como ligar o disparo real (5 min + QR code)
# ============================================================
# A Evolution API conecta seu WhatsApp via QR code e o Prospector
# envia as mensagens sozinho. Sem ela, o disparo fica no modo Simulado.
#
# PASSO 1 - Subir a Evolution (precisa do Docker instalado)
# ------------------------------------------------------------
#   cd evolution
#   docker compose up -d
#
# PASSO 2 - Conectar o WhatsApp DENTRO do Prospector
# ------------------------------------------------------------
#   1. Abra o Prospector > aba Comercial > painel "Disparo automático"
#   2. Clique em "Conectar WhatsApp" -> aparece o QR code na tela
#   3. No celular: WhatsApp > Config > Aparelhos conectados > Conectar
#      e escaneie o QR. O status muda para "conectado".
#
# PASSO 3 - Configurar (só 1 vez, em Configurações IA > Disparo)
# ------------------------------------------------------------
#   URL base ......: http://localhost:8080
#   API key .......: prospector123  (ou o EVO_APIKEY que você definir)
#   Instância .....: prospector     (qualquer nome, use o mesmo no QR)
#   Provedor ......: Evolution API (QR code)
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
