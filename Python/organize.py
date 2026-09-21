import os
import hashlib
import shutil
import time
import contextlib
import sys
from collections import defaultdict
from PIL import Image
import exifread
import cv2
import imagehash
from datetime import datetime

# ================= CONFIG =================
SOURCE_DIR = r"D:\ImageCollection\scan"
BASE_OUTPUT = r"D:\ImageCollection\results"

IMAGE_DIR = os.path.join(BASE_OUTPUT, "images")
VIDEO_DIR = os.path.join(BASE_OUTPUT, "videos")

DUP_IMAGE_DIR = os.path.join(BASE_OUTPUT, "duplicates_images")
SIMILAR_IMAGE_DIR = os.path.join(BASE_OUTPUT, "similar_images")
DUP_VIDEO_DIR = os.path.join(BASE_OUTPUT, "duplicates_videos")

BROKEN_IMAGE_DIR = os.path.join(BASE_OUTPUT, "broken_images")
BROKEN_VIDEO_DIR = os.path.join(BASE_OUTPUT, "broken_videos")

IMAGE_EXT = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic")
VIDEO_EXT = (".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".m2ts", ".mts")

PHASH_THRESHOLD = 5
# ==========================================

# Buat folder utama
for folder in [
    IMAGE_DIR, VIDEO_DIR,
    DUP_IMAGE_DIR, SIMILAR_IMAGE_DIR, DUP_VIDEO_DIR,
    BROKEN_IMAGE_DIR, BROKEN_VIDEO_DIR
]:
    os.makedirs(folder, exist_ok=True)

# ================= UTIL ===================

def get_file_hash(filepath, chunk_size=8192):
    hasher = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()
    except:
        return None

def get_phash(path):
    try:
        with Image.open(path) as img:
            return imagehash.phash(img)
    except:
        return None

def get_image_camera_info(path):
    try:
        with open(path, 'rb') as f:
            tags = exifread.process_file(f, details=False)
        make = str(tags.get("Image Make", "Unknown")).strip()
        model = str(tags.get("Image Model", "Unknown")).strip()
        return make, model
    except:
        return "Unknown", "Unknown"

def get_image_datetime(path):
    try:
        with open(path, 'rb') as f:
            tags = exifread.process_file(f, details=False)
        dt_str = tags.get("EXIF DateTimeOriginal")
        if dt_str:
            return datetime.strptime(str(dt_str), "%Y:%m:%d %H:%M:%S")
        else:
            return None
    except:
        return None

@contextlib.contextmanager
def suppress_stderr():
    with open(os.devnull, "w") as fnull:
        old_stderr = sys.stderr
        sys.stderr = fnull
        try:
            yield
        finally:
            sys.stderr = old_stderr

def is_image_broken(path):
    try:
        with Image.open(path) as img:
            img.verify()
        return False
    except:
        return True

def is_video_broken(path):
    try:
        with suppress_stderr():
            cap = cv2.VideoCapture(path)
            if not cap.isOpened():
                return True
            ret, frame = cap.read()
            cap.release()
            del cap
            return not ret or frame is None
    except:
        return True

def safe_move(src, dst_folder):
    if not os.path.exists(src):
        print(f"[SKIP] File tidak ditemukan: {src}")
        return None
    os.makedirs(dst_folder, exist_ok=True)
    filename = os.path.basename(src)
    destination = os.path.join(dst_folder, filename)
    counter = 1
    while os.path.exists(destination):
        name, ext = os.path.splitext(filename)
        destination = os.path.join(dst_folder, f"{name}_{counter}{ext}")
        counter += 1
    try:
        shutil.move(src, destination)
    except:
        try:
            shutil.copy2(src, destination)
            os.remove(src)
        except Exception as e:
            print(f"[FAILED MOVE] {src} | {e}")
            return None
    return destination

# ================= CORE ===================
def process_files():
    hash_map = {}
    phash_map = []

    for root, dirs, files in os.walk(SOURCE_DIR):
        if BASE_OUTPUT in root:
            continue  # skip folder hasil
        for file in files:
            full_path = os.path.join(root, file)
            if not os.path.exists(full_path):
                continue
            ext = os.path.splitext(file)[1].lower()

            # ===== IMAGE =====
            if ext in IMAGE_EXT:
                if is_image_broken(full_path):
                    dest = safe_move(full_path, BROKEN_IMAGE_DIR)
                    print(f"[BROKEN IMAGE] {dest}")
                    continue

                # --- camera info ---
                make, model = get_image_camera_info(full_path)
                camera_folder_path = os.path.join(IMAGE_DIR, f"{make}_{model}")

                # --- EXACT DUPLICATE ---
                file_hash = get_file_hash(full_path)
                if file_hash in hash_map:
                    dest = safe_move(full_path, DUP_IMAGE_DIR)
                    print(f"[DUP EXACT] {dest}")
                    continue
                else:
                    hash_map[file_hash] = full_path

                # --- SIMILAR IMAGE ---
                ph = get_phash(full_path)
                if ph is not None:
                    found_similar = False
                    for existing_ph, _ in phash_map:
                        if ph - existing_ph <= PHASH_THRESHOLD:
                            dest = safe_move(full_path, SIMILAR_IMAGE_DIR)
                            print(f"[SIMILAR] {dest}")
                            found_similar = True
                            break
                    if found_similar:
                        continue
                    phash_map.append((ph, full_path))

                # --- MOVE TO CAMERA FOLDER ---
                dest = safe_move(full_path, camera_folder_path)
                print(f"[OK IMAGE] {dest}")
                continue

            # ===== VIDEO =====
            elif ext in VIDEO_EXT:
                if is_video_broken(full_path):
                    dest = safe_move(full_path, BROKEN_VIDEO_DIR)
                    print(f"[BROKEN VIDEO] {dest}")
                    continue
                file_hash = get_file_hash(full_path)
                if file_hash in hash_map:
                    dest = safe_move(full_path, DUP_VIDEO_DIR)
                    print(f"[DUP VIDEO] {dest}")
                    continue
                else:
                    hash_map[file_hash] = full_path
                dest = safe_move(full_path, VIDEO_DIR)
                print(f"[OK VIDEO] {dest}")
                continue

# ======= RENAME FILES PER CAMERA =======
def rename_images_per_camera():
    for camera_folder in os.listdir(IMAGE_DIR):
        camera_path = os.path.join(IMAGE_DIR, camera_folder)
        if not os.path.isdir(camera_path):
            continue
        counter = defaultdict(int)
        for file in sorted(os.listdir(camera_path)):
            file_path = os.path.join(camera_path, file)
            ext = os.path.splitext(file)[1].lower()
            dt = get_image_datetime(file_path)
            dt_str = dt.strftime("%Y%m%d_%H%M%S") if dt else "UnknownDate"
            counter[dt_str] += 1
            new_name = f"{dt_str}_{camera_folder}_{counter[dt_str]}{ext}"
            new_path = os.path.join(camera_path, new_name)
            try:
                os.rename(file_path, new_path)
                print(f"[RENAMED] {new_path}")
            except Exception as e:
                print(f"[FAILED RENAME] {file_path} | {e}")

# ================= RUN ====================
if __name__ == "__main__":
    process_files()
    rename_images_per_camera()