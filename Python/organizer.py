import os
import shutil
import csv
from pathlib import Path
from PIL import Image, ExifTags
from tqdm import tqdm

# ===================== CONFIG =====================
SRC = Path("D:/scan-test")
DST = Path("D:/output")
LOG_FILE = "move_log.csv"
DRY_RUN = False
# =================================================

IMAGE_EXT = (".jpg", ".jpeg", ".png", ".heic", ".webp")

CATEGORIES = {
    "Images": IMAGE_EXT,
    "Documents": (".txt", ".pdf", ".docx"),
    "Programs": (".exe", ".msi"),
    "Archives": (".zip", ".rar", ".7z"),
    "Videos": (".avi", ".flv", ".m4v", ".mkv", ".mov", ".mp4"),
}

# ===================== SANITIZE =====================
def sanitize_name(name: str) -> str:
    if not name:
        return "UNKNOWN"

    name = name.replace("\x00", "")
    name = "".join(c for c in name if c not in r'<>:"/\|?*')
    name = name.strip()

    return name if name else "UNKNOWN"

# ===================== EXIF =====================
def get_exif(path):
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if not exif:
                return {}
            return {
                ExifTags.TAGS.get(k, k): str(v)
                for k, v in exif.items()
            }
    except:
        return {}

def normalize_folder(make, model):
    make = (make or "").upper()
    model = (model or "").upper()

    if "APPLE" in make:
        return model if model else "APPLE"
    if "CANON" in make:
        return "CANON"
    if "FUJIFILM" in make or "FUJI" in make:
        return "FUJIFILM"
    if "NIKON" in make:
        return "NIKON"
    if "OPPO" in make:
        return model if model else "OPPO"
    if "REALME" in make:
        return "REALME"
    if "SONY" in make:
        return "SONY"
    if "VIVO" in make:
        return "VIVO"
    if "XIAOMI" in make or "REDMI" in make:
        return "XIAOMI"
    if "NOKIA" in make:
        return "NOKIA"
    if "LAVA" in make:
        return "LAVA"

    return "UNKNOWN"

# ===================== VIDEO DEVICE =====================
def detect_video_device(filename):
    name = filename.upper()

    if name.startswith(("VID_", "MOV_", "IMG_")):
        return "IPHONE"

    if name.startswith(("MVI_", "DSC_")):
        return "CANON"

    if name.startswith(("PXL_",)):
        return "PIXEL"

    return "UNKNOWN"

# ===================== DUPLICATE IMAGE =====================
seen_metadata = set()

def metadata_signature(file_path, exif):
    try:
        size = os.path.getsize(file_path)
    except:
        size = 0

    return (
        exif.get("Make", "").upper().strip(),
        exif.get("Model", "").upper().strip(),
        exif.get("DateTimeOriginal", "").strip(),
        size
    )

# ===================== SAFE RENAME =====================
def safe_target(path: Path):
    if not path.exists():
        return path
    counter = 1
    while True:
        new_path = path.with_stem(f"{path.stem}_{counter}")
        if not new_path.exists():
            return new_path
        counter += 1

# ===================== CORE =====================
def get_category(ext):
    for cat, exts in CATEGORIES.items():
        if ext.lower() in exts:
            return cat
    return "Others"

def confirm_execution(total_files: int):
    print("\n⚠️ KONFIRMASI EKSEKUSI")
    print(f"📂 Source      : {SRC}")
    print(f"📁 Destination : {DST}")
    print(f"📦 Total file  : {total_files}")
    print(f"🧪 DRY RUN     : {DRY_RUN}")
    print("-" * 40)

    choice = input("Lanjutkan proses MOVE & ORGANIZE? (y/n): ").strip().lower()
    if choice not in ("y", "yes"):
        print("❌ Proses dibatalkan.")
        exit(0)

def main():
    files = [p for p in SRC.rglob("*") if p.is_file()]
    confirm_execution(len(files))

    with open(LOG_FILE, "w", newline="", encoding="utf-8") as log:
        writer = csv.writer(log)
        writer.writerow(["original_path", "new_path"])

        for file in tqdm(files, desc="📦 Organizing"):
            category = get_category(file.suffix)

            # ===== IMAGES =====
            if category == "Images":
                exif = get_exif(file)
                signature = metadata_signature(file, exif)

                if signature in seen_metadata:
                    if not DRY_RUN:
                        os.remove(file)
                    writer.writerow([str(file), "DELETED_DUPLICATE"])
                    continue

                seen_metadata.add(signature)

                folder = sanitize_name(
                    normalize_folder(
                        exif.get("Make"),
                        exif.get("Model")
                    )
                )
                target_dir = DST / "Images" / folder

            # ===== VIDEOS =====
            elif category == "Videos":
                device = sanitize_name(detect_video_device(file.name))
                target_dir = DST / "Videos" / device

            else:
                target_dir = DST / category

            try:
                target_dir.mkdir(parents=True, exist_ok=True)
            except ValueError as e:
                print(f"❌ Folder rusak dilewati: {target_dir}")
                continue

            target = safe_target(target_dir / sanitize_name(file.name))

            if not DRY_RUN:
                try:
                    shutil.move(str(file), str(target))
                except Exception as e:
                    print(f"❌ Error {file}: {e}")
                    continue

            writer.writerow([str(file), str(target)])

    print("\n✅ Selesai")
    print(f"📄 Log tersimpan di {LOG_FILE}")

if __name__ == "__main__":
    main()