# DEPRECATED: script ini MENGHAPUS file permanen (os.remove) dan logikanya
# duplikat dengan clean_and_move_image_error.py (yang aman: PINDAH ke errors/).
# Jangan dipakai langsung — auto_pipeline.py sudah tidak memanggilnya.
# File ini dipertahankan hanya sebagai arsip.
import os
import cv2
from PIL import Image
from config import DATASET_RAW

INPUT = DATASET_RAW
MIN_SIZE = 128

def is_blur(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var() < 50

def is_corrupt(path):
    try:
        img = Image.open(path)
        img.verify()
        return False
    except:
        return True

def clean():
    removed = 0

    for category in os.listdir(INPUT):
        path = os.path.join(INPUT, category)

        if not os.path.isdir(path):
            continue

        for file in os.listdir(path):
            fpath = os.path.join(path, file)

            try:
                if is_corrupt(fpath):
                    os.remove(fpath)
                    removed += 1
                    continue

                img = cv2.imread(fpath)
                if img is None:
                    os.remove(fpath)
                    removed += 1
                    continue

                h, w = img.shape[:2]

                if h < MIN_SIZE or w < MIN_SIZE or is_blur(img):
                    os.remove(fpath)
                    removed += 1

            except:
                os.remove(fpath)
                removed += 1

    print(f"🔥 Cleaning selesai | Removed: {removed}")

if __name__ == "__main__":
    clean()