# proposito: carrega o playbook SDR do disco e diz qual versao dele esta no ar
"""
O conhecimento da copywriter-expert virou arquivo (`playbook_sdr.md`) pra poder
viajar com a imagem ate a VPS. Este modulo e a unica porta de leitura dele.

Duas decisoes que valem o arquivo separado:

1. **Le do disco a cada chamada, com cache por mtime.** Na VPS o arquivo so muda
   quando a imagem sobe, entao o cache nunca erra; na maquina de quem escreve, o
   texto novo vale na proxima geracao, sem reiniciar o servidor. Cache eterno
   faria a copywriter editar o playbook e jurar que o servidor ignorou.

2. **Playbook ausente nao derruba a geracao.** Deploy quebrado, arquivo fora do
   pacote, permissao errada: a copy continua saindo com as regras minimas
   embutidas no copy_sdr, e a versao volta como 'indisponivel' pra denunciar na
   metrica em vez de sumir em silencio.
"""
import os
import re

CAMINHO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "playbook_sdr.md")

VERSAO_AUSENTE = "indisponivel"

# Casa SO o bloco de frontmatter do topo: a linha ---, o miolo, e a linha ---
# fechadora inteira. O corpo do playbook usa --- como separador de secao, e
# cortar no primeiro --- que aparecesse devolveria um pedaco do arquivo como se
# fosse o playbook inteiro, que foi exatamente o que aconteceu na primeira versao.
_FRONTMATTER = re.compile(r"\A---[^\S\n]*\n.*?\n---[^\S\n]*(?:\n|\Z)", re.DOTALL)

_cache = {"mtime": None, "texto": "", "versao": VERSAO_AUSENTE}


def _extrair_versao(bruto):
    """A versao mora no frontmatter. Sem ela o arquivo existe mas nao e
    rastreavel, e copy medida contra versao desconhecida nao ensina nada."""
    m = re.search(r"^versao:[ \t]*(.+)$", bruto, re.MULTILINE)
    return m.group(1).strip() if m else VERSAO_AUSENTE


def _sem_frontmatter(bruto):
    m = _FRONTMATTER.match(bruto)
    return bruto[m.end():] if m else bruto


def _vazio():
    _cache.update({"mtime": None, "texto": "", "versao": VERSAO_AUSENTE})
    return _cache


def _carregar():
    try:
        mtime = os.path.getmtime(CAMINHO)
    except OSError:
        return _vazio()
    if _cache["mtime"] == mtime:
        return _cache
    try:
        with open(CAMINHO, "r", encoding="utf-8") as fh:
            bruto = fh.read()
    except OSError:
        return _vazio()
    _cache.update({"mtime": mtime,
                   "texto": _sem_frontmatter(bruto).strip(),
                   "versao": _extrair_versao(bruto)})
    return _cache


def texto():
    """O playbook sem o frontmatter. Vazio quando o arquivo nao esta la."""
    return _carregar()["texto"]


def versao():
    """Carimbo que segue a copy ate o relatorio de conversao."""
    return _carregar()["versao"]


def disponivel():
    return bool(texto())
