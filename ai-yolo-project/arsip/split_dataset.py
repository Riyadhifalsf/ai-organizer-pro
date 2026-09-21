import hashlib
import os
import random
import shutil
from config import DATASET_RAW, DATASET, SEED, TRAIN_RATIO, VAL_RATIO, TEST_RATIO

assert abs(TRAIN_RATIO + VAL_RATIO + TEST_RATIO - 1.0) < 1e-6, "Rasio split harus = 1.0"

random.seed(SEED)  # KOREKSI: split reproducible


def sha256_of(path, n=1024 * 1024):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read(n))
    return h.hexdigest()


if DATASET.exists():
    shutil.rmtree(DATASET)

total = {"train": 0, "val": 0, "test": 0}
for category in sorted(os.listdir(DATASET_RAW)):
    src_path = DATASET_RAW / category
    if not src_path.is_dir():
        continue

    files = [f for f in os.listdir(src_path)
             if f.lower().endswith((".jpg", ".png", ".jpeg"))]

    # KOREKSI: deduplikasi isi sebelum split (bocor train/val bikin akurasi semu)
    seen, unique = set(), []
    for f in files:
        try:
            digest = sha256_of(src_path / f)
        except OSError:
            continue
        if digest not in seen:
            seen.add(digest)
            unique.append(f)
    if len(unique) < len(files):
        print(f"[DEDUP] {category}: {len(files)} -> {len(unique)}")
    files = unique

    if not files:
        print(f"[WARNING] kosong: {category}")
        continue

    random.shuffle(files)
    n = len(files)
    n_test = int(n * TEST_RATIO)
    n_val = int(n * VAL_RATIO)
    test_files = files[:n_test]
    val_files = files[n_test:n_test + n_val]
    train_files = files[n_test + n_val:]

    for split_name, split_files in (("train", train_files),
                                    ("val", val_files),
                                    ("test", test_files)):
        dst = DATASET / split_name / category
        dst.mkdir(parents=True, exist_ok=True)
        for f in split_files:
            shutil.copy(src_path / f, dst / f)
        total[split_name] += len(split_files)

print(f"🔥 Dataset siap (seed={SEED}): {total}")
print("   test/ hanya untuk evaluasi akhir — jangan dipakai tuning.")
