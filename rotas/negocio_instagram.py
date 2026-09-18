# proposito: prospeccao e analise de perfis do Instagram
"""
Saiu de rotas/negocio.py quando aquele arquivo passou do teto de 350 linhas.
A costura e a que o proprio arquivo ja tinha: de um lado a analise e a copy de
UM lead, do outro a prospeccao por Instagram, que chegou depois e nao
compartilha nada com a primeira alem do router.

Nenhuma rota mudou de caminho. app.py registra os dois routers.
"""
import asyncio
import os

from fastapi import APIRouter, HTTPException

import config
from analysis import analyzer
from nucleo import STATE
from scrapers import google_search, instagram
from storage import save_businesses, save_json
from rotas.modelos import (InstagramProspectRequest, InstagramRequest,
                           InstagramSitesRequest)

router = APIRouter()




@router.post("/api/instagram/analyze")
async def api_instagram(req: InstagramRequest):
    username = req.username.strip().lstrip("@")
    searched = False
    if not username:
        try:
            ref = await google_search.find_business_reference(req.name, "")
            username = ref.get("instagram_handle") or ""
            searched = True
        except Exception:
            username = ""
        if not username:
            raise HTTPException(400, "Não foi possível encontrar o @ do Instagram. Informe o @ do perfil manualmente.")

    try:
        profile, posts = await asyncio.to_thread(instagram.get_profile_and_posts, username, req.max_posts)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))

    saved = []
    if req.download and posts:
        saved = await asyncio.to_thread(instagram.download_media, username, posts, 6)

    settings = config.load_settings()
    report = analyzer.build_report(req.name, profile, posts, saved, settings)

    payload = {
        "nome": req.name,
        "username": username,
        "auto_descoberto": searched,
        "perfil": profile,
        "posts": posts,
        "conteudos_baixados": saved,
        "relatorio": report,
    }
    save_json(f"analise_{username}.json", payload)
    return payload


@router.post("/api/instagram/prospectar")
async def api_instagram_prospectar(req: InstagramProspectRequest):
    if not req.nicho.strip():
        raise HTTPException(400, "Informe o nicho.")

    try:
        achados = await google_search.prospectar_instagram(
            req.nicho.strip(), req.local.strip(), max_results=req.max_results)
    except Exception as e:
        raise HTTPException(502, f"Falha na descoberta: {e}")

    if not achados:
        raise HTTPException(404, "Nenhum perfil encontrado para esse nicho.")

    settings = config.load_settings()
    tem_sessao = bool((settings.get("instagram_sessionid") or "").strip())

    businesses = []
    for a in achados:
        b = {
            "nome": "@" + a["username"],
            "categoria": "Instagram",
            "nota": "",
            "avaliacoes": "",
            "endereco": "",
            "cidade": "",
            "estado": "",
            "telefone": "",
            "website": a["url"],
            "username": a["username"],
            "consulta": f"instagram | {req.local.strip()}",
            "url": a["url"],
        }
        if req.enriquecer and tem_sessao:
            try:
                profile, _ = await asyncio.to_thread(
                    instagram.get_profile_and_posts, a["username"], 1)
                b["nome"] = profile.get("nome_completo") or ("@" + a["username"])
                b["categoria"] = "Instagram" + (f" · {profile['categoria']}" if profile.get("categoria") else "")
                b["seguidores"] = profile.get("seguidores", 0)
                b["descricao"] = profile.get("biografia", "")
                b["foto"] = profile.get("foto_perfil", "")
                if profile.get("verificado"):
                    b["atributos"] = ["Verificado"]
                await asyncio.sleep(1.5)
            except Exception:
                pass
        businesses.append(b)

    repetidos_ocultos = 0
    try:
        from scrapers import cloud_store
        if req.apenas_novos:
            ids = [cloud_store.lead_id(b) for b in businesses]
            vistos = cloud_store.existing_ids(ids)
            if vistos:
                repetidos_ocultos = sum(1 for b in businesses if cloud_store.lead_id(b) in vistos)
                businesses = [b for b in businesses if cloud_store.lead_id(b) not in vistos]
        cloud_store.save_leads(businesses)
    except Exception:
        pass

    if not businesses:
        raise HTTPException(404, "Todos os perfis encontrados já foram coletados antes.")

    STATE["businesses"] = businesses
    STATE["last_search"] = f"instagram | {req.nicho.strip()} | {req.local.strip()}"
    path = save_businesses(businesses, "negocios")

    return {
        "query": req.nicho.strip(),
        "locations": [req.local.strip()] if req.local.strip() else [],
        "termos_usados": ["site:instagram.com"],
        "total": len(businesses),
        "por_local": {},
        "repetidos_ocultos": repetidos_ocultos,
        "enriquecidos": tem_sessao and req.enriquecer,
        "businesses": businesses,
        "csv": path,
    }


@router.post("/api/instagram/dos-sites")
async def api_instagram_dos_sites(req: InstagramSitesRequest):
    """Extrai @ do Instagram direto dos sites dos leads (não depende de buscador).
    São leads melhores: empresa real + site + Instagram."""
    from scrapers import site_contacts

    fontes = req.businesses or STATE.get("businesses") or []
    if not fontes:
        raise HTTPException(400, "Faça uma busca no Maps primeiro.")

    settings = config.load_settings()
    tem_sessao = bool((settings.get("instagram_sessionid") or "").strip())

    achados = []
    vistos = set()
    for b in fontes:
        site = (b.get("website") or "").strip()
        if not site or not site.startswith("http"):
            continue
        try:
            contatos = await asyncio.to_thread(site_contacts.extract_site_contacts, site)
        except Exception:
            continue
        handle = (contatos.get("instagram") or "").strip().lstrip("@")
        if not handle or handle in vistos:
            continue
        vistos.add(handle)

        novo = {
            "nome": "@" + handle,
            "categoria": "Instagram",
            "nota": b.get("nota", ""),
            "avaliacoes": b.get("avaliacoes", ""),
            "endereco": b.get("endereco", ""),
            "cidade": b.get("cidade", ""),
            "estado": b.get("estado", ""),
            "telefone": b.get("telefone", ""),
            "website": f"https://www.instagram.com/{handle}/",
            "username": handle,
            "consulta": "instagram via site",
            "url": f"https://www.instagram.com/{handle}/",
            "origem_maps": b.get("nome", ""),
        }
        if tem_sessao:
            try:
                profile, _ = await asyncio.to_thread(
                    instagram.get_profile_and_posts, handle, 1)
                novo["nome"] = profile.get("nome_completo") or ("@" + handle)
                novo["seguidores"] = profile.get("seguidores", 0)
                novo["descricao"] = profile.get("biografia", "")
                novo["foto"] = profile.get("foto_perfil", "")
                await asyncio.sleep(1.5)
            except Exception:
                pass
        achados.append(novo)

    if not achados:
        raise HTTPException(404, "Nenhum Instagram encontrado nos sites desses leads.")

    repetidos_ocultos = 0
    try:
        from scrapers import cloud_store
        if req.apenas_novos:
            ids = [cloud_store.lead_id(b) for b in achados]
            v = cloud_store.existing_ids(ids)
            if v:
                repetidos_ocultos = sum(1 for b in achados if cloud_store.lead_id(b) in v)
                achados = [b for b in achados if cloud_store.lead_id(b) not in v]
        cloud_store.save_leads(achados)
    except Exception:
        pass

    if not achados:
        raise HTTPException(404, "Todos já foram coletados antes.")

    STATE["businesses"] = achados
    STATE["last_search"] = "instagram via sites"
    path = save_businesses(achados, "negocios")

    return {
        "query": "instagram",
        "termos_usados": ["sites dos leads"],
        "total": len(achados),
        "por_local": {},
        "repetidos_ocultos": repetidos_ocultos,
        "enriquecidos": tem_sessao,
        "businesses": achados,
        "csv": path,
    }


