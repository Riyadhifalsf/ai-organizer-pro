# predict_selftrain_safe.py
import os
from pathlib import Path
from PIL import Image, UnidentifiedImageError
from ultralytics import YOLO
import shutil
from tqdm import tqdm
import torch

# ====== KONFIGURASI (terpusat di config.py) ======
from config import (BEST_MODEL, SCAN_DIR, PREDICTIONS_DIR, ERROR_IMAGES_DIR,
                    HIGH_CONF_DIR, MEDIUM_CONF_DIR, LOW_CONF_DIR,
                    HIGH_CONF_THRESHOLD, LOW_CONF_THRESHOLD, PRED_CONF)

MODEL_PATH = str(BEST_MODEL)
SOURCE_FOLDER = str(SCAN_DIR)
PLOT_FOLDER = str(PREDICTIONS_DIR)
ERROR_FOLDER = str(ERROR_IMAGES_DIR)
HIGH_CONF_FOLDER = str(HIGH_CONF_DIR)
MEDIUM_CONF_FOLDER = str(MEDIUM_CONF_DIR)
LOW_CONF_FOLDER = str(LOW_CONF_DIR)

# folder dataset training (self-train)
TRAIN_IMAGE_FOLDER = "dataset/train/images"
TRAIN_LABEL_FOLDER = "dataset/train/labels"

# buat semua folder
for folder in [PLOT_FOLDER, ERROR_FOLDER, HIGH_CONF_FOLDER, MEDIUM_CONF_FOLDER, LOW_CONF_FOLDER,
               TRAIN_IMAGE_FOLDER, TRAIN_LABEL_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# load model YOLO
model = YOLO(MODEL_PATH)

# ==== Fungsi Helper ====
def is_valid_image(img_path):
    """Cek apakah file image valid"""
    try:
        img = Image.open(img_path)
        img.verify()
        return True
    except (UnidentifiedImageError, OSError, ValueError):
        return False

def safe_move(src_path, dest_folder):
    """Pindahkan file dengan aman, hindari double extension dan file not found"""
    src = Path(src_path)
    if not src.exists():
        print(f"[WARNING] File not found: {src}")
        return
    dest_folder = Path(dest_folder)
    dest_folder.mkdir(parents=True, exist_ok=True)
    dest_path = dest_folder / src.name  # pakai nama file asli
    try:
        shutil.move(str(src), str(dest_path))
    except Exception:
        shutil.copy2(str(src), str(dest_path))
        try:
            src.unlink()
        except Exception:
            pass

def add_to_training(img_path, class_idx):
    """Tambahkan image & pseudo-label ke dataset training"""
    img_src = Path(img_path)
    dest_image = Path(TRAIN_IMAGE_FOLDER) / img_src.name
    shutil.copy(img_src, dest_image)
    label_file = Path(TRAIN_LABEL_FOLDER) / img_src.with_suffix('.txt').name
    with open(label_file, 'w') as f:
        f.write(f"{class_idx}\n")

# ==== Ambil semua file ====
image_files = list(Path(SOURCE_FOLDER).glob("*.*"))
print(f"[INFO] Found {len(image_files)} images to process.")

category_count = {}
confidence_count = {"high":0, "medium":0, "low":0}

# ==== Loop prediksi dengan progress bar ====
for img_path in tqdm(image_files, desc="Predicting images", unit="img"):
    img_path = str(img_path)

    # cek validitas
    if not is_valid_image(img_path):
        safe_move(img_path, ERROR_FOLDER)
        continue

    try:
        # prediksi YOLO
        results = model.predict(img_path, imgsz=224, conf=PRED_CONF)
        result = results[0]

        # ambil probabilitas top-1
        probs = result.probs
        class_idx = probs.top1
        class_conf = probs.top1conf.item()
        class_name = result.names[class_idx]

        # update count kategori
        category_count[class_name] = category_count.get(class_name, 0) + 1

        # simpan hasil plot
        plot_folder = Path(PLOT_FOLDER) / class_name
        plot_folder.mkdir(parents=True, exist_ok=True)
        result.save(plot_folder / Path(img_path).name)

        # pindahkan file asli & self-train sesuai confidence
        # KOREKSI: add_to_training DULU selagi file masih di tempat,
        # baru pindah. Kebalikannya = copy gagal FileNotFound (bug lama).
        if class_conf >= HIGH_CONF_THRESHOLD:
            add_to_training(img_path, class_idx)
            safe_move(img_path, Path(HIGH_CONF_FOLDER) / class_name)
            confidence_count["high"] += 1
        elif class_conf < LOW_CONF_THRESHOLD:
            safe_move(img_path, Path(LOW_CONF_FOLDER) / class_name)
            confidence_count["low"] += 1
        else:
            safe_move(img_path, Path(MEDIUM_CONF_FOLDER) / class_name)
            confidence_count["medium"] += 1

    except Exception as e:
        safe_move(img_path, ERROR_FOLDER)
        print(f"[ERROR] {img_path}: {e}")

# ==== Ringkasan ====
print("\n[INFO] Prediction complete!")
print("[INFO] Summary per category:")
for cat, count in category_count.items():
    print(f" - {cat}: {count} images")

print("[INFO] Confidence level summary:")
for level, count in confidence_count.items():
    print(f" - {level}: {count} images")

print(f"[INFO] Corrupt/failed images moved to: {ERROR_FOLDER}")
print(f"[INFO] High confidence images ≥ {HIGH_CONF_THRESHOLD} → {HIGH_CONF_FOLDER}")
print(f"[INFO] Added to training: {TRAIN_IMAGE_FOLDER} + {TRAIN_LABEL_FOLDER}")
print(f"[INFO] Medium confidence images → {MEDIUM_CONF_FOLDER}")
print(f"[INFO] Low confidence images < {LOW_CONF_THRESHOLD} → {LOW_CONF_FOLDER}")
print(f"[INFO] Predicted plots saved in: {PLOT_FOLDER}")