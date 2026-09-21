#!/usr/bin/env python3
"""scripts/daemon.py — ai_organizer berjalan di background (startup Windows).

Kerja:
- Pantau watch_folders (watchdog): file baru -> reasoning L1/L2 -> bila rusak/duplikat
  jelas, kirim rekomendasi; auto-aksi hanya untuk folder bertanda auto_* (persetujuan user).
- Poll jendela Explorer aktif -> rekomendasi kontekstual (integrations/explorer.py).
- Semua ringan: idle nyaris 0 CPU, reasoning di-cache.
Jalankan: organizer-cli.exe --daemon   (atau python organizer.py --daemon)
"""
import os
import sys
import threading
import time


def _approot():
    d = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # app/
    for _ in range(3):
        if os.path.isfile(os.path.join(d, "organizer.py")):
            return d
        d = os.path.dirname(d)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


BASE = _approot()
sys.path.insert(0, BASE)

from app.core import settings as settings_mod
from app.ai.behavior import Behavior
from app.integrations.explorer import explorer_poll_loop, notify
from app.ai.reason import Reasoner


def watch_loop(app_base):
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError:
        print("DAEMON: watchdog belum ada, coba bootstrap...", flush=True)
        sys.path.insert(0, app_base)
        from app.core import bootstrap
        if not bootstrap.ensure():
            return
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer

    st = settings_mod.load(app_base)
    be = Behavior(app_base)
    rs = Reasoner(app_base, st)
    folders = [f for f in st.get("watch_folders", []) if os.path.isdir(f)]
    if not folders:
        print("DAEMON: watch_folders kosong, hanya poll Explorer.", flush=True)
        return

    class H(FileSystemEventHandler):
        def on_created(self, e):
            if e.is_directory:
                return
            if not settings_mod.learn_allowed(e.src_path, st):
                return  # di luar izin belajar user
            be.log("file_new", e.src_path)
            try:
                r = rs.reason_file(e.src_path)
                rs.save()
                if r.get("aksi") == "karantina" and be.get_pref(f"auto_{os.path.dirname(e.src_path)}") == "1":
                    print(f"DAEMON AUTO: {e.src_path} -> {r.get('saran_folder')}", flush=True)
                elif r.get("kategori", "").startswith("Rusak") and st.get("notify", True):
                    notify("ai_organizer 🤖", f"File baru rusak: {os.path.basename(e.src_path)}")
            except Exception:
                pass

    ob = Observer()
    h = H()
    for f in folders:
        ob.schedule(h, f, recursive=True)
        print(f"DAEMON pantau: {f}", flush=True)
    ob.start()
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        ob.stop()
    ob.join()


def main(app_base):
    print("DAEMON ai_organizer aktif (Ctrl+C untuk stop).", flush=True)
    t = threading.Thread(target=watch_loop, args=(app_base,), daemon=True)
    t.start()
    try:
        explorer_poll_loop(app_base, notify_fn=(notify if settings_mod.load(app_base).get("notify", True) else None))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main(BASE)
