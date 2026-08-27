import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

DEFAULT_SETTINGS = {
    "openai_api_key": "",
    "openai_base_url": "https://api.openai.com/v1",
    "openai_model": "gpt-4o-mini",
    "instagram_sessionid": "",
    "headless": True,
    "request_delay": 1.5,
    "max_results": 15,
    "schedule_enabled": False,
    "schedule_time": "08:00",
    "schedule_niche": "restaurantes",
    "schedule_states": [],
    "schedule_max": 10,
    "schedule_last_run": "",
    "schedule_new_count": 0,
    "schedule_total_count": 0,
}


def load_settings():
    merged = dict(DEFAULT_SETTINGS)
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                merged.update(saved)
        except Exception:
            pass
    return merged


def save_settings(new_settings):
    current = load_settings()
    current.update(new_settings)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)
    return current