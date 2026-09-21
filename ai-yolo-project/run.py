#!/usr/bin/env python3
"""run.py — SATU perintah untuk memakai model: prediksi + sortir + laporan.

    python run.py <folder-sumber> [--model <best.pt>] [--plot]

  Hasil di results/ :
    sorted/high/<kelas>/, sorted/medium/<kelas>/, sorted/low/<kelas>/
    errors/ (file rusak), predictions/ (gambar anotasi, bila --plot),
    report_<waktu>.txt + report_<waktu>.csv
  Semua pengaturan ada di config.py.
"""
import csv
import shutil
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from tqdm import tqdm
from ultralytics import YOLO

import config as C


def parse_args():
    src, model, plot, ensemble = None, str(C.MODEL), False, C.USE_ENSEMBLE
    for a in sys.argv[1:]:
        if a == "--plot":
            plot = True
        elif a == "--single":
            ensemble = False
        elif a == "--ensemble":
            ensemble = True
        elif a.startswith("--model="):
            model = a.split("=", 1)[1]
            ensemble = False
        elif src is None:
            src = a
    if src is None:
        print("Pakai: python run.py <folder-sumber> [--model=<best.pt>] [--plot] [--single|--ensemble]")
        print(f"Default: ensemble={C.USE_ENSEMBLE} | MODEL tunggal: {C.MODEL}")
        sys.exit(1)
    return Path(src), model, plot, ensemble


def is_valid(p):
    try:
        with Image.open(p) as im:
            im.verify()
        return True
    except (UnidentifiedImageError, OSError, ValueError):
        return False


def unique(path):
    path = Path(path)
    if not path.exists():
        return path
    i = 1
    while True:
        cand = path.with_name(f"{path.stem}_dup{i}{path.suffix}")
        if not cand.exists():
            return cand
        i += 1


def load_models(single_path, ensemble):
    """Kembalikan (predict_fn, label). predict_fn(img) -> (kelas, conf)."""
    if ensemble and C.ENSEMBLE_MODELS:
        paths = [str(p) for p in C.ENSEMBLE_MODELS]
        weights = list(C.ENSEMBLE_WEIGHTS) or [1.0] * len(paths)
        models = [YOLO(p) for p in paths]
        def vote(img):
            scores = {}
            for m, w in zip(models, weights):
                r = m.predict(str(img), imgsz=C.IMGSZ, conf=C.PRED_CONF,
                              verbose=False)[0]
                for i, prob in enumerate(r.probs.data.tolist()):
                    cls = r.names[i]
                    scores[cls] = scores.get(cls, 0.0) + prob * w
            name = max(scores, key=scores.get)
            return name, scores[name] / sum(weights)
        return vote, f"ensemble:{len(models)}-model"
    m = YOLO(single_path)
    if C.USE_TTA:
        from PIL import Image as _I
        def tta(img):
            scores = {}
            variants = []
            base = _I.open(img).convert("RGB")
            for sz in C.TTA_IMGSZ:
                v = base.resize((sz, sz))
                variants.append(v)
                variants.append(v.transpose(_I.FLIP_LEFT_RIGHT))
            for v in variants:
                r = m.predict(v, imgsz=C.IMGSZ, conf=C.PRED_CONF,
                              verbose=False)[0]
                for i, prob in enumerate(r.probs.data.tolist()):
                    cls = r.names[i]
                    scores[cls] = scores.get(cls, 0.0) + prob
            base.close()
            name = max(scores, key=scores.get)
            return name, scores[name] / len(variants)
        return tta, f"single+TTA:{Path(single_path).parent.name}"
    def one(img):
        r = m.predict(str(img), imgsz=C.IMGSZ, conf=C.PRED_CONF,
                      verbose=False)[0]
        return r.names[r.probs.top1], float(r.probs.top1conf)
    return one, f"single:{Path(single_path).parent.name}"


def main():
    src, model_path, plot, ensemble = parse_args()
    if ensemble:
        if not C.ENSEMBLE_MODELS:
            print("ENSEMBLE_MODELS kosong di config -> fallback model tunggal.")
            ensemble = False
        else:
            missing = [str(p) for p in C.ENSEMBLE_MODELS if not Path(p).exists()]
            if missing:
                print(f"Model ensemble hilang: {missing}\nPakai --single atau cek config.")
                sys.exit(1)
    if not ensemble and not Path(model_path).exists():
        print(f"Model tidak ada: {model_path}\nJalankan dulu: python train.py")
        sys.exit(1)

    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out = C.RESULTS
    sorted_dir = out / "sorted"
    err_dir = out / "errors"
    plot_dir = out / "predictions"

    files = [p for p in sorted(src.rglob("*.*")) if p.is_file()]
    predict, label = load_models(model_path, ensemble)
    print(f"[INFO] {len(files)} file | {label}", flush=True)
    plot_model = None
    if plot:
        plot_model = YOLO(model_path) if not ensemble else YOLO(str(C.ENSEMBLE_MODELS[0]))

    stats = {"high": 0, "medium": 0, "low": 0, "error": 0}
    per_class = {}
    rows = []

    for img in tqdm(files, desc="Predicting", unit="img"):
        if not is_valid(img):
            shutil.move(str(img), str(unique(err_dir / img.name)))
            stats["error"] += 1
            rows.append([str(img), "error", "", "invalid-image"])
            continue
        try:
            name, conf = predict(img)
        except Exception as e:
            shutil.move(str(img), str(unique(err_dir / img.name)))
            stats["error"] += 1
            rows.append([str(img), "error", "", f"predict-fail: {e}"[:80]])
            continue

        per_class[name] = per_class.get(name, 0) + 1
        level = "high" if conf >= C.HIGH_TH else ("low" if conf < C.LOW_TH else "medium")
        stats[level] += 1
        dest = unique(sorted_dir / level / name / img.name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if plot:
            Path(plot_dir / name).mkdir(parents=True, exist_ok=True)
            rr = plot_model.predict(str(img), imgsz=C.IMGSZ, conf=C.PRED_CONF,
                                    verbose=False)[0]
            rr.save(str(unique(plot_dir / name / img.name)))
        shutil.move(str(img), str(dest))
        rows.append([str(img), level, name, round(conf, 4)])

    txt = out / f"report_{stamp}.txt"
    txt.write_text(
        f"RUN REPORT {stamp}\nmodel: {label}\n"
        f"total: {len(files)}\nhigh: {stats['high']} | "
        f"medium: {stats['medium']} | low: {stats['low']} | "
        f"error: {stats['error']}\n\nper kelas:\n" +
        "".join(f"- {k}: {v}\n" for k, v in sorted(per_class.items())))
    with open(out / f"report_{stamp}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["file", "level", "kelas", "confidence"])
        w.writerows(rows)

    print(f"\nSELESAI. high={stats['high']} medium={stats['medium']} "
          f"low={stats['low']} error={stats['error']}")
    print(f"Laporan: {txt}")


if __name__ == "__main__":
    main()
