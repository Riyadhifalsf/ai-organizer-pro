# config.py — SATU-SATUNYA yang perlu kamu sentuh untuk mengatur semuanya.
from pathlib import Path

PROJECT = Path(__file__).resolve().parent

# ---------- DATA ----------
DATASET_RAW = PROJECT / "dataset_raw"   # data mentah per kelas (input train.py)
DATASET = PROJECT / "dataset"           # hasil split (dibuat otomatis)
ERRORS_DIR = PROJECT / "errors"         # file rusak hasil cleaning

# ---------- HASIL ----------
RESULTS = PROJECT / "results"           # semua output train.py & run.py
BEST_PT = RESULTS / "best.pt"           # bobot terbaik (dicopy otomatis)

# ---------- TRAIN ----------
SEED = 42
TRAIN_RATIO = 0.8
VAL_RATIO = 0.1
TEST_RATIO = 0.1                        # test: evaluasi akhir saja, jangan tuning
MODEL_SIZE = "m"                        # n/s/m/l — makin besar makin akurat, makin berat
EPOCHS = 150                            # + early stopping di bawah
PATIENCE = 25                           # berhenti bila val tak membaik 25 epoch
IMGSZ = 288                             # resolusi latih (224 cepat, 288 akurat)
BATCH = 16
MIN_SIZE = 128                          # buang gambar < 128px (dipindah ke errors/)
BLUR_LIMIT = 50                         # Laplacian var di bawah ini = blur
OVERSAMPLE_MIN = 200                    # kelas kecil digandakan s/d jumlah ini
LABEL_SMOOTHING = 0.1                   # anti overconfident
DROPOUT = 0.2                           # regularisasi head klasifikasi

# ---------- RUN / INFERENCE ----------
# Ensemble hanya valid untuk model dengan SET KELAS SAMA.
# train9/train10 cuma punya 4 kelas (label beda) -> JANGAN dipakai voting.
# Senjata utama: TTA (test-time augmentation: flip + multi-resolusi).
RUNS = PROJECT / "runs" / "classify"
ENSEMBLE_MODELS = []                    # isi bila sudah retrain ≥2 model 9-kelas
ENSEMBLE_WEIGHTS = []
MODEL = BEST_PT if BEST_PT.exists() else RUNS / "train15" / "weights" / "best.pt"
USE_ENSEMBLE = False                    # otomatis False bila ENSEMBLE_MODELS kosong
USE_TTA = True                          # flip + multi-resolusi (lambat ~3x, akurat +)
TTA_IMGSZ = (224, 288)
SCAN_DIR = RESULTS / "scan"             # taruh file yang mau disortir di sini
HIGH_TH = 0.90                          # >= ini = high confidence
LOW_TH = 0.80                           # < ini = low, sisanya medium
PRED_CONF = 0.5
