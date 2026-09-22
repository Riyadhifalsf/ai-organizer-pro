#!/usr/bin/env python3
"""ai/image_organize.py — rapikan koleksi foto by metadata EXIF (ExifTool utama).

Mirror dari video_organize.py untuk file gambar. Struktur tujuan (flat per tipe):
  00_Uncategorized/ | 03_Content/<manual>/
  Cameras/<Tipe-Model-dulu>/ (mis. Cameras/iPhone 12/, fallback Maker, lalu Unknown)
  | 99_To-Delete/ (HANYA via daftar manual atau --junk-to-delete)

Aturan:
- Kamera dari EXIF (Make/Model), BUKAN nama file.
- Tanggal: DateTimeOriginal > CreateDate > CreationTime > MediaCreateDate > mtime.
- 03_Content HANYA via aturan manual user (--content / --content-map).
- 99_To-Delete HANYA via --to-delete-list / --junk-to-delete. TIDAK PERNAH hapus permanen.
- Seleksi file: --file / --file-list (default: seluruh folder).
- Default simulasi (dry-run): cetak RENCANA + tulis plan CSV. --apply mengeksekusi
  dengan pindah-terverifikasi (atau copy via --apply-copy).
- Stdlib saja (ExifTool dipanggil sebagai subprocess eksternal).
"""
import csv
import os
import re
import subprocess
import sys
from datetime import datetime

sys.dont_write_bytecode = True

from app.ai.video_organize import (
    TOP_DIRS, MAKERS, MODEL_ALIASES, sanitize, find_exiftool, _get,
    parse_date, norm_maker, file_date, match_rules, unique_dest, execute,
    prune_empty_dirs, canon_folder,
)

PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp",
                    ".bmp", ".gif", ".tiff", ".tif", ".livp", ".dng", ".rw2",
                    ".cr2", ".cr3", ".nef", ".arw", ".orf"}

PHOTO_TAGS = ["Make", "Model", "DateTimeOriginal", "CreateDate",
              "CreationTime", "MediaCreateDate", "FileModifyDate",
              "ImageWidth", "ImageHeight", "Software", "ExposureTime",
              "ISO", "FNumber", "GPSLatitude", "GPSLongitude"]


def exif_batch_photo(exiftool, paths):
    """Satu proses ExifTool untuk banyak file -> {abspath: tags}."""
    out = {}
    if not exiftool or not paths:
        return out
    import json
    for i in range(0, len(paths), 100):
        chunk = paths[i:i + 100]
        cmd = [exiftool, "-j", "-fast2", "-charset", "filename=UTF8",
               *["-" + t for t in PHOTO_TAGS], *chunk]
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


def plan_images(root, meta_map, content_rules, to_delete, rename_dated,
                only_files=None, dest_root=None, junk_to_delete=False,
                junk_files=None, cameras_top="Cameras"):
    """Susun rencana [(src, dest_rel, decision, reason, maker, model, datestr)]."""
    from app.ai.video_organize import _ds, _dated_name
    root = os.path.abspath(root)
    dest_root = os.path.abspath(dest_root) if dest_root else root
    plans = []
    if only_files is not None:
        files = sorted({os.path.abspath(f) for f in only_files
                        if os.path.splitext(f)[1].lower() in PHOTO_EXTENSIONS})
    else:
        skip = set(TOP_DIRS)
        files = []
        for cur, dirs, names in os.walk(root):
            dirs[:] = [d for d in dirs if d not in skip]
            for n in names:
                if os.path.splitext(n)[1].lower() in PHOTO_EXTENSIONS:
                    files.append(os.path.join(cur, n))
        files.sort()
    for src in files:
        rel = os.path.relpath(src, root).replace(os.sep, "/")
        meta = meta_map.get(os.path.abspath(src), {})
        maker = norm_maker(_get(meta, "Make"))
        model = sanitize(_get(meta, "Model"), "")
        (dated, date_src) = file_date(src, meta)

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
        if model:
            # Langsung tipe perangkat, tanpa level merek.
            leaf = _dated_name(src, dated) if (rename_dated and dated) else os.path.basename(src)
            folder = canon_folder(MODEL_ALIASES.get(
                re.sub(r"[^A-Z0-9]", "", model.upper()), model), maker)
            dest_rel = f"{cameras_top}/{folder}/{leaf}"
            tag = f"{maker}/{model}" if maker else model
            plans.append((src, dest_rel, "camera",
                          f"{tag}" + (f" {date_src}" if dated and date_src != "FileModifyDate" else " (tanggal file)"),
                          maker, model, _ds(dated)))
            continue
        if maker:
            leaf = _dated_name(src, dated) if (rename_dated and dated) else os.path.basename(src)
            dest_rel = f"{cameras_top}/{canon_folder(maker)}/{leaf}"
            plans.append((src, dest_rel, "camera",
                          f"{maker}/Unknown-Model" + (f" {date_src}" if dated and date_src != "FileModifyDate" else " (tanggal file)"),
                          maker, "Unknown-Model", _ds(dated)))
            continue
        plans.append((src, "00_Uncategorized/" + os.path.basename(src),
                      "uncategorized", "metadata tak cukup", "", "", _ds(dated) if dated else ""))
        # Tambahan: yang PUNYA tanggal dikelompokkan ke subfolder YYYY-MM
        # by metadata tanggal (tetap di bawah 00_Uncategorized/).
        if dated:
            leaf = _dated_name(src, dated) if rename_dated else os.path.basename(src)
            plans[-1] = (src, f"00_Uncategorized/{dated[0]}-{dated[1]}/{leaf}",
                         "uncategorized", f"metadata tak cukup (tanggal {date_src})",
                         "", "", _ds(dated))
    for src in sorted(junk_files or []):
        if junk_to_delete:
            plans.append((src, "99_To-Delete/" + os.path.basename(src),
                          "junk", "file non-foto -> 99_To-Delete", "", "", ""))
        else:
            plans.append((src, "",
                          "junk", "file non-foto (tambah --junk-to-delete untuk pindah ke 99_To-Delete)",
                          "", "", ""))
    return plans


def organize_images(root, out_reports="", apply=False, apply_copy=False,
                    rename_dated=False, content_rules=None, to_delete=None,
                    exiftool="", limit=0, dry_run=True, only_files=None,
                    dest_root=None, junk_to_delete=False, prune_empty=False,
                    cameras_top="Cameras"):
    """Entry utama. dry_run (default) = RENCANA + plan CSV saja."""
    root = os.path.abspath(root)
    if not os.path.isdir(root):
        print(f"Folder tidak ditemukan: {root}", flush=True)
        return []
    dest_root = os.path.abspath(dest_root) if dest_root else root
    protected = set()
    if out_reports:
        d = os.path.abspath(out_reports)
        while d.startswith(root + os.sep) or d == root:
            protected.add(d)
            if d == root:
                break
            d = os.path.dirname(d)
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
            (files if os.path.splitext(p)[1].lower() in PHOTO_EXTENSIONS
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
                (files if os.path.splitext(n)[1].lower() in PHOTO_EXTENSIONS
                 else junk).append(p)
    files.sort()
    junk.sort()
    if limit and limit > 0:
        files = files[:limit]
        print(f"CHUNK LIMIT: {limit}", flush=True)
    print(f"ORGANIZE FOTO: {root} | {len(files)} foto, {len(junk)} non-foto"
          f" | tujuan: {dest_root}", flush=True)

    ex = find_exiftool(exiftool)
    if not ex:
        print("ERROR: ExifTool tidak ditemukan (butuh untuk metadata EXIF).", flush=True)
        return []
    print(f"Metadata: ExifTool {ex}", flush=True)
    meta_map = exif_batch_photo(ex, files)

    plans = plan_images(root, meta_map, content_rules or [], to_delete or set(),
                        rename_dated, only_files=files, dest_root=dest_root,
                        junk_to_delete=junk_to_delete, junk_files=junk,
                        cameras_top=cameras_top)
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
        csv_path = os.path.join(out_reports, f"organize_img_plan_{stamp}.csv")
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            import csv as _csv
            w = _csv.writer(f)
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
