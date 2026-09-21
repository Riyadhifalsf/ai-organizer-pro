import os
import shutil
from PIL import Image, ImageFile
import numpy as np
import imagehash
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
import warnings

# ================= CONFIG =================
INPUT_FOLDER = r"D:\ImageCollection\scan"  # Folder gambar sumber
ICON_REF_FOLDER = r"D:\ImageCollection\results\icons"   # Folder icon referensi
ICON_OUTPUT = r"D:\ImageCollection\results\icons\icon_sorted"
SCREENSHOT_OUTPUT = r"D:\ImageCollection\results\screenshots"
MAX_SIZE = (64, 64)        # Resize untuk perhitungan histogram
HIST_THRESHOLD = 0.7
HASH_THRESHOLD = 12
ICON_MAX_SIZE = 256        # icon maksimal
SCREENSHOT_MIN_SIZE = 800  # minimal resolusi untuk dianggap screenshot
LOG_FILE = "image_sort_log.txt"
# ===========================================

# Suppress PIL warnings
warnings.filterwarnings("ignore", category=UserWarning, module="PIL.Image")
ImageFile.LOAD_TRUNCATED_IMAGES = True

# ================= FUNCTIONS =================
def load_reference_images(ref_folder, max_size=MAX_SIZE):
    """Load semua reference icon, hitung histogram & phash"""
    ref_histograms = []
    ref_hashes = []
    for root, _, files in os.walk(ref_folder):
        for file in files:
            path = os.path.join(root, file)
            try:
                with Image.open(path) as img:
                    img = img.convert("RGB").resize(max_size)
                    ref_histograms.append(np.array(img.histogram()))
                    ref_hashes.append(imagehash.phash(img))
            except Exception as e:
                print(f"Warning load ref {file}: {e}")
    return ref_histograms, ref_hashes

def hist_similarity(hist1, hist2):
    hist1 = hist1 / (hist1.sum() + 1e-6)
    hist2 = hist2 / (hist2.sum() + 1e-6)
    return np.sum(np.minimum(hist1, hist2))

def is_icon(img_path, ref_histograms, ref_hashes):
    """Cek apakah gambar adalah icon"""
    try:
        with Image.open(img_path) as img:
            if img.width > ICON_MAX_SIZE or img.height > ICON_MAX_SIZE:
                return False
            img_small = img.convert("RGB").resize(MAX_SIZE)
            hist = np.array(img_small.histogram())
            img_hash = imagehash.phash(img_small)
            for ref_hist, ref_hash in zip(ref_histograms, ref_hashes):
                sim = hist_similarity(hist, ref_hist)
                diff = img_hash - ref_hash
                if sim >= HIST_THRESHOLD or diff <= HASH_THRESHOLD:
                    return True
    except:
        return False
    return False

def is_screenshot(img_path, ref_histograms):
    """Cek apakah gambar adalah screenshot berdasarkan ukuran & histogram"""
    try:
        fname_lower = os.path.basename(img_path).lower()
        # Jika nama file mengandung "screenshot", langsung dianggap screenshot
        if "screenshot" in fname_lower:
            return True
        with Image.open(img_path) as img:
            if img.width < SCREENSHOT_MIN_SIZE or img.height < SCREENSHOT_MIN_SIZE:
                return False
            img_small = img.convert("RGB").resize(MAX_SIZE)
            hist = np.array(img_small.histogram())
            # screenshot harus berbeda jauh dari semua icon reference
            max_sim = max([hist_similarity(hist, ref_hist) for ref_hist in ref_histograms] or [0])
            if max_sim < 0.5:
                return True
    except:
        return False
    return False

def sort_images(input_folder, icon_ref_folder, icon_output, screenshot_output, log_file=LOG_FILE):
    os.makedirs(icon_output, exist_ok=True)
    os.makedirs(screenshot_output, exist_ok=True)
    ref_histograms, ref_hashes = load_reference_images(icon_ref_folder)

    all_files = []
    for root, _, files in os.walk(input_folder):
        for file in files:
            if file.lower().endswith((".jpg",".jpeg",".png",".bmp")):
                all_files.append(os.path.join(root, file))

    print(f"Found {len(all_files)} images to check.")

    with Progress(TextColumn("[bold blue]{task.description}"), BarColumn(), TimeElapsedColumn()) as progress:
        task_id = progress.add_task("Sorting images...", total=len(all_files))
        for path in all_files:
            fname = os.path.basename(path)
            if is_icon(path, ref_histograms, ref_hashes):
                dest = os.path.join(icon_output, fname)
                shutil.copy2(path, dest)
                log_msg = f"[ICON] {fname} -> {icon_output}"
            elif is_screenshot(path, ref_histograms):
                dest = os.path.join(screenshot_output, fname)
                shutil.copy2(path, dest)
                log_msg = f"[SCREENSHOT] {fname} -> {SCREENSHOT_OUTPUT}"
            else:
                log_msg = f"[SKIP] {fname}"

            print(log_msg)
            with open(log_file,'a') as f:
                f.write(log_msg + '\n')
            progress.update(task_id, advance=1)

# ================= MAIN =================
if __name__ == "__main__":
    print("Mulai sorting images...")
    sort_images(INPUT_FOLDER, ICON_REF_FOLDER, ICON_OUTPUT, SCREENSHOT_OUTPUT)
    print("Selesai. Cek folder output dan file log.")