#!/usr/bin/env python3
"""train.py — SATU perintah untuk melatih: clean -> split -> train -> evaluasi.

    python train.py

  Hasil: results/best.pt, results/training_log.csv, errors/, dataset/
  Semua pengaturan ada di config.py.
"""
import csv
import hashlib
import os
import random
import shutil
import sys

import cv2
from PIL import Image
from ultralytics import YOLO

import config as C

IMG_EXTS = (".jpg", ".jpeg", ".png")


def log(msg):
    print(msg, flush=True)


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read(1024 * 1024))
    return h.hexdigest()


def is_broken(path):
    """True jika file rusak/kecil/blur (tidak pernah menghapus, hanya tandai)."""
    try:
        with Image.open(path) as im:
            im.verify()
    except Exception:
        return "corrupt"
    img = cv2.imread(str(path))
    if img is None:
        return "unreadable"
    h, w = img.shape[:2]
    if h < C.MIN_SIZE or w < C.MIN_SIZE:
        return "too-small"
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if cv2.Laplacian(gray, cv2.CV_64F).var() < C.BLUR_LIMIT:
        return "blur"
    if str(path).lower().endswith((".jpg", ".jpeg")):
        with open(path, "rb") as f:
            data = f.read()
        if not data.endswith(b"\xff\xd9"):
            return "truncated-jpeg"
    return ""


# ---------- STEP 1: clean (PINDAH, bukan hapus) ----------
def step_clean():
    moved = 0
    for root, _, files in os.walk(C.DATASET_RAW):
        for f in files:
            p = os.path.join(root, f)
            reason = is_broken(p) if f.lower().endswith(IMG_EXTS) else "not-image"
            if reason:
                rel = os.path.relpath(root, C.DATASET_RAW)
                dest_dir = C.ERRORS_DIR / rel
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest = dest_dir / f
                i = 1
                while dest.exists():
                    dest = dest_dir / f"{dest.stem}_{i}{dest.suffix}"
                    i += 1
                shutil.move(p, dest)
                moved += 1
    log(f"[1/4] clean: {moved} file dipindah ke errors/")


# ---------- STEP 2: dedup + split ----------
def step_split():
    assert abs(C.TRAIN_RATIO + C.VAL_RATIO + C.TEST_RATIO - 1.0) < 1e-6
    random.seed(C.SEED)
    if C.DATASET.exists():
        shutil.rmtree(C.DATASET)
    total = {"train": 0, "val": 0, "test": 0}
    for category in sorted(os.listdir(C.DATASET_RAW)):
        src = C.DATASET_RAW / category
        if not src.is_dir():
            continue
        files = [f for f in os.listdir(src) if f.lower().endswith(IMG_EXTS)]
        seen, unique = set(), []
        for f in files:
            try:
                d = sha256_of(src / f)
            except OSError:
                continue
            if d not in seen:
                seen.add(d)
                unique.append(f)
        if len(unique) < len(files):
            log(f"  [DEDUP] {category}: {len(files)} -> {len(unique)}")
        files = unique
        if not files:
            log(f"  [WARNING] kosong: {category}")
            continue
        random.shuffle(files)
        n = len(files)
        n_test, n_val = int(n * C.TEST_RATIO), int(n * C.VAL_RATIO)
        parts = {"test": files[:n_test],
                 "val": files[n_test:n_test + n_val],
                 "train": files[n_test + n_val:]}
        # KOREKSI: oversample kelas kecil HANYA di train (test/val murni).
        # Copy fisik dgn nama unik; augmentasi train-time membuatnya beragam.
        tr = parts["train"]
        if 0 < len(tr) < C.OVERSAMPLE_MIN:
            import itertools
            need = C.OVERSAMPLE_MIN - len(tr)
            tr = [(f, f) for f in tr] + [
                (f"os{i:04d}_{f}", f)
                for i, f in enumerate(itertools.islice(itertools.cycle(parts["train"]), need))]
            parts["train"] = tr
            log(f"  [OVERSAMPLE] {category}: train {len(tr) - need} -> {len(tr)}")
        else:
            parts["train"] = [(f, f) for f in tr]
        parts["test"] = [(f, f) for f in parts["test"]]
        parts["val"] = [(f, f) for f in parts["val"]]
        for name, part in parts.items():
            dst = C.DATASET / name / category
            dst.mkdir(parents=True, exist_ok=True)
            for alias, orig in part:
                shutil.copy(src / orig, dst / alias)
            total[name] += len(part)
    log(f"[2/4] split (seed={C.SEED}): {total}")


# ---------- STEP 3: train (backbone besar + aug kuat + early stopping) ----------
def step_train():
    weights = f"yolov8{C.MODEL_SIZE}-cls.pt"
    log(f"Backbone: {weights} | imgsz={C.IMGSZ} | epochs={C.EPOCHS} | patience={C.PATIENCE}")
    model = YOLO(weights)
    model.train(data=str(C.DATASET), epochs=C.EPOCHS, imgsz=C.IMGSZ,
                batch=C.BATCH, patience=C.PATIENCE,
                project=str(C.PROJECT / "runs" / "classify"),
                hsv_h=0.015, hsv_s=0.7, hsv_v=0.4,
                degrees=15, translate=0.15, scale=0.6, shear=5.0,
                perspective=0.0005, fliplr=0.5, erasing=0.4, mixup=0.1,
                dropout=C.DROPOUT)
    runs = sorted((C.PROJECT / "runs" / "classify").glob("train*"),
                  key=lambda p: p.stat().st_mtime)
    best = runs[-1] / "weights" / "best.pt"
    shutil.copy(best, C.BEST_PT)
    log(f"[3/4] train selesai. best.pt disalin ke {C.BEST_PT}")
    return YOLO(str(best))


# ---------- STEP 4: evaluasi di TEST SET + catat ----------
def step_evaluate(model):
    test_dir = C.DATASET / "test"
    correct = total = 0
    per_class = {}
    for category in sorted(os.listdir(test_dir)):
        cdir = test_dir / category
        if not cdir.is_dir():
            continue
        ok = n = 0
        for f in os.listdir(cdir):
            try:
                r = model.predict(str(cdir / f), imgsz=C.IMGSZ,
                                  conf=C.PRED_CONF, verbose=False)[0]
                pred = r.names[r.probs.top1]
            except Exception:
                pred = "<error>"
            n += 1
            if pred == category:
                ok += 1
        per_class[category] = (ok, n)
        correct += ok
        total += n
    acc = correct / max(1, total)
    log(f"[4/4] TEST SET accuracy: {acc:.4f} ({correct}/{total})")
    for cat, (ok, n) in per_class.items():
        log(f"   - {cat}: {ok}/{n} = {ok / max(1, n):.3f}")
    C.RESULTS.mkdir(parents=True, exist_ok=True)
    log_path = C.RESULTS / "training_log.csv"
    new = not log_path.exists()
    with open(log_path, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["model", "test_acc", "test_n"])
        w.writerow([str(C.BEST_PT), round(acc, 4), total])
    log(f"Dicatat di {log_path}")


if __name__ == "__main__":
    if not C.DATASET_RAW.exists():
        log("❌ dataset_raw belum ada!")
        sys.exit(1)
    step_clean()
    step_split()
    model = step_train()
    step_evaluate(model)
    log("SELESAI. Model siap dipakai: python run.py <folder>")
