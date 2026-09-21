import os
import hashlib
from pathlib import Path
import csv
from tqdm import tqdm  # <-- untuk progress bar

# ===================== CONFIG =====================
SRC = Path(r"/mnt/wsl/PHYSICALDRIVE2p2/result")  # Ganti path WSL partisi Linux kamu
LOG_FILE = "deleted_duplicates.csv"
DRY_RUN = False  # True untuk hanya cek tanpa hapus
# ==================================================

def file_hash(file_path, chunk_size=8192):
    """Menghitung hash file (SHA256)"""
    h = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        print(f"❌ Error membaca file {file_path}: {e}")
        return None

def main():
    seen_hashes = {}
    files = [p for p in SRC.rglob("*") if p.is_file()]

    print(f"📂 Ditemukan {len(files)} file di {SRC}\n")

    with open(LOG_FILE, "w", newline="", encoding="utf-8") as log:
        writer = csv.writer(log)
        writer.writerow(["original_path", "deleted_path"])

        for file in tqdm(files, desc="🗂 Memeriksa file", unit="file"):
            h = file_hash(file)
            if not h:
                continue

            if h in seen_hashes:
                # File duplikat
                if not DRY_RUN:
                    try:
                        os.remove(file)
                        tqdm.write(f"🗑️ DUPLIKAT DIHAPUS: {file}")
                    except Exception as e:
                        tqdm.write(f"❌ Gagal hapus {file}: {e}")
                        continue
                else:
                    tqdm.write(f"[DRY RUN] DUPLIKAT TERDETEKSI: {file}")

                writer.writerow([str(seen_hashes[h]), str(file)])
            else:
                seen_hashes[h] = file

    print("\n✅ Selesai")
    print(f"📄 Log tersimpan di {LOG_FILE}")

if __name__ == "__main__":
    main()