#!/usr/bin/env python3
"""ai/behavior.py — AI belajar mandiri dari perilaku user (sqlite3 stdlib).

Mencatat: folder dibuka (Explorer aktif), file dibuat/diubah (watchdog),
aksi user di aplikasi (scan/karantina/apply/koreksi). Dari situ:
- folder favorit & jam aktif -> rekomendasi proaktif ("biasanya jam segini
  kamu beres-beres Downloads, mau scan sekarang?")
- aturan auto: folder yang 3x berturut user karantina -> tawarkan auto-mode.
- semua lokal, tidak ada data keluar.
"""
import os
import sqlite3
import time
from datetime import datetime

DB_NAME = os.path.join("results", "reports", "behavior.db")


class Behavior:
    def __init__(self, app_base):
        self.base = os.path.abspath(app_base)
        self.db = os.path.join(self.base, DB_NAME)
        os.makedirs(os.path.dirname(self.db), exist_ok=True)
        self._init()

    def _con(self):
        c = sqlite3.connect(self.db, timeout=30)
        c.execute("PRAGMA journal_mode=WAL")
        return c

    def _init(self):
        with self._con() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS events(
                id INTEGER PRIMARY KEY, t REAL, kind TEXT, path TEXT, detail TEXT)""")
            c.execute("""CREATE TABLE IF NOT EXISTS prefs(
                key TEXT PRIMARY KEY, val TEXT)""")

    def log(self, kind, path="", detail=""):
        try:
            with self._con() as c:
                c.execute("INSERT INTO events(t,kind,path,detail) VALUES(?,?,?,?)",
                          (time.time(), kind, path, detail))
        except Exception:
            pass
        # mirror best-effort ke DB terpadu (dipakai GUI modern + core C++)
        try:
            from app.ai import unified
            unified.mirror_behavior(self.base, kind, path, detail)
        except Exception:
            pass

    def get_pref(self, key, default=""):
        try:
            with self._con() as c:
                r = c.execute("SELECT val FROM prefs WHERE key=?", (key,)).fetchone()
                return r[0] if r else default
        except Exception:
            return default

    def set_pref(self, key, val):
        try:
            with self._con() as c:
                c.execute("INSERT OR REPLACE INTO prefs(key,val) VALUES(?,?)", (key, val))
        except Exception:
            pass

    def top_folders(self, days=30, limit=5):
        """Folder paling sering muncul di event user."""
        since = time.time() - days * 86400
        try:
            with self._con() as c:
                rows = c.execute(
                    """SELECT path, COUNT(*) n FROM events
                       WHERE t>? AND kind IN ('folder_open','scan','karantina','apply')
                       AND path<>'' GROUP BY path ORDER BY n DESC LIMIT ?""",
                    (since, limit)).fetchall()
                return [{"path": p, "n": n} for p, n in rows]
        except Exception:
            return []

    def active_hours(self):
        try:
            with self._con() as c:
                rows = c.execute(
                    "SELECT CAST(strftime('%H', t, 'unixepoch', 'localtime') AS INT), COUNT(*) "
                    "FROM events GROUP BY 1 ORDER BY 2 DESC LIMIT 3").fetchall()
                return [h for h, _ in rows]
        except Exception:
            return []

    def recommend(self):
        """Hasilkan rekomendasi proaktif (list string). Dipakai daemon + GUI."""
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
        try:
            with self._con() as c:
                rows = c.execute(
                    """SELECT path, COUNT(*) n FROM events WHERE kind='karantina'
                       AND t>? GROUP BY path HAVING n>=3""",
                    (time.time() - 30 * 86400,)).fetchall()
                for p, n in rows:
                    if self.get_pref(f"auto_{p}") != "1":
                        recs.append({"kind": "auto_offer",
                                     "text": f"Kamu {n}x karantina {p}. Aktifkan auto?",
                                     "path": p})
        except Exception:
            pass
        return recs
