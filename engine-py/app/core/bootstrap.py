#!/usr/bin/env python3
"""bootstrap.py — auto-install library saat awal (user tidak install manual).

Dipanggil otomatis oleh organizer.py / GUI / daemon bila import gagal.
Paket: pillow (gambar), watchdog (monitor folder, daemon).
Jalankan manual: python bootstrap.py
"""
import subprocess
import sys

REQUIRED = {
    "PIL": "pillow",
    "watchdog": "watchdog",
}

OPTIONAL_INFO = [
    ("Ollama + qwen2.5:0.5b", "LLM lokal (ringkasan/second-opinion). Install: winget install Ollama.Ollama lalu: ollama pull qwen2.5:0.5b"),
    ("FFmpeg", "Deteksi video rusak. Sudah ada di app/ffmpeg/bin sebelah aplikasi."),
]


def ensure(auto=True):
    missing = []
    for mod, pip_name in REQUIRED.items():
        try:
            __import__(mod)
        except ImportError:
            missing.append(pip_name)
    if not missing:
        return True
    frozen = bool(getattr(sys, "frozen", False))
    if frozen:
        # Di dalam EXE tidak bisa pip install: library harus sudah dibundel.
        print(f"BOOTSTRAP: kurang di dalam EXE: {', '.join(missing)} "
              f"(pakai versi source .py bila perlu).", flush=True)
        return False
    if missing and auto:
        print(f"BOOTSTRAP: menginstall {', '.join(missing)} ...", flush=True)
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", *missing],
                           check=True, timeout=600)
            print("BOOTSTRAP: selesai.", flush=True)
        except Exception as e:
            print(f"BOOTSTRAP GAGAL: {e}", flush=True)
            print("Install manual: pip install " + " ".join(missing), flush=True)
            return False
    else:
        print("Kurang: pip install " + " ".join(missing), flush=True)
        return False
    return True


def show_optional():
    print("Opsional (ada pilihan install di GUI -> Pengaturan):")
    for name, desc in OPTIONAL_INFO:
        print(f"  - {name}: {desc}")


if __name__ == "__main__":
    ok = ensure()
    show_optional()
    sys.exit(0 if ok else 1)
