# proposito: telas de acesso e as rotas de conta: entrar, criar, liberar, tirar
import os

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse

import contas
from nucleo import WEB_DIR, _origem, _quem, _so_dono
from rotas.modelos import ContaRequest, EntrarRequest, SenhaRequest

router = APIRouter()


# ===================== TELAS E ROTAS DE ACESSO =====================
# As quatro telas sao o MESMO arquivo: quem escolhe qual cartao aparece e o
# acesso.js, olhando o endereco e o estado da sessao. Separar em quatro arquivos
# duplicaria o cabecalho e a marca em todos eles.

def _tela_de_acesso():
    return FileResponse(os.path.join(WEB_DIR, "acesso.html"))
@router.get("/entrar")
def tela_entrar():
    return _tela_de_acesso()


@router.get("/criar-conta")
def tela_criar_conta():
    return _tela_de_acesso()


@router.get("/aguardando")
def tela_aguardando():
    return _tela_de_acesso()


@router.get("/acessos")
def tela_acessos():
    return _tela_de_acesso()


@router.get("/senha")
def tela_senha():
    return _tela_de_acesso()


def _por_o_cookie(resposta, email, request=None):
    # O Secure so entra quando o pedido chegou por https. Ligado sempre, ele
    # quebraria quem roda a ferramenta local em http na rede; desligado sempre,
    # o navegador mandaria a sessao na primeira visita em http, antes de o proxy
    # empurrar pro https.
    seguro = bool(request) and request.url.scheme == "https"
    resposta.set_cookie(
        contas.NOME_COOKIE, contas.criar_cookie(email),
        max_age=contas.DURACAO_SESSAO, httponly=True, samesite="lax",
        secure=seguro, path="/")
    return resposta


@router.get("/api/acesso/eu")
def api_acesso_eu(request: Request):
    """O estado que as telas leem pra decidir o que mostrar."""
    conta = contas.conta_do_cookie_mesmo_pendente(request.cookies.get(contas.NOME_COOKIE))
    if not conta:
        return {"entrou": False}
    return {
        "entrou": True,
        "email": conta.get("email"),
        "status": conta.get("status"),
        "papel": conta.get("papel"),
        "criada_em": conta.get("criada_em"),
        "dono": conta.get("papel") == "dono",
    }


@router.post("/api/acesso/entrar")
def api_acesso_entrar(req: EntrarRequest, request: Request):
    conta, erro = contas.entrar(req.email, req.senha, _origem(request))
    if erro:
        return JSONResponse({"erro": erro}, status_code=401)
    corpo = {"ok": True, "status": conta.get("status"), "dono": conta.get("papel") == "dono"}
    return _por_o_cookie(JSONResponse(corpo), conta.get("email"), request)


@router.post("/api/acesso/criar")
def api_acesso_criar(req: EntrarRequest, request: Request):
    conta, erro = contas.criar(req.email, req.senha)
    if erro:
        return JSONResponse({"erro": erro}, status_code=400)
    # Ja entra com a sessao: se a conta for a primeira, cai direto na ferramenta;
    # se nao for, cai na tela de espera sabendo quem e.
    corpo = {"ok": True, "status": conta.get("status"), "dono": conta.get("papel") == "dono"}
    return _por_o_cookie(JSONResponse(corpo), conta.get("email"), request)


@router.post("/api/acesso/trocar-senha")
def api_acesso_trocar_senha(req: SenhaRequest, request: Request):
    """Troca a senha de QUEM ESTA LOGADO, e de mais ninguem.

    O e-mail nao vem do corpo do pedido de proposito: se viesse, qualquer pessoa
    logada trocaria a senha de outra conta mandando outro e-mail.
    """
    conta = _quem(request)
    if not conta:
        raise HTTPException(status_code=401, detail="Entre para trocar a senha.")
    ok, erro = contas.trocar_senha(conta.get("email"), req.senha_atual, req.senha_nova)
    if not ok:
        return JSONResponse({"erro": erro}, status_code=400)
    # A sessao continua valendo: quem trocou a propria senha nao precisa entrar
    # de novo, e o cookie nao carrega a senha dentro dele.
    return {"ok": True}


@router.post("/api/acesso/sair")
def api_acesso_sair():
    resposta = JSONResponse({"ok": True})
    resposta.delete_cookie(contas.NOME_COOKIE, path="/")
    return resposta


@router.get("/api/acesso/contas")
def api_acesso_contas(request: Request):
    _so_dono(request)
    return {"contas": contas.listar()}


@router.post("/api/acesso/liberar")
def api_acesso_liberar(req: ContaRequest, request: Request):
    _so_dono(request)
    if not contas.liberar(req.email):
        raise HTTPException(status_code=404, detail="Conta nao encontrada.")
    return {"ok": True}


@router.post("/api/acesso/recusar")
def api_acesso_recusar(req: ContaRequest, request: Request):
    _so_dono(request)
    if not contas.recusar(req.email):
        raise HTTPException(status_code=404, detail="Conta nao encontrada.")
    return {"ok": True}


@router.post("/api/acesso/tirar")
def api_acesso_tirar(req: ContaRequest, request: Request):
    _so_dono(request)
    if not contas.tirar_acesso(req.email):
        raise HTTPException(status_code=400, detail="Essa conta nao pode perder o acesso.")
    return {"ok": True}

