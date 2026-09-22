#!/usr/bin/env python3
"""docai.py — AI dokumen kecil, murni stdlib (tanpa install, ramah EXE).

Cara kerja (jujur, tanpa klaim palsu):
- Ekstraksi teks: txt/md/csv/log langsung; docx via zip+xml stdlib;
  pdf berbasis-teks via parser stream Tj/TJ stdlib (pdf hasil scan -> "no-text").
- Fitur: TF-IDF + stopword Indonesia/Inggris.
- Klasifikasi: centroid (Rocchio) supervised — bisa BELAJAR dari koreksi user
  (feedback tersimpan di laporan/doc_feedback.json).
- Rekomendasi: folder = kategori, nama file = kata kunci + tanggal,
  confidence = margin skor centroid. Near-duplicate teks via SimHash 64-bit.
- Ini machine learning klasik yang jalan offline. BUKAN deep learning
  (model transformer butuh ratusan MB dan tidak muat di EXE kecil ini).

Kategori bawaan: Keuangan, Akademik, Kantor, Hukum, Kesehatan, Teknologi, Pribadi.
"""
import csv
import hashlib
import io
import json
import math
import os
import re
import zipfile
from collections import Counter, defaultdict
from datetime import datetime

STOP = set("""
yang dan di ke dari pada untuk dengan ini itu adalah sebagai dalam atau juga
tidak ada oleh karena pada saat para sebuah suatu akan telah sudah bisa agar
bagi antara setiap semua sangat lebih kurang hanya pun nya lah kah pun
the and of to in a is for on that with as are be by from or an at this which
we you your our they their he she it his her its was were has have had will
would can may not but if then than so such into over under about after before
all any each few more most other some such only own same than too very
""".split())

CATEGORIES = ["Keuangan", "Akademik", "Kantor", "Hukum", "Kesehatan", "Teknologi", "Pribadi"]

SEEDS = {
    "Keuangan": "invoice faktur pembayaran tagihan kwitansi bank transfer rekening pajak npwp gaji slip anggaran kas bon nota",
    "Akademik": "bab kuliah kampus dosen mahasiswa skripsi tesis jurnal tugas ujian uts uas modul pelajaran sekolah rangkuman",
    "Kantor": "rapat notulen memo surat undangan agenda proposal laporan kerja dinas cuti absen karyawan",
    "Hukum": "perda peraturan undang hukum pasal ayat perda keputusan perjanjian kontrak kuasa pengadilan gugatan",
    "Kesehatan": "obat dokter rumah sakit resep diagnosa pasien klinik kesehatan medis lab",
    "Teknologi": "software aplikasi server kode program data jaringan komputer python tutorial error",
    "Pribadi": "ktp kk kartu keluarga akta ijazah sertifikat cv lamaran nikah undangan foto",
}

TOKEN_RE = re.compile(r"[a-zA-Z]{3,}")


def tokenize(text):
    toks = [t.lower() for t in TOKEN_RE.findall(text or "")]
    return [t for t in toks if t not in STOP]


def extract_text(path):
    """Return (text, info). info 'ok' / 'no-text' / 'unsupported'."""
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in (".txt", ".md", ".csv", ".log", ".json", ".srt"):
            with open(path, encoding="utf-8", errors="replace") as f:
                return f.read(200000), "ok"
        if ext == ".docx":
            return _docx_text(path)
        if ext == ".pdf":
            return _pdf_text(path)
    except Exception as e:
        return "", f"error: {e}"[:200]
    return "", "unsupported"


def _docx_text(path):
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8", "replace")
    except Exception as e:
        return "", f"docx rusak: {e}"[:200]
    xml = re.sub(r"<w:p[^>]*>", "\n", xml)
    txt = re.sub(r"<[^>]+>", " ", xml)
    txt = re.sub(r"\s+", " ", txt).strip()
    return (txt[:200000], "ok") if len(txt) > 50 else ("", "no-text")


def _pdf_text(path):
    """Parser PDF minimal: ambil literal (...) dan hex <...> dari stream terkompresi."""
    import zlib
    try:
        with open(path, "rb") as f:
            data = f.read(30_000_000)
    except OSError as e:
        return "", f"error: {e}"[:200]
    if not data.startswith(b"%PDF"):
        return "", "bukan pdf valid"
    texts = []
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", data, re.S):
        blk = m.group(1).strip()
        try:
            blk = zlib.decompress(blk)
        except Exception:
            pass
        for lit in re.findall(rb"\((?:\\.|[^\\()])*\)", blk):
            try:
                texts.append(lit[1:-1].decode("latin-1"))
            except Exception:
                pass
        if len(" ".join(texts)) > 150000:
            break
    joined = re.sub(r"\s+", " ", " ".join(texts)).strip()
    return (joined[:200000], "ok") if len(joined) > 100 else ("", "no-text (kemungkinan hasil scan)")


def tfidf(docs_tokens):
    df = Counter()
    for toks in docs_tokens:
        df.update(set(toks))
    n = max(1, len(docs_tokens))
    vecs = []
    for toks in docs_tokens:
        tf = Counter(toks)
        total = max(1, len(toks))
        vecs.append({t: (c / total) * math.log(n / (1 + df[t])) for t, c in tf.items()})
    return vecs


def _norm(vec):
    return math.sqrt(sum(v * v for v in vec.values())) or 1.0


def _cos(a, na, b, nb):
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(t, 0.0) for t, v in a.items()) / (na * nb)


def train_centroids(extra=None):
    """Centroid per kategori dari SEEDS + feedback user."""
    docs, labels = [], []
    for cat, seed in SEEDS.items():
        docs.append(tokenize(seed * 6))
        labels.append(cat)
    for fb in (extra or []):
        toks = tokenize(fb.get("text", ""))
        if toks and fb.get("category") in CATEGORIES:
            docs.append(toks)
            labels.append(fb["category"])
    vecs = tfidf(docs)
    cents = {}
    for cat in CATEGORIES:
        agg = defaultdict(float)
        n = 0
        for v, lab in zip(vecs, labels):
            if lab == cat:
                n += 1
                for t, w in v.items():
                    agg[t] += w
        cents[cat] = ({t: w / max(1, n) for t, w in agg.items()}, _norm(agg))
    return cents


def classify(text, cents):
    toks = tokenize(text)
    if not toks:
        return "Lainnya", 0.0, []
    tf = Counter(toks)
    total = len(toks)
    vec = {t: c / total for t, c in tf.items()}
    nv = _norm(vec)
    scores = sorted(((cat, _cos(vec, nv, c, nc)) for cat, (c, nc) in cents.items()),
                    key=lambda x: -x[1])
    best, second = scores[0], scores[1] if len(scores) > 1 else (None, 0.0)
    conf = max(0.0, min(1.0, best[1] * 3.0))
    if best[1] <= 0.001:
        return "Lainnya", 0.0, [k for k, _ in tf.most_common(5)]
    keywords = [k for k, _ in tf.most_common(5)]
    return best[0], round(conf, 2), keywords


def simhash64(text):
    toks = tokenize(text)
    if not toks:
        return None
    tf = Counter(toks)
    bits = [0] * 64
    for t, c in tf.items():
        h = int(hashlib.sha256(t.encode()).hexdigest()[:16], 16)
        for i in range(64):
            bits[i] += c if (h >> i) & 1 else -c
    out = 0
    for i, b in enumerate(bits):
        if b > 0:
            out |= 1 << i
    return out


def ham64(a, b):
    return bin(a ^ b).count("1")


def safe_name(text, max_words=5):
    words = [w for w in re.findall(r"[a-zA-Z0-9]+", (text or "").lower())
             if w not in STOP and len(w) > 2][:max_words]
    stamp = datetime.now().strftime("%Y%m%d")
    base = "-".join(words)[:60] or "dokumen"
    return f"{stamp}_{base}"


def analyze_folder(target, out_root, limit=0, feedback_path=None):
    """Scan dokumen -> list dict(path, kategori, confidence, keywords, saran_folder, saran_nama, status)."""
    exts = (".txt", ".md", ".csv", ".log", ".docx", ".pdf")
    files = []
    for dp, _, fn in os.walk(target):
        for f in sorted(fn):
            if f.lower().endswith(exts):
                files.append(os.path.join(dp, f))
    if limit:
        files = files[:limit]
    fb = []
    if feedback_path and os.path.exists(feedback_path):
        try:
            with open(feedback_path, encoding="utf-8") as fh:
                fb = json.load(fh)
        except Exception:
            fb = []
    cents = train_centroids(fb)
    results, hashes = [], []
    for p in files:
        try:
            size = os.path.getsize(p)
        except OSError:
            continue
        text, info = extract_text(p)
        if info != "ok":
            results.append({"path": p, "kategori": "Tak-terbaca", "confidence": 0.0,
                            "keywords": [], "saran_folder": "Tak-terbaca",
                            "saran_nama": os.path.basename(p), "status": info,
                            "size": size, "near_dup_of": ""})
            continue
        cat, conf, kw = classify(text, cents)
        if conf < 0.15:
            # fallback: judul file sering lebih jelas daripada isi (mis. PDF scan)
            cat2, conf2, kw2 = classify(os.path.basename(p) * 5, cents)
            if conf2 > conf:
                cat, conf, kw = cat2, conf2, kw2
        sh = simhash64(text)
        near = ""
        if sh is not None:
            for q, qh in hashes:
                if ham64(sh, qh) <= 5:
                    near = q
                    break
            hashes.append((p, sh))
        base, ext = os.path.basename(p), os.path.splitext(p)[1].lower()
        if conf >= 0.3 and kw:
            saran = safe_name(" ".join(kw)) + ext
        else:
            saran = base  # confidence rendah -> jangan sarankan rename
        results.append({"path": p, "kategori": cat, "confidence": conf,
                        "keywords": kw, "saran_folder": cat,
                        "saran_nama": saran,
                        "status": "ok", "size": size, "near_dup_of": near})
    return results


def save_feedback(feedback_path, text_sample, category):
    fb = []
    if os.path.exists(feedback_path):
        try:
            with open(feedback_path, encoding="utf-8") as fh:
                fb = json.load(fh)
        except Exception:
            fb = []
    fb.append({"text": (text_sample or "")[:5000], "category": category,
               "time": datetime.now().isoformat()})
    os.makedirs(os.path.dirname(os.path.abspath(feedback_path)), exist_ok=True)
    with open(feedback_path, "w", encoding="utf-8") as fh:
        json.dump(fb, fh, ensure_ascii=False, indent=1)
    return len(fb)
