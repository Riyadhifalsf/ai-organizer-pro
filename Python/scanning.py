import os
import hashlib
import json
import shutil
from collections import defaultdict
from openpyxl import Workbook
from tqdm import tqdm  # 🔥 progress bar

# ================= CONFIG =================
SOURCE_DIR = r"D:\ImageCollection\scan"

REPORT_DIR = r"D:\ImageCollection\results\duplicate_report"
DUPLICATE_DIR = r"D:\ImageCollection\results\duplicates"

EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp",
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv"
)

os.makedirs(REPORT_DIR, exist_ok=True)
os.makedirs(DUPLICATE_DIR, exist_ok=True)

# ================ HASH ===================
def get_file_hash(filepath, chunk_size=8192):
    hasher = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()
    except:
        return None

# ================ GET FILE LIST ==========
def get_all_files(source_dir):
    file_list = []
    for root, _, files in os.walk(source_dir):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in EXTENSIONS:
                file_list.append(os.path.join(root, file))
    return file_list

# ================ SCAN ===================
def scan_duplicates(source_dir):
    hash_map = defaultdict(list)

    all_files = get_all_files(source_dir)

    print(f"Total file terdeteksi: {len(all_files)}")

    for full_path in tqdm(all_files, desc="Scanning", unit="file"):
        file_hash = get_file_hash(full_path)
        if file_hash:
            hash_map[file_hash].append(full_path)

    duplicates = {h: paths for h, paths in hash_map.items() if len(paths) > 1}
    return duplicates

# ================ MOVE DUPLICATES ========
def move_duplicates(duplicates):
    moved_pairs = []

    total_moves = sum(len(paths) - 1 for paths in duplicates.values())

    with tqdm(total=total_moves, desc="Moving", unit="file") as pbar:
        for file_hash, paths in duplicates.items():
            original = paths[0]

            for dup in paths[1:]:
                try:
                    filename = os.path.basename(dup)
                    target_path = os.path.join(DUPLICATE_DIR, filename)

                    counter = 1
                    while os.path.exists(target_path):
                        name, ext = os.path.splitext(filename)
                        target_path = os.path.join(
                            DUPLICATE_DIR, f"{name}_{counter}{ext}"
                        )
                        counter += 1

                    shutil.move(dup, target_path)
                    moved_pairs.append((original, target_path))

                except Exception as e:
                    print(f"\nGagal memindahkan: {dup} | {e}")

                pbar.update(1)

    return moved_pairs

# ================ REPORT =================
def generate_reports(duplicates, moved_pairs):
    # TXT
    txt_path = os.path.join(REPORT_DIR, "duplicate.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        for h, paths in duplicates.items():
            f.write(f"Hash: {h}\n")
            for p in paths:
                f.write(f"{p}\n")
            f.write("\n")

    # JSON
    json_path = os.path.join(REPORT_DIR, "duplicate.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(duplicates, f, indent=4)

    # EXCEL
    excel_path = os.path.join(REPORT_DIR, "duplicate.xlsx")
    wb = Workbook()

    ws1 = wb.active
    ws1.title = "All Duplicates"
    ws1.append(["Hash", "File Path"])

    for h, paths in duplicates.items():
        for p in paths:
            ws1.append([h, p])

    ws2 = wb.create_sheet("Pairs")
    ws2.append(["Original File", "Duplicate File (Moved)"])

    for original, dup in moved_pairs:
        ws2.append([original, dup])

    wb.save(excel_path)

    print(f"[OK] TXT  : {txt_path}")
    print(f"[OK] JSON : {json_path}")
    print(f"[OK] Excel: {excel_path}")

# ================ MAIN ===================
if __name__ == "__main__":
    print("Scanning duplicate files...")

    duplicates = scan_duplicates(SOURCE_DIR)

    total_dup = sum(len(v) - 1 for v in duplicates.values())
    print(f"Total duplicate ditemukan: {total_dup}")

    if not duplicates:
        print("Tidak ada duplicate.")
        exit()

    print("Memindahkan duplicate...")
    moved_pairs = move_duplicates(duplicates)

    print("Membuat laporan...")
    generate_reports(duplicates, moved_pairs)

    print("Selesai.")