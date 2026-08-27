import asyncio
import datetime
import json
import os
import threading
import time

from config import BASE_DIR, load_settings, save_settings

AGENDADA_DIR = os.path.join(BASE_DIR, "output", "agendadas")
PREV_FILE = os.path.join(AGENDADA_DIR, "anterior.json")

_started = False


def _key(b):
    return (b.get("nome") or "").lower().strip()


def _load_prev_keys():
    if os.path.exists(PREV_FILE):
        try:
            with open(PREV_FILE, "r", encoding="utf-8") as f:
                arr = json.load(f)
            return set(_key(b) for b in arr)
        except Exception:
            return set()
    return set()


def _save_results(all_results, new_results, today):
    os.makedirs(AGENDADA_DIR, exist_ok=True)
    with open(os.path.join(AGENDADA_DIR, f"busca_{today}.json"), "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    with open(PREV_FILE, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)


def run_scheduled():
    s = load_settings()
    niche = s.get("schedule_niche") or "restaurantes"
    states = s.get("schedule_states") or []
    max_r = int(s.get("schedule_max") or 10)
    if not states:
        return 0, 0

    from scrapers import google_maps

    results = asyncio.run(google_maps.search_places(niche, locations=states, max_results=max_r))

    prev = _load_prev_keys()
    new = [b for b in results if _key(b) not in prev]

    today = datetime.datetime.now().strftime("%Y-%m-%d")
    _save_results(results, new, today)

    save_settings({
        "schedule_last_run": today,
        "schedule_new_count": len(new),
        "schedule_total_count": len(results),
    })
    return len(new), len(results)


def _check():
    s = load_settings()
    if not s.get("schedule_enabled"):
        return
    now = datetime.datetime.now()
    target = (s.get("schedule_time") or "08:00").strip()
    if now.strftime("%H:%M") != target:
        return
    today = now.strftime("%Y-%m-%d")
    if s.get("schedule_last_run") == today:
        return

    print(f"[agendador] rodando busca automatica: {s.get('schedule_niche')} em {s.get('schedule_states')}")
    try:
        new, total = run_scheduled()
        print(f"[agendador] concluido: {new} novos de {total} totais")
    except Exception as e:
        print(f"[agendador] erro: {e}")
        save_settings({"schedule_last_run": today})


def _loop():
    while True:
        try:
            _check()
        except Exception:
            pass
        time.sleep(30)


def start_scheduler():
    global _started
    if _started:
        return
    _started = True
    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    print("[agendador] iniciado")