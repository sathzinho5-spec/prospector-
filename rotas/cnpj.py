# proposito: garimpo de empresas grandes por UF na base de CNPJ
import asyncio

from fastapi import APIRouter, HTTPException

from rotas.modelos import CnpjMarcarRequest

router = APIRouter()


@router.get("/api/cnpj/grandes")
def api_cnpj_grandes(uf: str = "", cidade: str = "", capital_min: int = 500000, limite: int = 20, apenas_nao_vistos: bool = True):
    from scrapers import cnpj_supabase

    try:
        rows = cnpj_supabase.buscar_grandes_supabase(
            uf=uf or None, cidade=cidade or None, capital_min=capital_min, limite=limite, apenas_nao_vistos=apenas_nao_vistos
        )
        return {"total": len(rows), "empresas": rows}
    except Exception as e:
        raise HTTPException(502, f"Erro ao consultar Supabase: {e}")


@router.post("/api/cnpj/marcar-vistos")
def api_cnpj_marcar(req: CnpjMarcarRequest):
    from scrapers import cnpj_supabase

    try:
        cnpj_supabase.marcar_vistos(req.cnpjs)
        return {"vistos": len(req.cnpjs)}
    except Exception as e:
        raise HTTPException(502, str(e))


@router.post("/api/cnpj/sync")
async def api_cnpj_sync(capital_min: int = 500000, max_arquivos: int = 2):
    from scrapers import cnpj_supabase

    loop = asyncio.get_event_loop()
    count = await loop.run_in_executor(None, lambda: cnpj_supabase.sync_completo(capital_min=capital_min, max_arquivos=max_arquivos))
