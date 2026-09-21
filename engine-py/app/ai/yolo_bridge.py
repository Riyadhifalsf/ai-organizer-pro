#!/usr/bin/env python3
"""ai/yolo_bridge.py — jembatan organizer -> ai-yolo-project TANPA merusak YOLO.

Prinsip:
- ai-yolo-project adalah kanonis: TIDAK dipindah, TIDAK diubah, TIDAK diimpor
  secara destruktif. Semua akses lewat path + lazy import.
- ultralytics/YOLO bersifat opsional: bila belum install / model belum ada,
  fungsi mengembalikan status jelas, engine tetap jalan.
- Kontrak aman organizer berlaku: default dry-run (prediksi + plan CSV saja).
  Pemindahan file HANYA bila apply=True, dengan verifikasi + nama unik,
  TIDAK PERNAH hapus permanen.

Pakai:
    from app.ai import yolo_bridge as yb
    yb.is_available()          # (ok, info)
    yb.classify_images(folder) # list dict prediksi
    yb.run(target, out_reports, apply=False, ...)
"""

import csv
import os
import sys
from datetime import datetime

sys.dont_write_bytecode = True

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff", ".tif"}


def project_root():
    """Lokasi ai-yolo-project. Bisa dioverride via env AIORG_YOLO_PROJECT."""
    env = os.environ.get("AIORG_YOLO_PROJECT", "").strip()
    if env and os.path.isdir(env):
        return os.path.abspath(env)
    here = os.path.dirname(os.path.abspath(__file__))  # .../engine-py/app/ai
    app_dir = os.path.dirname(here)                     # .../engine-py/app
    engine_py = os.path.dirname(app_dir)                # .../engine-py
    pro_root = os.path.dirname(engine_py)               # .../ai-organizer-pro
    cand = os.path.join(pro_root, "ai-yolo-project")
    if os.path.isdir(cand):
        return os.path.abspath(cand)
    return ""


def _load_config():
    """Baca config.py YOLO tanpa mengimpor ultralytics. Return dict + path."""
    root = project_root()
    if not root:
        return {}, ""
    cfg_path = os.path.join(root, "config.py")
    info = {"project": root, "config": cfg_path}
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("aiyolo_config", cfg_path)
        mod = importlib.util.module_from_spec(spec)
        # config.py hanya pakai pathlib -> aman diimpor
        spec.loader.exec_module(mod)
        for k in ("MODEL", "BEST_PT", "HIGH_TH", "LOW_TH", "PRED_CONF",
                  "IMGSZ", "USE_TTA", "TTA_IMGSZ", "RESULTS"):
            if hasattr(mod, k):
                v = getattr(mod, k)
                info[k] = str(v) if k in ("MODEL", "BEST_PT", "RESULTS") else v
    except Exception as e:
        info["config_error"] = str(e)
    return info, root


def is_available():
    """Cek kesiapan YOLO: (ok: bool, info: dict). Tidak raise."""
    info, root = _load_config()
    if not root:
        return False, {"reason": "ai-yolo-project tidak ditemukan"}
    try:
        import importlib.util
        if importlib.util.find_spec("ultralytics") is None:
            info["reason"] = "ultralytics belum install (python setup.py --install di ai-yolo-project)"
            return False, info
    except Exception as e:
        return False, {"reason": f"cek ultralytics gagal: {e}"}
    model = info.get("MODEL", "")
    if not model or not os.path.isfile(model):
        info["reason"] = f"model tidak ada: {model} (jalankan train.py dulu di ai-yolo-project)"
        return False, info
    return True, info


def get_model_path(override=""):
    if override and os.path.isfile(override):
        return os.path.abspath(override)
    info, _ = _load_config()
    m = info.get("MODEL", "")
    return os.path.abspath(m) if m else ""


def _iter_images(target, limit=0):
    target = os.path.abspath(target)
    files = []
    for cur, dirs, names in os.walk(target):
        # jangan scan output YOLO sendiri bila target == project
        dirs[:] = [d for d in dirs if d not in ("runs", "results", "dataset", "__pycache__")]
        for n in sorted(names):
            if os.path.splitext(n)[1].lower() in IMG_EXTS:
                files.append(os.path.join(cur, n))
    files.sort()
    if limit and limit > 0:
        files = files[:limit]
    return files


def classify_images(target, model="", limit=0, conf=0.5):
    """Prediksi saja (tanpa pindah file). Return (rows, info).

    rows: [{path, kelas, confidence, level}] — level ikut HIGH_TH/LOW_TH config.
    Melempar RuntimeError bila YOLO/model tak siap (ditangkap caller).
    """
    from PIL import Image
    ok, info = is_available()
    if not ok:
        raise RuntimeError(info.get("reason", "YOLO tidak siap"))
    model_path = get_model_path(model)
    if not model_path or not os.path.isfile(model_path):
        raise RuntimeError(f"model tidak ada: {model_path}")

    from ultralytics import YOLO
    m = YOLO(model_path)
    high_th = float(info.get("HIGH_TH", 0.90) or 0.90)
    low_th = float(info.get("LOW_TH", 0.80) or 0.80)
    imgsz = int(info.get("IMGSZ", 288) or 288)

    rows = []
    for p in _iter_images(target, limit):
        try:
            with Image.open(p) as im:
                im.verify()
        except Exception:
            rows.append({"path": p, "kelas": "error", "confidence": 0.0,
                         "level": "error", "note": "invalid-image"})
            continue
        try:
            r = m.predict(p, imgsz=imgsz, conf=conf, verbose=False)[0]
            name = r.names[r.probs.top1]
            c = float(r.probs.top1conf)
            level = "high" if c >= high_th else ("low" if c < low_th else "medium")
            rows.append({"path": p, "kelas": name, "confidence": round(c, 4),
                         "level": level, "note": ""})
        except Exception as e:
            rows.append({"path": p, "kelas": "error", "confidence": 0.0,
                         "level": "error", "note": f"predict-fail: {e}"[:80]})
    return rows, {"model": model_path, **info}


def _unique(path):
    from pathlib import Path
    p = Path(path)
    if not p.exists():
        return str(p)
    i = 1
    while True:
        cand = p.with_name(f"{p.stem}_dup{i}{p.suffix}")
        if not cand.exists():
            return str(cand)
        i += 1


def run(target, out_reports="", apply=False, apply_copy=False, limit=0,
        model="", conf=0.5, dest_root=""):
    """Entry organizer: dry-run default. Return rows.

    - Selalu tulis plan CSV ke out_reports (yolo_plan_<stamp>.csv).
    - Bila apply: pindah (atau copy) ke <dest_root|target>/YOLO/<level>/<kelas>/.
    """
    target = os.path.abspath(target)
    if not os.path.isdir(target):
        print(f"Folder tidak ditemukan: {target}", flush=True)
        return []
    rows, info = classify_images(target, model=model, limit=limit, conf=conf)
    print(f"YOLO CLASSIFY: {target} | {len(rows)} gambar | model: {info.get('model')}", flush=True)
    by = {}
    for r in rows:
        by[r["level"]] = by.get(r["level"], 0) + 1
    print("RENCANA: " + ", ".join(f"{k}={v}" for k, v in sorted(by.items())), flush=True)
    for r in rows[:20]:
        print(f"  [{r['level']}] {os.path.basename(r['path'])} -> {r['kelas']} ({r['confidence']})",
              flush=True)
    if len(rows) > 20:
        print(f"  ... +{len(rows) - 20} lagi (lihat plan CSV)", flush=True)

    if out_reports:
        os.makedirs(out_reports, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        csv_path = os.path.join(out_reports, f"yolo_plan_{stamp}.csv")
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["path", "level", "kelas", "confidence", "dest", "note"])
            for r in rows:
                dest = f"YOLO/{r['level']}/{r['kelas']}/{os.path.basename(r['path'])}" \
                    if r["level"] != "error" else ""
                w.writerow([r["path"], r["level"], r["kelas"],
                            r["confidence"], dest, r.get("note", "")])
        print(f"Plan CSV: {csv_path}", flush=True)

    if not apply:
        print("DRY-RUN: tidak ada file dipindah. Ulangi dengan --apply untuk eksekusi.", flush=True)
        return rows

    import shutil
    dest_base = os.path.abspath(dest_root) if dest_root else target
    ok, gagal = 0, 0
    for r in rows:
        if r["level"] == "error":
            continue
        src = r["path"]
        rel = f"YOLO/{r['level']}/{r['kelas']}/{os.path.basename(src)}"
        dst = _unique(os.path.join(dest_base, *rel.split("/")))
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if apply_copy:
                shutil.copy2(src, dst)
            else:
                shutil.copy2(src, dst)
                # pindah-terverifikasi: hapus sumber hanya bila copy identik
                with open(src, "rb") as a, open(dst, "rb") as b:
                    same = (os.path.getsize(src) == os.path.getsize(dst)
                            and a.read(1024 * 1024) == b.read(1024 * 1024))
                if same:
                    os.remove(src)
                else:
                    print(f"GAGAL verifikasi: {src}", flush=True)
                    gagal += 1
                    continue
            ok += 1
        except Exception as e:
            print(f"GAGAL: {src}: {e}", flush=True)
            gagal += 1
    print(f"SELESAI YOLO: {ok} ok, {gagal} gagal", flush=True)
    return rows
