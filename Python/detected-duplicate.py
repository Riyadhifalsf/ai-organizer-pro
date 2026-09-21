import os
import hashlib
import shutil

# Folder sumber
SOURCE_DIR = r"D:\ImageCollection\scan"

# Folder output
BASE_OUTPUT = r"D:\ImageCollection\results"

IMAGE_DIR = os.path.join(BASE_OUTPUT, "images")
VIDEO_DIR = os.path.join(BASE_OUTPUT, "videos")

DUP_IMAGE_DIR = os.path.join(BASE_OUTPUT, "duplicates_images")
DUP_VIDEO_DIR = os.path.join(BASE_OUTPUT, "duplicates_videos")

BROKEN_IMAGE_DIR = os.path.join(BASE_OUTPUT, "broken_images")
BROKEN_VIDEO_DIR = os.path.join(BASE_OUTPUT, "broken_videos")

# Buat folder
for folder in [
    IMAGE_DIR, VIDEO_DIR,
    DUP_IMAGE_DIR, DUP_VIDEO_DIR,
    BROKEN_IMAGE_DIR, BROKEN_VIDEO_DIR
]:
    os.makedirs(folder, exist_ok=True)

# Ekstensi file
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp")
VIDEO_EXT = (".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv")

def get_file_hash(filepath, chunk_size=8192):
    hasher = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        print(f"[BROKEN] Tidak bisa baca: {filepath}")
        return None

def safe_move(src, dst_folder):
    filename = os.path.basename(src)
    destination = os.path.join(dst_folder, filename)

    counter = 1
    while os.path.exists(destination):
        name, ext = os.path.splitext(filename)
        destination = os.path.join(dst_folder, f"{name}_{counter}{ext}")
        counter += 1

    shutil.move(src, destination)
    return destination

def process_files():
    hash_map = {}

    for root, dirs, files in os.walk(SOURCE_DIR):
        for file in files:
            full_path = os.path.join(root, file)
            ext = os.path.splitext(file)[1].lower()

            # Tentukan kategori awal
            if ext in IMAGE_EXT:
                file_type = "IMAGE"
                target_dir = IMAGE_DIR
                dup_dir = DUP_IMAGE_DIR
                broken_dir = BROKEN_IMAGE_DIR
            elif ext in VIDEO_EXT:
                file_type = "VIDEO"
                target_dir = VIDEO_DIR
                dup_dir = DUP_VIDEO_DIR
                broken_dir = BROKEN_VIDEO_DIR
            else:
                continue

            file_hash = get_file_hash(full_path)

            # Jika file rusak
            if file_hash is None:
                dest = safe_move(full_path, broken_dir)
                print(f"[BROKEN {file_type}] --> {dest}")
                continue

            # Cek duplikat
            if file_hash in hash_map:
                print(f"[DUP {file_type}] {full_path}")
                dest = safe_move(full_path, dup_dir)
                print(f"--> Dipindah ke: {dest}")
            else:
                hash_map[file_hash] = full_path
                dest = safe_move(full_path, target_dir)
                print(f"[OK {file_type}] {dest}")

if __name__ == "__main__":
    process_files()