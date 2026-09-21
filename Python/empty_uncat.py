import os
import re
import shutil
from datetime import datetime
from collections import Counter
import pillow_heif
pillow_heif.register_heif_opener()
from PIL import Image
from PIL.ExifTags import TAGS

UNC = r"D:\Gallery\PICTURES\Uncategorized"
TM = os.path.join(UNC, "Tanpa-Metadata")
PHOTOS = r"D:\Gallery\PICTURES\Photos"
SHOT = r"D:\Gallery\PICTURES\Screenshots"
CAM = r"D:\Gallery\PICTURES\Camera"
VID = r"D:\Gallery\PICTURES\Videos"
BACKUP = r"D:\Gallery\BACKUP\Laptop"
VIDEXT = {".mov", ".mp4", ".m2ts", ".mts", ".avi", ".mkv"}
IMGEXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".bmp", ".gif"}
BRANDS = ["APPLE", "SAMSUNG", "OPPO", "VIVO", "XIAOMI", "REALME", "NOKIA",
          "SONY", "CANON", "NIKON", "LAVA", "FUJIFILM"]
TAIL_PAREN = re.compile(r"[\s_]*\(\d+\)\s*$")
TAIL_NUM = re.compile(r"_\d{1,4}$")

branddir = {d.upper(): os.path.join(CAM, d)
            for d in os.listdir(CAM)
            if os.path.isdir(os.path.join(CAM, d))}

c = Counter()
errs = []


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


def exif_of(p):
    try:
        ex = Image.open(p).getexif()
        return {TAGS.get(k, k): v for k, v in ex.items()} if ex else {}
    except Exception:
        return {}


def month_of(p, d):
    for k in ("DateTimeOriginal", "DateTime"):
        v = str(d.get(k, "") or "")
        m = re.match(r"(\d{4}):(\d{2})", v)
        if m:
            return f"{m.group(1)}-{m.group(2)}"
    return datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m")


def strip_tail(s):
    s2 = TAIL_PAREN.sub("", s)
    return s2 if s2 != s else TAIL_NUM.sub("", s)


def brand_target(stem):
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


def sort_file(src, m=None, no_brand=False):
    """Route satu file by type. Return True jika pindah."""
    f = os.path.basename(src)
    if f in ("LABEL.md", "LABELS.md"):
        return False
    fl = f.lower()
    ext = os.path.splitext(fl)[1]
    d = exif_of(src) if ext in IMGEXT else {}
    m = m or month_of(src, d)
    if "screenshot" in fl and ext in IMGEXT:
        move(src, os.path.join(SHOT, m, f))
        c["screenshot"] += 1
    elif ext in VIDEXT:
        move(src, os.path.join(VID, m, f))
        c["video"] += 1
    elif ext == ".livp":
        move(src, os.path.join(VID, m, f))
        c["livp"] += 1
    elif ext in IMGEXT and not no_brand:
        t = brand_target(os.path.splitext(f)[0])
        if t:
            move(src, os.path.join(t, f))
            c["brand"] += 1
        else:
            move(src, os.path.join(PHOTOS, m, f))
            c["foto"] += 1
    elif ext in IMGEXT:
        move(src, os.path.join(PHOTOS, m, f))
        c["foto"] += 1
    else:
        return False
    return True


# A. bulan Tanpa-Metadata -> Photos (wholesale, LABEL ikut)
for d in sorted(os.listdir(TM)):
    s = os.path.join(TM, d)
    if os.path.isdir(s) and re.match(r"^\d{4}-\d{2}$", d):
        move(s, os.path.join(PHOTOS, d))
        c["monthdir"] += 1

# B. broken/duplicate/Images -> Videos (wholesale)
for d in ("broken", "duplicate", "Images"):
    s = os.path.join(TM, d)
    if os.path.isdir(s):
        move(s, os.path.join(VID, d))
        c["viddir"] += 1

# C. Download/Pictures tree + test + root files
for base in [os.path.join(UNC, "Download", "Pictures"),
             os.path.join(UNC, "Download", "test"),
             os.path.join(UNC, "Download")]:
    if not os.path.isdir(base):
        continue
    for dp, dn, fn in os.walk(base):
        if ".thumbnails" in os.path.relpath(dp, base).split(os.sep):
            continue
        for f in fn:
            src = os.path.join(dp, f)
            if not os.path.isfile(src):
                continue
            m = None
            mm = re.search(r"Screenshot_(\d{4})-(\d{2})", f)
            if mm:
                m = f"{mm.group(1)}-{mm.group(2)}"
            try:
                if sort_file(src, m):
                    pass
                else:
                    c["stay"] += 1
            except Exception as e:
                c["error"] += 1
                errs.append(f"{src}: {e}")

# D. hapus .thumbnails (cache regenerable)
th = 0
for base in [os.path.join(UNC, "Download", "Pictures")]:
    for dp, dn, fn in os.walk(base):
        if os.path.basename(dp) == ".thumbnails":
            for f in fn:
                try:
                    os.remove(os.path.join(dp, f))
                    th += 1
                except Exception:
                    pass
c["thumb-del"] = th

# E. Laptop root: video/foto by type, rar+lain ke BACKUP
lp = os.path.join(UNC, "Laptop")
for f in sorted(os.listdir(lp)):
    src = os.path.join(lp, f)
    if not os.path.isfile(src):
        continue
    ext = os.path.splitext(f.lower())[1]
    try:
        if ext in VIDEXT or (ext in IMGEXT):
            m = None
            mm = re.search(r"(\d{4})[_-](\d{2})[_-]\d{2}", f)
            if mm and mm.group(1).startswith(("19", "20")):
                m = f"{mm.group(1)}-{mm.group(2)}"
            sort_file(src, m)
        else:
            move(src, os.path.join(BACKUP, f))
            c["backup"] += 1
    except Exception as e:
        c["error"] += 1
        errs.append(f"{src}: {e}")

print(dict(c))
for e in errs[:15]:
    print(e)
