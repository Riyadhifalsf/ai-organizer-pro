#!/usr/bin/env python3
"""core/settings.py — pengaturan AI (kekuatan, startup, level). Satu file JSON."""
import json
import os

DEFAULTS = {
    "reason_level": 2,          # 1 cepat, 2 standar+isi, 3 + LLM lokal
    "llm_max": 20,              # maks file dibantu LLM per analisis
    "llm_model": "qwen2.5:0.5b",  # model Ollama aktif (lihat ai/llm.py MODELS)
    "cache_ttl_h": 24,          # umur cache reasoning (jam)
    "watch_folders": [],        # folder dipantau daemon (default: diisi saat install)
    "learn_folders": [],        # folder yang BOLEH dipelajari AI (kosong = semua kecuali system)
    "learn_exclude": [],        # folder yang TIDAK boleh dipelajari AI
    "startup": False,           # jalan otomatis saat Windows startup
    "notify": True,             # notifikasi rekomendasi Windows
    "broken_mode": "copy",      # copy | move
    "dup_mode": "exact",        # exact | visual
    "out": "",                  # "" = folder ai_organizer
    "lang": "id",               # id | en
}

NAME = os.path.join("config", "settings.json")


def path(app_base):
    return os.path.join(os.path.abspath(app_base), NAME)


def load(app_base):
    p = path(app_base)
    try:
        with open(p, encoding="utf-8") as f:
            d = dict(DEFAULTS)
            d.update(json.load(f))
            return d
    except Exception:
        return dict(DEFAULTS)


def save(app_base, settings):
    p = path(app_base)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
    os.replace(tmp, p)
    return p


SYSTEM_EXCLUDE = ("c:\\windows", "c:\\program files", "c:\\program files (x86)",
                  "$recycle.bin", "system volume information")


def _under(path, folder):
    try:
        return os.path.abspath(path).lower().startswith(os.path.abspath(folder).lower() + os.sep)
    except Exception:
        return False


def learn_allowed(path, st=None):
    """True bila AI boleh mempelajari path ini (allowlist user + system exclude)."""
    p = os.path.abspath(path or "").lower()
    for s in SYSTEM_EXCLUDE:
        if s in p:
            return False
    st = st or {}
    for ex in st.get("learn_exclude", []):
        if ex and (_under(path, ex) or p == os.path.abspath(ex).lower()):
            return False
    allow = [a for a in st.get("learn_folders", []) if a]
    if allow:
        return any(_under(path, a) or p == os.path.abspath(a).lower() for a in allow)
    return True
