import os
import re
import shutil
from collections import Counter

TM = r"D:\Gallery\PICTURES\Uncategorized\Tanpa-Metadata"
CAM = r"D:\Gallery\PICTURES\Camera"
IMGEXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".bmp", ".gif"}
BRANDS = ["APPLE", "SAMSUNG", "OPPO", "VIVO", "XIAOMI", "REALME", "NOKIA",
          "SONY", "CANON", "NIKON", "LAVA", "FUJIFILM"]
TAIL_PAREN = re.compile(r"[\s_]*\(\d+\)\s*$")
TAIL_NUM = re.compile(r"_\d{1,4}$")

branddir = {d.upper(): os.path.join(CAM, d)
            for d in os.listdir(CAM)
            if os.path.isdir(os.path.join(CAM, d))}

c = Counter()


def strip_tail(s):
    s2 = TAIL_PAREN.sub("", s)
    if s2 != s:
        return s2
    return TAIL_NUM.sub("", s)


for dp, dn, fn in os.walk(TM):
    for f in fn:
        if f in ("LABEL.md", "LABELS.md"):
            continue
        if os.path.splitext(f.lower())[1] not in IMGEXT:
            continue
        if "screenshot" in f.lower():
            continue
        stem = os.path.splitext(f)[0]
        up = stem.upper()
        hit = [b for b in BRANDS if b in up]
        if len(hit) != 1:
            continue
        b = hit[0]
        if b not in branddir:
            continue
        rest = re.sub(r"\s+", "_", stem[up.find(b) + len(b):]).strip("_")
        cand = rest.upper()
        done = False
        for _ in range(5):
            for name in (b + "_" + cand, cand):
                t = os.path.join(branddir[b], name)
                if os.path.isdir(t):
                    dst = os.path.join(t, f)
                    if not os.path.exists(dst):
                        shutil.move(os.path.join(dp, f), dst)
                        c[b] += 1
                    else:
                        c["collide"] += 1
                    done = True
                    break
            if done:
                break
            nc = strip_tail(cand)
            if nc == cand:
                break
            cand = nc

print(dict(c))
