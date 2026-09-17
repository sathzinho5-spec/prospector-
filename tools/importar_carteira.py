# proposito: importa a carteira de leads da planilha do Drive pro Prospector
"""Importa a carteira de leads da planilha pra dentro do Prospector.

A planilha vive no Drive do fundador ("Prospeccao Ativa - Vitrine Rapida.xlsx",
aba Leads) e e a fonte dos 30 leads que a operacao ja tinha. Esta ferramenta
existe porque isso vai se repetir: a planilha ganha linha nova e a carteira
precisa entrar de novo sem ninguem digitar.

Duas coisas que ela faz e que nao sao obvias:

1. **DONO.** Cada lead entra com o e-mail de quem e dono dele. As colunas dono e
   disparo_ativo nascem por migracao de SQL, nao por aqui: mudar banco em
   producao passa por quem tem a chave, nao por um importador de planilha. Este
   arquivo so CONFERE que elas existem antes de gravar.
2. **DESATIVADO PRO DISPARO.** Com --desativado, o telefone de cada lead entra
   na lista de numero bloqueado do disparo. Isso NAO e enfeite de tela: o
   bloqueio e conferido na entrada da fila, no robo e no envio manual, entao o
   lead pode ser visto, editado e movido no CRM sem nunca sair uma mensagem.

Uso:
    python tools/importar_carteira.py --planilha "CAMINHO.xlsx" \
        --dono do.digiital@gmail.com --desativado
    python tools/importar_carteira.py --planilha ... --dry-run
"""
import argparse
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import load_settings  # noqa: E402
from scrapers import disparo  # noqa: E402

# A planilha fala uma lingua, a tabela fala outra. Este e o dicionario entre as
# duas, e e o unico lugar onde os dois vocabularios se encontram.
DE_PARA = {
    "Nome": "nome",
    "Nicho": "categoria",
    "Cidade": "cidade",
    "Numero E164": "telefone",
    "Instagram": "instagram",
    "Nota": "nota",
    "Avaliacoes": "avaliacoes",
    "Informacoes": "descricao",
    "Origem": "consulta",
}


def identificador(nome, telefone):
    """Mesmo formato de id que o storage.py usa, pra reimportar nao duplicar."""
    return hashlib.md5(("%s|%s" % (nome, telefone)).encode()).hexdigest()[:16]


def ler_planilha(caminho, aba):
    try:
        import pandas as pd
    except ImportError:
        sys.exit("falta o pandas: pip install -r requirements.txt")
    if not os.path.exists(caminho):
        sys.exit("nao achei a planilha: " + caminho)
    df = pd.ExcelFile(caminho).parse(aba)

    linhas = []
    for _, linha in df.iterrows():
        lead = {}
        for coluna, campo in DE_PARA.items():
            if coluna not in df.columns:
                continue
            valor = linha[coluna]
            lead[campo] = "" if valor != valor or valor is None else str(valor).strip()
        tel = disparo._norm_phone(lead.get("telefone"))
        if not tel or not lead.get("nome"):
            continue
        lead["telefone"] = tel
        lead["id"] = identificador(lead["nome"], tel)
        linhas.append(lead)
    return linhas


def conferir_colunas(cliente):
    """As colunas dono e disparo_ativo precisam existir ANTES do carregamento.

    Elas nascem pela migracao de SQL, nao por aqui: criar coluna e mudanca de
    banco, e mudanca de banco em producao passa por quem tem a chave, nao por
    um importador de planilha.
    """
    try:
        cliente.table("leads").select("dono,disparo_ativo").limit(1).execute()
        return True, ""
    except Exception as e:
        return False, str(e)[:200]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--planilha", required=True)
    p.add_argument("--aba", default="Leads")
    p.add_argument("--dono", required=True, help="e-mail da conta dona dos leads")
    p.add_argument("--desativado", action="store_true",
                   help="desativa o disparo pra todos os numeros importados")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    leads = ler_planilha(args.planilha, args.aba)
    print("lidos da planilha: %d leads" % len(leads))
    sem_cidade = sum(1 for l in leads if not l.get("cidade"))
    if sem_cidade:
        print("ATENCAO: %d sem cidade. A pendencia da nota pede a cidade preenchida;"
              % sem_cidade)
        print("         ela NAO e inventada aqui - continua vazia ate alguem preencher.")

    for l in leads:
        l["dono"] = args.dono
        l["disparo_ativo"] = not args.desativado

    if args.dry_run:
        print("\n--dry-run: nada foi gravado. Os tres primeiros ficariam assim:")
        for l in leads[:3]:
            print("   ", l.get("nome"), "|", l.get("telefone"), "| dono", l.get("dono"),
                  "| disparo", "ativo" if l.get("disparo_ativo") else "DESATIVADO")
        return

    s = load_settings()
    url = s.get("supabase_url")
    chave = s.get("supabase_secret") or s.get("supabase_publishable")
    if not url or not chave:
        sys.exit("o Supabase nao esta configurado nas Configuracoes do Prospector")

    from supabase import create_client
    cliente = create_client(url, chave)

    ok, erro = conferir_colunas(cliente)
    if not ok:
        sys.exit("a tabela leads nao tem as colunas dono e disparo_ativo ainda. "
                 "Rode a migracao de SQL antes. Motivo: " + erro)
    print("colunas dono e disparo_ativo: presentes")

    gravados = 0
    for i in range(0, len(leads), 100):
        cliente.table("leads").upsert(leads[i:i + 100], on_conflict="id").execute()
        gravados += len(leads[i:i + 100])
    print("gravados no banco: %d" % gravados)

    if args.desativado:
        for l in leads:
            disparo.bloquear(l["telefone"], "carteira importada desativada pro disparo")
        print("desativados pro disparo: %d numeros" % len(leads))
        print("o bloqueio vale na entrada da fila, no robo e no envio manual.")


if __name__ == "__main__":
    main()
