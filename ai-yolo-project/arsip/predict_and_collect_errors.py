import os
import shutil
from ultralytics import YOLO
from tqdm import tqdm
from config import BEST_MODEL, DATASET, ERRORS_DIR

MODEL = str(BEST_MODEL)
DATASET_VAL = str(DATASET / "val")
ERROR_DIR = str(ERRORS_DIR)

if not os.path.exists(MODEL):
    print("❌ Model belum ada! Jalankan train.py dulu")
    exit()

model = YOLO(MODEL)

def collect_errors():
    os.makedirs(ERROR_DIR, exist_ok=True)

    for category in os.listdir(DATASET_VAL):
        path = os.path.join(DATASET_VAL, category)

        if not os.path.isdir(path):
            continue

        for file in tqdm(os.listdir(path), desc=category):
            fpath = os.path.join(path, file)

            try:
                result = model(fpath)
                pred = result[0].names[result[0].probs.top1]

                if pred != category:
                    dst = os.path.join(ERROR_DIR, category)
                    os.makedirs(dst, exist_ok=True)
                    shutil.copy(fpath, os.path.join(dst, file))

            except:
                continue

    print("🔥 Error collected")

if __name__ == "__main__":
    collect_errors()