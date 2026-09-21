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
        db = unified.unified_db_path(BASE)
        if not db or not os.path.isfile(db):
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
