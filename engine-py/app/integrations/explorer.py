#!/usr/bin/env python3
"""integrations/explorer.py — integrasi File Manager Windows.

1) Shell extension COM (AiShExt.dll, C#): klik kanan folder/background ->
   submenu "ai_organizer" DINAMIS (Scan, Analisis AI, GUI + top-3 rekomendasi
   dari results/reports/recommend.json). HKCU, tanpa admin.
   Fallback: entri statis Directory\\shell bila DLL tak bisa dipakai.
2) AiHelper.exe (C#): toast balon + folder Explorer aktif tanpa lib tambahan.
3) Daemon --watch: pantau folder (watchdog) + deteksi folder aktif Explorer.
"""
import os
import subprocess
import sys
import time

APP_NAME = "ai_organizer"
CLSID = "{7E3A9B2C-4D1F-4A8E-9C6B-5F0A2D4E8C1A}"


def _walk_root(start):
    d = os.path.abspath(start)
    for _ in range(5):
        if os.path.isfile(os.path.join(d, "organizer.py")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return os.path.abspath(start)


def _app_root():
    here = os.path.dirname(os.path.abspath(__file__))  # app/integrations/
    return _walk_root(os.path.dirname(here))


def _exe_root():
    """Folder aplikasi saat berjalan dari EXE (dist/|bin/ -> parent-nya)."""
    if getattr(sys, "frozen", False):
        d = os.path.dirname(os.path.abspath(sys.executable))
        if os.path.basename(d).lower() in ("dist", "bin"):
            return os.path.dirname(d)
        return d
    return _app_root()


def _files_root():
    return os.path.join(_exe_root(), "app")


def _native_paths():
    root = _files_root()
    bindir = os.path.join(root, "native", "bin")
    return (os.path.join(bindir, "AiShExt.dll"),
            os.path.join(bindir, "AiHelper.exe"))


def _csc():
    return r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"


def build_native():
    """Compile DLL+helper bila belum ada / source lebih baru. Return (ok, msg)."""
    if os.name != "nt":
        return False, "hanya Windows"
    root = _files_root()
    dll, helper = _native_paths()
    jobs = [("AiShExt.cs", dll, ["/target:library"]),
            ("AiHelper.cs", helper, ["/target:exe", "/reference:System.Windows.Forms.dll",
                                     "/reference:System.Drawing.dll"])]
    csc = _csc()
    if not os.path.isfile(csc):
        have = os.path.isfile(dll) and os.path.isfile(helper)
        return have, "csc tidak ada" if not have else "binari sudah ada"
    os.makedirs(os.path.dirname(dll), exist_ok=True)
    try:
        for src, out, extra in jobs:
            s = os.path.join(root, "native", src)
            if not os.path.isfile(s):
                if os.path.isfile(out):
                    continue  # frozen: pakai binari yang sudah ada
                return False, f"source hilang: {s}"
            if os.path.isfile(out) and os.path.getmtime(out) >= os.path.getmtime(s):
                continue
            r = subprocess.run([csc, "/nologo"] + extra + ["/out:" + out, s],
                               capture_output=True, text=True, timeout=180)
            if r.returncode != 0 or not os.path.isfile(out):
                return False, (r.stdout + r.stderr)[-500:]
        return True, "native OK"
    except Exception as e:
        return False, str(e)


def _reg(cmd):
    import winreg
    return cmd(winreg)


def _remove_static_entries():
    import winreg
    done = 0
    for base in (r"Software\Classes\Directory\shell",
                 r"Software\Classes\Directory\Background\shell"):
        try:
            labels = [n for n in _subkeys(base) if n.startswith(APP_NAME)]
        except Exception:
            continue
        for label in labels:
            try:
                _del_tree(winreg.HKEY_CURRENT_USER, base + "\\" + label)
                done += 1
            except OSError:
                pass
    return done


def register_com(dll_path, app_exe, app_root):
    """Daftarkan shell extension (HKCU). Return (ok, msg)."""
    import winreg
    try:
        cls = rf"Software\Classes\CLSID\{CLSID}"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, cls) as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, "ai_organizer ShellExt")
            winreg.SetValueEx(k, "AppExe", 0, winreg.REG_SZ, os.path.abspath(app_exe))
            winreg.SetValueEx(k, "AppRoot", 0, winreg.REG_SZ, os.path.abspath(app_root))
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                              cls + r"\InprocServer32") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, "mscoree.dll")
            winreg.SetValueEx(k, "Assembly", 0, winreg.REG_SZ,
                              "AiShExt, Version=0.0.0.0, Culture=neutral, PublicKeyToken=null")
            winreg.SetValueEx(k, "Class", 0, winreg.REG_SZ, "AiOrganizerShell.ShellExt")
            winreg.SetValueEx(k, "RuntimeVersion", 0, winreg.REG_SZ, "v4.0.30319")
            winreg.SetValueEx(k, "CodeBase", 0, winreg.REG_SZ,
                              "file:///" + os.path.abspath(dll_path).replace("\\", "/"))
            winreg.SetValueEx(k, "ThreadingModel", 0, winreg.REG_SZ, "Both")
        # ProgId -> CLSID (agar New-Object -ComObject 'AiOrganizer.ShellExt' bisa)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                              r"Software\Classes\AiOrganizer.ShellExt\CLSID") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, CLSID)
        n = 0
        for base in (r"Software\Classes\Directory\shellex\ContextMenuHandlers",
                     r"Software\Classes\Directory\Background\shellex\ContextMenuHandlers"):
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + "\\" + APP_NAME) as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, CLSID)
                n += 1
        return True, f"COM terdaftar ({n} handler)"
    except Exception as e:
        return False, str(e)


def unregister_com():
    import winreg
    try:
        for base in (r"Software\Classes\Directory\shellex\ContextMenuHandlers",
                     r"Software\Classes\Directory\Background\shellex\ContextMenuHandlers"):
            try:
                _del_tree(winreg.HKEY_CURRENT_USER, base + "\\" + APP_NAME)
            except OSError:
                pass
        try:
            _del_tree(winreg.HKEY_CURRENT_USER, rf"Software\Classes\CLSID\{CLSID}")
        except OSError:
            pass
        try:
            _del_tree(winreg.HKEY_CURRENT_USER, r"Software\Classes\AiOrganizer.ShellExt")
        except OSError:
            pass
        return True, "COM dilepas"
    except Exception as e:
        return False, str(e)


def install_context_menu(exe_path):
    """Utamakan COM dinamis; fallback entri statis. (HKCU, tanpa admin)."""
    if os.name != "nt":
        return False, "hanya Windows"
    ok, msg = build_native()
    dll, _helper = _native_paths()
    if ok and os.path.isfile(dll):
        ok2, msg2 = register_com(dll, exe_path, _exe_root())
        if ok2:
            n = _remove_static_entries()
            return True, f"{msg2} (statis dibersihkan: {n})"
    # fallback statis
    import winreg
    exe = os.path.abspath(exe_path)
    entries = [
        (f"{APP_NAME} - Scan di sini", f'"{exe}" cli scan "%V"'),
        (f"{APP_NAME} - Analisis AI di sini", f'"{exe}" cli analyze "%V"'),
    ]
    try:
        for label, command in entries:
            key = rf"Software\Classes\Directory\shell\{label}"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, label)
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key + r"\command") as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, command)
        return True, f"statis: {len(entries)} menu ({msg})"
    except Exception as e:
        return False, str(e)


def uninstall_context_menu():
    if os.name != "nt":
        return True, "skip"
    import winreg
    done = 0
    try:
        ok, msg = unregister_com()
        labels = [n for n in _subkeys(r"Software\Classes\Directory\shell") if n.startswith(APP_NAME)]
        for label in labels:
            _del_tree(winreg.HKEY_CURRENT_USER, rf"Software\Classes\Directory\shell\{label}")
            done += 1
        bg = [n for n in _subkeys(r"Software\Classes\Directory\Background\shell") if n.startswith(APP_NAME)]
        for label in bg:
            _del_tree(winreg.HKEY_CURRENT_USER, rf"Software\Classes\Directory\Background\shell\{label}")
            done += 1
        return True, f"{msg}; statis dihapus: {done}"
    except Exception as e:
        return False, str(e)


def _subkeys(path):
    import winreg
    out = []
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as k:
            i = 0
            while True:
                try:
                    out.append(winreg.EnumKey(k, i))
                    i += 1
                except OSError:
                    break
    except OSError:
        pass
    return out


def _del_tree(hive, path):
    import winreg
    try:
        with winreg.OpenKey(hive, path) as k:
            subs = []
            i = 0
            while True:
                try:
                    subs.append(winreg.EnumKey(k, i))
                    i += 1
                except OSError:
                    break
        for s in subs:
            _del_tree(hive, path + "\\" + s)
        winreg.DeleteKey(hive, path)
    except OSError:
        pass


def create_desktop_shortcut(exe_path, name="ai_organizer", icon_path=""):
    """Buat shortcut Desktop (.lnk) ber-icon via PowerShell. Return (ok, msg)."""
    if os.name != "nt":
        return False, "hanya Windows"
    try:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        lnk = os.path.join(desktop, name + ".lnk")
        icon = icon_path or exe_path
        ps = (f"$ws = New-Object -ComObject WScript.Shell; "
              f"$s = $ws.CreateShortcut('{lnk}'); "
              f"$s.TargetPath = '{os.path.abspath(exe_path)}'; "
              f"$s.WorkingDirectory = '{os.path.dirname(os.path.abspath(exe_path))}'; "
              f"$s.IconLocation = '{os.path.abspath(icon)}'; $s.Save()")
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, timeout=30,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode == 0 and os.path.isfile(lnk):
            return True, lnk
        return False, (r.stderr or b"").decode(errors="replace")[-200:]
    except Exception as e:
        return False, str(e)


def remove_desktop_shortcut(name="ai_organizer"):
    try:
        lnk = os.path.join(os.path.expanduser("~"), "Desktop", name + ".lnk")
        if os.path.isfile(lnk):
            os.remove(lnk)
            return True, "shortcut dihapus"
        return True, "tidak ada shortcut"
    except Exception as e:
        return False, str(e)


def set_startup(enable, exe_path):
    """Auto-start via HKCU Run (per-user, tanpa admin)."""
    if os.name != "nt":
        return False, "hanya Windows"
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Run",
                            0, winreg.KEY_SET_VALUE) as k:
            if enable:
                winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ,
                                  f'"{os.path.abspath(exe_path)}" cli --daemon')
            else:
                try:
                    winreg.DeleteValue(k, APP_NAME)
                except OSError:
                    pass
        return True, "startup ON" if enable else "startup OFF"
    except Exception as e:
        return False, str(e)


def _helper():
    _dll, helper = _native_paths()
    return helper if os.path.isfile(helper) else ""


def notify(title, message, timeout=8):
    """Urutan: AiHelper balon -> BurntToast PS -> MessageBox."""
    if os.name != "nt":
        print(f"[NOTIF] {title}: {message}", flush=True)
        return
    h = _helper()
    if h:
        try:
            r = subprocess.run([h, "toast", title, message[:250]],
                               capture_output=True, timeout=20,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if r.returncode == 0:
                return
        except Exception:
            pass
    ps = ("New-BurntToastNotification -Text @('%s','%s') "
          "-AppLogo '%s'" % (title.replace("'", "''"), message.replace("'", "''")[:180],
                             os.path.abspath(sys.executable)))
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, timeout=15,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode == 0:
            return
    except Exception:
        pass
    try:  # fallback: balon MessageBox non-blocking-ish
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message[:500], title, 0x40 | 0x1000)
    except Exception:
        print(f"[NOTIF] {title}: {message}", flush=True)


def active_explorer_folder():
    """Urutan: AiHelper native -> pywin32 (bila ada)."""
    if os.name != "nt":
        return ""
    h = _helper()
    if h:
        try:
            r = subprocess.run([h, "activefolder"], capture_output=True, text=True,
                               timeout=15,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            p = (r.stdout or "").strip()
            if p and os.path.isdir(p):
                return p
        except Exception:
            pass
    try:
        from win32com.client import Dispatch  # pywin32 bila ada
        for w in Dispatch("Shell.Application").Windows():
            try:
                loc = w.LocationURL
                if loc and loc.lower().startswith("file:///"):
                    from urllib.parse import unquote
                    return unquote(loc[8:]).replace("/", os.sep)
            except Exception:
                continue
    except Exception:
        pass
    return ""


def write_recommend_json(reports_dir, recs):
    """Tulis top rekomendasi untuk submenu shell extension. Return path."""
    import json
    try:
        os.makedirs(reports_dir, exist_ok=True)
        p = os.path.join(reports_dir, "recommend.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump([{"text": r.get("text", "")[:80], "path": r.get("path", ""),
                        "args": ""} for r in recs[:3]], f, ensure_ascii=False)
        return p
    except Exception:
        return ""


def explorer_poll_loop(app_base, interval=10, notify_fn=None):
    """Loop daemon ringan: deteksi folder Explorer aktif -> behavior + rekomendasi."""
    sys.path.insert(0, _app_root())
    from app.ai.behavior import Behavior
    from app.core import settings as _st
    be = Behavior(app_base)
    try:
        _settings = _st.load(app_base)
    except Exception:
        _settings = {}
    seen = {}
    tick = 0
    while True:
        try:
            folder = active_explorer_folder()
            if folder and os.path.isdir(folder):
                now = time.time()
                if now - seen.get(folder, 0) > 600:  # max 1x/10 mnt per folder
                    seen[folder] = now
                    if _st.learn_allowed(folder, _settings):
                        be.log("folder_open", folder)
                    recs = [r for r in be.recommend() if r.get("path") == folder]
                    if recs and notify_fn:
                        notify_fn("ai_organizer", recs[0]["text"])
            tick += 1
            if tick % 6 == 0:  # ~1 mnt: segarkan JSON submenu shell extension
                try:
                    write_recommend_json(
                        os.path.join(os.path.abspath(app_base), "results", "reports"),
                        be.recommend())
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(interval)
