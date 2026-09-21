import os
import subprocess
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from tqdm import tqdm
import shutil

# ================= CONFIG =================
TARGET_FOLDER = r"D:\output"  # folder yang mau discan
BROKEN_FOLDER = r"D:\output\broken"  # folder untuk file rusak
MAX_WORKERS = 4
LOG_FILE = "scan_report.txt"

IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff")
VIDEO_EXT = (".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv")

# ================= UTIL =================
def is_ffmpeg_available():
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except FileNotFoundError:
        return False

# ================= IMAGE CHECK =================
def check_image(file_path):
    try:
        with Image.open(file_path) as img:
            img.verify()
        return (file_path, "OK", "Image valid")
    except Exception as e:
        return (file_path, "BROKEN", f"Image error: {str(e)}")

# ================= VIDEO CHECK =================
def check_video(file_path):
    try:
        cmd = ["ffmpeg", "-v", "error", "-i", file_path, "-f", "null", "-"]
        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        error_output = process.stderr.strip()
        if error_output:
            return (file_path, "BROKEN", error_output[:300])
        else:
            return (file_path, "OK", "Video valid")
    except Exception as e:
        return (file_path, "BROKEN", f"FFmpeg exception: {str(e)}")

# ================= ROUTER =================
def process_file(file_path):
    file_lower = file_path.lower()
    if file_lower.endswith(IMAGE_EXT):
        return check_image(file_path)
    elif file_lower.endswith(VIDEO_EXT):
        return check_video(file_path)
    else:
        return None

# ================= SCAN =================
def scan_files(folder):
    all_files = []
    for root, _, files in os.walk(folder):
        for f in files:
            all_files.append(os.path.join(root, f))
    return all_files

# ================= MAIN =================
def main():
    print("🔍 Starting scan...\n")

    if not os.path.exists(TARGET_FOLDER):
        print(f"❌ Folder tidak ditemukan: {TARGET_FOLDER}")
        return

    if not is_ffmpeg_available():
        print("❌ FFmpeg tidak ditemukan! Install dulu.")
        return

    files = scan_files(TARGET_FOLDER)
    total = len(files)

    print(f"📂 Total file ditemukan: {total}\n")

    results = []
    ok_count = 0
    broken_count = 0

    os.makedirs(BROKEN_FOLDER, exist_ok=True)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_file, f): f for f in files}

        for future in tqdm(as_completed(futures), total=total, desc="🔄 Scanning", unit="file"):
            result = future.result()
            if result:
                results.append(result)

                status_icon = "✅" if result[1] == "OK" else "❌"
                print(f"{status_icon} {result[0]}")

                if result[1] == "OK":
                    ok_count += 1
                else:
                    broken_count += 1
                    # ===== pindahkan file rusak =====
                    try:
                        base_name = os.path.basename(result[0])
                        target_path = os.path.join(BROKEN_FOLDER, base_name)
                        counter = 1
                        while os.path.exists(target_path):
                            name, ext = os.path.splitext(base_name)
                            target_path = os.path.join(BROKEN_FOLDER, f"{name}_{counter}{ext}")
                            counter += 1
                        shutil.move(result[0], target_path)
                    except Exception as e:
                        print(f"❌ Gagal pindahkan file rusak: {e}")

    # ================= SAVE LOG =================
    with open(LOG_FILE, "w", encoding="utf-8") as log:
        log.write(f"SCAN REPORT\nTime: {datetime.now()}\n")
        log.write("=" * 50 + "\n\n")
        for r in results:
            log.write(f"{r[1]} | {r[0]}\n  -> {r[2]}\n\n")
        log.write("=" * 50 + "\n")
        log.write(f"TOTAL: {total}\nOK: {ok_count}\nBROKEN: {broken_count}\n")

    print("\n==============================")
    print(f"✅ OK: {ok_count}")
    print(f"❌ BROKEN: {broken_count} (dipindah ke {BROKEN_FOLDER})")
    print(f"📄 Report: {LOG_FILE}")
    print("==============================")

if __name__ == "__main__":
    main()