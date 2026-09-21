#!/usr/bin/env python3
"""ai/reason.py — reasoning ringan-mendalam, bisa diatur kekuatannya.

Level (hemat -> kuat):
  L1 heuristics : nama/ekstensi/ukuran/umur file. ~1ms/file, tanpa baca isi.
  L2 ml        : + isi dokumen (TF-IDF centroid), dHash visual, header media.
  L3 llm       : + Qwen lokal untuk yang ambigu (lambat, ~5 dtk/file).

Kekuatan diatur via config/settings.json:
  {"reason_level": 1|2|3, "llm_max": 20, "budgets": {...}, "cache_ttl_h": 24}

Hasil per file: skor, keputusan, alasan (trace), confidence. Semua di-cache
di laporan/reason_cache.json keyed path+size+mtime agar hemat.
"""
import hashlib
import json
import os
import time
from datetime import datetime

CACHE_NAME = os.path.join("results", "reports", "reason_cache.json")

EXT_MAP = {
    ".pdf": ("Dokumen", 0.3), ".docx": ("Dokumen", 0.3), ".txt": ("Dokumen", 0.3),
    ".md": ("Dokumen", 0.3), ".xlsx": ("Data", 0.3), ".csv": ("Data", 0.3),
    ".jpg": ("Media", 0.3), ".jpeg": ("Media", 0.3), ".png": ("Media", 0.3),
    ".mp4": ("Media", 0.3), ".mov": ("Media", 0.3), ".mkv": ("Media", 0.3),
    ".mp3": ("Media", 0.3), ".zip": ("Arsip", 0.3), ".rar": ("Arsip", 0.3),
    ".exe": ("Aplikasi", 0.3), ".msi": ("Aplikasi", 0.3),
}

SUGGEST_FOLDER = {"Dokumen": "dokumen", "Media": "media", "Data": "data",
                  "Arsip": "arsip", "Aplikasi": "aplikasi"}


class Reasoner:
    def __init__(self, app_base, settings=None):
        self.base = os.path.abspath(app_base)
        self.settings = settings or {}
        self.level = int(self.settings.get("reason_level", 2))
        self.llm_max = int(self.settings.get("llm_max", 20))
        self.ttl = int(self.settings.get("cache_ttl_h", 24)) * 3600
        self.cache_path = os.path.join(self.base, CACHE_NAME)
        self.cache = self._load()
        self.llm_used = 0

    def _load(self):
        try:
            with open(self.cache_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            tmp = self.cache_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.cache, f)
            os.replace(tmp, self.cache_path)
        except Exception:
            pass

    def _key(self, path, size, mtime):
        return hashlib.sha256(f"{path}|{size}|{mtime}".encode()).hexdigest()[:32]

    def reason_file(self, path):
        """Analisis 1 file -> dict(kategori, confidence, aksi, alasan[], level)."""
        try:
            st = os.stat(path)
        except OSError as e:
            return {"path": path, "kategori": "Tak-terbaca", "confidence": 0.0,
                    "aksi": "lewati", "alasan": [f"stat gagal: {e}"], "level": 0}
        key = self._key(path, st.st_size, st.st_mtime_ns)
        hit = self.cache.get(key)
        if hit and time.time() - hit.get("t", 0) < self.ttl:
            return hit["r"]
        trace, r = [], {"path": path, "level": 1}
        # ---- L1:heuristik nama & atribut ----
        name, ext = os.path.basename(path), os.path.splitext(path)[1].lower()
        cat, conf = EXT_MAP.get(ext, ("Lainnya", 0.1))
        trace.append(f"L1: ekstensi {ext or '?'} -> {cat} ({conf})")
        age_d = (time.time() - st.st_mtime) / 86400
        if age_d > 365 and st.st_size > 100 * 1024 * 1024:
            trace.append(f"L1: lama ({age_d:.0f} hari) + besar -> kandidat arsip")
            r["arsip_hint"] = True
        r.update(kategori=cat, confidence=conf, aksi="tata",
                 saran_folder=SUGGEST_FOLDER.get(cat, "lainnya"))
        # ---- L2: isi (dokumen/gambar) ----
        if self.level >= 2:
            r["level"] = 2
            if ext in (".txt", ".md", ".csv", ".log", ".docx", ".pdf"):
                d = self._l2_doc(path)
                if d:
                    r.update(d)
                    trace.append(f"L2: isi dokumen -> {d['kategori']} ({d['confidence']})")
            elif ext in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
                d = self._l2_image(path)
                if d:
                    r.update(d)
                    trace.append(f"L2: header gambar -> {d['kategori']} ({d['confidence']})")
        # ---- L3: LLM untuk yang ambigu ----
        if self.level >= 3 and r["confidence"] < 0.5 and self.llm_used < self.llm_max:
            r["level"] = 3
            d = self._l3_llm(path)
            self.llm_used += 1
            if d:
                r.update(d)
                trace.append(f"L3: LLM Qwen -> {d['kategori']} ({d['confidence']})")
        r["alasan"] = trace
        self.cache[key] = {"t": time.time(), "r": r}
        return r

    def _l2_doc(self, path):
        try:
            import sys
            sys.path.insert(0, os.path.dirname(self.base))
            sys.path.insert(0, self.base)
            from app.ai import docai
            text, info = docai.extract_text(path)
            if info != "ok":
                return {"kategori": "Tak-terbaca", "confidence": 0.0,
                        "aksi": "cek-manual", "saran_folder": "Tak-terbaca"}
            cents = docai.train_centroids(self._feedback())
            cat, conf, kw = docai.classify(text, cents)
            if conf < 0.15:
                c2, f2, k2 = docai.classify(os.path.basename(path) * 5, cents)
                if f2 > conf:
                    cat, conf, kw = c2, f2, k2
            return {"kategori": cat, "confidence": conf, "aksi": "tata",
                    "saran_folder": cat, "keywords": kw,
                    "saran_nama": (docai.safe_name(" ".join(kw)) + os.path.splitext(path)[1].lower())
                                  if conf >= 0.3 and kw else os.path.basename(path)}
        except Exception as e:
            return {"kategori": "Lainnya", "confidence": 0.0, "aksi": "lewati",
                    "alasan_extra": str(e)[:100]}

    def _l2_image(self, path):
        try:
            import sys
            sys.path.insert(0, self.base)
            sys.path.insert(0, os.path.dirname(self.base))
            from app.core.engine import _image_status
            status, reason = _image_status(path)
            if status == "HEAVY_BROKEN":
                return {"kategori": "Rusak-berat", "confidence": 0.9, "aksi": "karantina",
                        "saran_folder": "broken/heavy"}
            if status == "LIGHT_BROKEN":
                return {"kategori": "Rusak-ringan", "confidence": 0.7, "aksi": "cek-manual",
                        "saran_folder": "broken/light"}
            return {"kategori": "Media", "confidence": 0.6, "aksi": "tata",
                    "saran_folder": "media"}
        except Exception:
            return None

    def _l3_llm(self, path):
        try:
            import sys
            sys.path.insert(0, self.base)
            from app.ai import docai
            from app.ai import llm
            if not llm.ensure_server(wait=20):
                return None
            text, info = docai.extract_text(path)
            if info != "ok":
                return None
            d = llm.analyze_doc(text, path)
            if not d:
                return None
            return {"kategori": d.get("kategori", "Lainnya"), "confidence": 0.5,
                    "aksi": "tata", "saran_folder": d.get("kategori", "Lainnya"),
                    "ringkasan": d.get("ringkasan", ""),
                    "saran_nama": (d["nama"] + os.path.splitext(path)[1].lower()) if d.get("nama")
                                  else os.path.basename(path)}
        except Exception:
            return None

    def _feedback(self):
        for name in ("doc_feedback.json",):
            p = os.path.join(self.base, "results", "reports", name)
            if os.path.exists(p):
                try:
                    with open(p, encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    pass
        return []

    def reason_folder(self, target, progress=None):
        """Reasoning 1 folder penuh (sub folder ikut). Return list hasil."""
        out = []
        n = 0
        for dp, _, fn in os.walk(target):
            for f in sorted(fn):
                n += 1
                out.append(self.reason_file(os.path.join(dp, f)))
                if progress and n % 100 == 0:
                    progress(n)
        self.save()
        return out
