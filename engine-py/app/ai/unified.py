#!/usr/bin/env python3
"""ai/unified.py — jembatan engine-py ke database terpadu AIOrganizerPro.

Skema v3 (dibuat oleh core C++, tabel CREATE IF NOT EXISTS di sini juga agar
sidecar bisa jalan duluan). Semua fungsi aman: gagal -> diam, engine tetap jalan.

Lokasi DB terpadu:
  env AIORG_DB, atau <pro-root>/data/aiorganizer.db (pro-root = parent engine-py),
  dipakai HANYA bila env diset atau file-nya sudah ada (tidak pernah membuat
  folder stray di instalasi lama D:\\ai_organizer).
"""
import hashlib
import os
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS behavior_events(
  id INTEGER PRIMARY KEY, t_ms INTEGER NOT NULL, kind TEXT NOT NULL,
  path TEXT NOT NULL DEFAULT '', detail TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS behavior_prefs(
  key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS doc_index(
  path TEXT PRIMARY KEY, kategori TEXT NOT NULL DEFAULT '',
  confidence REAL NOT NULL DEFAULT 0, ringkasan TEXT NOT NULL DEFAULT '',
  saran_nama TEXT NOT NULL DEFAULT '', updated_ms INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS doc_feedback(
  id INTEGER PRIMARY KEY, t_ms INTEGER NOT NULL, path TEXT NOT NULL,
  kategori TEXT NOT NULL, teks_hash TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS jobs(
  id INTEGER PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'pending', created_ms INTEGER NOT NULL,
  started_ms INTEGER NOT NULL DEFAULT 0, ended_ms INTEGER NOT NULL DEFAULT 0,
  result TEXT NOT NULL DEFAULT '');
"""


def unified_db_path(app_base):
    env = os.environ.get("AIORG_DB", "").strip()
    if env:
        # ":memory:" = mode efemeral (DB dimatikan): jangan tulis ke mana pun.
        if env == ":memory:":
            return ""
        return os.path.abspath(env)
    base = os.path.abspath(app_base)
    parent = os.path.dirname(base)
    cand = os.path.join(parent, "data", "aiorganizer.db")
    # jangan bikin folder baru di instalasi lama: hanya bila file sudah ada
    if os.path.isfile(cand):
        return cand
    return ""


def _con(db):
    c = sqlite3.connect(db, timeout=30)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    c.executescript(SCHEMA)
    return c


def mirror_behavior(app_base, kind, path="", detail=""):
    db = unified_db_path(app_base)
    if not db:
        return
    try:
        os.makedirs(os.path.dirname(db), exist_ok=True)
        with _con(db) as c:
            c.execute("INSERT INTO behavior_events(t_ms,kind,path,detail)"
                      " VALUES(?,?,?,?)",
                      (int(time.time() * 1000), kind, path, detail))
    except Exception:
        pass


def upsert_doc(app_base, path, kategori, confidence, ringkasan="", saran_nama=""):
    db = unified_db_path(app_base)
    if not db:
        return
    try:
        os.makedirs(os.path.dirname(db), exist_ok=True)
        with _con(db) as c:
            c.execute(
                "INSERT INTO doc_index(path,kategori,confidence,ringkasan,"
                "saran_nama,updated_ms) VALUES(?,?,?,?,?,?)"
                " ON CONFLICT(path) DO UPDATE SET kategori=excluded.kategori,"
                "confidence=excluded.confidence,ringkasan=excluded.ringkasan,"
                "saran_nama=excluded.saran_nama,updated_ms=excluded.updated_ms",
                (path, kategori, float(confidence or 0), ringkasan,
                 saran_nama, int(time.time() * 1000)))
    except Exception:
        pass


def save_doc_feedback(app_base, path, kategori, teks=""):
    db = unified_db_path(app_base)
    if not db:
        return
    try:
        h = hashlib.sha256((teks or path).encode("utf-8", "replace")).hexdigest()[:16]
        os.makedirs(os.path.dirname(db), exist_ok=True)
        with _con(db) as c:
            c.execute("INSERT INTO doc_feedback(t_ms,path,kategori,teks_hash)"
                      " VALUES(?,?,?,?)",
                      (int(time.time() * 1000), path, kategori, h))
    except Exception:
        pass
