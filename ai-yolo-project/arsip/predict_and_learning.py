# predict_selftrain.py
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
                    HIGH_CONF_THRESHOLD, LOW_CONF_THRESHOLD)

MODEL_PATH = str(BEST_MODEL)
SOURCE_FOLDER = str(SCAN_DIR)
PLOT_FOLDER = str(PREDICTIONS_DIR)
ERROR_FOLDER = str(ERROR_IMAGES_DIR)
HIGH_CONF_FOLDER = str(HIGH_CONF_DIR)
MEDIUM_CONF_FOLDER = str(MEDIUM_CONF_DIR)
LOW_CONF_FOLDER = str(LOW_CONF_DIR)

# folder dataset training
TRAIN_IMAGE_FOLDER = "dataset/train/images"
TRAIN_LABEL_FOLDER = "dataset/train/labels"

# buat folder utama
for folder in [
    PLOT_FOLDER, ERROR_FOLDER,
    HIGH_CONF_FOLDER, MEDIUM_CONF_FOLDER, LOW_CONF_FOLDER,
    TRAIN_IMAGE_FOLDER, TRAIN_LABEL_FOLDER
]:
    os.makedirs(folder, exist_ok=True)

# ====== DUPLICATE HANDLER ======
duplicate_count = 0

def get_unique_path(path):
    global duplicate_count
    path = Path(path)

    if not path.exists():
        return path

    duplicate_count += 1
    counter = 1

    while True:
        new_path = path.with_name(f"{path.stem}_dup{counter}{path.suffix}")
        if not new_path.exists():
            return new_path
        counter += 1

# ====== LOAD MODEL ======
model = YOLO(MODEL_PATH)

# ====== VALIDASI IMAGE ======
def is_valid_image(img_path):
    try:
        img = Image.open(img_path)
        img.verify()
        return True
    except (UnidentifiedImageError, OSError, ValueError):
        return False

# ====== MOVE FILE (SAFE) ======
def move_file_to_folder(img_path, base_folder, class_name):
    folder = Path(base_folder) / class_name
    os.makedirs(folder, exist_ok=True)

    dst = folder / Path(img_path).name
    dst = get_unique_path(dst)

    shutil.move(img_path, dst)

# ====== ERROR MOVE (SAFE) ======
def move_to_error(img_path):
    dst = Path(ERROR_FOLDER) / Path(img_path).name
    dst = get_unique_path(dst)
    shutil.move(img_path, dst)

# ====== ADD TO TRAINING ======
def add_to_training(img_path, class_name, class_idx):
    dest_image = Path(TRAIN_IMAGE_FOLDER) / Path(img_path).name
    dest_image = get_unique_path(dest_image)

    shutil.copy(img_path, dest_image)

    label_file = Path(TRAIN_LABEL_FOLDER) / dest_image.with_suffix('.txt').name

    with open(label_file, 'w') as f:
        f.write(f"{class_idx}\n")

# ====== LOAD IMAGE LIST ======
image_files = list(Path(SOURCE_FOLDER).rglob("*.*"))
print(f"[INFO] Found {len(image_files)} images to process.")

category_count = {}
confidence_count = {"high": 0, "medium": 0, "low": 0}

# ====== MAIN LOOP ======
for img_path in tqdm(image_files, desc="Predicting images", unit="img"):
    img_path = str(img_path)

    # validasi image
    if not is_valid_image(img_path):
        move_to_error(img_path)
        continue

    try:
        results = model.predict(img_path, imgsz=224, conf=0.5)
        result = results[0]

        # ambil probabilitas
        probs = result.probs
        class_idx = probs.top1
        class_conf = probs.top1conf.item()
        class_name = result.names[class_idx]

        # count kategori
        category_count[class_name] = category_count.get(class_name, 0) + 1

        # ====== SAVE PLOT (SAFE) ======
        plot_folder = Path(PLOT_FOLDER) / class_name
        os.makedirs(plot_folder, exist_ok=True)

        plot_path = plot_folder / Path(img_path).name
        plot_path = get_unique_path(plot_path)

        result.save(plot_path)

        # ====== CLASSIFY CONFIDENCE ======
        if class_conf >= HIGH_CONF_THRESHOLD:
            add_to_training(img_path, class_name, class_idx)
            move_file_to_folder(img_path, HIGH_CONF_FOLDER, class_name)
            confidence_count["high"] += 1

        elif class_conf < LOW_CONF_THRESHOLD:
            move_file_to_folder(img_path, LOW_CONF_FOLDER, class_name)
            confidence_count["low"] += 1

        else:
            move_file_to_folder(img_path, MEDIUM_CONF_FOLDER, class_name)
            confidence_count["medium"] += 1

    except Exception as e:
        move_to_error(img_path)
        print(f"[ERROR] {img_path}: {e}")

# ====== SUMMARY ======
print("\n[INFO] Prediction complete!")

print("\n[INFO] Summary per category:")
for cat, count in category_count.items():
    print(f" - {cat}: {count} images")

print("\n[INFO] Confidence level summary:")
for level, count in confidence_count.items():
    print(f" - {level}: {count} images")

print(f"\n[INFO] Duplicate files handled: {duplicate_count}")
print(f"[INFO] Corrupt/failed images → {ERROR_FOLDER}")
print(f"[INFO] High confidence ≥ {HIGH_CONF_THRESHOLD} → {HIGH_CONF_FOLDER}")
print(f"[INFO] Medium confidence → {MEDIUM_CONF_FOLDER}")
print(f"[INFO] Low confidence < {LOW_CONF_THRESHOLD} → {LOW_CONF_FOLDER}")
print(f"[INFO] Training dataset → {TRAIN_IMAGE_FOLDER} + {TRAIN_LABEL_FOLDER}")
print(f"[INFO] Plots saved in → {PLOT_FOLDER}")