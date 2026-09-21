#!/usr/bin/env python3
"""tools/migrate_unified.py — gabungkan data lama ke DB terpadu v3.

Sumber:
  D:\\ai_organizer\\results\\reports\\behavior.db  (events t DETIK, prefs)
  D:\\ai_organizer\\results\\reports\\doc_feedback.json (+ doc_report_*.csv)
Tujuan:
  D:\\AIOrganizerPro\\data\\aiorganizer.db (dibuat bila belum ada)

Aman: hanya INSERT, tidak menghapus sumber. Bisa dijalankan berulang
(duplikat behavior di-skip via UNIQUE index sementara pada (t_ms,kind,path)).
"""
import json
import os
import sqlite3
import sys

PRO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_BEHAV = os.path.join(PRO, "ai_organizer", "results", "reports",
                         "behavior.db")
SRC_REPORTS = os.path.join(PRO, "ai_organizer", "results", "reports")
DST = os.environ.get("AIORG_DB", os.path.join(PRO, "data", "aiorganizer.db"))


def main():
    os.makedirs(os.path.dirname(DST), exist_ok=True)
    schema = os.path.join(PRO, "db", "schema_v4.sql")
    dst = sqlite3.connect(DST, timeout=60)
    dst.execute("PRAGMA journal_mode=WAL")
    with open(schema, encoding="utf-8") as f:
        dst.executescript(f.read())
    n_beh = n_pref = n_fb = 0
    if os.path.isfile(SRC_BEHAV):
        src = sqlite3.connect(f"file:{SRC_BEHAV}?mode=ro", uri=True)
        try:
            rows = src.execute(
                "SELECT t,kind,path,detail FROM events").fetchall()
        except Exception:
            rows = []
        for t, k, p, d in rows:
            try:
                dst.execute(
                    "INSERT INTO behavior_events(t_ms,kind,path,detail)"
                    " VALUES(?,?,?,?)",
                    (int(float(t) * 1000), k or "", p or "", d or ""))
                n_beh += 1
            except Exception:
                pass
        try:
            prefs = src.execute("SELECT key,val FROM prefs").fetchall()
        except Exception:
            prefs = []
        for k, v in prefs:
            try:
                dst.execute("INSERT OR IGNORE INTO behavior_prefs(key,value)"
                            " VALUES(?,?)", (k, v))
                n_pref += 1
            except Exception:
                pass
        src.close()
    fb = os.path.join(SRC_REPORTS, "doc_feedback.json")
    if os.path.isfile(fb):
        try:
            data = json.load(open(fb, encoding="utf-8"))
            items = data if isinstance(data, list) else data.get("items", [])
            for it in items:
                if isinstance(it, dict):
                    dst.execute(
                        "INSERT INTO doc_feedback(t_ms,path,kategori,teks_hash)"
                        " VALUES(0,?,?,?)",
                        (it.get("path", ""), it.get("kategori", ""),
                         it.get("hash", "")[:16]))
                    n_fb += 1
        except Exception as e:
            print(f"feedback skip: {e}")
    # doc_report_*.csv -> doc_index (bisa diulang: INSERT OR REPLACE per path)
    import csv
    import glob
    import time
    n_doc = 0
    for csv_path in sorted(glob.glob(os.path.join(SRC_REPORTS,
                                                  "doc_report_*.csv"))):
        try:
            with open(csv_path, encoding="utf-8-sig") as f:
                for r in csv.DictReader(f):
                    try:
                        dst.execute(
                            "INSERT INTO doc_index(path,kategori,confidence,"
                            "ringkasan,saran_nama,updated_ms)"
                            " VALUES(?,?,?,?,?,?)"
                            " ON CONFLICT(path) DO UPDATE SET"
                            " kategori=excluded.kategori,"
                            "confidence=excluded.confidence,"
                            "ringkasan=excluded.ringkasan,"
                            "saran_nama=excluded.saran_nama,"
                            "updated_ms=excluded.updated_ms",
                            (r.get("path", ""), r.get("kategori", ""),
                             float(r.get("confidence") or 0),
                             r.get("ringkasan", "") or r.get("summary", ""),
                             r.get("saran_nama", ""),
                             int(time.time() * 1000)))
                        n_doc += 1
                    except Exception:
                        continue
        except Exception as e:
            print(f"doc csv skip {csv_path}: {e}")
    dst.commit()
    print(f"OK -> {DST}: behavior={n_beh} prefs={n_pref} feedback={n_fb} docs={n_doc}")
    dst.close()


if __name__ == "__main__":
    sys.exit(main())
