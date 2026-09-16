"""Porta de entrada do Prospector: quem pode entrar e quem ainda nao pode.

O sistema saiu do computador do fundador e passou a responder na internet. Antes
a protecao era so rodar em localhost; agora e esta.

Tres ideias, e so:

  1. CONTA mora num arquivo JSON fora da imagem (o volume de dados). Qualquer
     pessoa se cadastra, mas o cadastro NAO libera: a conta nasce pendente e
     alguem com acesso de dono precisa liberar.
  2. SESSAO e um cookie assinado com HMAC. Sem banco de sessao. A conta e relida
     a cada pedido, entao tirar o acesso de alguem derruba a sessao na hora.
  3. A PRIMEIRA conta vira dona e ja nasce liberada. Sem isso ninguem poderia
     aprovar ninguem, e o sistema nasceria trancado pra todo mundo.

Nada aqui depende de servico externo: e `hashlib` e `hmac` da biblioteca padrao.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time

from config import DADOS_DIR

ARQUIVO_CONTAS = os.path.join(DADOS_DIR, "contas.json")
ARQUIVO_CHAVE = os.path.join(DADOS_DIR, "sessao.chave")

NOME_COOKIE = "prospector_sessao"
DURACAO_SESSAO = 7 * 24 * 60 * 60
MINIMO_SENHA = 6

# Freio de forca bruta, por origem.
TENTATIVAS_ATE_TRAVAR = 5
TRAVA_SEGUNDOS = 5 * 60

SCRYPT_N = 16384
SCRYPT_R = 8
SCRYPT_P = 1
TAMANHO_CHAVE = 32

_trava = threading.Lock()
_tentativas = {}


# ------------------------------------------------------------------- senha --

def gerar_hash(senha):
    """Formato guardado: scrypt:N:r:p:sal:hash, sal e hash em hexadecimal.

    Sem cifrao no meio de proposito: se um dia este valor passar por arquivo de
    variaveis do docker, o cifrao seria lido como nome de variavel e a senha
    certa passaria a ser recusada calada.
    """
    sal = os.urandom(16)
    chave = hashlib.scrypt(str(senha).encode("utf-8"), salt=sal,
                           n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=TAMANHO_CHAVE)
    return ":".join(["scrypt", str(SCRYPT_N), str(SCRYPT_R), str(SCRYPT_P),
                     sal.hex(), chave.hex()])


def conferir_senha(senha, guardado):
    partes = str(guardado or "").split(":")
    if len(partes) != 6 or partes[0] != "scrypt":
        return False
    try:
        n, r, p = int(partes[1]), int(partes[2]), int(partes[3])
        sal = bytes.fromhex(partes[4])
        esperado = bytes.fromhex(partes[5])
    except ValueError:
        return False
    if not esperado:
        return False
    try:
        obtido = hashlib.scrypt(str(senha).encode("utf-8"), salt=sal,
                                n=n, r=r, p=p, dklen=len(esperado))
    except ValueError:
        return False
    return hmac.compare_digest(obtido, esperado)


# ------------------------------------------------------------------ contas --

def _ler_tudo():
    if not os.path.exists(ARQUIVO_CONTAS):
        return []
    try:
        with open(ARQUIVO_CONTAS, "r", encoding="utf-8") as f:
            dados = json.load(f)
        return dados if isinstance(dados, list) else []
    except Exception:
        # Arquivo corrompido nao pode virar "ninguem tem acesso": isso trancaria
        # o dono do lado de fora. Devolve vazio e deixa o chamador decidir.
        return []


def _gravar_tudo(contas):
    os.makedirs(DADOS_DIR, exist_ok=True)
    temporario = ARQUIVO_CONTAS + ".tmp"
    with open(temporario, "w", encoding="utf-8") as f:
        json.dump(contas, f, ensure_ascii=False, indent=2)
    os.replace(temporario, ARQUIVO_CONTAS)


def _normalizar(email):
    return str(email or "").strip().lower()


def _agora():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def listar():
    """Contas sem o hash da senha. E o que a tela do dono mostra."""
    return [{k: v for k, v in c.items() if k != "senha"} for c in _ler_tudo()]


def buscar(email):
    alvo = _normalizar(email)
    for c in _ler_tudo():
        if c.get("email") == alvo:
            return c
    return None


def criar(email, senha):
    """Devolve (conta, erro). A primeira conta do sistema nasce dona e liberada."""
    alvo = _normalizar(email)
    if "@" not in alvo or "." not in alvo.split("@")[-1]:
        return None, "Informe um e-mail valido."
    if len(str(senha or "")) < MINIMO_SENHA:
        return None, "A senha precisa de pelo menos %d caracteres." % MINIMO_SENHA

    with _trava:
        contas = _ler_tudo()
        if any(c.get("email") == alvo for c in contas):
            return None, "Ja existe uma conta com esse e-mail."
        primeira = len(contas) == 0
        conta = {
            "email": alvo,
            "senha": gerar_hash(senha),
            "status": "aprovado" if primeira else "pendente",
            "papel": "dono" if primeira else "usuario",
            "criada_em": _agora(),
            "aprovada_em": _agora() if primeira else "",
        }
        contas.append(conta)
        _gravar_tudo(contas)
    return {k: v for k, v in conta.items() if k != "senha"}, ""


def _mudar(email, mudanca):
    alvo = _normalizar(email)
    with _trava:
        contas = _ler_tudo()
        for c in contas:
            if c.get("email") == alvo:
                c.update(mudanca)
                _gravar_tudo(contas)
                return True
    return False


def liberar(email):
    return _mudar(email, {"status": "aprovado", "aprovada_em": _agora()})


def recusar(email):
    """Apaga a conta. Recusar e sumir com o pedido, nao guardar um nao."""
    alvo = _normalizar(email)
    with _trava:
        contas = _ler_tudo()
        restantes = [c for c in contas if c.get("email") != alvo or c.get("papel") == "dono"]
        if len(restantes) == len(contas):
            return False
        _gravar_tudo(restantes)
    return True


def tirar_acesso(email):
    """Volta a conta pra pendente. O dono nunca perde o proprio acesso."""
    conta = buscar(email)
    if not conta or conta.get("papel") == "dono":
        return False
    return _mudar(email, {"status": "pendente", "aprovada_em": ""})


# ------------------------------------------------------------------ sessao --

def _chave_de_assinatura():
    """Uma chave por instalacao, guardada no volume.

    Se ela fosse sorteada a cada partida, toda publicacao deslogaria todo mundo.
    """
    if os.path.exists(ARQUIVO_CHAVE):
        try:
            with open(ARQUIVO_CHAVE, "r", encoding="utf-8") as f:
                chave = f.read().strip()
            if chave:
                return chave.encode("utf-8")
        except Exception:
            pass
    chave = secrets.token_urlsafe(32)
    os.makedirs(DADOS_DIR, exist_ok=True)
    with open(ARQUIVO_CHAVE, "w", encoding="utf-8") as f:
        f.write(chave)
    try:
        os.chmod(ARQUIVO_CHAVE, 0o600)
    except Exception:
        pass
    return chave.encode("utf-8")


def _assinar(mensagem):
    return base64.urlsafe_b64encode(
        hmac.new(_chave_de_assinatura(), mensagem.encode("utf-8"), hashlib.sha256).digest()
    ).decode("ascii").rstrip("=")


def criar_cookie(email):
    corpo = "%s|%d" % (_normalizar(email), int(time.time()) + DURACAO_SESSAO)
    return "%s.%s" % (base64.urlsafe_b64encode(corpo.encode("utf-8")).decode("ascii").rstrip("="),
                      _assinar(corpo))


def ler_cookie(valor):
    """Devolve a conta viva do dono do cookie, ou None.

    A conta e RELIDA aqui, nunca vem de dentro do cookie: assim tirar o acesso
    de alguem derruba a sessao dela no pedido seguinte, sem esperar expirar.
    """
    if not valor or "." not in str(valor):
        return None
    codificado, assinatura = str(valor).rsplit(".", 1)
    try:
        corpo = base64.urlsafe_b64decode(
            codificado + "=" * (-len(codificado) % 4)).decode("utf-8")
    except Exception:
        return None
    if not hmac.compare_digest(_assinar(corpo), assinatura):
        return None
    if "|" not in corpo:
        return None
    email, expira = corpo.rsplit("|", 1)
    try:
        if int(expira) < time.time():
            return None
    except ValueError:
        return None
    conta = buscar(email)
    if not conta or conta.get("status") != "aprovado":
        return None
    return {k: v for k, v in conta.items() if k != "senha"}


def conta_do_cookie_mesmo_pendente(valor):
    """Como o ler_cookie, mas devolve tambem quem ainda espera aprovacao.

    E o que a tela de espera precisa: a pessoa esta identificada, so nao esta
    liberada. Nao serve pra autorizar nada.
    """
    if not valor or "." not in str(valor):
        return None
    codificado, assinatura = str(valor).rsplit(".", 1)
    try:
        corpo = base64.urlsafe_b64decode(
            codificado + "=" * (-len(codificado) % 4)).decode("utf-8")
    except Exception:
        return None
    if not hmac.compare_digest(_assinar(corpo), assinatura):
        return None
    if "|" not in corpo:
        return None
    email, expira = corpo.rsplit("|", 1)
    try:
        if int(expira) < time.time():
            return None
    except ValueError:
        return None
    conta = buscar(email)
    if not conta:
        return None
    return {k: v for k, v in conta.items() if k != "senha"}


# --------------------------------------------------------- forca bruta ------

def travado(origem):
    registro = _tentativas.get(origem)
    if not registro:
        return False
    contagem, ate = registro
    if ate > time.time():
        return True
    if ate:
        _tentativas.pop(origem, None)
    return False


def marcar_erro(origem):
    contagem, _ = _tentativas.get(origem, (0, 0))
    contagem += 1
    ate = time.time() + TRAVA_SEGUNDOS if contagem >= TENTATIVAS_ATE_TRAVAR else 0
    _tentativas[origem] = (contagem, ate)
    # Teto simples pra memoria nao crescer sem fim com origens diferentes.
    if len(_tentativas) > 5000:
        _tentativas.clear()


def limpar_erros(origem):
    _tentativas.pop(origem, None)


def entrar(email, senha, origem=""):
    """Devolve (conta, erro). Erro em linguagem de gente, nunca detalhando qual
    metade da dupla estava errada: dizer 'esse e-mail nao existe' entrega quem
    tem conta."""
    if travado(origem):
        return None, "Muitas tentativas. Espere 5 minutos e tente de novo."
    conta = buscar(email)
    if not conta or not conferir_senha(senha, conta.get("senha")):
        marcar_erro(origem)
        return None, "E-mail ou senha nao confere."
    limpar_erros(origem)
    return {k: v for k, v in conta.items() if k != "senha"}, ""
