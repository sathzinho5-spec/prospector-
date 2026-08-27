import json
import re

import requests

from config import DOWNLOADS_DIR, load_settings

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

SESSIONID_HINT = (
    "O Instagram bloqueou o acesso anônimo (sem login). Para obter os dados do perfil, "
    "abra o Instagram no navegador, faça login e copie o cookie de sessão "
    "(dev tools > Application > Cookies > instagram.com > sessionid) "
    "e cole-o em 'Configurações' > 'Cookie de sessão do Instagram'."
)


def _headers():
    return {
        "User-Agent": UA,
        "X-IG-App-ID": "936619743392459",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.instagram.com/",
    }


def _cookies():
    settings = load_settings()
    sid = (settings.get("instagram_sessionid") or "").strip()
    if sid:
        return {"sessionid": sid}
    return {}


def _http_get(url):
    session = requests.Session()
    session.headers.update(_headers())
    session.cookies.update(_cookies())
    return session.get(url, timeout=25)


def get_profile_and_posts(username, limit=12):
    username = username.strip().lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9._]+", username):
        raise ValueError("Nome de usuário inválido.")

    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    resp = _http_get(url)
    if resp.status_code != 200:
        # Se não tem sessionid, avisa claramente; se tem sessionid, tenta novamente
        if not (settings := load_settings()).get("instagram_sessionid"):
            raise RuntimeError(SESSIONID_HINT)
        resp = _http_get(url)
        if resp.status_code != 200:
            raise RuntimeError(SESSIONID_HINT)

    try:
        data = resp.json()
    except Exception:
        raise RuntimeError(SESSIONID_HINT)

    user = (data.get("data") or {}).get("user")
    if not user:
        raise RuntimeError(SESSIONID_HINT)

    profile = {
        "username": username,
        "nome_completo": user.get("full_name") or "",
        "biografia": user.get("biography") or "",
        "seguidores": user.get("edge_followed_by", {}).get("count", 0),
        "seguindo": user.get("edge_follow", {}).get("count", 0),
        "total_posts": user.get("edge_owner_to_timeline_media", {}).get("count", 0),
        "verificado": user.get("is_verified", False),
        "conta_negocio": user.get("is_business_account", False),
        "categoria": user.get("category_name") or "",
        "site": user.get("external_url") or "",
        "foto_perfil": user.get("profile_pic_url_hd") or "",
    }

    media = user.get("edge_owner_to_timeline_media", {})
    posts = []
    for edge in media.get("edges", [])[: int(limit)]:
        node = edge.get("node", {})
        caption = ""
        cap_edges = node.get("edge_media_to_caption", {}).get("edges") or []
        if cap_edges:
            caption = cap_edges[0].get("node", {}).get("text", "") or ""
        posts.append(
            {
                "id": node.get("id"),
                "shortcode": node.get("shortcode"),
                "legenda": caption,
                "curtidas": node.get("edge_liked_by", {}).get("count", 0),
                "comentarios": node.get("edge_media_to_comment", {}).get("count", 0),
                "timestamp": node.get("taken_at_timestamp"),
                "e_video": node.get("is_video", False),
                "url_imagem": node.get("display_url") or "",
                "permalink": f"https://www.instagram.com/p/{node.get('shortcode')}/" if node.get("shortcode") else "",
            }
        )

    return profile, posts


def download_media(username, posts, max_images=6):
    username = username.strip().lstrip("@")
    folder = os.path.join(DOWNLOADS_DIR, username)
    os.makedirs(folder, exist_ok=True)

    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    session.cookies.update(_cookies())

    saved = []
    for post in posts:
        if len(saved) >= int(max_images):
            break
        url = post.get("url_imagem")
        if not url:
            continue
        ext = ".mp4" if post.get("e_video") else ".jpg"
        fname = f"{post.get('shortcode') or post.get('id')}{ext}"
        path = os.path.join(folder, fname)
        try:
            r = session.get(url, timeout=30)
            if r.status_code == 200 and r.content:
                with open(path, "wb") as f:
                    f.write(r.content)
                saved.append(
                    {"post": post.get("shortcode"), "arquivo": path, "tipo": "video" if post.get("e_video") else "imagem"}
                )
        except Exception:
            continue
    return saved