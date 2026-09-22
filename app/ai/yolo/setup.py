#!/usr/bin/env python3
"""setup.py — siapkan environment & folder sekali jalan.

    python setup.py            cek saja (tanpa install)
    python setup.py --install  install dependensi yang kurang (pip)
    python setup.py --gpu      info install PyTorch GPU (CUDA)
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent
NEED = ["ultralytics", "cv2", "PIL", "tqdm", "numpy"]
PIP_NAMES = {"cv2": "opencv-python", "PIL": "pillow"}


def check():
    return [m for m in NEED if importlib.util.find_spec(m) is None]


def make_dirs():
    sys.path.insert(0, str(PROJECT))
    import config as C
    dirs = [C.DATASET_RAW, C.DATASET, C.ERRORS_DIR, C.RESULTS,
            C.RESULTS / "scan", C.RESULTS / "sorted", C.RESULTS / "errors",
            C.RESULTS / "predictions"]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    print("folder OK")


def main():
    print("== ai-yolo-project setup ==")
    print("python:", sys.version.split()[0])
    make_dirs()
    missing = check()
    if not missing:
        print("dependensi OK: semua terinstall")
    else:
        print("KURANG:", ", ".join(missing))
        if "--install" in sys.argv:
            pkgs = [PIP_NAMES.get(m, m) for m in missing]
            print("install:", pkgs)
            r = subprocess.run([sys.executable, "-m", "pip", "install", *pkgs])
            if r.returncode == 0:
                missing = check()
                print("dependensi OK" if not missing else f"KURANG: {', '.join(missing)}")
            else:
                print("pip gagal, cek koneksi/PATH")
        else:
            print("jalankan: python setup.py --install")
    if "--gpu" in sys.argv:
        print("\nUntuk GPU NVIDIA (CUDA 12.1):")
        print("  pip install torch torchvision --index-url "
              "https://download.pytorch.org/whl/cu121")
        try:
            import torch
            print("torch:", torch.__version__, "| cuda:", torch.cuda.is_available())
        except ImportError:
            print("torch belum terinstall")


if __name__ == "__main__":
    main()
