#!/usr/bin/env bash
# Publica o Prospector na VPS quando aparece commit novo no GitHub.
#
# Mesmo desenho do cameras e do painel da Vitrine Rapida: quem chama e o
# temporizador prospector-deploy.timer, de 2 em 2 minutos. Sem commit novo ele
# sai em silencio. Roda na VPS de proposito: nenhuma credencial do servidor
# fica guardada no GitHub.
#
# O repositorio e publico, entao a leitura e por HTTPS e nao existe chave de
# implantacao pra guardar.
set -euo pipefail

REPO=/srv/prospector
IMAGEM=prospector
CONTAINER=prospector
LOG=/var/log/prospector-deploy.log
REDE=nginx-proxy-manager_default
# As configuracoes e os resultados vivem FORA do container. Sem isso, cada
# publicacao apagaria a chave da OpenAI e o sessionid do Instagram.
DADOS=/srv/prospector-dados

# Um deploy por vez. Se o anterior ainda roda, este sai sem fazer nada.
exec 9>/var/lock/prospector-deploy.lock
flock -n 9 || exit 0

registrar() { echo "[$(date '+%F %T')] $*" >> "$LOG"; }

if [ -f "$LOG" ] && [ "$(wc -l < "$LOG")" -gt 2000 ]; then
    tail -n 500 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi

cd "$REPO"
git fetch --quiet origin main
local_commit=$(git rev-parse HEAD)
remoto_commit=$(git rev-parse origin/main)

# Nada novo e o container de pe: nada a fazer. Container ausente publica mesmo
# sem commit novo (e o caso da primeira vez).
if [ "$local_commit" = "$remoto_commit" ] && [ -n "$(docker ps -q -f "name=^/${CONTAINER}$")" ]; then
    exit 0
fi

registrar "publicando: ${local_commit:0:7} -> ${remoto_commit:0:7} ($(git log -1 --format=%s origin/main))"
mkdir -p "$DADOS"
git reset --hard --quiet origin/main

# Roda de uma copia instalada: se rodasse do repositorio, o git reset acima
# reescreveria o arquivo no meio da execucao. A copia nova vale na PROXIMA vez.
INSTALADO=/usr/local/bin/publicar-prospector.sh
if ! cmp -s "$REPO/deploy/publicar.sh" "$INSTALADO"; then
    install -m 755 "$REPO/deploy/publicar.sh" "$INSTALADO"
    registrar "o proprio publicador mudou; a versao nova vale a partir da proxima execucao."
fi

# A imagem so troca se a construcao passar.
if ! docker build -t "$IMAGEM:novo" . >> "$LOG" 2>&1; then
    registrar "FALHOU ao construir a imagem. O que esta no ar segue na versao anterior."
    exit 1
fi

anterior=$(docker inspect "$IMAGEM:atual" --format '{{.Id}}' 2>/dev/null || echo "")
docker tag "$IMAGEM:novo" "$IMAGEM:atual"

subir() {
    docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
    # 1g de memoria e de /dev/shm porque quem gasta aqui e o Chromium: com os
    # 64m padrao de memoria compartilhada ele fecha a aba no meio da varredura.
    docker run -d --name "$CONTAINER" --restart unless-stopped \
        --network "$REDE" --memory 1g --shm-size 1g --cpus 2 \
        -v "$DADOS:/app/dados" \
        "$IMAGEM:atual" >/dev/null
}

subir

# Nao basta o container existir: ele precisa responder.
saudavel=0
for _ in $(seq 1 15); do
    sleep 2
    if docker exec "$CONTAINER" python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/saude', timeout=3).status==200 else 1)" >/dev/null 2>&1; then
        saudavel=1
        break
    fi
done

if [ "$saudavel" -eq 1 ]; then
    registrar "publicado: ${remoto_commit:0:7} respondendo"
    docker image prune -f >/dev/null 2>&1 || true
    exit 0
fi

registrar "ATENCAO: a versao ${remoto_commit:0:7} subiu mas nao respondeu. Voltando para a anterior."
if [ -n "$anterior" ]; then
    docker tag "$anterior" "$IMAGEM:atual"
    subir
    registrar "voltou para a versao anterior."
else
    registrar "nao havia versao anterior guardada para voltar."
fi
exit 1
