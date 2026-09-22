#!/usr/bin/env python3
"""llm.py — otak LLM lokal: Qwen kecil via Ollama (stdlib saja, tanpa pip).

Model default: qwen2.5:0.5b (397MB, ~5 detik/jawab di CPU, RAM 8GB aman).
Model disimpan di D:\\ai_organizer\\llm\\models (OLLAMA_MODELS) agar C: hemat.
Fungsi: ringkasan 1 kalimat, second-opinion kategori, saran nama file.
"""
import json
import os
import subprocess
import time
import urllib.request

MODEL = "qwen2.5:0.5b"
HOST = "http://127.0.0.1:11434"
CATEGORIES = ["Keuangan", "Akademik", "Kantor", "Hukum", "Kesehatan", "Teknologi", "Pribadi", "Lainnya"]


def _ollama_exe():
    cands = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Links", "ollama.exe"),
    ]
    for c in cands:
        if c and os.path.isfile(c):
            return c
    return "ollama"


MODELS = [
    # (id ollama, label, RAM, ukuran) — dipilih di GUI Pengaturan / settings llm_model
    ("qwen2.5:0.5b", "Qwen2.5 0.5B — tercepat, RAM 2GB+ (~400MB)", "2GB", "~400MB"),
    ("qwen2.5:1.5b", "Qwen2.5 1.5B — seimbang, RAM 4GB+ (~1GB)", "4GB", "~1GB"),
    ("qwen2.5:3b", "Qwen2.5 3B — pintar, RAM 8GB+ (~2GB)", "8GB", "~2GB"),
    ("qwen3:0.6b", "Qwen3 0.6B — generasi baru, ringan (~400MB)", "2GB", "~400MB"),
    ("qwen3:1.7b", "Qwen3 1.7B — generasi baru, akurat (~1.2GB)", "4GB", "~1.2GB"),
    ("deepseek-r1:1.5b", "DeepSeek-R1 1.5B — reasoning kuat, lambat (~1.1GB)", "4GB", "~1.1GB"),
    ("llama3.2:1b", "Llama3.2 1B — alternatif Meta (~1.3GB)", "4GB", "~1.3GB"),
    ("gemma3:1b", "Gemma3 1B — alternatif Google (~800MB)", "4GB", "~800MB"),
]

MODEL = "qwen2.5:0.5b"


def _approot():
    d = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # app/
    for _ in range(3):
        if os.path.isfile(os.path.join(d, "organizer.py")):
            return d
        d = os.path.dirname(d)
    return d


def _env():
    env = dict(os.environ)
    env.setdefault("OLLAMA_MODELS", os.path.join(_approot(), "llm", "models"))
    return env


def alive(timeout=5):
    try:
        with urllib.request.urlopen(HOST + "/", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def ensure_server(wait=60):
    """Pastikan `ollama serve` jalan; start bila belum. Return True bila hidup."""
    if alive():
        return True
    try:
        subprocess.Popen([_ollama_exe(), "serve"], env=_env(),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:
        return False
    t0 = time.monotonic()
    while time.monotonic() - t0 < wait:
        if alive(timeout=3):
            return True
        time.sleep(2)
    return False


def has_model(model=MODEL):
    try:
        out = subprocess.run([_ollama_exe(), "list"], capture_output=True, text=True,
                             timeout=30, env=_env(),
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        return model.split(":")[0] in out
    except Exception:
        return False


def chat(prompt, max_tokens=256, timeout=180, model=MODEL):
    """Kirim prompt, kembalikan teks jawaban (tanpa stream)."""
    req = urllib.request.Request(
        HOST + "/api/generate",
        data=json.dumps({"model": model, "prompt": prompt, "stream": False,
                         "options": {"num_predict": max_tokens}}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode()).get("response", "").strip()


PROMPT_DOC = (
    "Kamu pengarsip dokumen. Klasifikasikan ke SATU kategori dari: {cats}.\n"
    "Nama file: {name}\nIsi (potongan):\n{text}\n\n"
    "Jawab HANYA JSON valid tanpa teks lain, format persis: "
)


def analyze_doc(text, filename, model=MODEL):
    """Return dict(kategori, ringkasan, nama) atau {} bila gagal."""
    import re
    cats = ", ".join(CATEGORIES)
    prompt = (PROMPT_DOC.format(cats=cats, name=os.path.basename(filename),
                                text=(text or "")[:3000])
              + '{"kategori": "...", "ringkasan": "maks 15 kata", '
              + '"nama": "maks-5-kata-tanpa-spasi"}')
    try:
        ans = chat(prompt, model=model)
    except Exception:
        return {}
    m = re.search(r"\{.*\}", ans, re.S)
    if not m:
        return {}
    try:
        d = json.loads(m.group(0))
    except Exception:
        return {}
    cat = str(d.get("kategori", "")).strip().title()
    if cat not in CATEGORIES:
        # cocokkan longgar
        for c in CATEGORIES:
            if c.lower() in cat.lower() or cat.lower() in c.lower():
                cat = c
                break
        else:
            return {}
    return {"kategori": cat,
            "ringkasan": str(d.get("ringkasan", ""))[:120],
            "nama": re.sub(r"[^a-zA-Z0-9\-]+", "-", str(d.get("nama", "")))[:60].strip("-") or ""}
