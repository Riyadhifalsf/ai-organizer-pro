import os
import re
import shutil
from collections import Counter
from PIL import Image
from PIL.ExifTags import TAGS

PH = r"D:\Gallery\PICTURES\Photos"
CAM = r"D:\Gallery\PICTURES\Camera"
UNC = r"D:\Gallery\PICTURES\Uncategorized"
IMGEXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".bmp", ".gif"}
BRANDS = ["APPLE", "SAMSUNG", "OPPO", "VIVO", "XIAOMI", "REALME", "NOKIA",
          "SONY", "CANON", "NIKON", "LAVA", "FUJIFILM"]
TAIL_PAREN = re.compile(r"[\s_]*\(\d+\)\s*$")
TAIL_NUM = re.compile(r"_\d{1,4}$")
SKIPDIRS = {"_cache-ikon", "_corrupt"}

branddir = {d.upper(): os.path.join(CAM, d)
            for d in os.listdir(CAM)
            if os.path.isdir(os.path.join(CAM, d))}
os.makedirs(UNC, exist_ok=True)
c = Counter()


def strip_tail(s):
    s2 = TAIL_PAREN.sub("", s)
    return s2 if s2 != s else TAIL_NUM.sub("", s)


def brand_match(stem):
    up = stem.upper()
    hit = [b for b in BRANDS if b in up]
    if len(hit) != 1 or hit[0] not in branddir:
        return None
    b = hit[0]
    rest = re.sub(r"\s+", "_", stem[up.find(b) + len(b):]).strip("_").upper()
    cand = rest
    for _ in range(5):
        for name in (b + "_" + cand, cand):
            t = os.path.join(branddir[b], name)
            if os.path.isdir(t):
                return t
        nc = strip_tail(cand)
        if nc == cand:
            return None
        cand = nc
    return None


def move_flat(src):
    dst = os.path.join(UNC, os.path.basename(src))
    if os.path.exists(dst):
        base, ext = os.path.splitext(os.path.basename(dst))
        i = 2
        while os.path.exists(os.path.join(UNC, f"{base}_{i}{ext}")):
            i += 1
        dst = os.path.join(UNC, f"{base}_{i}{ext}")
        c["collide"] += 1
    shutil.move(src, dst)


for month in sorted(os.listdir(PH)):
    mp = os.path.join(PH, month)
    if not os.path.isdir(mp) or month in SKIPDIRS:
        continue
    for dp, dn, fn in os.walk(mp):
        for f in fn:
            if f in ("LABEL.md", "LABELS.md", "desktop.ini"):
                continue
            if os.path.splitext(f.lower())[1] not in IMGEXT:
                continue
            if "screenshot" in f.lower():
                continue
            src = os.path.join(dp, f)
            try:
                ex = Image.open(src).getexif()
                d = {TAGS.get(k, k): v for k, v in ex.items()} if ex else {}
            except Exception:
                d = {}
            U = " ".join([str(d.get("Make", "") or ""),
                          str(d.get("Model", "") or ""),
                          str(d.get("Software", "") or "")]).upper()
            mediatek = "MEDIATEK" in U
            if mediatek and not any(x in U for x in
                                    ("RMX200", "NARZO", "REALME 6", "22081283G", "ILCE")):
                move_flat(src)
                c["mediatek"] += 1
                continue
            t = brand_match(os.path.splitext(f)[0])
            if t:
                dst = os.path.join(t, os.path.basename(src))
                if os.path.exists(dst):
                    base, ext = os.path.splitext(os.path.basename(dst))
                    i = 2
                    while os.path.exists(os.path.join(t, f"{base}_{i}{ext}")):
                        i += 1
                    dst = os.path.join(t, f"{base}_{i}{ext}")
                    c["collide"] += 1
                shutil.move(src, dst)
                c["brand"] += 1
            elif any(b in f.upper() for b in BRANDS):
                move_flat(src)
                c["unmatchable"] += 1

print(dict(c))
print("uncat-total:",
      sum(1 for f in os.listdir(UNC)
          if os.path.isfile(os.path.join(UNC, f))))
