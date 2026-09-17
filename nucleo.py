# proposito: estado em memoria, porta de acesso e quem esta do outro lado
import os

from fastapi import HTTPException

import config
import contas


STATE = {"businesses": [], "last_search": ""}
WEB_DIR = os.path.join(config.BASE_DIR, "web")
os.makedirs(WEB_DIR, exist_ok=True)
# ===================== PORTA DE ACESSO =====================
# Ate 16/09/2026 o Prospector so rodava no computador do fundador e a protecao
# era essa. Agora ele responde na internet, entao tudo passa por aqui.

# O que abre sem sessao. Nao entra nada que mostre dado: so as proprias telas de
# acesso, os arquivos que elas carregam e a rota de saude da publicacao.
LIVRES = {"/entrar", "/criar-conta", "/aguardando", "/api/saude", "/favicon.ico"}
PREFIXOS_LIVRES = ("/static/", "/api/acesso/")
def _origem(request):
    """Quem esta tentando entrar, pro freio de forca bruta.

    Atras do proxy, request.client e o proprio proxy: sem olhar o
    X-Forwarded-For, cinco erros de qualquer pessoa trancariam todas as outras.
    O primeiro endereco da lista e o de quem originou o pedido.
    """
    encaminhado = request.headers.get("x-forwarded-for", "")
    if encaminhado:
        return encaminhado.split(",")[0].strip()
    return (request.client.host if request.client else "") or "desconhecida"


def _quem(request):
    return contas.ler_cookie(request.cookies.get(contas.NOME_COOKIE))


def _so_dono(request):
    conta = _quem(request)
    if not conta or conta.get("papel") != "dono":
        raise HTTPException(status_code=403, detail="So o dono mexe nos acessos.")
    return conta


