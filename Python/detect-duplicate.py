import os
from PIL import Image
import imagehash
from collections import defaultdict

# ================= CONFIG =================
SOURCE_DIR = r"D:\ImageCollection\scan"

IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
THRESHOLD = 5  # semakin kecil = semakin ketat

# ==========================================

hash_map = {}
similar_groups = []

def get_phash(path):
    try:
        with Image.open(path) as img:
            return imagehash.phash(img)
    except:
        return None


def scan_duplicates():
    for root, _, files in os.walk(SOURCE_DIR):
        for file in files:
            path = os.path.join(root, file)
            ext = os.path.splitext(file)[1].lower()

            if ext not in IMAGE_EXT:
                continue

            print(f"[SCAN] {file}")
            ph = get_phash(path)

            if ph is None:
                continue

            found = False

            # cek similarity
            for existing_hash in hash_map:
                distance = ph - existing_hash

                if distance <= THRESHOLD:
                    hash_map[existing_hash].append(path)
                    found = True
                    break

            if not found:
                hash_map[ph] = [path]

    # ambil yang duplicate saja
    for group in hash_map.values():
        if len(group) > 1:
            similar_groups.append(group)

    # ===== OUTPUT =====
    print("\n===== DUPLICATE GROUP =====")
    for i, group in enumerate(similar_groups, 1):
        print(f"\nGroup {i}:")
        for file in group:
            print(" -", file)


if __name__ == "__main__":
    scan_duplicates()