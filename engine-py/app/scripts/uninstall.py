#!/usr/bin/env python3
"""uninstall.exe — lepas ai_organizer dari Windows (double-click).

1. Matikan startup + hapus context-menu Explorer.
2. Cabut paket pip yang pernah di-download (pillow, watchdog).
3. Tanya: hapus juga folder aplikasi + hasil? (default TIDAK).
Jalankan sebagai user biasa (HKCU, tanpa admin).
"""
import os
import shutil
import sys


def _app_dir():
    if getattr(sys, "frozen", False):
        d = os.path.dirname(os.path.abspath(sys.executable))
        return d  # EXE di root aplikasi (tanpa folder dist/)
    d = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # app/
    for _ in range(3):
        if os.path.isfile(os.path.join(d, "organizer.py")):
            return d
        d = os.path.dirname(d)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


BASE = _app_dir()
sys.path.insert(0, BASE)

print("== UNINSTALL ai_organizer ==")
try:
    from app.core import engine
    if not engine.is_installed(BASE):
        print("Belum terinstall, lanjut bersih-bersih sisa.")
    engine.do_uninstall()
except Exception as e:
    print(f"Uninstall engine gagal: {e}")
    try:
        from app.integrations import explorer
        ok, msg = explorer.set_startup(False, "")
        print(f"Startup: {msg}")
        ok, msg = explorer.uninstall_context_menu()
        print(f"Context-menu: {msg}")
    except Exception as e2:
        print(f"Fallback gagal: {e2}")

ans = input("Hapus juga folder aplikasi + hasil (results/)? [ketik HAPUS / Enter=tidak] ").strip()
if ans.upper() == "HAPUS":
    try:
        shutil.rmtree(BASE, ignore_errors=False)
        print("Folder aplikasi dihapus.")
    except Exception as e:
        print(f"Tutup dulu aplikasi ini lalu hapus manual: {BASE} ({e})")
else:
    print("File hasil dipertahankan. Hapus manual bila perlu:", BASE)
print("Selesai.")
