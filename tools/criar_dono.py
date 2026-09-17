"""Cria ou promove uma conta de dono do Prospector.

Existe porque a regra normal e "a PRIMEIRA conta vira dona", e isso resolve so o
primeiro dono. Quando o sistema precisa de mais de um, ou quando o dono precisa
nascer antes de o endereco abrir pro mundo, o caminho e este.

Roda dentro do container, onde o volume de dados esta montado:

    docker exec prospector python tools/criar_dono.py --email x@y.com --senha SEGREDO

Idempotente: se a conta ja existe, ele nao recria, so promove a dona e libera.
Com --senha numa conta que ja existe, a senha e trocada. E tambem o unico jeito
de trocar senha hoje, ja que nao existe tela pra isso.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import contas  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--email", required=True)
    p.add_argument("--senha", required=True)
    args = p.parse_args()

    existente = contas.buscar(args.email)
    if existente:
        contas._mudar(args.email, {
            "senha": contas.gerar_hash(args.senha),
            "status": "aprovado",
            "papel": "dono",
        })
        print("conta ja existia: promovida a dona, liberada e com senha nova ->", args.email)
        return

    conta, erro = contas.criar(args.email, args.senha)
    if erro:
        sys.exit("nao deu: " + erro)
    if conta.get("papel") != "dono":
        # Nao era a primeira conta do sistema, entao nasceu comum. Promove.
        contas._mudar(args.email, {"status": "aprovado", "papel": "dono"})
    print("conta de dono criada ->", args.email)


if __name__ == "__main__":
    main()
