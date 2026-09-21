# proposito: trava contra o bug do split 042e1b5, que perdeu o return e fez
# toda busca raspar por minutos e devolver 404. Scraper de verdade precisa de
# navegador e rede, entao aqui vai a garantia barata: o contrato da funcao
# (devolve a lista) e verificado na arvore do codigo a cada rodada de testes.
import ast
import os


def _fonte():
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(raiz, "scrapers", "google_maps.py"), encoding="utf-8") as f:
        return f.read()


def test_search_places_devolve_a_lista():
    arvore = ast.parse(_fonte())
    funcs = [n for n in ast.walk(arvore)
             if isinstance(n, ast.AsyncFunctionDef) and n.name == "search_places"]
    assert len(funcs) == 1, "search_places sumiu ou duplicou"
    retornos = [n for n in ast.walk(funcs[0]) if isinstance(n, ast.Return) and n.value]
    nomes = [r.value.id for r in retornos
             if isinstance(r.value, ast.Name)]
    assert "businesses" in nomes, "search_places nao devolve businesses (bug 042e1b5 de novo?)"
