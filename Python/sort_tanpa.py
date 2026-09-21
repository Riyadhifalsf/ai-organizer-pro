import os, re, shutil
from collections import Counter

TM = r"D:\Gallery\PICTURES\Uncategorized\Tanpa-Metadata"
SHOT = r"D:\Gallery\PICTURES\Screenshots"
CAM = r"D:\Gallery\PICTURES\Camera"
VID = r"D:\Gallery\PICTURES\Videos"
LIVPDST = r"D:\Gallery\PICTURES\RAW\LIVP_TO_JPG"
VIDEXT = {".mov", ".mp4", ".m2ts", ".mts", ".avi", ".mkv"}
IMGEXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".bmp", ".gif"}
BRANDS = ["APPLE", "SAMSUNG", "OPPO", "VIVO", "XIAOMI", "REALME", "NOKIA",
          "SONY", "CANON", "NIKON", "LAVA", "FUJIFILM"]

# petakan folder brand (case-insensitive)
branddir = {}
for d in os.listdir(CAM):
    if os.path.isdir(os.path.join(CAM, d)):
        branddir[d.upper()] = os.path.join(CAM, d)

def brand_model(stem):
    up = stem.upper()
    for b in BRANDS:
        i = up.find(b)
        if i < 0:
            continue
        rest = re.sub(r"\s+", "_", stem[i + len(b):]).strip("_")
        return b, rest
    return None, None

def strip_tail(s):
    # hapus counter akhir satu level: ' (1)', '_1', '_001'
    s2 = re.sub(r"[\s_]*\(\d+\)\s*$", "", s)
    if s2 != s:
        return s2
    return re.sub(r"_\d{1,4}$", "", s)

c = Counter()
errs = []
def move(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        return False
    shutil.move(src, dst)
    return True

for folder in sorted(os.listdir(TM)):
    fp = os.path.join(TM, folder)
    if not os.path.isdir(fp):
        continue
    for dp, dn, fn in os.walk(fp):
        for f in fn:
            if f in ("LABEL.md", "LABELS.md"):
                continue
            src = os.path.join(dp, f)
            fl = f.lower()
            ext = os.path.splitext(fl)[1]
            try:
                if "screenshot" in fl:
                    dst = os.path.join(SHOT, folder, f)
                    ok = move(src, dst); c["screenshot" if ok else "collide"] += 1
                elif ext == ".livp":
                    dst = os.path.join(LIVPDST, f)
                    ok = move(src, dst); c["livp" if ok else "collide"] += 1
                elif ext in VIDEXT and folder not in ("broken", "duplicate", "Images"):
                    dst = os.path.join(VID, folder, f)
                    ok = move(src, dst); c["video" if ok else "collide"] += 1
                elif ext in IMGEXT:
                    b, rest = brand_model(os.path.splitext(f)[0])
                    moved = False
                    if b and b in branddir and rest:
                        cand = rest.upper()
                        for _ in range(4):
                            target = os.path.join(branddir[b], f"{b}_{cand}")
                            if os.path.isdir(target):
                                if move(src, os.path.join(target, f)):
                                    c[f"brand:{b}"] += 1
                                else:
                                    c["collide"] += 1
                                moved = True
                                break
                            nc = strip_tail(cand)
                            if nc == cand:
                                break
                            cand = nc
                    if not moved:
                        c["stay"] += 1
                else:
                    c["stay"] += 1
            except Exception as e:
                c["error"] += 1
                errs.append(f"{src}: {e}")
print(dict(c))
for e in errs[:15]:
    print(e)
