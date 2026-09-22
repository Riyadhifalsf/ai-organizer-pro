#!/usr/bin/env python3
"""organizer.py — launcher tipis ai_organizer. Hanya 4 perintah:

    organizer install          pasang (bila belum): lib + menu Explorer + startup
    organizer hapus            lepas (bila sudah): menu + startup + paket pip
    organizer cli <args...>    jalankan engine mode teks (scan/karantina/analyze/...)
    organizer gui              buka aplikasi desktop Qt

Contoh:
    organizer install
    organizer cli scan D:\\foto --dry-run
    organizer gui
"""
import os
import sys

sys.dont_write_bytecode = True  # jangan buat __pycache__ di folder utama

if getattr(sys, "frozen", False):
    BASE = os.path.dirname(os.path.abspath(sys.executable))
    if os.path.basename(BASE).lower() == "dist":
        BASE = os.path.dirname(BASE)
else:
    BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

HELP = __doc__ + "\nLihat juga: CARA_PAKAI.txt"


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(HELP)
        return
    from app.core import engine
    cmd, rest = argv[0].lower(), argv[1:]
    if cmd == "install":
        if engine.is_installed(BASE):
            print("Sudah terinstall. Pakai 'organizer hapus' untuk melepas.", flush=True)
            return
        return engine.do_install(None)
    if cmd in ("hapus", "uninstall"):
        if not engine.is_installed(BASE):
            print("Belum terinstall, tidak ada yang dilepas.", flush=True)
            return
        return engine.do_uninstall()
    if cmd == "cli":
        return engine.main(rest)
    if cmd == "gui":
        return run_gui()
    print(f"Perintah tidak dikenal: {cmd}\n{HELP}")


def run_gui():
    """Buka aplikasi desktop Qt (qt/build/AIOrganizerPro.exe)."""
    pro = os.path.dirname(BASE)  # BASE = engine-py -> pro root
    exe = os.path.join(pro, "qt", "build", "AIOrganizerPro.exe")
    if os.path.isfile(exe):
        if os.name == "nt":
            os.startfile(exe)
        else:
            import subprocess
            subprocess.Popen([exe])
        return
    print(f"Aplikasi Qt belum dibuild: {exe}\nJalankan: PRO.cmd build-qt",
          flush=True)


if __name__ == "__main__":
    main()
