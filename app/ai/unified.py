#!/usr/bin/env python3
"""ai/unified.py — state user AIOrganizerPro dalam JSON (tanpa database).

- data/doc_index.json  : hasil analyze dokumen (bisa dibaca manusia)
- data/doc_feedback.jsonl : koreksi user per dokumen
- behavior user         : lihat behavior.py (data/behavior.jsonl)
- antrean job           : lihat jobs.py (data/jobs.json)

SQLite (.db) tersisa HANYA sebagai cache mesin internal core C++ yang tidak
perlu dibaca user. Semua fungsi aman: gagal -> diam, engine tetap jalan.
"""
import hashlib
import json
import os
import time

DOC_INDEX_NAME = os.path.join("data", "doc_index.json")
DOC_FEEDBACK_NAME = os.path.join("data", "doc_feedback.jsonl")
MAX_DOCS = 5000


def _root(app_base):
    """Pro root: naik dari app_base sampai ketemu penanda PRO.cmd."""
    cur = os.path.abspath(app_base)
    for _ in range(7):
        if os.path.isfile(os.path.join(cur, "PRO.cmd")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return os.path.abspath(app_base)


def _doc_path(app_base):
    return os.path.join(_root(app_base), DOC_INDEX_NAME)


def unified_db_path(app_base):
    """Kompat: tidak ada DB user lagi -> string kosong (cache mesin milik core)."""
    return ""


def mirror_behavior(app_base, kind, path="", detail=""):
    """Kompat no-op: Behavior.log() adalah satu-satunya penulis behavior.jsonl."""
    return


def _read_docs(app_base):
    try:
        with open(_doc_path(app_base), encoding="utf-8") as f:
            d = json.load(f)
            docs = d.get("docs", []) if isinstance(d, dict) else []
            return [x for x in docs if isinstance(x, dict)]
    except (OSError, ValueError):
        return []


def read_docs(app_base, limit=200):
    docs = _read_docs(app_base)
    docs.sort(key=lambda d: d.get("updated_ms", 0), reverse=True)
    return docs[:max(1, min(int(limit or 200), 500))]


def upsert_doc(app_base, path, kategori, confidence, ringkasan="", saran_nama=""):
    try:
        docs = _read_docs(app_base)
        now = int(time.time() * 1000)
        row = {"path": path, "kategori": kategori or "",
               "confidence": float(confidence or 0),
               "ringkasan": ringkasan or "", "saran_nama": saran_nama or "",
               "updated_ms": now}
        docs = [d for d in docs if d.get("path") != path]
        docs.insert(0, row)
        docs = docs[:MAX_DOCS]
        p = _doc_path(app_base)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"updated_ms": now, "docs": docs}, f, ensure_ascii=False)
        os.replace(tmp, p)
    except (OSError, ValueError):
        pass


def save_doc_feedback(app_base, path, kategori, teks=""):
    try:
        h = hashlib.sha256((teks or path).encode("utf-8", "replace")).hexdigest()[:16]
        p = os.path.join(_root(app_base), DOC_FEEDBACK_NAME)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t_ms": int(time.time() * 1000), "path": path,
                                "kategori": kategori, "teks_hash": h},
                               ensure_ascii=False) + "\n")
    except OSError:
        pass
