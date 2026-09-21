import os
import shutil
import cv2
from PIL import Image
from config import DATASET_RAW, ERRORS_DIR

INPUT = DATASET_RAW
BROKEN_DIR = ERRORS_DIR / "image-broken"

MIN_SIZE = 128

os.makedirs(BROKEN_DIR, exist_ok=True)

# ================= DETECTION =================

def is_corrupt_pil(path):
    try:
        img = Image.open(path)
        img.verify()
        return False
    except:
        return True

def is_bad_opencv(path):
    try:
        img = cv2.imread(path)
        if img is None:
            return True

        h, w = img.shape[:2]
        if h < MIN_SIZE or w < MIN_SIZE:
            return True

        return False
    except:
        return True

def has_jpeg_issue(path):
    try:
        if not path.lower().endswith((".jpg", ".jpeg")):
            return False

        with open(path, "rb") as f:
            data = f.read()
            # cek EOF JPEG
            if not data.endswith(b'\xff\xd9'):
                return True

        return False
    except:
        return True

def reencode_check(path):
    try:
        img = cv2.imread(path)
        if img is None:
            return True

        success, _ = cv2.imencode(".jpg", img)
        return not success
    except:
        return True

# ================= MOVE =================

def move_file(src_path):
    filename = os.path.basename(src_path)
    dst_path = os.path.join(BROKEN_DIR, filename)

    base, ext = os.path.splitext(filename)
    counter = 1

    while os.path.exists(dst_path):
        dst_path = os.path.join(BROKEN_DIR, f"{base}_{counter}{ext}")
        counter += 1

    shutil.move(src_path, dst_path)

# ================= MAIN =================

def clean():
    moved = 0

    for root, _, files in os.walk(INPUT):
        for file in files:
            fpath = os.path.join(root, file)

            try:
                if (
                    is_corrupt_pil(fpath)
                    or is_bad_opencv(fpath)
                    or has_jpeg_issue(fpath)
                    or reencode_check(fpath)
                ):
                    move_file(fpath)
                    moved += 1
                    print(f"[MOVED] {fpath}")

            except Exception as e:
                move_file(fpath)
                moved += 1
                print(f"[FORCE MOVE] {fpath} | {e}")

    print(f"\n🔥 TOTAL DIPINDAHKAN: {moved}")

# ================= RUN =================

if __name__ == "__main__":
    clean()