#!/usr/bin/env python3
"""ai_organizer — duplicate + broken detector (lokal, tanpa remote).

    python organizer.py scan <folder> [--out DIR] [--mode exact|visual] [--dry-run]
    python organizer.py karantina <folder> [--out DIR] [--mode exact|visual] [--dry-run]
    python organizer.py video-broken <folder> [--out DIR] [--broken-mode copy|move] [--dry-run]
    python organizer.py image-broken <folder> [--out DIR] [--broken-mode copy|move] [--dry-run]
    python organizer.py size <folder> [--out DIR] [--dry-run]

  Struktur output di <out> (default: folder ai_organizer ini):
    duplicate/        duplikat yang dipindah (selalu PINDAH, sisakan 1)
    broken/light/     rusak ringan (copy atau pindah, lihat --broken-mode)
    broken/heavy/     rusak parah (copy atau pindah)
    laporan/          csv/zip laporan + cache resume

  Cara kerja duplikat exact: samakan ukuran -> hash 1MB pertama -> hash penuh SHA256.
  Mode visual: exact + thumbnail tengah video (ffmpeg) / foto langsung -> dHash PIL,
  grup bila jarak Hamming <= threshold (ketat=4, normal=8, longgar=12).
  Yang disimpan: file dengan path terpendek / nama paling awal.
  Tanpa install apa-apa (stdlib + PIL untuk image/visual saja).
"""
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
import time
from collections import defaultdict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

def _app_base():
    # App root: folder yang berisi organizer.py (launcher).
    # - dev: file ini di app/core/engine.py -> naik 2 level.
    # - frozen: folder EXE (dist/|bin/ -> parent-nya).
    # - fallback: naik sampai ketemu organizer.py (maks 4 level).
    if getattr(sys, "frozen", False):
        d = os.path.dirname(os.path.abspath(sys.executable))
        if os.path.basename(d).lower() in ("dist", "bin"):
            return os.path.dirname(d)
        return d
    d = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for _ in range(4):
        if os.path.isfile(os.path.join(d, "organizer.py")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


BASE = _app_base()
APP_FILES = os.path.join(BASE, "app")
KARANTINA = os.path.join(BASE, "duplikat")   # legacy, dipertahankan bila ada
LAPORAN = os.path.join(BASE, "laporan")
CACHE = os.path.join(LAPORAN, "hash_cache.csv")

# Struktur output baru. resolve_out() mengembalikan dict path.
def default_out_root():
    return BASE

# Struktur output baru: semua di bawah results/.
#   results/duplicate/  duplikat yang dipindah (selalu PINDAH, sisakan 1)
#   results/broken/light|heavy/  rusak ringan/parah
#   results/reports/    csv/zip laporan + cache resume + feedback + behavior db
#   results/dokumen/<kategori>/  hasil tata Dokumen AI
LEGACY_DIRS = ("duplikat", "laporan", "video_broken_detection")
MIGRATE_FILES = ("hash_cache.csv", "doc_feedback.json", "behavior.db",
                 "reason_cache.json", "video_scan_state.csv", "image_scan_state.csv")


def resolve_out(out_arg):
    """Tentukan root output: default folder ai_organizer, atau folder pilihan user."""
    root = os.path.abspath(normalize_target(out_arg)) if out_arg else os.path.abspath(BASE)
    res = os.path.join(root, "results")
    return {
        "root": root,
        "results": res,
        "duplicate": os.path.join(res, "duplicate"),
        "broken_light": os.path.join(res, "broken", "light"),
        "broken_heavy": os.path.join(res, "broken", "heavy"),
        "reports": os.path.join(res, "reports"),
        "dokumen": os.path.join(res, "dokumen"),
        "cache": os.path.join(res, "reports", "hash_cache.csv"),
    }

def ensure_out(out):
    for k in ("duplicate", "broken_light", "broken_heavy", "reports", "dokumen"):
        os.makedirs(out[k], exist_ok=True)
    # migrasi sekali: cache/feedback lama di <root>/laporan/ -> results/reports/
    old_lap = os.path.join(out["root"], "laporan")
    if os.path.isdir(old_lap):
        for name in MIGRATE_FILES:
            src, dst = os.path.join(old_lap, name), os.path.join(out["reports"], name)
            try:
                if os.path.isfile(src) and not os.path.exists(dst):
                    shutil.copy2(src, dst)
            except OSError:
                pass


def is_admin():
    """True bila proses elevated (dibutuhkan untuk pindah/hapus di folder protektif)."""
    if os.name != "nt":
        return os.geteuid() == 0 if hasattr(os, "geteuid") else True
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def require_admin_for_move():
    if not is_admin():
        print("PERINGATAN: proses TIDAK elevated (bukan Run as administrator).", flush=True)
        print("Pemindahan file di folder protektif bisa gagal (WinError 5).", flush=True)
        print("Lanjut dengan risiko sebagian GAGAL, atau batalkan (Ctrl+C) lalu", flush=True)
        print("jalankan ulang sebagai administrator. Lanjut dalam 5 detik...", flush=True)
        try:
            time.sleep(5)
        except KeyboardInterrupt:
            raise PermissionError("Dibatalkan user (butuh administrator).")


class DirLock:
    """Kunci sederhana agar dua proses tidak menggarap out_root yang sama."""

    def __init__(self, out_root):
        self.path = os.path.join(os.path.abspath(out_root), ".ai_organizer.lock")

    def __enter__(self):
        if os.path.exists(self.path):
            raise RuntimeError(
                f"Terkunci: {self.path} sudah ada. "
                "Proses lain sedang berjalan? Hapus file itu bila yakin tidak."
            )
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(f"pid={os.getpid()} time={datetime.now().isoformat()}\n")
        return self

    def __exit__(self, *exc):
        try:
            os.remove(self.path)
        except OSError:
            pass
        return False


def write_csv_atomic(path, fieldnames, rows):
    """Tulis CSV via file sementara + fsync + rename atomik (tahan corrupt NTFS)."""
    tmp = path + ".tmp"
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            pass
    os.replace(tmp, path)


def format_duration(seconds):
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def show_progress(label, done, total, started):
    elapsed = time.monotonic() - started
    rate = done / elapsed if elapsed > 0 else 0
    per_min = rate * 60
    if total:
        pct = done / total * 100
        width = 30
        filled = min(width, int(width * done / total))
        bar = "#" * filled + "-" * (width - filled)
        remaining = (total - done) / rate if rate > 0 else 0
        print(
            f"\r  {label:<12} [{bar}] {pct:6.2f}% | "
            f"{done:,}/{total:,} | {per_min:7.1f} file/menit | "
            f"elapsed {format_duration(elapsed)} | ETA {format_duration(remaining)}",
            end="", flush=True,
        )
    else:
        print(
            f"\r  {label:<12} {done:,} | {per_min:7.1f} file/menit | "
            f"elapsed {format_duration(elapsed)}",
            end="", flush=True,
        )

def normalize_target(target):
    r"""Terima D:\scan, D:/scan, /d/scan, dan D:scan (Git Bash)."""
    target = target.strip().strip('"')

    # Git Bash dapat menghapus backslash dari argumen seperti D:\scan,
    # sehingga Python menerima D:scan. Pulihkan menjadi D:\scan.
    if len(target) >= 3 and target[1] == ':' and not target[2] in ('\\', '/'):
        target = target[:2] + os.sep + target[2:]

    # Konversi /d/scan -> D:/scan pada Windows.
    elif len(target) >= 3 and target[0] == '/' and target[2] == '/' and target[1].isalpha():
        target = target[1].upper() + ':' + target[2:]

    return os.path.normpath(target)


def load_cache(cache_path=None):
    known = {}
    cp = cache_path or CACHE
    if os.path.exists(cp):
        with open(cp, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                try:
                    if os.path.getsize(r["path"]) == int(r["size"]):
                        known[r["path"]] = r["sha256"]
                except OSError:
                    pass
    return known


def save_cache(known, sizes, cache_path=None):
    cp = cache_path or CACHE
    os.makedirs(os.path.dirname(os.path.abspath(cp)), exist_ok=True)
    with open(cp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["path", "size", "sha256"])
        for p, h in known.items():
            w.writerow([p, sizes.get(p, 0), h])


def partial(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        h.update(f.read(1024 * 1024))
    return h.hexdigest()


def full(p, known):
    if p in known:
        return known[p]
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            b = f.read(4 * 1024 * 1024)
            if not b:
                break
            h.update(b)
    known[p] = h.hexdigest()
    return known[p]


def scan(target, out=None):
    target = normalize_target(target)
    if not os.path.isdir(target):
        raise FileNotFoundError(f"Folder tidak ditemukan: {target}")

    out = out or resolve_out(None)
    cache_path = out["cache"]
    skip_dirs = {
        os.path.abspath(out["root"]) + os.sep,
        os.path.abspath(KARANTINA) + os.sep,  # legacy
        os.path.abspath(os.path.join(target, "video_broken_detection")) + os.sep,
    }

    files, sizes = [], {}
    folder_count = 0
    skipped = 0
    started = time.monotonic()
    last_progress = 0
    for dp, dn, fn in os.walk(target):
        folder_count += 1
        dp_abs = os.path.abspath(dp) + os.sep
        if any(dp_abs.startswith(s) for s in skip_dirs):
            dn[:] = []
            continue
        for f in fn:
            if f.lower().endswith(".csv"):
                continue
            p = os.path.join(dp, f)
            try:
                s = os.path.getsize(p)
            except OSError:
                skipped += 1
                continue
            if s == 0:
                skipped += 1
                continue
            files.append(p)
            sizes[p] = s
            if len(files) - last_progress >= 5000:
                last_progress = len(files)
                show_progress("scan file", len(files), None, started)
    print()
    print(f"TOTAL {len(files):,} file | folder {folder_count:,} | dilewati {skipped:,} | waktu {format_duration(time.monotonic() - started)}", flush=True)

    by_size = defaultdict(list)
    for p in files:
        by_size[sizes[p]].append(p)

    known = load_cache(cache_path)
    groups, n_full = [], [0]
    size_groups = 0
    duplicate_size_groups = [(size, paths) for size, paths in by_size.items() if len(paths) >= 2]
    partial_total = sum(len(paths) for _, paths in duplicate_size_groups)
    partial_done = 0
    partial_started = time.monotonic()
    full_candidates_total = 0
    for _, paths in duplicate_size_groups:
        full_candidates_total += len(paths)
    full_done = 0
    full_started = time.monotonic()
    for size, paths in duplicate_size_groups:
        size_groups += 1
        by_part = defaultdict(list)
        for p in paths:
            try:
                by_part[partial(p)].append(p)
            except OSError:
                pass
            partial_done += 1
            if partial_done % 100 == 0 or partial_done == partial_total:
                show_progress("hash 1MB", partial_done, partial_total, partial_started)
        if size_groups % 100 == 0:
            print()
            print(f"  kandidat berdasarkan ukuran: {size_groups:,}", flush=True)
        for cand in by_part.values():
            if len(cand) < 2:
                continue
            by_full = defaultdict(list)
            for p in cand:
                try:
                    by_full[full(p, known)].append(p)
                    n_full[0] += 1
                except OSError:
                    pass
                full_done += 1
                if full_done % 20 == 0 or full_done == full_candidates_total:
                    show_progress("hash penuh", full_done, full_candidates_total, full_started)
            for same in by_full.values():
                if len(same) > 1:
                    same.sort(key=lambda x: (len(x), x))
                    groups.append((size, same))
        if n_full[0] % 20 == 0:
            save_cache(known, sizes, cache_path)
    print()
    save_cache(known, sizes, cache_path)
    return groups, sizes


def report(groups, sizes, target, out=None):
    out = out or resolve_out(None)
    lap = out["reports"]
    os.makedirs(lap, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    rep = os.path.join(lap, f"duplikat_{stamp}.csv")
    with open(rep, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["grup", "status", "size_MB", "path"])
        for i, (size, g) in enumerate(groups, 1):
            w.writerow([i, "disimpan", round(size / 1024 / 1024, 2), g[0]])
            for p in g[1:]:
                w.writerow([i, "duplikat", round(size / 1024 / 1024, 2), p])
    dup_n = sum(len(g) - 1 for _, g in groups)
    dup_b = sum(s * (len(g) - 1) for s, g in groups)
    print(f"GRUP: {len(groups)} | duplikat: {dup_n} file | "
          f"hemat: {dup_b / 1024 / 1024 / 1024:.2f} GB", flush=True)
    for i, (s, g) in enumerate(groups[:10], 1):
        print(f"  {i}. {os.path.basename(g[0])} x{len(g)} "
              f"({s / 1024 / 1024:.1f} MB)", flush=True)
    # Buat ZIP berisi laporan CSV.
    zip_path = os.path.splitext(rep)[0] + ".zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.write(rep, arcname=os.path.basename(rep))
    try:
        os.remove(rep)
    except OSError:
        pass
    print(f"Laporan ZIP: {zip_path}", flush=True)
    return dup_n


def _windows_take_ownership_and_grant(path):
    """Perbaiki ownership/ACL file dan seluruh parent folder yang relevan."""
    if os.name != "nt":
        return False

    import subprocess
    changed = False

    # Perbaiki dari file -> parent -> parent berikutnya.
    targets = []
    cur = os.path.abspath(path)
    for _ in range(4):
        targets.append(cur)
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent

    username = os.environ.get("USERNAME", "")
    domain = os.environ.get("USERDOMAIN", "")
    principal = f"{domain}\\{username}" if domain and username else username

    for target in targets:
        # Ownership.
        try:
            r = subprocess.run(
                ["takeown", "/f", target, "/a"],
                capture_output=True, text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            changed |= (r.returncode == 0)
        except (OSError, FileNotFoundError):
            pass

        # Full control untuk user aktif.
        if principal:
            try:
                r = subprocess.run(
                    ["icacls", target, "/grant", f"{principal}:F", "/c"],
                    capture_output=True, text=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                changed |= (r.returncode == 0)
            except (OSError, FileNotFoundError):
                pass

        # Hilangkan atribut yang bisa mengganggu operasi file.
        try:
            r = subprocess.run(
                ["attrib", "-R", "-S", "-H", target],
                capture_output=True, text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            changed |= (r.returncode == 0)
        except (OSError, FileNotFoundError):
            pass

    return changed


def _move_with_permission_retry(src, dst):
    """Pindahkan file; bila ditolak, perbaiki ACL sumber+folder dan ulangi."""
    try:
        shutil.move(src, dst)
        return True, None
    except PermissionError as first_error:
        if os.name != "nt":
            return False, first_error

        # Pertama coba buka akses sumber, parent, dan parent di atasnya.
        _windows_take_ownership_and_grant(src)

        # Folder tujuan juga perlu bisa ditulisi.
        _windows_take_ownership_and_grant(os.path.dirname(dst))

        try:
            shutil.move(src, dst)
            return True, None
        except PermissionError:
            # Beberapa file Windows lebih mudah dipindahkan dengan robocopy
            # (move file dalam volume yang sama), lalu hapus sumber.
            try:
                import subprocess
                src_dir = os.path.dirname(os.path.abspath(src))
                name = os.path.basename(src)
                dst_dir = os.path.dirname(os.path.abspath(dst))
                os.makedirs(dst_dir, exist_ok=True)

                r = subprocess.run(
                    ["robocopy", src_dir, dst_dir, name, "/MOV", "/COPY:DAT",
                     "/R:1", "/W:1", "/NFL", "/NDL", "/NJH", "/NJS", "/NP"],
                    capture_output=True, text=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                # Robocopy: 0-7 umumnya sukses/acceptable, >=8 gagal.
                if r.returncode < 8 and not os.path.exists(src) and os.path.exists(dst):
                    return True, None
            except (OSError, FileNotFoundError):
                pass
            return False, first_error
        except OSError as second_error:
            return False, second_error


def karantina(groups, out=None, dry_run=False):
    out = out or resolve_out(None)
    dest_dir = out["duplicate"]
    n = 0
    gagal = []
    if not dry_run:
        os.makedirs(dest_dir, exist_ok=True)

    for _, g in groups:
        for p in g[1:]:
            d = os.path.join(dest_dir, os.path.basename(p))
            if os.path.exists(d):
                stem, ext = os.path.splitext(os.path.basename(p))
                i = 1
                while os.path.exists(os.path.join(dest_dir, f"{stem} ({i}){ext}")):
                    i += 1
                d = os.path.join(dest_dir, f"{stem} ({i}){ext}")

            if dry_run:
                print(f"RENCANA {p} -> {d}", flush=True)
                n += 1
                continue
            ok, err = _move_with_permission_retry(p, d)
            if ok:
                try:  # verifikasi: source hilang, dest ada
                    assert not os.path.exists(p) and os.path.exists(d)
                except AssertionError:
                    ok, err = False, "verifikasi pindah gagal"
            if ok:
                n += 1
                print(f"PINDAH {p} -> {d}", flush=True)
            else:
                gagal.append((p, str(err)))
                print(f"GAGAL {p}: {err}", flush=True)

    tag = "RENCANA" if dry_run else "berhasil dikarantina"
    print(f"{n} file {tag} di {dest_dir}", flush=True)
    if gagal:
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        gagal_path = os.path.join(out["reports"], f"gagal_karantina_{stamp}.csv")
        os.makedirs(out["reports"], exist_ok=True)
        with open(gagal_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["path", "error"])
            w.writerows(gagal)
        print(f"{len(gagal)} file masih gagal dipindahkan.", flush=True)
        print(f"Daftar gagal: {gagal_path}", flush=True)




# ============================================================
# VIDEO BROKEN DETECTOR
# ============================================================

VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm",
    ".m4v", ".ts", ".mts", ".m2ts", ".3gp", ".3g2", ".mpeg",
    ".mpg", ".vob", ".ogv", ".asf", ".rm", ".rmvb"
}

def _env_workers(name, default):
    try:
        v = int(os.environ.get(name, default))
        return min(max(v, 1), 16)
    except (TypeError, ValueError):
        return default


VIDEO_WORKERS = _env_workers("AIORG_VIDEO_WORKERS", 6)

def _find_ffprobe():
    """Return ffprobe executable path if available.

    Urutan: sebelah EXE -> third_party/ffmpeg/bin -> app/ffmpeg/bin bawaan -> PATH.
    """
    import shutil
    ff = "ffprobe.exe" if os.name == "nt" else "ffprobe"
    cands = []
    try:  # lokasi EXE hasil PyInstaller
        if getattr(sys, "frozen", False):
            base = os.path.dirname(os.path.abspath(sys.executable))
            cands.append(os.path.join(base, ff))
            cands.append(os.path.join(base, "ffmpeg", "bin", ff))
    except Exception:
        pass
    # pro root = 3 tingkat di atas app/core (python/ai_worker/app/core).
    pro_root = os.path.dirname(os.path.dirname(os.path.dirname(APP_FILES)))
    cands.append(os.path.join(pro_root, "third_party", "ffmpeg", "bin", ff))
    cands.append(os.path.join(APP_FILES, "ffmpeg", "bin", ff))
    cands.append(os.path.join(BASE, "ffmpeg-9.0.1", "bin", ff))  # legacy
    for c in cands:
        if os.path.isfile(c):
            return c
    return shutil.which("ffprobe")

def _video_status(path):
    """
    Return:
      NORMAL       = ffprobe can read the video stream.
      LIGHT_BROKEN = stream is readable but ffprobe reports decode/container issues.
      HEAVY_BROKEN = cannot be opened / no usable video stream / severe failure.
    """
    import subprocess

    ffprobe = _find_ffprobe()
    if not ffprobe:
        return "HEAVY_BROKEN", "ffprobe tidak ditemukan di PATH"

    cmd = [
        ffprobe,
        "-v", "error",
        # NB: tanpa duration — duration memaksa full-file scan (10 dtk/file MTS).
        "-select_streams", "v:0",
        "-show_entries", "stream=index,codec_name,width,height",
        "-of", "json",
        str(path),
    ]

    try:
        p = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            timeout=120,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired:
        return "LIGHT_BROKEN", "ffprobe timeout"
    except Exception as e:
        return "HEAVY_BROKEN", f"ffprobe error: {e}"

    stderr = (p.stderr or "").strip()
    stdout = (p.stdout or "").strip()

    # No video stream / completely unreadable.
    if p.returncode != 0 and not stdout:
        return "HEAVY_BROKEN", stderr[-1000:] or "ffprobe gagal membaca file"

    try:
        import json
        data = json.loads(stdout) if stdout else {}
    except Exception:
        data = {}

    streams = data.get("streams") or []
    if not streams:
        return "HEAVY_BROKEN", stderr[-1000:] or "tidak ditemukan video stream"

    # ffprobe may still return a stream while reporting recoverable errors.
    if stderr:
        return "LIGHT_BROKEN", stderr[-1000:]

    return "NORMAL", ""

def _safe_place_broken(src, dst_root, category, base_root, mode="copy", dry_run=False):
    """
    Letakkan file broken ke dst_root/category/ (pertahankan struktur relatif).
    mode="copy": original tetap. mode="move": original dipindah + verifikasi.
    """
    import shutil

    src = os.path.abspath(src)
    base_root = os.path.abspath(base_root)

    try:
        rel = os.path.relpath(src, base_root)
    except ValueError:
        rel = os.path.basename(src)

    destination = os.path.join(dst_root, category, rel)

    # Avoid copying onto itself.
    if os.path.abspath(destination).lower() == src.lower():
        return destination

    # If a file already exists, make a unique destination.
    if os.path.exists(destination):
        stem, ext = os.path.splitext(destination)
        n = 1
        candidate = f"{stem}__{n}{ext}"
        while os.path.exists(candidate):
            n += 1
            candidate = f"{stem}__{n}{ext}"
        destination = candidate

    if dry_run:
        return destination
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    if mode == "move":
        ok, err = _move_with_permission_retry(src, destination)
        if not ok:
            raise OSError(err)
    else:
        shutil.copy2(src, destination)
    return destination

def video_broken(target, out=None, broken_mode="copy", dry_run=False, limit=0):
    """
    Scan videos recursively.

    - broken_mode="copy": original TIDAK dihapus (default, perilaku lama).
    - broken_mode="move": original DIPINDAH ke broken/light|heavy + verifikasi.
    - Hasil: <out>/broken/light|heavy + laporan CSV + resume state.
    """
    import csv
    import hashlib
    from datetime import datetime

    target = os.path.abspath(target)

    if not os.path.isdir(target):
        print(f"Folder tidak ditemukan: {target}")
        return

    ffprobe = _find_ffprobe()
    if not ffprobe:
        print("ERROR: ffprobe tidak ditemukan.")
        print("Letakkan ffprobe di third_party/ffmpeg/bin, atau install FFmpeg ke PATH.")
        return

    out = out or resolve_out(None)
    out_root = out["root"]
    light_root = out["broken_light"]
    heavy_root = out["broken_heavy"]
    if not dry_run:
        os.makedirs(light_root, exist_ok=True)
        os.makedirs(heavy_root, exist_ok=True)

    state_file = os.path.join(out["reports"], "video_scan_state.csv")
    report_file = os.path.join(
        out["reports"],
        f"video_report_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"
    )

    # Never scan our own generated result directory (out_root bila di dalam target).
    out_abs = os.path.abspath(out_root) + os.sep
    videos = []
    for root, dirs, files in os.walk(target):
        if (os.path.abspath(root) + os.sep).startswith(out_abs):
            dirs[:] = []
            continue
        dirs[:] = [
            d for d in dirs
            if (os.path.abspath(os.path.join(root, d)) + os.sep) != out_abs
            and os.path.abspath(os.path.join(root, d)).lower() != os.path.join(target, "video_broken_detection").lower()
        ]
        for name in files:
            p = os.path.join(root, name)
            if os.path.splitext(name)[1].lower() in VIDEO_EXTENSIONS:
                videos.append(p)

    print(f"VIDEO BROKEN SCAN: {target}")
    print(f"TOTAL VIDEO: {len(videos)}")

    # Load resume state keyed by path + size + mtime_ns.
    old_state = {}
    if os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    key = (row.get("path", ""), row.get("size", ""), row.get("mtime_ns", ""))
                    old_state[key] = row
        except Exception:
            old_state = {}

    def make_key(p):
        st = os.stat(p)
        return (p, str(st.st_size), str(st.st_mtime_ns))

    pending = []
    results = []

    for p in videos:
        try:
            key = make_key(p)
        except OSError as e:
            results.append({
                "path": p,
                "status": "HEAVY_BROKEN",
                "reason": f"stat error: {e}",
                "size": "",
                "mtime_ns": "",
                "copied_to": "",
            })
            continue

        cached = old_state.get(key)
        if cached:
            results.append(cached)
        else:
            pending.append((p, key))

    print(f"RESUME CACHE: {len(results)}")
    print(f"TO PROCESS: {len(pending)}")
    if limit and limit > 0 and len(pending) > limit:
        pending = pending[:limit]
        print(f"CHUNK LIMIT: {limit} (ulangi perintah untuk lanjut)", flush=True)

    def worker(item):
        p, key = item
        try:
            status, reason = _video_status(p)
            copied_to = ""

            if status == "LIGHT_BROKEN":
                copied_to = _safe_place_broken(
                    p, out_root, os.path.join("broken", "light"), target,
                    broken_mode, dry_run,
                )
            elif status == "HEAVY_BROKEN":
                copied_to = _safe_place_broken(
                    p, out_root, os.path.join("broken", "heavy"), target,
                    broken_mode, dry_run,
                )

            return {
                "path": p,
                "status": status,
                "reason": reason,
                "size": key[1],
                "mtime_ns": key[2],
                "copied_to": copied_to,
            }
        except Exception as e:
            return {
                "path": p,
                "status": "HEAVY_BROKEN",
                "reason": f"processing error: {e}",
                "size": key[1],
                "mtime_ns": key[2],
                "copied_to": "",
            }

    done = 0
    total_pending = len(pending)
    fieldnames = ["path", "status", "reason", "size", "mtime_ns", "copied_to"]
    if not dry_run:
        os.makedirs(out["reports"], exist_ok=True)

    import concurrent.futures as _fut
    with ThreadPoolExecutor(max_workers=VIDEO_WORKERS) as executor:
        fut2item = {executor.submit(worker, item): item for item in pending}
        remaining = set(fut2item)
        while remaining:
            done_set, _ = _fut.wait(remaining, timeout=180,
                                    return_when=_fut.FIRST_COMPLETED)
            if not done_set:
                # Semua worker macet >180 dtk: catat timeout, lanjut (anti-hang total).
                for fu in list(remaining):
                    p, key = fut2item[fu]
                    fu.cancel()
                    results.append({"path": p, "status": "LIGHT_BROKEN",
                                    "reason": "worker timeout 180s", "size": key[1],
                                    "mtime_ns": key[2], "copied_to": ""})
                    print(f"TIMEOUT {p}", flush=True)
                    remaining.discard(fu)
                    done += 1
                continue
            for fu in done_set:
                try:
                    results.append(fu.result())
                except Exception as e:
                    p, key = fut2item[fu]
                    results.append({"path": p, "status": "HEAVY_BROKEN",
                                    "reason": f"future error: {e}", "size": key[1],
                                    "mtime_ns": key[2], "copied_to": ""})
                remaining.discard(fu)
                done += 1
            if done % 25 == 0 or done == total_pending:
                print(f"PROGRESS: {done}/{total_pending}", flush=True)
            if not dry_run and done % 100 == 0:
                try:
                    write_csv_atomic(state_file, fieldnames, results)
                except Exception:
                    pass

    # Save resume state (atomik + fsync, tahan corrupt).
    if not dry_run:
        os.makedirs(out["reports"], exist_ok=True)
        write_csv_atomic(state_file, fieldnames, results)

    # Write human-readable report.
    results.sort(key=lambda x: x.get("path", "").lower())
    if not dry_run:
        with open(report_file, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in results:
                writer.writerow({k: row.get(k, "") for k in fieldnames})

    normal = sum(r.get("status") == "NORMAL" for r in results)
    light = sum(r.get("status") == "LIGHT_BROKEN" for r in results)
    heavy = sum(r.get("status") == "HEAVY_BROKEN" for r in results)

    print()
    print("SELESAI")
    print(f"NORMAL       : {normal}")
    print(f"LIGHT_BROKEN : {light}")
    print(f"HEAVY_BROKEN : {heavy}")
    print(f"MODE         : {broken_mode}{' (dry-run)' if dry_run else ''}")
    print(f"REPORT       : {report_file}{' (tidak ditulis: dry-run)' if dry_run else ''}")
    print(f"STATE        : {state_file}")
    print(f"LIGHT FOLDER : {light_root}")
    print(f"HEAVY FOLDER : {heavy_root}")
    print(f"ORIGINAL FILE: {'TIDAK DIHAPUS (copy)' if broken_mode == 'copy' else 'DIPINDAH (move)'}")


# ============================================================
# IMAGE BROKEN DETECTOR (PIL, tanpa ffmpeg)
# ============================================================

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
IMAGE_WORKERS = 4


def _image_status(path):
    """Klasifikasi gambar rusak (2 tahap, mirip _video_status).

    HEAVY_BROKEN = gagal dibuka / header rusak / truncated fatal.
    LIGHT_BROKEN = bisa dibuka tapi truncated sebagian / warning / dimensi janggal.
    NORMAL       = terbuka penuh tanpa masalah.
    """
    try:
        from PIL import Image, ImageFile
    except ImportError:
        return "HEAVY_BROKEN", "PIL (Pillow) belum terinstall"
    try:
        with Image.open(path) as im:
            im.verify()
    except Exception as e:
        return "HEAVY_BROKEN", f"verify gagal: {e}"[:500]
    try:
        from PIL import ImageFile
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        with Image.open(path) as im:
            w, h = im.size
            if not w or not h:
                return "HEAVY_BROKEN", "dimensi nol"
            try:
                im.load()
            except Exception as e:
                return "LIGHT_BROKEN", f"load sebagian: {e}"[:500]
            if getattr(im, "tile", None) is None and im.format in ("JPEG", "JPG"):
                pass
    except Exception as e:
        return "LIGHT_BROKEN", f"load gagal: {e}"[:500]
    return "NORMAL", ""


def image_broken(target, out=None, broken_mode="copy", dry_run=False, limit=0):
    """Scan gambar rusak. Struktur output & resume sama seperti video_broken."""
    import csv
    from datetime import datetime

    target = os.path.abspath(target)
    if not os.path.isdir(target):
        print(f"Folder tidak ditemukan: {target}")
        return
    try:
        import PIL  # noqa: F401
    except ImportError:
        print("ERROR: Pillow belum terinstall (pip install pillow).")
        return

    out = out or resolve_out(None)
    out_root = out["root"]
    light_root = out["broken_light"]
    heavy_root = out["broken_heavy"]
    if not dry_run:
        os.makedirs(light_root, exist_ok=True)
        os.makedirs(heavy_root, exist_ok=True)
    state_file = os.path.join(out["reports"], "image_scan_state.csv")
    report_file = os.path.join(
        out["reports"], f"image_report_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv")

    out_abs = os.path.abspath(out_root) + os.sep
    images = []
    for root, dirs, files in os.walk(target):
        if (os.path.abspath(root) + os.sep).startswith(out_abs):
            dirs[:] = []
            continue
        for name in files:
            if os.path.splitext(name)[1].lower() in IMAGE_EXTENSIONS:
                images.append(os.path.join(root, name))
    print(f"IMAGE BROKEN SCAN: {target}")
    print(f"TOTAL IMAGE: {len(images)}")

    old_state = {}
    if os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    old_state[(row.get("path", ""), row.get("size", ""), row.get("mtime_ns", ""))] = row
        except Exception:
            old_state = {}

    def make_key(p):
        st = os.stat(p)
        return (p, str(st.st_size), str(st.st_mtime_ns))

    pending, results = [], []
    for p in images:
        try:
            key = make_key(p)
        except OSError as e:
            results.append({"path": p, "status": "HEAVY_BROKEN",
                            "reason": f"stat error: {e}", "size": "",
                            "mtime_ns": "", "copied_to": ""})
            continue
        results.append(old_state[key]) if key in old_state else pending.append((p, key))

    print(f"RESUME CACHE: {len(results)}")
    print(f"TO PROCESS: {len(pending)}")
    if limit and limit > 0 and len(pending) > limit:
        pending = pending[:limit]
        print(f"CHUNK LIMIT: {limit} (ulangi perintah untuk lanjut)", flush=True)

    def worker(item):
        p, key = item
        try:
            status, reason = _image_status(p)
            placed = ""
            if status in ("LIGHT_BROKEN", "HEAVY_BROKEN"):
                cat = os.path.join("broken", "light" if status == "LIGHT_BROKEN" else "heavy")
                placed = _safe_place_broken(p, out_root, cat, target, broken_mode, dry_run)
            return {"path": p, "status": status, "reason": reason,
                    "size": key[1], "mtime_ns": key[2], "copied_to": placed}
        except Exception as e:
            return {"path": p, "status": "HEAVY_BROKEN",
                    "reason": f"processing error: {e}", "size": key[1],
                    "mtime_ns": key[2], "copied_to": ""}

    done, total_pending = 0, len(pending)
    fieldnames = ["path", "status", "reason", "size", "mtime_ns", "copied_to"]
    if not dry_run:
        os.makedirs(out["reports"], exist_ok=True)
    import concurrent.futures as _fut2
    with ThreadPoolExecutor(max_workers=IMAGE_WORKERS) as ex:
        fut2item = {ex.submit(worker, it): it for it in pending}
        remaining = set(fut2item)
        while remaining:
            done_set, _ = _fut2.wait(remaining, timeout=180,
                                     return_when=_fut2.FIRST_COMPLETED)
            if not done_set:
                for fu in list(remaining):
                    p, key = fut2item[fu]
                    fu.cancel()
                    results.append({"path": p, "status": "LIGHT_BROKEN",
                                    "reason": "worker timeout 180s", "size": key[1],
                                    "mtime_ns": key[2], "copied_to": ""})
                    print(f"TIMEOUT {p}", flush=True)
                    remaining.discard(fu)
                    done += 1
                continue
            for fu in done_set:
                try:
                    results.append(fu.result())
                except Exception as e:
                    p, key = fut2item[fu]
                    results.append({"path": p, "status": "HEAVY_BROKEN",
                                    "reason": f"future error: {e}", "size": key[1],
                                    "mtime_ns": key[2], "copied_to": ""})
                remaining.discard(fu)
                done += 1
            if done % 50 == 0 or done == total_pending:
                print(f"PROGRESS: {done}/{total_pending}", flush=True)
            if not dry_run and done % 100 == 0:
                try:
                    write_csv_atomic(state_file, fieldnames, results)
                except Exception:
                    pass

    if not dry_run:
        write_csv_atomic(state_file, fieldnames, results)
        results.sort(key=lambda x: x.get("path", "").lower())
        with open(report_file, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in results:
                writer.writerow({k: row.get(k, "") for k in fieldnames})
    normal = sum(r.get("status") == "NORMAL" for r in results)
    light = sum(r.get("status") == "LIGHT_BROKEN" for r in results)
    heavy = sum(r.get("status") == "HEAVY_BROKEN" for r in results)
    print()
    print("SELESAI")
    print(f"NORMAL       : {normal}")
    print(f"LIGHT_BROKEN : {light}")
    print(f"HEAVY_BROKEN : {heavy}")
    print(f"MODE         : {broken_mode}{' (dry-run)' if dry_run else ''}")
    print(f"REPORT       : {report_file}")
    print(f"ORIGINAL FILE: {'TIDAK DIHAPUS (copy)' if broken_mode == 'copy' else 'DIPINDAH (move)'}")


# ============================================================
# VISUAL DUPLICATE (dHash murni PIL, tanpa numpy/imagehash)
# ============================================================

VISUAL_VIDEO_EXT = {".mp4", ".mov", ".m2ts", ".mts", ".m2t", ".mkv", ".avi",
                    ".3gp", ".webm", ".wmv", ".flv", ".m4v", ".ts", ".mpg", ".mpeg"}
VISUAL_IMG_EXT = IMAGE_EXTENSIONS


def _dhash_pil(img, hash_size=8):
    """dHash 64-bit murni PIL: grayscale -> resize (h+1,h) -> banding horizontal."""
    from PIL import Image
    g = img.convert("L").resize((hash_size + 1, hash_size), Image.BILINEAR)
    px = list(g.getdata())
    bits, w = 0, hash_size + 1
    for y in range(hash_size):
        row = y * w
        for x in range(hash_size):
            bits = (bits << 1) | (1 if px[row + x] > px[row + x + 1] else 0)
    return bits


def _phash_of_image(path):
    try:
        from PIL import Image
        with Image.open(path) as im:
            return _dhash_pil(im)
    except Exception:
        return None


def _thumb_hash(path, idx, thumb_dir):
    out = os.path.join(thumb_dir, f"t{idx}.jpg")
    try:
        if os.path.exists(out) and os.path.getsize(out) > 0:
            return _phash_of_image(out)
    except OSError:
        pass
    ffprobe = _find_ffprobe()
    ss = "1.0"
    if ffprobe:
        try:
            import subprocess
            r = subprocess.run([ffprobe, "-v", "quiet", "-show_entries", "format=duration",
                                "-of", "csv=p=0", path], capture_output=True, text=True,
                               timeout=15, stderr=subprocess.DEVNULL)
            d = float(r.stdout.strip())
            if d and d > 1:
                ss = str(round(d * 0.5, 1))
        except Exception:
            pass
    try:
        import subprocess
        subprocess.run(["ffmpeg", "-y", "-v", "quiet", "-ss", ss, "-i", path,
                        "-frames:v", "1", "-vf", "scale=256:256", "-q:v", "5", out],
                       timeout=30, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(out) and os.path.getsize(out) > 0:
            return _phash_of_image(out)
    except Exception:
        pass
    return None


def _ham(a, b):
    return bin(a ^ b).count("1")


def scan_visual(target, out=None, threshold=8, limit=0, thumb_dir="/tmp/vthumbs_win"):
    """Hash visual semua file (sub folder). Return list (path, hash_int)."""
    target = normalize_target(target)
    out = out or resolve_out(None)
    skip = {os.path.abspath(out["root"]) + os.sep,
            os.path.abspath(KARANTINA) + os.sep}
    files = []
    for dp, dn, fn in os.walk(target):
        da = os.path.abspath(dp) + os.sep
        if any(da.startswith(s) for s in skip):
            dn[:] = []
            continue
        dn.sort()
        for f in sorted(fn):
            if os.path.splitext(f)[1].lower() in VISUAL_VIDEO_EXT | VISUAL_IMG_EXT:
                files.append(os.path.join(dp, f))
    if limit:
        files = files[:limit]
    print(f"TOTAL {len(files):,} file visual (semua sub folder) | threshold {threshold}", flush=True)
    if not files:
        return []
    os.makedirs(thumb_dir, exist_ok=True)
    hashes, t0 = [], time.monotonic()
    for i, p in enumerate(files, 1):
        ext = os.path.splitext(p)[1].lower()
        h = _phash_of_image(p) if ext in VISUAL_IMG_EXT else _thumb_hash(p, i, thumb_dir)
        if h is not None:
            hashes.append((p, h))
        if i % 50 == 0 or i == len(files):
            el = time.monotonic() - t0
            print(f"  {i}/{len(files)} hashed={len(hashes)} "
                  f"elapsed={format_duration(el)}", flush=True)
    return hashes


def group_visual(hashes, threshold=8):
    parent = list(range(len(hashes)))
    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    # bucketing per 16 bit atas agar tidak O(n^2) penuh
    buckets = defaultdict(list)
    for i, (_, h) in enumerate(hashes):
        buckets[h >> 48].append(i)
    for idxs in buckets.values():
        for x in range(len(idxs)):
            i = idxs[x]
            for y in range(x + 1, len(idxs)):
                j = idxs[y]
                if _ham(hashes[i][1], hashes[j][1]) <= threshold:
                    ri, rj = find(i), find(j)
                    if ri != rj:
                        parent[rj] = ri
    groups = defaultdict(list)
    for i, (p, h) in enumerate(hashes):
        groups[find(i)].append((p, f"{h:016x}"))
    dup = sorted([g for g in groups.values() if len(g) > 1], key=lambda g: -len(g))
    return dup


def _llm_second_opinion(results, llm_max=20, model=None):
    """Minta LLM lokal untuk file bingung (confidence rendah). Override bila centroid lemah."""
    sys.path.insert(0, BASE)
    from app.ai import docai, llm
    from app.core import settings as settings_mod
    model = model or settings_mod.load(BASE).get("llm_model", llm.MODEL)
    st = settings_mod.load(BASE)
    cands = [r for r in results
             if r.get("status") == "ok" and r.get("confidence", 0) < 0.5
             and settings_mod.learn_allowed(r.get("path", ""), st)]
    cands.sort(key=lambda r: r.get("confidence", 0))
    cands = cands[:max(0, llm_max)]
    if not cands:
        return results
    print(f"LLM ({model}): second-opinion untuk {len(cands)} file...", flush=True)
    if not llm.ensure_server():
        print("LLM: server Ollama tidak bisa dinyalakan, lewati.", flush=True)
        return results
    if not llm.has_model(model):
        print(f"LLM: model {model} belum ada. Jalankan: ollama pull {model}", flush=True)
        return results
    for i, r in enumerate(cands, 1):
        try:
            text, info = docai.extract_text(r["path"])
        except Exception:
            text, info = "", "error"
        if info != "ok" or not text.strip():
            continue
        d = llm.analyze_doc(text, r["path"], model=model)
        if not d:
            continue
        r["llm_kategori"] = d.get("kategori", "")
        r["llm_ringkas"] = d.get("ringkasan", "")
        if r.get("confidence", 0) < 0.3 and d.get("kategori"):
            r["kategori"] = d["kategori"]
            r["saran_folder"] = d["kategori"]
            if d.get("nama"):
                r["saran_nama"] = d["nama"] + os.path.splitext(r["path"])[1].lower()
        print(f"  LLM {i}/{len(cands)}: {os.path.basename(r['path'])[:40]} -> "
              f"{r.get('llm_kategori')}", flush=True)
    return results


def run_analyze(target, out, args):
    """Mode analyze: pahami isi dokumen -> kategori + rekomendasi. Opsional --apply."""
    sys.path.insert(0, BASE)
    from app.ai import docai
    fb_path = os.path.join(out["reports"], "doc_feedback.json")
    results = docai.analyze_folder(target, out["root"], limit=args.limit,
                                   feedback_path=fb_path)
    if getattr(args, "llm", False):
        results = _llm_second_opinion(results, getattr(args, "llm_max", 20),
                                      getattr(args, "llm_model", None))
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    rep = os.path.join(out["reports"], f"doc_report_{stamp}.csv")
    with open(rep, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["path", "kategori", "confidence", "keywords",
                    "saran_folder", "saran_nama", "status", "near_dup_of",
                    "llm_kategori", "llm_ringkas"])
        for r in results:
            w.writerow([r["path"], r["kategori"], r["confidence"],
                        ";".join(r["keywords"]), r["saran_folder"],
                        r["saran_nama"], r["status"], r["near_dup_of"],
                        r.get("llm_kategori", ""), r.get("llm_ringkas", "")])
    print(f"Laporan: {rep}", flush=True)
    cats = defaultdict(int)
    for r in results:
        cats[r["kategori"]] += 1
    for c, n in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {c}: {n}", flush=True)
    near = sum(1 for r in results if r["near_dup_of"])
    if near:
        print(f"Near-duplicate teks: {near} file mirip isi", flush=True)
    if not args.apply:
        print("Mode analyze: tidak ada yang dipindah. Tambah --apply untuk menata.", flush=True)
        return
    do_copy = args.apply_copy or args.dry_run
    n = ggl = 0
    for r in results:
        if r["status"] != "ok":
            continue
        dest_dir = os.path.join(out["root"], "dokumen", r["saran_folder"])
        dest = os.path.join(dest_dir, r["saran_nama"])
        if os.path.abspath(dest).lower() == os.path.abspath(r["path"]).lower():
            continue
        if os.path.exists(dest):
            stem, ext = os.path.splitext(dest)
            i = 1
            while os.path.exists(f"{stem} ({i}){ext}"):
                i += 1
            dest = f"{stem} ({i}){ext}"
        if args.dry_run:
            print(f"RENCANA {r['path']} -> {dest}", flush=True)
            n += 1
            continue
        try:
            os.makedirs(dest_dir, exist_ok=True)
            if do_copy:
                shutil.copy2(r["path"], dest)
            else:
                ok, err = _move_with_permission_retry(r["path"], dest)
                if not ok:
                    raise OSError(err)
            print(f"{'COPY' if do_copy else 'PINDAH'} {r['path']} -> {dest}", flush=True)
            n += 1
        except Exception as e:
            print(f"GAGAL {r['path']}: {e}", flush=True)
            ggl += 1
    print(f"APPLY: {n} ok, {ggl} gagal -> {os.path.join(out['root'], 'dokumen')}", flush=True)


def size_groups(target, out=None):
    """Grup file berukuran SAMA PERSIS (tanpa hash). Untuk folder broken."""
    target = normalize_target(target)
    out = out or resolve_out(None)
    skip = {os.path.abspath(out["root"]) + os.sep}
    by_size = defaultdict(list)
    for dp, _, fn in os.walk(target):
        if (os.path.abspath(dp) + os.sep).startswith(tuple(skip)):
            continue
        for f in fn:
            p = os.path.join(dp, f)
            try:
                s = os.path.getsize(p)
            except OSError:
                continue
            if s:
                by_size[s].append(p)
    return sorted([sorted(v) for v in by_size.values() if len(v) > 1],
                  key=lambda v: (-len(v), v[0]))



MODES = ("scan", "karantina", "video-broken", "image-broken", "size", "analyze",
         "organize-videos", "organize-images", "yolo-classify")
MODE_DESCR = {
    "scan": "cari saja, aman (tidak pindah/hapus)",
    "karantina": "cari + PINDAH duplikat ke duplicate/ (sisakan 1)",
    "video-broken": "deteksi video rusak LIGHT/HEAVY via ffprobe",
    "image-broken": "deteksi gambar rusak LIGHT/HEAVY via PIL",
    "size": "grup ukuran SAMA PERSIS + PINDAH (khusus folder broken)",
    "analyze": "AI dokumen: pahami isi, kategori, rekomendasi nama/folder",
    "organize-videos": "rapikan video by metadata (ExifTool): Cameras/tanggal, screen-rec, manual content",
    "organize-images": "rapikan foto by metadata EXIF (ExifTool): Cameras/tipe, manual content",
    "yolo-classify": "klasifikasi isi gambar via ai-yolo-project (YOLO, opsional): prediksi + plan CSV, dry-run default",
}


def parse_args(argv):
    import argparse
    ap = argparse.ArgumentParser(prog="organizer.py",
                                 description="ai_organizer: duplikat + broken (lokal).")
    ap.add_argument("mode", nargs="?", choices=MODES, help="; ".join(f"{m}: {d}" for m, d in MODE_DESCR.items()))
    ap.add_argument("target", nargs="?", help="folder yang di-scan (terima D:\\x, D:/x, /d/x)")
    ap.add_argument("--out", default=None,
                    help="folder output (default: folder ai_organizer). Isi: duplicate/ broken/light|heavy/ laporan/")
    ap.add_argument("--mode", dest="dup_mode", default="exact", choices=["exact", "visual"],
                    help="exact: 100%% identik SHA256, cepat, tanpa salah tuduh. "
                         "visual: exact + mirip-visual dHash (lebih lambat, bisa false positive).")
    ap.add_argument("--visual-threshold", type=int, default=8,
                    help="jarak Hamming dHash 64-bit: 4 ketat, 8 normal, 12 longgar.")
    ap.add_argument("--broken-mode", default="copy", choices=["copy", "move"],
                    help="copy: original tetap (aman). move: original dipindah + verifikasi.")
    ap.add_argument("--dry-run", action="store_true",
                    help="tampilkan RENCANA saja tanpa pindah/copy/hapus.")
    ap.add_argument("--limit", type=int, default=0,
                    help="batasi jumlah file (uji coba / chunk resume). 0 = semua.")
    ap.add_argument("--apply", action="store_true",
                     help="(analyze/organize-videos/organize-images) eksekusi pemindahan sesuai rekomendasi/rencana.")
    ap.add_argument("--apply-copy", action="store_true",
                     help="(analyze/organize-videos/organize-images) copy saja, original tetap.")
    ap.add_argument("--llm", action="store_true",
                    help="(analyze) second-opinion + ringkasan via LLM lokal Qwen "
                         "(butuh Ollama + model qwen2.5:0.5b, ~5 dtk/file).")
    ap.add_argument("--llm-max", type=int, default=20,
                    help="(analyze) maks file dibantu LLM (prioritas confidence rendah).")
    ap.add_argument("--llm-model", default=None,
                    help="(analyze) model Ollama, mis qwen2.5:1.5b (default: pengaturan).")
    ap.add_argument("--daemon", action="store_true",
                    help="jalan di background: pantau folder + rekomendasi Explorer.")
    ap.add_argument("--install", action="store_true",
                    help="install: context-menu Explorer + startup + folder llm/models.")
    ap.add_argument("--uninstall", action="store_true",
                    help="lepas context-menu + startup (file hasil tidak dihapus).")
    ap.add_argument("--reason", default=None, metavar="PATH",
                    help="reasoning 1 file/folder (L1-L3 sesuai pengaturan).")
    ap.add_argument("--recommend", action="store_true",
                    help="tampilkan rekomendasi proaktif dari perilaku user.")
    ap.add_argument("--watch", default=None, metavar="DIR",
                     help="tambah folder ke daftar pantauan daemon.")
    ap.add_argument("--rename-dated", action="store_true",
                     help="(organize-videos/organize-images) namai file kamera YYYY-MM-DD_HHMMSS.ext.")
    ap.add_argument("--content", action="append", default=[],
                     metavar="POLA=>TUJUAN",
                     help="(organize-videos/organize-images) aturan manual Content, mis "
                          "'*liburan*=>YouTube/Raw'. Bisa diulang. TUJUAN relatif ke 03_Content/.")
    ap.add_argument("--content-map", default=None, metavar="JSON",
                     help="(organize-videos/organize-images) file JSON {pola: tujuan} untuk 03_Content/ (manual).")
    ap.add_argument("--to-delete-list", default=None, metavar="TXT",
                     help="(organize-videos/organize-images) file teks berisi daftar path (1/baris) "
                          "yang dipindah ke 99_To-Delete/. TIDAK PERNAH otomatis.")
    ap.add_argument("--exiftool", default=None, metavar="EXE",
                     help="(organize-videos/organize-images) path ExifTool bila tidak di PATH.")
    ap.add_argument("--file", action="append", default=[], metavar="PATH",
                     help="(organize-videos/organize-images) proses file ini saja. Bisa diulang.")
    ap.add_argument("--file-list", default=None, metavar="TXT",
                     help="(organize-videos/organize-images) file teks berisi daftar path (1/baris) "
                          "yang diproses. Tanpa ini = seluruh folder.")
    ap.add_argument("--dest-root", default=None, metavar="DIR",
                     help="(organize-videos/organize-images) folder tujuan. Default = path yang sama "
                          "dengan sumber. Struktur 00_/03_/04_/Cameras/99_ dibuat di sini.")
    ap.add_argument("--junk-to-delete", action="store_true",
                     help="(organize-videos/organize-images) pindahkan file NON-VIDEO tak berkepentingan "
                          "ke 99_To-Delete/. Tanpa ini hanya dicatat. TIDAK PERNAH hapus permanen.")
    ap.add_argument("--prune-empty", action="store_true",
                     help="(organize-videos/organize-images) hapus folder kosong sisa pemindahan "
                          "(hanya saat --apply tanpa --apply-copy).")
    ap.add_argument("--cameras-dir", default="Cameras", metavar="NAMA",
                     help="(organize-videos/organize-images) nama folder kamera tujuan "
                          "(mis. Pictures). Default: Cameras.")
    ap.add_argument("--yolo-model", default="", metavar="PT",
                     help="(yolo-classify) path best.pt kustom (default: MODEL di ai-yolo-project/config.py).")
    ap.add_argument("--yolo-conf", type=float, default=0.5,
                     help="(yolo-classify) confidence threshold prediksi (default 0.5).")
    return ap.parse_args(argv)


def _exe_for_integration():
    if getattr(sys, "frozen", False):
        return sys.executable
    return os.path.join(BASE, "organizer.py")


INSTALLED_MARKER = os.path.join("config", "installed.json")


def is_installed(app_base=None):
    return os.path.isfile(os.path.join(os.path.abspath(app_base or BASE), INSTALLED_MARKER))


def mark_installed(app_base, on=True):
    p = os.path.join(os.path.abspath(app_base or BASE), INSTALLED_MARKER)
    try:
        if on:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write('{"installed": true}\n')
        elif os.path.exists(p):
            os.remove(p)
    except OSError:
        pass


def do_install(args):
    from app.core import settings as settings_mod
    from app.core import bootstrap
    print("== INSTALL ai_organizer ==", flush=True)
    print(f"1. Library Python: {'OK' if bootstrap.ensure() else 'GAGAL (lihat atas)'}", flush=True)
    os.makedirs(os.path.join(BASE, "llm", "models"), exist_ok=True)
    from app.integrations import explorer
    exe = _exe_for_integration()
    ok, msg = explorer.install_context_menu(exe)
    print(f"2. Context-menu Explorer: {msg}", flush=True)
    ok, msg = explorer.set_startup(True, exe)
    print(f"3. Startup Windows: {msg}", flush=True)
    gui = [p for p in (os.path.join(os.path.dirname(exe), "ai_organizer-gui.exe"),
                       os.path.join(BASE, "ai_organizer-gui.exe")) if os.path.isfile(p)]
    icon = os.path.join(BASE, "icon.ico")
    ok, msg = explorer.create_desktop_shortcut(gui[0] if gui else exe, "ai_organizer",
                                               icon if os.path.isfile(icon) else "")
    print(f"4. Shortcut Desktop: {msg}", flush=True)
    st = settings_mod.load(BASE)
    st["startup"] = True
    settings_mod.save(BASE, st)
    mark_installed(BASE, True)
    print("4. Opsional (tidak otomatis):", flush=True)
    print("   - LLM Qwen: winget install Ollama.Ollama && ollama pull qwen2.5:0.5b", flush=True)
    print("   - FFmpeg: third_party/ffmpeg/bin sebelah aplikasi.", flush=True)
    print("SELESAI. Daemon aktif setelah restart / login berikutnya.", flush=True)


def do_uninstall():
    from app.integrations import explorer
    print("== UNINSTALL ai_organizer ==", flush=True)
    ok, msg = explorer.set_startup(False, "")
    print(f"1. Startup: {msg}", flush=True)
    ok, msg = explorer.remove_desktop_shortcut("ai_organizer")
    print(f"1b. Shortcut: {msg}", flush=True)
    ok, msg = explorer.uninstall_context_menu()
    print(f"2. Context-menu: {msg}", flush=True)
    print("3. File hasil (results/) TIDAK dihapus (aman).", flush=True)
    print("   Hapus manual folder aplikasi bila ingin bersih total.", flush=True)
    mark_installed(None, False)
    # 4. Cabut paket dependensi yang pernah di-download (pillow, watchdog).
    if getattr(sys, "frozen", False):
        print("4. Lewati: versi EXE tidak memakai pip (library sudah di dalam EXE).", flush=True)
        return
    try:
        from app.core.bootstrap import REQUIRED
        pkgs = sorted(set(REQUIRED.values()))
        print(f"4. Uninstall paket: {' '.join(pkgs)} ...", flush=True)
        r = subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", *pkgs],
                           capture_output=True, text=True, timeout=300)
        print(("OK" if r.returncode == 0 else "GAGAL") + ".", flush=True)
        if r.returncode != 0:
            print((r.stdout + r.stderr)[-500:], flush=True)
    except Exception as e:
        print(f"4. GAGAL uninstall paket: {e}", flush=True)


def do_reason(args):
    from app.core import settings as settings_mod
    from app.ai.reason import Reasoner
    st = settings_mod.load(BASE)
    rs = Reasoner(BASE, st)
    p = os.path.abspath(normalize_target(args.reason))
    results = rs.reason_folder(p) if os.path.isdir(p) else [rs.reason_file(p)]
    rs.save()
    for r in results[:50]:
        print(f"[{r.get('kategori')}|{r.get('confidence')}|L{r.get('level')}] "
              f"{r.get('aksi')} -> {r.get('saran_folder')} | {r['path']}", flush=True)
        for a in r.get("alasan", [])[:4]:
            print(f"    - {a}", flush=True)
    if len(results) > 50:
        print(f"... +{len(results) - 50} lagi", flush=True)


def _fix_console():
    """Paksa stdout/stderr tahan karakter non-latin (emoji/CJK di nama file).

    Console Windows default cp1252 membuat print() crash UnicodeEncodeError
    di tengah eksekusi (kasus: organize 35rb file). Dipanggil sekali di main().
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except Exception:
            pass


def main(argv=None):
    _fix_console()
    args = parse_args(argv or sys.argv[1:])
    from app.core import settings as settings_mod

    if args.install:
        return do_install(args)
    if args.uninstall:
        return do_uninstall()
    if args.watch:
        st = settings_mod.load(BASE)
        wl = st.get("watch_folders", [])
        w = os.path.abspath(normalize_target(args.watch))
        if w not in wl:
            wl.append(w)
            st["watch_folders"] = wl
            settings_mod.save(BASE, st)
        print(f"Watch list: {wl}", flush=True)
        return
    if args.daemon:
        from app.scripts import daemon
        return daemon.main(BASE)
    if args.reason:
        return do_reason(args)
    if args.recommend:
        from app.ai.behavior import Behavior
        from app.integrations.explorer import write_recommend_json
        from app.core import settings as settings_mod
        st = settings_mod.load(BASE)
        recs = [r for r in Behavior(BASE).recommend()
                if not r.get("path") or settings_mod.learn_allowed(r["path"], st)]
        for r in recs:
            print(f"[{r['kind']}] {r['text']}", flush=True)
        out = resolve_out(args.out)
        ensure_out(out)
        write_recommend_json(out["reports"], recs)
        return
    if not args.mode or not args.target:
        print("Pilih mode + target, atau --help. Contoh: organizer.py scan D:\\foto", flush=True)
        return
    target = normalize_target(args.target)
    if not os.path.isdir(target):
        print(f"Folder tidak ditemukan: {target}", flush=True)
        return
    out = resolve_out(args.out)
    ensure_out(out)
    print(f"OUT: {out['root']}", flush=True)

    try:
        with DirLock(out["root"]):
            run_with_out(args, target, out)
    except RuntimeError as e:
        print(f"ERROR: {e}", flush=True)
    except PermissionError as e:
        print(f"ERROR: akses ditolak: {e}", flush=True)


def run_with_out(args, target, out):
    mode = args.mode
    try:  # catat perilaku (non-fatal)
        from app.ai.behavior import Behavior
        Behavior(BASE).log(mode if mode else "run", target)
    except Exception:
        pass
    if mode in ("video-broken", "image-broken") and args.broken_mode == "move":
        require_admin_for_move()

    if mode == "video-broken":
        print(f"VIDEO BROKEN SCAN: {target}", flush=True)
        video_broken(target, out, args.broken_mode, args.dry_run,
                     getattr(args, "limit", 0))
        return
    if mode in ("organize-videos", "organize-images"):
        print(f"ORGANIZE {'VIDEOS' if mode == 'organize-videos' else 'IMAGES'}: {target}", flush=True)
        from app.ai import video_organize
        rules = []
        if args.content_map and os.path.isfile(args.content_map):
            try:
                with open(args.content_map, encoding="utf-8-sig") as f:
                    data = json.load(f)
                rules += [(str(k), str(v)) for k, v in data.items()]
            except Exception as e:
                print(f"content-map gagal dibaca: {e}", flush=True)
        for spec in (args.content or []):
            if "=>" in spec:
                pat, dest = spec.split("=>", 1)
                rules.append((pat.strip(), dest.strip()))
            else:
                print(f"aturan --content diabaikan (butuh '=>'): {spec}", flush=True)
        doomed = set()
        if args.to_delete_list and os.path.isfile(args.to_delete_list):
            with open(args.to_delete_list, encoding="utf-8-sig") as f:
                for line in f:
                    line = line.strip().strip('"')
                    if line:
                        doomed.add(line)
                        doomed.add(os.path.abspath(line))
        if args.to_delete_list and not os.path.isfile(args.to_delete_list):
            print(f"to-delete-list tidak ada: {args.to_delete_list}", flush=True)
        if not args.dry_run and args.apply:
            require_admin_for_move()
        only = list(args.file or [])
        if args.file_list and os.path.isfile(args.file_list):
            with open(args.file_list, encoding="utf-8-sig") as f:
                only += [ln.strip().strip('"') for ln in f if ln.strip()]
        if args.file_list and not os.path.isfile(args.file_list):
            print(f"file-list tidak ada: {args.file_list}", flush=True)
        if mode == "organize-videos":
            video_organize.organize_videos(
                target, out["reports"], apply=args.apply,
                apply_copy=args.apply_copy or args.dry_run,
                rename_dated=args.rename_dated, content_rules=rules,
                to_delete=doomed, exiftool=args.exiftool or "",
                limit=getattr(args, "limit", 0), dry_run=args.dry_run,
                only_files=only or None, dest_root=args.dest_root,
                junk_to_delete=args.junk_to_delete,
                prune_empty=args.prune_empty)
        else:
            from app.ai import image_organize
            image_organize.organize_images(
                target, out["reports"], apply=args.apply,
                apply_copy=args.apply_copy or args.dry_run,
                rename_dated=args.rename_dated, content_rules=rules,
                to_delete=doomed, exiftool=args.exiftool or "",
                limit=getattr(args, "limit", 0), dry_run=args.dry_run,
                only_files=only or None, dest_root=args.dest_root,
                junk_to_delete=args.junk_to_delete,
                prune_empty=args.prune_empty,
                cameras_top=args.cameras_dir or "Cameras")
        return
    if mode == "image-broken":
        print(f"IMAGE BROKEN SCAN: {target}", flush=True)
        image_broken(target, out, args.broken_mode, args.dry_run,
                     getattr(args, "limit", 0))
        return
    if mode == "analyze":
        print(f"ANALYZE DOKUMEN: {target}", flush=True)
        run_analyze(target, out, args)
        return
    if mode == "yolo-classify":
        print(f"YOLO CLASSIFY: {target}", flush=True)
        try:
            from app.ai import yolo_bridge
            ok, info = yolo_bridge.is_available()
            if not ok:
                print(f"YOLO tidak siap: {info.get('reason')}", flush=True)
                print("Tetap aman: tidak ada file dipindah. Lihat docs/YOLO_INTEGRATION.md", flush=True)
                return
            if not args.dry_run and args.apply:
                require_admin_for_move()
            yolo_bridge.run(
                target, out["reports"], apply=args.apply,
                apply_copy=args.apply_copy or args.dry_run,
                limit=getattr(args, "limit", 0),
                model=getattr(args, "yolo_model", "") or "",
                conf=getattr(args, "yolo_conf", 0.5) or 0.5,
                dest_root=args.dest_root)
        except RuntimeError as e:
            print(f"YOLO gagal: {e}", flush=True)
        except Exception as e:
            print(f"YOLO error tak terduga: {e}", flush=True)
        return
    if mode == "size":
        print(f"SIZE SCAN: {target}", flush=True)
        try:
            groups = size_groups(target, out)
        except FileNotFoundError as e:
            print(f"ERROR: {e}", flush=True)
            return
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        rep = os.path.join(out["reports"], f"size_{stamp}.csv")
        with open(rep, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["grup", "status", "size", "path"])
            for i, g in enumerate(groups, 1):
                s = os.path.getsize(g[0])
                w.writerow([i, "disimpan", s, g[0]])
                for p in g[1:]:
                    w.writerow([i, "duplikat-size", s, p])
        print(f"GRUP SIZE: {len(groups)} | terlibat: {sum(len(g) for g in groups)}", flush=True)
        print(f"Laporan: {rep}", flush=True)
        if args.dry_run:
            n = sum(len(g) - 1 for g in groups)
            print(f"RENCANA: {n} file akan dipindah ke {out['duplicate']}", flush=True)
            return
        require_admin_for_move()
        karantina([(0, g) for g in groups], out)
        return

    # scan / karantina (exact, opsional + visual)
    print(f"SCAN: {target} | dup_mode={args.dup_mode}", flush=True)
    try:
        groups, sizes = scan(target, out)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", flush=True)
        return
    except PermissionError as e:
        print(f"ERROR: akses ditolak: {e}", flush=True)
        return

    if args.dup_mode == "visual":
        hashes = scan_visual(target, out, args.visual_threshold)
        vdup = group_visual(hashes, args.visual_threshold)
        print(f"GRUP VISUAL: {len(vdup)} | terlibat: {sum(len(g) for g in vdup)}", flush=True)
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        rep = os.path.join(out["reports"], f"visual_{stamp}.csv")
        with open(rep, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["grup", "n", "phash", "path"])
            for gi, g in enumerate(vdup, 1):
                for p, h in g:
                    w.writerow([gi, len(g), h, p])
        print(f"Laporan visual: {rep}", flush=True)
        # gabung ke groups agar karantina memindahkan keduanya
        exact_paths = {p for _, g in groups for p in g}
        for g in vdup:
            paths = sorted([p for p, _ in g if p not in exact_paths],
                           key=lambda x: (len(x), x))
            if len(paths) > 1:
                groups.append((0, paths))

    report(groups, sizes, target, out)
    if mode == "karantina":
        if args.dry_run:
            karantina(groups, out, dry_run=True)
        else:
            require_admin_for_move()
            karantina(groups, out)
    else:
        print("Mode scan: tidak ada yang dipindah/dihapus.", flush=True)


if __name__ == "__main__":
    main()
