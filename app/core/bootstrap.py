#!/usr/bin/env python3
"""bootstrap.py — cek library Python (100% offline, TANPA download otomatis).

Aplikasi full offline: fungsi ini HANYA memeriksa + memberi tahu perintah
manual. Tidak ada pip install otomatis agar perilaku bisa diprediksi dan
aman untuk pemula. Paket: pillow (gambar), watchdog (monitor folder, daemon).
Jalankan manual: python bootstrap.py
"""
import sys

REQUIRED = {
    "PIL": "pillow",
    "watchdog": "watchdog",
}

OPTIONAL_INFO = [
    ("Ollama + qwen2.5:0.5b", "LLM lokal (ringkasan/second-opinion). Install: winget install Ollama.Ollama lalu: ollama pull qwen2.5:0.5b"),
    ("FFmpeg", "Deteksi video rusak. Sudah ada di bin/ffmpeg sebelah aplikasi."),
]


def ensure(auto=False):
    """Cek dependensi. TIDAK PERNAH download (offline-first).

    Argumen auto dipertahankan untuk kompatibilitas pemanggil lama, namun
    diabaikan: install selalu manual oleh user.
    """
    _ = auto
    missing = []
    for mod, pip_name in REQUIRED.items():
        try:
            __import__(mod)
        except ImportError:
            missing.append(pip_name)
    if not missing:
        return True
    print("Kurang (offline, install manual bila butuh): pip install " +
          " ".join(missing), flush=True)
    return False


def show_optional():
    print("Opsional (ada pilihan install di GUI -> Pengaturan):")
    for name, desc in OPTIONAL_INFO:
        print(f"  - {name}: {desc}")


if __name__ == "__main__":
    ok = ensure()
    show_optional()
    sys.exit(0 if ok else 1)
