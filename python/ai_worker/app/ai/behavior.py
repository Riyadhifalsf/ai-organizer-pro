#!/usr/bin/env python3
"""ai/behavior.py — AI belajar mandiri dari perilaku user (JSON, tanpa DB).

Mencatat: folder dibuka, file dibuat/diubah, aksi user di aplikasi
(scan/karantina/apply/koreksi) ke data/behavior.jsonl (1 baris = 1 event,
bisa dibaca manusia). Preferensi di data/behavior_prefs.json. Dari situ:
- folder favorit & jam aktif -> rekomendasi proaktif
- aturan auto: folder yang 3x karantina -> tawarkan auto-mode.
- semua lokal 100% offline, tidak ada data keluar.
"""
import json
import os
import time
from collections import Counter
from datetime import datetime

EVENTS_NAME = os.path.join("data", "behavior.jsonl")
PREFS_NAME = os.path.join("data", "behavior_prefs.json")
# Event lebih tua dari ini dipangkas saat baca (file tetap append-only).
KEEP_DAYS = 120


class Behavior:
    def __init__(self, app_base):
        # app_base = folder ai_worker; state user tinggal di PRO ROOT/data.
        base = os.path.abspath(app_base)
        self.root = base
        cur = base
        for _ in range(7):
            if os.path.isfile(os.path.join(cur, "PRO.cmd")):
                self.root = cur
                break
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent
        self.events_path = os.path.join(self.root, EVENTS_NAME)
        self.prefs_path = os.path.join(self.root, PREFS_NAME)
        try:
            os.makedirs(os.path.dirname(self.events_path), exist_ok=True)
        except OSError:
            pass
        self._migrate_legacy_once()

    def _migrate_legacy_once(self):
        """Impor sekali dari behavior.db lama (results/reports/) bila JSONL masih kosong."""
        try:
            if os.path.getsize(self.events_path) > 0:
                return
        except OSError:
            pass
        legacy = os.path.join(self.root, "results", "reports", "behavior.db")
        if not os.path.isfile(legacy):
            return
        try:
            import sqlite3
            c = sqlite3.connect("file:" + legacy + "?mode=ro", uri=True)
            rows = c.execute(
                "SELECT t,kind,path,detail FROM events ORDER BY t").fetchall()
            prefs = c.execute("SELECT key,val FROM prefs").fetchall()
            c.close()
            with open(self.events_path, "a", encoding="utf-8") as f:
                for t, kind, path, detail in rows:
                    f.write(json.dumps({"t": t, "kind": kind or "",
                                        "path": path or "",
                                        "detail": detail or ""},
                                       ensure_ascii=False) + "\n")
            if prefs:
                cur = self._load_prefs()
                for k, v in prefs:
                    cur.setdefault(k, v)
                self._save_prefs(cur)
        except Exception:
            pass

    # ---------- tulis ----------
    def log(self, kind, path="", detail=""):
        try:
            with open(self.events_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"t": time.time(), "kind": kind,
                                    "path": path, "detail": detail},
                                   ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _load_prefs(self):
        try:
            with open(self.prefs_path, encoding="utf-8") as f:
                d = json.load(f)
                return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save_prefs(self, prefs):
        try:
            tmp = self.prefs_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(prefs, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.prefs_path)
        except OSError:
            pass

    def get_pref(self, key, default=""):
        return self._load_prefs().get(key, default)

    def set_pref(self, key, val):
        prefs = self._load_prefs()
        prefs[key] = val
        self._save_prefs(prefs)

    # ---------- baca ----------
    def _events(self, days=KEEP_DAYS):
        since = time.time() - days * 86400
        out = []
        try:
            with open(self.events_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(e, dict) and e.get("t", 0) >= since:
                        out.append(e)
        except OSError:
            pass
        return out

    def top_folders(self, days=30, limit=5):
        """Folder paling sering muncul di event user."""
        counts = Counter()
        for e in self._events(days):
            if e.get("kind") in ("folder_open", "scan", "karantina", "apply") and e.get("path"):
                counts[e["path"]] += 1
        return [{"path": p, "n": n} for p, n in counts.most_common(limit)]

    def active_hours(self):
        hours = Counter()
        for e in self._events():
            try:
                hours[datetime.fromtimestamp(float(e.get("t", 0))).hour] += 1
            except (TypeError, ValueError):
                continue
        return [h for h, _ in hours.most_common(3)]

    def recommend(self):
        """Hasilkan rekomendasi proaktif (list dict). Dipakai daemon + GUI."""
        recs = []
        tops = self.top_folders()
        for t in tops[:3]:
            recs.append({"kind": "scan_suggest",
                         "text": f"Folder langganan: {t['path']} ({t['n']}x). Scan sekarang?",
                         "path": t["path"]})
        hours = self.active_hours()
        now_h = datetime.now().hour
        if hours and now_h in hours:
            recs.append({"kind": "time_nudge",
                         "text": f"Jam aktifmu ({now_h}:00). Mau beres-beres cepat?",
                         "path": tops[0]["path"] if tops else ""})
        # aturan auto: 3x karantina di folder sama -> tawarkan auto
        counts = Counter()
        for e in self._events(30):
            if e.get("kind") == "karantina" and e.get("path"):
                counts[e["path"]] += 1
        for p, n in counts.most_common():
            if n >= 3 and self.get_pref(f"auto_{p}") != "1":
                recs.append({"kind": "auto_offer",
                             "text": f"Kamu {n}x karantina {p}. Aktifkan auto?",
                             "path": p})
        return recs
