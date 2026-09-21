import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

# KOREKSI: clean_dataset.py (hapus permanen) dikeluarkan dari pipeline.
# Pembersih resmi: clean_and_move_image_error.py (pindah ke errors/, aman).
STEPS = [
    "clean_and_move_image_error.py",
    "split_dataset.py",
    "train.py",
    "predict_and_collect_errors.py",
]

for i, script in enumerate(STEPS, 1):
    print(f"STEP {i}: {script}...")
    r = subprocess.run([sys.executable, str(PROJECT_ROOT / script)])
    if r.returncode != 0:
        print(f"❌ Berhenti di {script} (exit {r.returncode})")
        raise SystemExit(r.returncode)

print("🔥 SELESAI")
