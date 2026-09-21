#!/usr/bin/env python3
"""sidecar.py — jembatan JSON engine-py untuk GUI non-Python / server Node.

Protokol: JSON per baris di stdin -> JSON per baris di stdout.
  {"id":1,"cmd":"ping"}
  {"id":2,"cmd":"engine","argv":["analyze","D:\\Data","--limit","5"]}
  {"id":3,"cmd":"recommend"}
  {"id":4,"cmd":"reason","path":"D:\\Data\\x.pdf"}

Respon: {"id":..,"ok":true,...}. Engine dipakai ulang 100% (kontrak AGENTS.md
tetap berlaku: dry-run, copy default, tanpa hapus). Hasil analyze CSV
di-mirror ke tabel doc_index terpadu agar GUI bisa baca dari satu DB.
"""
import csv
import glob
import io
import json
import os
import sys
import traceback

sys.dont_write_bytecode = True
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)


def _latest(pattern, folder):
    try:
        cands = glob.glob(os.path.join(folder, pattern))
        return max(cands, key=os.path.getmtime) if cands else ""
    except Exception:
        return ""


def _reports_dir(out_root):
    if out_root:
        return os.path.join(os.path.abspath(out_root), "results", "reports")
    return os.path.join(BASE, "results", "reports")


def _mirror_doc_csv(csv_path):
    """Mirror doc_report_*.csv -> tabel doc_index terpadu (best effort)."""
    try:
        from app.ai import unified
        with open(csv_path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                try:
                    unified.upsert_doc(
                        BASE, r.get("path", ""), r.get("kategori", ""),
                        float(r.get("confidence") or 0),
                        r.get("ringkasan", "") or r.get("summary", ""),
                        r.get("saran_nama", ""))
                except Exception:
                    continue
    except Exception:
        pass


def cmd_engine(argv):
    from app.core import engine
    import contextlib
    out_root = ""
    if "--out" in argv:
        i = argv.index("--out")
        if i + 1 < len(argv):
            out_root = argv[i + 1]
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            engine.main(list(argv))
        ok = True
    except SystemExit as e:
        ok = (e.code in (0, None))
    out = buf.getvalue()
    report = ""
    for line in out.splitlines():
        if "Laporan:" in line:
            report = line.split("Laporan:", 1)[1].strip()
    # mirror: behavior + doc_index
    try:
        from app.ai import unified
        mode = argv[0] if argv else ""
        src = argv[1] if len(argv) > 1 else ""
        unified.mirror_behavior(BASE, mode, src, report)
    except Exception:
        pass
    if (argv and argv[0] == "analyze") or "doc_report" in (report or ""):
        rep = report if os.path.isfile(report) else _latest(
            "doc_report_*.csv", _reports_dir(out_root))
        if rep and os.path.isfile(rep):
            _mirror_doc_csv(rep)
            report = rep
    return {"ok": ok, "output": out, "report": report}


def cmd_recommend():
    try:
        from app.ai import behavior
        recs = behavior.Behavior(BASE).recommend()
        return {"ok": True, "recommendations": recs}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def cmd_reason(path):
    try:
        from app.core import settings as settings_mod
        from app.ai import reason
        st = settings_mod.load(BASE)
        r = reason.Reasoner(BASE, st.get("reason_level", 2))
        info = r.explain(path)
        if isinstance(info, dict):
            return {"ok": True, "reason": info}
        return {"ok": True, "reason": {"text": str(info)}}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def cmd_docs(limit=200):
    """Baca doc_index terpadu (read-only) untuk GUI native / Node."""
    import sqlite3
    try:
        from app.ai import unified
        db = os.environ.get("AIORG_DB", "")
        if not db or db == ":memory:" or not os.path.isfile(db):
            return {"ok": False, "error": "db belum ada"}
        n = max(1, min(int(limit or 200), 500))
        c = sqlite3.connect("file:" + db + "?mode=ro", uri=True)
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT path,kategori,confidence,ringkasan,saran_nama"
            " FROM doc_index ORDER BY updated_ms DESC LIMIT ?", (n,)).fetchall()
        docs = [dict(r) for r in rows]
        c.close()
        return {"ok": True, "docs": docs}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def cmd_list_folders(root, limit=2000):
    """Daftar direktori nyata di bawah root beserta jumlah media aktual. Read-only."""
    try:
        from app.core.engine import VIDEO_EXTENSIONS, IMAGE_EXTENSIONS
    except Exception:
        VIDEO_EXTENSIONS = {".mp4", ".mov", ".mts", ".m2ts", ".mkv", ".avi", ".wmv", ".webm"}
        IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff", ".heic", ".heif"}
    try:
        root = os.path.abspath(root or "")
        if not os.path.isdir(root):
            return {"ok": False, "error": "folder tidak ada"}
        n = max(1, min(int(limit or 2000), 5000))
        folders = {}
        folders[root] = {"path": root, "rel": ".", "depth": 0, "videos": 0, "images": 0, "files": 0}
        for cur, dirs, names in os.walk(root):
            rel = os.path.relpath(cur, root)
            if rel == ".":
                folder_info = folders[root]
            else:
                folder_info = folders.setdefault(cur, {
                    "path": cur, "rel": rel.replace(os.sep, "/"),
                    "depth": rel.count(os.sep) + 1, "videos": 0, "images": 0, "files": 0
                })
            for nm in names:
                folder_info["files"] += 1
                ext = os.path.splitext(nm)[1].lower()
                if ext in VIDEO_EXTENSIONS:
                    folder_info["videos"] += 1
                elif ext in IMAGE_EXTENSIONS:
                    folder_info["images"] += 1
            for d in dirs:
                child = os.path.join(cur, d)
                rel_child = os.path.relpath(child, root)
                folders.setdefault(child, {
                    "path": child, "rel": rel_child.replace(os.sep, "/"),
                    "depth": rel_child.count(os.sep) + 1, "videos": 0, "images": 0, "files": 0
                })
        items = sorted(folders.values(), key=lambda x: (x["rel"].lower(), x["path"].lower()))
        return {"ok": True, "root": root, "folders": items[:n], "folder_total": len(items), "truncated": len(items) > n}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def cmd_list_videos(root, limit=2000, kind="videos"):
    """Daftar file media (+ hitung non-media) untuk selektor GUI. Read-only."""
    try:
        from app.core.engine import VIDEO_EXTENSIONS
        from app.ai.video_organize import TOP_DIRS
    except Exception:
        VIDEO_EXTENSIONS = {".mp4", ".mov", ".mts", ".m2ts", ".mkv", ".avi"}
        TOP_DIRS = ()
    try:
        from app.ai.image_organize import PHOTO_EXTENSIONS
    except Exception:
        PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp"}
    exts = PHOTO_EXTENSIONS if kind == "images" else VIDEO_EXTENSIONS
    try:
        root = os.path.abspath(root or "")
        if not os.path.isdir(root):
            return {"ok": False, "error": "folder tidak ada"}
        skip = set(TOP_DIRS)
        vids, junk_n, total, vtotal = [], 0, 0, 0
        n = max(1, min(int(limit or 2000), 5000))
        for cur, dirs, names in os.walk(root):
            dirs[:] = [d for d in dirs if d not in skip]
            for nm in sorted(names):
                p = os.path.join(cur, nm)
                total += 1
                if os.path.splitext(nm)[1].lower() in exts:
                    vtotal += 1
                    if len(vids) < n:
                        try:
                            vids.append({"path": p,
                                         "size": os.path.getsize(p),
                                         "rel": os.path.relpath(p, root).replace(os.sep, "/")})
                        except OSError:
                            vtotal -= 1
                else:
                    junk_n += 1
        return {"ok": True, "root": root, "videos": vids,
                "video_total": vtotal,
                "truncated": vtotal > len(vids), "junk_count": junk_n,
                "file_total": total}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _pro_root():
    return os.path.dirname(BASE)


def _annot_path():
    return os.path.join(_pro_root(), "data", "video-annotations.json")


def _read_annots():
    try:
        with open(_annot_path(), encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _write_annots(all_):
    try:
        os.makedirs(os.path.dirname(_annot_path()), exist_ok=True)
        with open(_annot_path(), "w", encoding="utf-8") as f:
            json.dump(all_, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _annot_keys(path):
    p = os.path.abspath(path)
    return [p, "\\\\?\\" + p]


def _annot_for(path):
    all_ = _read_annots()
    for k in _annot_keys(path):
        if k in all_:
            v = all_[k]
            return {"tags": v.get("tags", []), "note": v.get("note", "")}
    return {"tags": [], "note": ""}


def _migrate_annot(old, new):
    all_ = _read_annots()
    moved = False
    for k in _annot_keys(old):
        if k in all_:
            all_[os.path.abspath(new)] = all_.pop(k)
            moved = True
    if moved:
        _write_annots(all_)


def _checked(path):
    p = os.path.abspath((path or "").strip())
    if not os.path.isfile(p):
        raise RuntimeError("file video tidak ditemukan")
    return p


def _ffprobe():
    env = os.environ.get("AIORG_FFPROBE", "").strip()
    if env and os.path.isfile(env):
        return env
    cand = os.path.join(BASE, "app", "ffmpeg", "bin", "ffprobe.exe")
    return cand if os.path.isfile(cand) else "ffprobe"


def _file_contents_equal(a, b):
    try:
        if os.path.getsize(a) != os.path.getsize(b):
            return False
        with open(a, "rb") as fa, open(b, "rb") as fb:
            while True:
                ba, bb = fa.read(1024 * 1024), fb.read(1024 * 1024)
                if ba != bb:
                    return False
                if not ba:
                    return True
    except OSError:
        return False


def _move_verified(source, target, action):
    if os.path.exists(target):
        raise RuntimeError("file tujuan sudah ada")
    parent = os.path.dirname(target)
    if parent:
        os.makedirs(parent, exist_ok=True)
    old_key = os.path.abspath(source)
    try:
        os.rename(source, target)
        mode = "rename"
    except OSError:
        import shutil
        mode = "copy-verify-delete"
        shutil.copy2(source, target)
        if not _file_contents_equal(source, target):
            try:
                os.remove(target)
            except OSError:
                pass
            raise RuntimeError("verifikasi copy gagal: isi file tujuan berbeda")
        try:
            os.remove(source)
        except OSError as e:
            try:
                os.remove(target)
            except OSError:
                pass
            raise RuntimeError(f"copy sudah dibuat tetapi file sumber tidak dapat dihapus: {e}")
    _migrate_annot(old_key, target)
    return {"ok": True, "path": os.path.abspath(target), "mode": mode}


def cmd_file_info(path):
    try:
        p = _checked(path)
        st = os.stat(p)
        return {"ok": True, "path": p,
                "name": os.path.basename(p), "size": st.st_size,
                "modified_ms": int(st.st_mtime * 1000),
                "extension": os.path.splitext(p)[1][1:] or ""}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def cmd_video_inspect(path):
    try:
        p = _checked(path)
        st = os.stat(p)
        probe = {"ok": False, "error": "ffprobe tidak tersedia"}
        try:
            import subprocess
            r = subprocess.run(
                [_ffprobe(), "-v", "error", "-show_entries",
                 "format=duration:stream=codec_type,codec_name,profile,width,height,avg_frame_rate,display_aspect_ratio",
                 "-of", "json", p],
                capture_output=True, timeout=120,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if r.returncode == 0:
                raw = json.loads(r.stdout.decode("utf-8", "replace") or "{}")
                streams = raw.get("streams", []) or []
                vs = next((s for s in streams if s.get("codec_type") == "video"), None)
                au = next((s for s in streams if s.get("codec_type") == "audio"), None)
                fps = None
                if vs and isinstance(vs.get("avg_frame_rate"), str) and "/" in vs["avg_frame_rate"]:
                    try:
                        a, b = vs["avg_frame_rate"].split("/", 1)
                        a, b = float(a), float(b)
                        fps = round(a / b * 100) / 100 if b > 0 else None
                    except ValueError:
                        fps = None
                dur = None
                try:
                    dur = float((raw.get("format", {}) or {}).get("duration"))
                except (TypeError, ValueError):
                    dur = None
                probe = {"ok": vs is not None, "duration": dur,
                         "video": {"codec": (vs or {}).get("codec_name", "—"),
                                   "profile": (vs or {}).get("profile", "—"),
                                   "width": (vs or {}).get("width"),
                                   "height": (vs or {}).get("height"),
                                   "fps": fps,
                                   "aspect": (vs or {}).get("display_aspect_ratio", "—")},
                         "audio": {"codec": (au or {}).get("codec_name", "Tidak ada")}}
            else:
                probe = {"ok": False, "error": r.stderr.decode("utf-8", "replace").strip()}
        except FileNotFoundError:
            pass
        except Exception as e:
            probe = {"ok": False, "error": str(e)[:200]}
        return {"ok": True, "path": p, "name": os.path.basename(p),
                "size": st.st_size, "modified_ms": int(st.st_mtime * 1000),
                "extension": os.path.splitext(p)[1][1:] or "video",
                "probe": probe, "annotation": _annot_for(p)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def cmd_video_open(path):
    try:
        p = _checked(path)
        os.startfile(p)  # noqa: S606 — Windows, path terverifikasi isfile
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def cmd_video_folder(path):
    try:
        import subprocess
        p = _checked(path)
        subprocess.Popen(["explorer.exe", f"/select,{p}"])
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _valid_name(name):
    name = (name or "").strip()
    if not name or name in (".", ".."):
        return ""
    if any(ord(c) < 32 for c in name) or any(c in '\\/:*?"<>|' for c in name):
        return ""
    return name


def cmd_video_rename(path, new_name):
    try:
        src = _checked(path)
        name = _valid_name(new_name)
        if not name:
            return {"ok": False, "error": "nama file tidak valid"}
        if not os.path.splitext(name)[1]:
            ext = os.path.splitext(src)[1]
            name += ext
        target = os.path.join(os.path.dirname(src), name)
        if os.path.abspath(target) == src:
            return {"ok": True, "path": src}
        return _move_verified(src, target, "video-rename")
    except Exception as e:
        return {"ok": False, "error": str(e)}


def cmd_video_move(path, destination):
    try:
        src = _checked(path)
        dest = (destination or "").strip()
        if not dest:
            return {"ok": False, "error": "folder tujuan wajib diisi"}
        try:
            os.makedirs(dest, exist_ok=True)
        except OSError as e:
            return {"ok": False, "error": f"folder tujuan tidak bisa dibuat: {e}"}
        if not os.path.isdir(dest):
            return {"ok": False, "error": "tujuan bukan folder"}
        return _move_verified(src, os.path.join(os.path.abspath(dest), os.path.basename(src)), "video-move")
    except Exception as e:
        return {"ok": False, "error": str(e)}


def cmd_video_quarantine(path):
    try:
        src = _checked(path)
        folder = os.path.join(os.path.dirname(src), "99_To-Delete")
        os.makedirs(folder, exist_ok=True)
        stem, ext = os.path.splitext(os.path.basename(src))
        target = os.path.join(folder, os.path.basename(src))
        n = 1
        while os.path.exists(target):
            target = os.path.join(folder, f"{stem}-{n}{ext}")
            n += 1
        return _move_verified(src, target, "video-quarantine")
    except Exception as e:
        return {"ok": False, "error": str(e)}


def cmd_video_annotation(path, tags, note):
    try:
        p = _checked(path)
        clean = [str(t).strip() for t in (tags or []) if str(t).strip()][:50]
        all_ = _read_annots()
        all_[p] = {"tags": clean, "note": str(note or "")[:5000]}
        _write_annots(all_)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def cmd_video_dupcheck(path):
    """Cek duplikat exact (size -> SHA-256 penuh) dalam folder induk. Tanpa core/DB."""
    try:
        import hashlib
        p = _checked(path)
        parent = os.path.dirname(p)
        size = os.path.getsize(p)
        same_size = []
        for nm in os.listdir(parent):
            q = os.path.join(parent, nm)
            if os.path.isfile(q) and os.path.getsize(q) == size:
                same_size.append(q)
        if len(same_size) < 2:
            return {"ok": True, "duplicate": False, "group": None}
        h0 = hashlib.sha256()
        with open(p, "rb") as f:
            for ch in iter(lambda: f.read(4 * 1024 * 1024), b""):
                h0.update(ch)
        digest = h0.hexdigest()
        members = [p]
        for q in same_size:
            if os.path.abspath(q) == p:
                continue
            h = hashlib.sha256()
            try:
                with open(q, "rb") as f:
                    for ch in iter(lambda: f.read(4 * 1024 * 1024), b""):
                        h.update(ch)
            except OSError:
                continue
            if h.hexdigest() == digest:
                members.append(os.path.abspath(q))
        if len(members) > 1:
            return {"ok": True, "duplicate": True,
                    "group": {"id": 0, "size": size, "sha256": digest,
                              "paths": sorted(members)}}
        return {"ok": True, "duplicate": False, "group": None}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def cmd_yolo(root, limit=50, model=""):
    """Klasifikasi YOLO read-only (prediksi saja, tanpa pindah file)."""
    try:
        from app.ai import yolo_bridge
        ok, info = yolo_bridge.is_available()
        if not ok:
            return {"ok": False, "error": info.get("reason", "YOLO tidak siap")}
        rows, meta = yolo_bridge.classify_images(root, model=model or "", limit=int(limit or 50))
        return {"ok": True, "model": meta.get("model", ""), "rows": rows[:int(limit or 50)],
                "total": len(rows)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def handle(req):
    cmd = req.get("cmd", "")
    if cmd == "ping":
        return {"ok": True, "engine": "ai_organizer-py", "base": BASE}
    if cmd == "engine":
        return cmd_engine(req.get("argv", []))
    if cmd == "recommend":
        return cmd_recommend()
    if cmd == "reason":
        return cmd_reason(req.get("path", ""))
    if cmd == "docs":
        return cmd_docs(req.get("limit", 200))
    if cmd == "list-videos":
        return cmd_list_videos(req.get("root", ""), req.get("limit", 2000),
                               req.get("kind", "videos"))
    if cmd == "list-folders":
        return cmd_list_folders(req.get("root", ""), req.get("limit", 2000))
    if cmd == "file-info":
        return cmd_file_info(req.get("path", ""))
    if cmd == "video-inspect":
        return cmd_video_inspect(req.get("path", ""))
    if cmd == "video-open":
        return cmd_video_open(req.get("path", ""))
    if cmd == "video-folder":
        return cmd_video_folder(req.get("path", ""))
    if cmd == "video-rename":
        return cmd_video_rename(req.get("path", ""), req.get("new_name", ""))
    if cmd == "video-move":
        return cmd_video_move(req.get("path", ""), req.get("destination", ""))
    if cmd == "video-quarantine":
        return cmd_video_quarantine(req.get("path", ""))
    if cmd == "video-annotation":
        return cmd_video_annotation(req.get("path", ""), req.get("tags", []),
                                    req.get("note", ""))
    if cmd == "video-duplicate-check":
        return cmd_video_dupcheck(req.get("path", ""))
    if cmd == "yolo-classify":
        return cmd_yolo(req.get("root", ""), req.get("limit", 50),
                        req.get("model", ""))
    return {"ok": False, "error": f"cmd tidak dikenal: {cmd}"}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            sys.stdout.write(json.dumps({"id": 0, "ok": False,
                                         "error": "bukan JSON"}) + "\n")
            sys.stdout.flush()
            continue
        try:
            res = handle(req)
        except Exception:
            res = {"ok": False, "error": traceback.format_exc(limit=3)}
        res["id"] = req.get("id", 0)
        sys.stdout.write(json.dumps(res, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
