#!/usr/bin/env python3
"""ai/video_organize.py — rapikan koleksi video by metadata (ExifTool utama).

Struktur tujuan (default di path yang sama; bisa --dest-root lain):
  00_Uncategorized/ | 03_Content/<manual>/ | 04_Screen-Recordings/<sub>/
  Cameras/<Tipe-Perangkat>/ (Model dulu: iPhone 12, Realme 6, HDR-XR150E;
  fallback Maker bila model kosong; Unknown bila tak ada info)
  | 99_To-Delete/ (HANYA via daftar manual atau --junk-to-delete)

Aturan:
- Kamera dari metadata (Make/Model/CameraModelName), BUKAN nama file.
- Screen recording hanya bila Software/Encoder/Title/Comment kuat, else Other/Uncategorized.
- 03_Content HANYA via aturan manual user (--content / --content-map).
- 99_To-Delete HANYA via --to-delete-list / --junk-to-delete. TIDAK PERNAH hapus permanen.
- Seleksi file: --file / --file-list (default: seluruh folder).
- Default simulasi (dry-run): cetak RENCANA + tulis plan CSV. --apply mengeksekusi
  dengan pindah-terverifikasi (atau copy via --apply-copy).
- Stdlib saja (ExifTool/ffprobe dipanggil sebagai subprocess eksternal).
"""
import csv
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime

sys.dont_write_bytecode = True

TOP_DIRS = ("00_Uncategorized", "03_Content", "04_Screen-Recordings",
            "Cameras", "99_To-Delete")

EXIF_TAGS = ["Make", "Model", "CameraModelName", "DateTimeOriginal",
             "CreateDate", "CreationTime", "MediaCreateDate",
             "FileModifyDate", "Duration", "ImageWidth", "ImageHeight",
             "VideoFrameRate", "VideoCodec", "Encoder", "Software",
             "HandlerDescription", "Title", "Comment", "Description",
             "WritingApplication", "EncodedBy"]

MAKERS = {
    "SONY": "Sony", "CANON": "Canon", "NIKON": "Nikon",
    "PANASONIC": "Panasonic", "FUJIFILM": "Fujifilm", "FUJI": "Fujifilm",
    "DJI": "DJI", "SAMSUNG": "Samsung", "APPLE": "Apple",
    "XIAOMI": "Xiaomi", "HUAWEI": "Huawei", "OPPO": "Oppo",
    "VIVO": "Vivo", "ONEPLUS": "OnePlus", "GOPRO": "GoPro",
    "BLACKMAGIC": "Blackmagic", "BLACKMAGICDESIGN": "Blackmagic",
    "INSTA360": "Insta360", "RICOH": "Ricoh", "OLYMPUS": "OM System",
    "OM SYSTEM": "OM System", "LEICA": "Leica", "HASSELBLAD": "Hasselblad",
    "REALME": "Realme", "INFINIX": "Infinix", "HONOR": "Honor",
    "MOTOROLA": "Motorola", "MOTO": "Motorola", "NOKIA": "Nokia",
    "ASUS": "Asus", "LENOVO": "Lenovo", "TECNO": "Tecno",
}

SCREEN_SOFTWARE = [
    "obs", "streamlabs", "xsplit", "xbox game bar", "game bar", "game dvr",
    "shadowplay", "nvidia share", "geforce experience", "amd relive",
    "radeon relive", "bandicam", "camtasia", "sharex", "flashback",
    "loom", "mirillis action", "fraps", "dxtory", " Debut Video Capture".lower(),
]
SCREEN_TITLE_KW = ["screen recording", "screen record", "display capture",
                   "screen capture", "perekaman layar", "tangkapan layar"]
GAMING_KW = ["game", "gaming", "gameplay", "shadowplay", "relive", "fraps",
             "xbox", "gta", "minecraft", "valorant", "genshin", "mlbb",
             "mobile legend", "pubg", "free fire", "roblox"]
TUTORIAL_KW = ["tutorial", "course", "lesson", "belajar", "panduan",
               "how to", "cara ", "pelatihan", "kuliah", "materi"]
CODING_KW = ["code", "coding", "vscode", "visual studio", "terminal",
             "programming", "github", "python", "javascript", "ngoding",
             "program"]

_DATE_RE = re.compile(r"(\d{4})[:\-](\d{2})[:\-](\d{2})[ T](\d{2}):(\d{2}):(\d{2})")
_BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Kode model -> nama produk kanonis (UPPER_SNAKE). Contoh: RMX2001 = Realme 6.
MODEL_ALIASES = {
    "RMX2001": "REALME_6",
    "RMX2002": "REALME_NARZO",
    "22081283G": "REDMI_PAD",
    "M2003J15SC": "REDMI_NOTE_9",
}


def canon_folder(name, maker=""):
    """Nama folder kanonis: UPPER_SNAKE; contoh Apple -> IPHONE_7_PLUS.

    Awalan merek dibuang khusus Apple (iPhone_*), produk lain pakai nama penuh.
    """
    u = re.sub(r"\s+", "_", (name or "").strip().upper())
    if maker.upper() == "APPLE" and u.startswith("APPLE_"):
        u = u[len("APPLE_"):]
    return u or "UNKNOWN"


def sanitize(name, default="Unknown"):
    s = _BAD_CHARS.sub("_", (name or "").strip()).strip().strip(".")
    s = re.sub(r"\s+", " ", s)
    return s[:80] if s else default


def find_exiftool(explicit=None):
    cands = []
    if explicit:
        cands.append(explicit)
    cands.append(os.environ.get("AIORG_EXIFTOOL", ""))
    cands.append(os.path.join(os.environ.get("LOCALAPPDATA", ""),
                              "Programs", "ExifTool", "ExifTool.exe"))
    cands.append("C:/Program Files/ExifTool/exiftool.exe")
    cands.append("exiftool")
    for c in cands:
        if not c:
            continue
        if os.path.isfile(c):
            return c
        hit = shutil.which(c)
        if hit:
            return hit
    return ""


def find_ffprobe():
    try:
        from app.core.engine import _find_ffprobe
        return _find_ffprobe() or ""
    except Exception:
        return shutil.which("ffprobe") or ""


def _get(d, *keys):
    for k in keys:
        v = d.get(k)
        if v is None or (isinstance(v, str) and not v.strip()):
            continue
        return v
    return ""


def exif_batch(exiftool, paths):
    """Satu proses ExifTool untuk banyak file -> {abspath: tags}."""
    out = {}
    if not exiftool or not paths:
        return out
    for i in range(0, len(paths), 100):
        chunk = paths[i:i + 100]
        cmd = [exiftool, "-j", "-fast2", "-charset", "filename=UTF8",
               *["-" + t for t in EXIF_TAGS], *chunk]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True,
                               errors="replace", timeout=300,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            arr = json.loads(p.stdout or "[]")
            for row in arr:
                src = row.get("SourceFile", "")
                if src:
                    out[os.path.abspath(src)] = row
        except Exception:
            continue
    return out


def ffprobe_meta(ffprobe, path):
    """Fallback bila ExifTool tak ada: tag dasar via ffprobe JSON."""
    try:
        p = subprocess.run(
            [ffprobe, "-v", "quiet", "-show_format", "-show_streams",
             "-of", "json", path],
            capture_output=True, text=True, errors="replace", timeout=60,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        data = json.loads(p.stdout or "{}")
    except Exception:
        return {}
    fmt = data.get("format", {}) or {}
    tags = fmt.get("tags", {}) or {}
    streams = [s for s in (data.get("streams") or []) if s.get("codec_type") == "video"]
    v0 = streams[0] if streams else {}
    low = {str(k).lower(): v for k, v in tags.items()}
    return {
        "Make": low.get("com.apple.quicktime.make", ""),
        "Model": low.get("com.apple.quicktime.model", ""),
        "CreateDate": tags.get("creation_time", ""),
        "Duration": fmt.get("duration", ""),
        "ImageWidth": v0.get("width", ""),
        "ImageHeight": v0.get("height", ""),
        "VideoFrameRate": v0.get("avg_frame_rate", "") or v0.get("r_frame_rate", ""),
        "VideoCodec": v0.get("codec_name", ""),
        "Encoder": tags.get("encoder", ""),
        "Software": low.get("com.apple.quicktime.software", ""),
        "Title": tags.get("title", ""),
        "Comment": tags.get("comment", ""),
    }


def norm_maker(raw):
    s = (raw or "").strip()
    if not s:
        return ""
    key = re.sub(r"[^A-Z0-9]", "", s.upper())
    if key in MAKERS:
        return MAKERS[key]
    if s.upper() in MAKERS:
        return MAKERS[s.upper()]
    return ""  # maker tak dikenal -> Unknown (jangan karang)


def parse_date(s):
    if not s:
        return None
    m = _DATE_RE.search(str(s))
    if not m:
        return None
    try:
        return (m.group(1), m.group(2), m.group(3),
                m.group(4) + m.group(5) + m.group(6))
    except Exception:
        return None


def file_date(path, meta):
    for k in ("DateTimeOriginal", "CreateDate", "CreationTime",
              "MediaCreateDate"):
        d = parse_date(_get(meta, k))
        if d:
            return d, k
    try:
        ts = datetime.fromtimestamp(os.path.getmtime(path))
        return ((f"{ts.year:04d}", f"{ts.month:02d}", f"{ts.day:02d}",
                 f"{ts.hour:02d}{ts.minute:02d}{ts.second:02d}"), "FileModifyDate")
    except OSError:
        return None, ""


def _contains(hay, needles):
    h = (hay or "").lower()
    return [n for n in needles if n in h]


def detect_screen(meta):
    """Return (is_screen, sub) — konservatif: bukti lemah -> (False, '')."""
    soft = " ".join(str(_get(meta, k)) for k in
                    ("Software", "Encoder", "WritingApplication", "EncodedBy",
                     "HandlerDescription", "Comment", "Title", "Description"))
    low = soft.lower()
    if _contains(low, SCREEN_SOFTWARE):
        sub = "Other"
        blob = low
        if _contains(blob, GAMING_KW):
            sub = "Gaming"
        elif _contains(blob, TUTORIAL_KW):
            sub = "Tutorials"
        elif _contains(blob, CODING_KW):
            sub = "Coding"
        return True, sub
    title_blob = " ".join(str(_get(meta, k)) for k in ("Title", "Comment", "Description")).lower()
    if _contains(title_blob, SCREEN_TITLE_KW):
        return True, "Other"
    return False, ""


def match_rules(rel_posix, base_posix, rules):
    """rules: [(pattern, dest)] — cocokkan pola ke path relatif/nama file."""
    name = rel_posix.rsplit("/", 1)[-1]
    for pat, dest in rules:
        p = pat.strip().lower()
        if not p:
            continue
        if (fnmatch.fnmatch(rel_posix.lower(), p) or fnmatch.fnmatch(name.lower(), p)
                or p in rel_posix.lower() or p in name.lower()):
            return dest
    return ""


def plan(root, meta_map, content_rules, to_delete, rename_dated,
         only_files=None, dest_root=None, junk_to_delete=False,
         junk_files=None):
    """Susun rencana [(src, dest_rel, decision, reason, maker, model, datestr)].

    dest_rel relatif ke dest_root (default = root = path yang sama).
    dest_rel "" = hanya dicatat, tidak dieksekusi (junk tanpa --junk-to-delete).
    """
    root = os.path.abspath(root)
    dest_root = os.path.abspath(dest_root) if dest_root else root
    plans = []
    try:
        from app.core.engine import VIDEO_EXTENSIONS
    except Exception:
        VIDEO_EXTENSIONS = {".mp4", ".mov", ".mts", ".m2ts", ".mkv", ".avi"}
    if only_files is not None:
        files = sorted({os.path.abspath(f) for f in only_files
                        if os.path.splitext(f)[1].lower() in VIDEO_EXTENSIONS})
    else:
        skip = set(TOP_DIRS)
        files = []
        for cur, dirs, names in os.walk(root):
            dirs[:] = [d for d in dirs if d not in skip]
            for n in names:
                if os.path.splitext(n)[1].lower() in VIDEO_EXTENSIONS:
                    files.append(os.path.join(cur, n))
        files.sort()
    for src in files:
        rel = os.path.relpath(src, root).replace(os.sep, "/")
        meta = meta_map.get(os.path.abspath(src), {})
        maker = norm_maker(_get(meta, "Make"))
        model = sanitize(_get(meta, "Model", "CameraModelName"), "")
        (dated, date_src) = file_date(src, meta)
        y, m = (dated[0], dated[1]) if dated else ("", "")

        dest = match_rules(rel, "", content_rules)
        if dest:
            decision, reason = ("content", f"aturan manual '{dest}' cocok")
            dest_rel = "03_Content/" + dest.strip("/ ") + "/" + os.path.basename(src)
            plans.append((src, dest_rel, decision, reason, maker, model, _ds(dated)))
            continue
        if os.path.abspath(src) in to_delete or rel in to_delete or os.path.basename(src) in to_delete:
            plans.append((src, "99_To-Delete/" + os.path.basename(src),
                          "to-delete", "daftar manual user", maker, model, _ds(dated)))
            continue
        is_screen, sub = detect_screen(meta)
        if is_screen:
            plans.append((src, f"04_Screen-Recordings/{sub}/" + os.path.basename(src),
                          "screen", f"screen recording ({sub})", maker, model, _ds(dated)))
            continue
        if model:
            # Langsung tipe perangkat (IPHONE_7_PLUS, REALME_6, ...) —
            # tanpa level merek. Maker hanya fallback bila model kosong.
            leaf = _dated_name(src, dated) if (rename_dated and dated) else os.path.basename(src)
            folder = canon_folder(MODEL_ALIASES.get(
                re.sub(r"[^A-Z0-9]", "", model.upper()), model), maker)
            dest_rel = f"Cameras/{folder}/{leaf}"
            tag = f"{maker}/{model}" if maker else model
            plans.append((src, dest_rel, "camera",
                          f"{tag}" + (f" {date_src}" if dated and date_src != "FileModifyDate" else " (tanggal file)"),
                          maker, model, _ds(dated)))
            continue
        if maker:
            leaf = _dated_name(src, dated) if (rename_dated and dated) else os.path.basename(src)
            dest_rel = f"Cameras/{canon_folder(maker)}/{leaf}"
            plans.append((src, dest_rel, "camera",
                          f"{maker}/Unknown-Model" + (f" {date_src}" if dated and date_src != "FileModifyDate" else " (tanggal file)"),
                          maker, "Unknown-Model", _ds(dated)))
            continue
        if dated:
            leaf = _dated_name(src, dated) if rename_dated else os.path.basename(src)
            plans.append((src, f"Cameras/Unknown/{leaf}", "unknown-cam",
                          "maker tak dikenal, tanggal ada", "", "", _ds(dated)))
            continue
        plans.append((src, "00_Uncategorized/" + os.path.basename(src),
                      "uncategorized", "metadata tak cukup", "", "", ""))
    # file non-video (tak berkepentingan): catat; pindah HANYA via --junk-to-delete
    for src in sorted(junk_files or []):
        if junk_to_delete:
            plans.append((src, "99_To-Delete/" + os.path.basename(src),
                          "junk", "file non-video -> 99_To-Delete", "", "", ""))
        else:
            plans.append((src, "",
                          "junk", "file non-video (tambah --junk-to-delete untuk pindah ke 99_To-Delete)",
                          "", "", ""))
    return plans


def _ds(dated):
    return f"{dated[0]}-{dated[1]}-{dated[2]} {dated[3][:2]}:{dated[3][2:4]}:{dated[3][4:6]}" if dated else ""


def _dated_name(src, dated):
    ext = os.path.splitext(src)[1].lower()
    return f"{dated[0]}-{dated[1]}-{dated[2]}_{dated[3]}{ext}"


def unique_dest(dest_root, dest_rel):
    dest = os.path.join(dest_root, *dest_rel.split("/"))
    if not os.path.exists(dest):
        return dest
    stem, ext = os.path.splitext(dest)
    i = 1
    while True:
        cand = f"{stem} ({i}){ext}"
        if not os.path.exists(cand):
            return cand
        i += 1


def execute(plans, dest_root, apply_copy=False):
    """Eksekusi rencana. Return (ok, gagal, lewati). Pakai kontrak engine (verify)."""
    from app.core.engine import _move_with_permission_retry
    import shutil
    ok = gagal = lewati = 0
    for src, dest_rel, decision, reason, maker, model, datestr in plans:
        if not dest_rel:
            print(f"LEWATI {src} ({reason})", flush=True)
            lewati += 1
            continue
        dest = unique_dest(dest_root, dest_rel)
        if os.path.abspath(dest).lower() == os.path.abspath(src).lower():
            continue
        try:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            if apply_copy:
                shutil.copy2(src, dest)
                assert os.path.exists(dest) and os.path.getsize(dest) == os.path.getsize(src)
                print(f"COPY {src} -> {dest}", flush=True)
            else:
                good, err = _move_with_permission_retry(src, dest)
                if not good:
                    raise OSError(err)
                assert not os.path.exists(src) and os.path.exists(dest)
                print(f"PINDAH {src} -> {dest}", flush=True)
            ok += 1
        except Exception as e:
            print(f"GAGAL {src}: {e}", flush=True)
            gagal += 1
    return ok, gagal, lewati


def prune_empty_dirs(root, protected=()):
    """Hapus folder kosong sisa pemindahan (tidak pernah hapus root/terlindungi)."""
    n = 0
    root = os.path.abspath(root)
    prot = {os.path.abspath(p) for p in protected}
    for cur, dirs, names in os.walk(root, topdown=False):
        here = os.path.abspath(cur)
        if here == root:
            continue
        if any(here == p or here.startswith(p + os.sep) for p in prot):
            continue
        try:
            if not os.listdir(cur):
                os.rmdir(cur)
                print(f"HAPUS folder kosong: {cur}", flush=True)
                n += 1
        except OSError:
            pass
    return n


def organize_videos(root, out_reports="", apply=False, apply_copy=False,
                    rename_dated=False, content_rules=None, to_delete=None,
                    exiftool="", limit=0, dry_run=True, only_files=None,
                    dest_root=None, junk_to_delete=False, prune_empty=False):
    """Entry utama. dry_run (default) = RENCANA + plan CSV saja.

    only_files: proses file itu saja (seleksi user). None = seluruh folder.
    dest_root: folder tujuan (default = root = path yang sama).
    """
    from app.core.engine import VIDEO_EXTENSIONS
    root = os.path.abspath(root)
    if not os.path.isdir(root):
        print(f"Folder tidak ditemukan: {root}", flush=True)
        return []
    dest_root = os.path.abspath(dest_root) if dest_root else root
    # lindungi folder laporan/lock bila --out ada di dalam root
    protected = set()
    if out_reports:
        d = os.path.abspath(out_reports)
        while d.startswith(root + os.sep) or d == root:
            protected.add(d)
            if d == root:
                break
            d = os.path.dirname(d)
    # kumpulkan file dulu (agar ExifTool batch efisien)
    skip = set(TOP_DIRS)
    same_tree = (dest_root == root or
                 dest_root.startswith(root + os.sep))
    files, junk = [], []
    if only_files:
        skipped = 0
        for f in only_files:
            p = os.path.abspath(f)
            if not os.path.isfile(p):
                print(f"LEWATI (tak ada): {f}", flush=True)
                skipped += 1
                continue
            (files if os.path.splitext(p)[1].lower() in VIDEO_EXTENSIONS
             else junk).append(p)
        if skipped:
            print(f"Dilewati (bukan file): {skipped}", flush=True)
    else:
        for cur, dirs, names in os.walk(root):
            dirs[:] = [d for d in dirs
                       if (d not in skip or not same_tree)
                       and os.path.abspath(os.path.join(cur, d)) not in protected]
            for n in names:
                if n == ".ai_organizer.lock":
                    continue
                p = os.path.join(cur, n)
                if os.path.abspath(p) in protected:
                    continue
                (files if os.path.splitext(n)[1].lower() in VIDEO_EXTENSIONS
                 else junk).append(p)
    files.sort()
    junk.sort()
    if limit and limit > 0:
        files = files[:limit]
        print(f"CHUNK LIMIT: {limit}", flush=True)
    print(f"ORGANIZE VIDEO: {root} | {len(files)} video, {len(junk)} non-video"
          f" | tujuan: {dest_root}", flush=True)

    ex = find_exiftool(exiftool)
    ff = "" if ex else find_ffprobe()
    print(f"Metadata: {'ExifTool ' + ex if ex else ('ffprobe ' + ff if ff else 'TIDAK ADA (fallback nama?)')}", flush=True)
    meta_map = exif_batch(ex, files) if ex else {}
    if not ex and ff:
        for i, p in enumerate(files):
            if i % 50 == 0:
                print(f"PROGRESS meta: {i}/{len(files)}", flush=True)
            meta_map[os.path.abspath(p)] = ffprobe_meta(ff, p)
    if not ex and not ff:
        print("ERROR: ExifTool maupun ffprobe tidak ditemukan.", flush=True)
        return []

    plans = plan(root, meta_map, content_rules or [], to_delete or set(),
                 rename_dated, only_files=files, dest_root=dest_root,
                 junk_to_delete=junk_to_delete, junk_files=junk)
    by = {}
    for pl in plans:
        by[pl[2]] = by.get(pl[2], 0) + 1
    print("RENCANA: " + ", ".join(f"{k}={v}" for k, v in sorted(by.items())), flush=True)
    for src, dest_rel, decision, reason, maker, model, datestr in plans[:30]:
        print(f"  [{decision}] {os.path.basename(src)} -> {dest_rel} ({reason})", flush=True)
    if len(plans) > 30:
        print(f"  ... +{len(plans) - 30} lagi (lihat plan CSV)", flush=True)

    if out_reports:
        os.makedirs(out_reports, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        csv_path = os.path.join(out_reports, f"organize_plan_{stamp}.csv")
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["path", "decision", "dest", "dest_root", "maker",
                        "model", "date", "reason"])
            for src, dest_rel, decision, reason, maker, model, datestr in plans:
                w.writerow([src, decision, dest_rel, dest_root, maker,
                            model, datestr, reason])
        print(f"Plan CSV: {csv_path}", flush=True)

    if dry_run or not apply:
        print("DRY-RUN: tidak ada file dipindah. Ulangi dengan --apply untuk eksekusi.", flush=True)
        return plans
    ok, gagal, lewati = execute(plans, dest_root, apply_copy)
    if prune_empty and not apply_copy:
        n = prune_empty_dirs(root, protected)
        print(f"Folder kosong dihapus: {n}", flush=True)
    print(f"SELESAI: {ok} ok, {gagal} gagal, {lewati} dilewati", flush=True)
    return plans
