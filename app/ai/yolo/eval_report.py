#!/usr/bin/env python3
"""eval_report.py — ukur kemampuan model saat ini (akurasi per kelas + total).

    python eval_report.py [--model <best.pt>] [--data <folder-val>] [--tta]

  --tta = test-time augmentation (flip + multi-resolusi, ~3x lambat, akurat+)
  Bisa dijalankan berulang (resume otomatis).
  Hasil: results/laporan_akurasi.txt + results/eval_detail.csv
  (--tta menulis eval_tta_log.csv + laporan_tta.txt)
"""
import csv
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from ultralytics import YOLO

import config as C

MODEL = sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv else str(C.MODEL)
DATA = Path(sys.argv[sys.argv.index("--data") + 1]) if "--data" in sys.argv else C.DATASET / "val"
TTA = "--tta" in sys.argv

LOG = C.RESULTS / ("eval_tta_log.csv" if TTA else "eval_log.csv")
REPORT_TXT = C.RESULTS / ("laporan_tta.txt" if TTA else "laporan_akurasi.txt")
REPORT_CSV = C.RESULTS / ("eval_tta_detail.csv" if TTA else "eval_detail.csv")
done = set()
if LOG.exists():
    with open(LOG, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            done.add(r["file"])

files = []
for cat in sorted(os.listdir(DATA)):
    cdir = DATA / cat
    if not cdir.is_dir():
        continue
    for fn in sorted(os.listdir(cdir)):
        p = str(cdir / fn)
        if p not in done:
            files.append((cat, p))
print(f"MODEL: {MODEL}\nDATA: {DATA}\nTTA: {TTA}\nsudah dinilai: {len(done)}, sisa: {len(files)}", flush=True)

model = YOLO(MODEL)

if TTA:
    from PIL import Image as _I

    def predict(p):
        scores = {}
        base = _I.open(p).convert("RGB")
        variants = []
        for sz in C.TTA_IMGSZ:
            v = base.resize((sz, sz))
            variants.append(v)
            variants.append(v.transpose(_I.FLIP_LEFT_RIGHT))
        base.close()
        for v in variants:
            r = model.predict(v, imgsz=C.IMGSZ, conf=C.PRED_CONF, verbose=False)[0]
            for i, prob in enumerate(r.probs.data.tolist()):
                cls = r.names[i]
                scores[cls] = scores.get(cls, 0.0) + prob
        name = max(scores, key=scores.get)
        return name, round(scores[name] / len(variants), 4)
else:
    def predict(p):
        r = model.predict(p, imgsz=C.IMGSZ, conf=C.PRED_CONF, verbose=False)[0]
        return r.names[r.probs.top1], round(float(r.probs.top1conf), 4)

new = not LOG.exists()
logf = open(LOG, "a", newline="", encoding="utf-8")
w = csv.writer(logf)
if new:
    w.writerow(["file", "aktual", "prediksi", "confidence"])

for i, (cat, p) in enumerate(files):
    try:
        pred, conf = predict(p)
    except Exception as e:
        pred, conf = "<error>", 0.0
    w.writerow([p, cat, pred, conf])
    done.add(p)
    if (i + 1) % 100 == 0:
        logf.flush()
        print(f"  {i + 1}/{len(files)}", flush=True)
logf.close()

# ---------- laporan ----------
rows = list(csv.DictReader(open(LOG, encoding="utf-8")))
# hanya file yang masih ada di DATA (abaikan log lama dari lokasi lain)
valid = [r for r in rows if r["file"].startswith(str(DATA))]
per_class = defaultdict(lambda: [0, 0])
wrong = Counter()
for r in valid:
    ok = r["aktual"] == r["prediksi"]
    per_class[r["aktual"]][1] += 1
    if ok:
        per_class[r["aktual"]][0] += 1
    else:
        wrong[(r["aktual"], r["prediksi"])] += 1

total_ok = sum(v[0] for v in per_class.values())
total_n = sum(v[1] for v in per_class.values())
lines = [f"LAPORAN KEMAMPUAN MODEL",
         f"Tanggal: {datetime.now():%Y-%m-%d %H:%M}",
         f"Model: {MODEL}", f"Data uji: {DATA} ({total_n} gambar)", "",
         f"AKURASI KESELURUHAN: {total_ok / max(1, total_n) * 100:.2f}% ({total_ok}/{total_n})", "",
         "Per kelas:"]
for cat in sorted(per_class):
    ok, n = per_class[cat]
    lines.append(f"  - {cat}: {ok / max(1, n) * 100:.2f}% ({ok}/{n})")
lines.append("")
lines.append("Salah tebak tersering (aktual -> prediksi):")
for (a, p), n in wrong.most_common(10):
    lines.append(f"  - {a} -> {p}: {n}x")
lines.append("")
lines.append("CATATAN: data ini = validation set (pernah dipakai pilih model),")
lines.append("jadi angka sedikit optimistis. Untuk angka final, evaluasi di test set")
lines.append("hasil split_dataset baru (python train.py).")

C.RESULTS.mkdir(parents=True, exist_ok=True)
REPORT_TXT.write_text("\n".join(lines), encoding="utf-8")
with open(REPORT_CSV, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["kelas", "benar", "total", "akurasi_%"])
    for cat in sorted(per_class):
        ok, n = per_class[cat]
        w.writerow([cat, ok, n, round(ok / max(1, n) * 100, 2)])
print("\n".join(lines), flush=True)
