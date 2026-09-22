#!/usr/bin/env python3
"""sidecar.py â€” jembatan JSON AI untuk aplikasi Qt (QProcess persisten).

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
    """Baca doc_index JSON (read-only) untuk aplikasi Qt."""
    try:
        from app.ai import unified
        docs = unified.read_docs(BASE, limit)
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
                         "video": {"codec": (vs or {}).get("codec_name", "â€”"),
                                   "profile": (vs or {}).get("profile", "â€”"),
                                   "width": (vs or {}).get("width"),
                                   "height": (vs or {}).get("height"),
                                   "fps": fps,
                                   "aspect": (vs or {}).get("display_aspect_ratio", "â€”")},
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
        os.startfile(p)  # noqa: S606 â€” Windows, path terverifikasi isfile
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
        parent = os.path.dirname(src)
        if os.path.basename(parent) == "99_To-Delete":
            return {"ok": True, "path": src, "mode": "already-quarantined"}
        folder = os.path.join(parent, "99_To-Delete")
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


# ---------- YOLO training dari aplikasi (detached, log ke file) ----------
def _train_pid_path(project):
    return os.path.join(project, "results", ".train_app.json")


def _pid_alive(pid):
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong(0)
        alive = k32.GetExitCodeProcess(h, ctypes.byref(code)) and code.value == 259
        k32.CloseHandle(h)
        return bool(alive)
    except Exception:
        try:
            import subprocess
            r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                               capture_output=True, text=True, timeout=15)
            return str(pid) in (r.stdout or "")
        except Exception:
            return False


def _train_state(project):
    try:
        with open(_train_pid_path(project), encoding="utf-8") as f:
            st = json.load(f)
    except Exception:
        return {"running": False}
    pid = st.get("pid")
    if _pid_alive(pid):
        st["running"] = True
        return st
    return {"running": False, "last_pid": pid, "last_params": st.get("params", {})}


def cmd_yolo_status():
    try:
        from app.ai import yolo_bridge
        project = yolo_bridge.project_root()
        if not project:
            return {"ok": False, "error": "folder app/ai/yolo tidak ditemukan"}
        ok, info = yolo_bridge.is_available()
        raw = os.path.join(project, "dataset_raw")
        classes = {}
        if os.path.isdir(raw):
            for nm in sorted(os.listdir(raw)):
                d = os.path.join(raw, nm)
                if os.path.isdir(d):
                    try:
                        classes[nm] = sum(1 for f in os.listdir(d)
                                          if os.path.isfile(os.path.join(d, f)))
                    except OSError:
                        classes[nm] = 0
        return {"ok": True, "project": project,
                "ready": bool(ok), "ready_note": "" if ok else info.get("reason", ""),
                "model": info.get("MODEL", ""),
                "classes": classes, "class_total": sum(classes.values()),
                "train": _train_state(project)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def cmd_yolo_train_start(epochs=150, batch=16, model_size="m", imgsz=288, patience=25):
    try:
        from app.ai import yolo_bridge
        project = yolo_bridge.project_root()
        if not project:
            return {"ok": False, "error": "folder app/ai/yolo tidak ditemukan"}
        try:
            import ultralytics  # noqa: F401 â€” wajib ada sebelum spawn
        except ImportError:
            return {"ok": False,
                    "error": "ultralytics belum install. Jalankan: pip install ultralytics"}
        st = _train_state(project)
        if st.get("running"):
            return {"ok": False, "error": f"training sudah berjalan (pid {st.get('pid')})"}
        try:
            epochs = max(1, min(int(epochs or 150), 2000))
            batch = max(1, min(int(batch or 16), 512))
            patience = max(0, min(int(patience or 0), 500))
            imgsz = max(64, min(int(imgsz or 288), 1280))
        except (TypeError, ValueError):
            return {"ok": False, "error": "parameter angka tidak valid"}
        model_size = str(model_size or "m").lower().strip()
        if model_size not in ("n", "s", "m", "l", "x"):
            return {"ok": False, "error": "model_size harus salah satu: n/s/m/l/x"}
        raw = os.path.join(project, "dataset_raw")
        n_img = 0
        if os.path.isdir(raw):
            for _, _, files in os.walk(raw):
                n_img += len(files)
        if n_img == 0:
            return {"ok": False,
                    "error": "dataset_raw kosong â€” isi dulu tiap kelas dengan foto (lihat config.py)"}
        import subprocess
        # train.py tidak terima argumen: override konstanta config via wrapper,
        # tanpa mengubah file YOLO mana pun.
        wrapper = (
            "import runpy, sys; "
            f"sys.path.insert(0, {project!r}); "
            "import config as C; "
            f"C.EPOCHS={epochs}; C.BATCH={batch}; "
            f"C.MODEL_SIZE={model_size!r}; C.IMGSZ={imgsz}; C.PATIENCE={patience}; "
            f"runpy.run_path({os.path.join(project, 'train.py')!r}, run_name='__main__')"
        )
        os.makedirs(os.path.join(project, "results"), exist_ok=True)
        log_path = os.path.join(project, "results", "train_app.log")
        log_f = open(log_path, "a", encoding="utf-8", errors="replace")
        log_f.write(f"\n===== TRAIN DIMULAI epochs={epochs} batch={batch} "
                    f"model={model_size} imgsz={imgsz} patience={patience} =====\n")
        log_f.flush()
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(
            subprocess, "DETACHED_PROCESS", 0)
        proc = subprocess.Popen(
            [sys.executable, "-u", "-c", wrapper], cwd=project,
            stdout=log_f, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, creationflags=flags, close_fds=True)
        log_f.close()
        params = {"epochs": epochs, "batch": batch, "model_size": model_size,
                  "imgsz": imgsz, "patience": patience}
        try:
            with open(_train_pid_path(project), "w", encoding="utf-8") as f:
                import time
                json.dump({"pid": proc.pid, "started": int(time.time()),
                           "params": params}, f)
        except OSError:
            pass
        return {"ok": True, "pid": proc.pid, "params": params, "log": log_path}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def cmd_yolo_train_status():
    try:
        from app.ai import yolo_bridge
        project = yolo_bridge.project_root()
        if not project:
            return {"ok": False, "error": "folder app/ai/yolo tidak ditemukan"}
        st = _train_state(project)
        tail = []
        log_path = os.path.join(project, "results", "train_app.log")
        try:
            with open(log_path, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            tail = [ln.rstrip("\n") for ln in lines[-40:]]
        except OSError:
            pass
        st.update({"ok": True, "log": log_path, "log_tail": tail})
        return st
    except Exception as e:
        return {"ok": False, "error": str(e)}


def cmd_yolo_train_stop():
    try:
        from app.ai import yolo_bridge
        project = yolo_bridge.project_root()
        if not project:
            return {"ok": False, "error": "folder app/ai/yolo tidak ditemukan"}
        st = _train_state(project)
        if not st.get("running"):
            try:
                os.remove(_train_pid_path(project))
            except OSError:
                pass
            return {"ok": True, "stopped": False, "note": "tidak ada training berjalan"}
        import subprocess
        subprocess.run(["taskkill", "/PID", str(st["pid"]), "/T", "/F"],
                       capture_output=True, timeout=30)
        try:
            os.remove(_train_pid_path(project))
        except OSError:
            pass
        try:
            with open(os.path.join(project, "results", "train_app.log"),
                      "a", encoding="utf-8") as f:
                f.write("===== TRAIN DIHENTIKAN DARI APLIKASI =====\n")
        except OSError:
            pass
        return {"ok": True, "stopped": True, "pid": st["pid"]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def cmd_job(action, job_id=0, kind="", payload="", status="", result="",
              limit=50):
    """Antrean JSON (app/ai/jobs.py). Bentuk mirror perintah core."""
    try:
        from app.ai import jobs as J
        if action == "enqueue":
            return J.enqueue(BASE, kind, payload)
        if action == "claim":
            return J.claim(BASE)
        if action == "finish":
            return J.finish(BASE, job_id, status, result)
        if action == "list":
            return J.list_jobs(BASE, status, limit)
        if action in ("pause", "resume", "cancel"):
            return J.set_status(BASE, job_id, action)
        if action == "run-once":
            def _engine(argv):
                r = cmd_engine(argv)
                r["ok"] = bool(r.get("ok"))
                return r
            return J.run_once(BASE, _engine)
        return {"ok": False, "error": f"aksi job tak dikenal: {action}"}
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
    if cmd == "yolo-status":
        return cmd_yolo_status()
    if cmd == "yolo-train-start":
        return cmd_yolo_train_start(req.get("epochs", 150), req.get("batch", 16),
                                    req.get("model_size", "m"), req.get("imgsz", 288),
                                    req.get("patience", 25))
    if cmd == "yolo-train-status":
        return cmd_yolo_train_status()
    if cmd == "yolo-train-stop":
        return cmd_yolo_train_stop()
    if cmd == "job":
        return cmd_job(req.get("action", ""), req.get("id", 0),
                       req.get("kind", ""), req.get("payload", ""),
                       req.get("status", ""), req.get("result", ""),
                       req.get("limit", 50))
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
