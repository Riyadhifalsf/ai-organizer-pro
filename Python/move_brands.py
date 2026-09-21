import os
import shutil
from collections import Counter
from PIL import Image
from PIL.ExifTags import TAGS

PH = r"D:\Gallery\PICTURES\Photos"
CAM = r"D:\Gallery\PICTURES\Camera"

T = {
    "REALME_6": os.path.join(CAM, "REALME", "REALME_6"),
    "REALME_6S_6I": os.path.join(CAM, "REALME", "REALME_6S_6I"),
    "REALME_NARZO": os.path.join(CAM, "REALME", "REALME_NARZO"),
    "REDMI_PAD": os.path.join(CAM, "XIAOMI", "REDMI_PAD"),
    "SONY_A7R3": os.path.join(CAM, "SONY", "SONY_ILCE_7RM3A"),
}
c = Counter()


def norm(s):
    return str(s or "").replace("\x00", " ").split()


def move(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        base, ext = os.path.splitext(os.path.basename(dst))
        i = 2
        while os.path.exists(os.path.join(os.path.dirname(dst), f"{base}_{i}{ext}")):
            i += 1
        dst = os.path.join(os.path.dirname(dst), f"{base}_{i}{ext}")
        c["collide"] += 1
    shutil.move(src, dst)


for month in sorted(os.listdir(PH)):
    mp = os.path.join(PH, month)
    if not os.path.isdir(mp):
        continue
    for dp, dn, fn in os.walk(mp):
        for f in fn:
            if f in ("LABEL.md", "LABELS.md", "desktop.ini"):
                continue
            if os.path.splitext(f.lower())[1] not in (".jpg", ".jpeg", ".heic", ".heif"):
                continue
            src = os.path.join(dp, f)
            try:
                ex = Image.open(src).getexif()
            except Exception:
                continue
            if not ex:
                continue
            d = {TAGS.get(k, k): v for k, v in ex.items()}
            toks = (norm(d.get("Make")) + norm(d.get("Model"))
                    + norm(d.get("Software")))
            U = " ".join(toks).upper()
            dest = None
            if "RMX2002" in U:
                dest = "REALME_6S_6I"
            elif "NARZO" in U:
                dest = "REALME_NARZO"
            elif "RMX2001" in U or "REALME 6" in U:
                dest = "REALME_6"
            elif "22081283G" in U:
                dest = "REDMI_PAD"
            elif "ILCE-7RM3A" in U or "ILCE7RM3A" in U:
                dest = "SONY_A7R3"
            if dest:
                move(src, os.path.join(T[dest], month, f))
                c[dest] += 1

print(dict(c))
