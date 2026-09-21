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
DL = os.path.join(UNC, "Download")
PHOTOS = r"D:\Gallery\PICTURES\Photos"
SHOT = r"D:\Gallery\PICTURES\Screenshots"
CAM = r"D:\Gallery\PICTURES\Camera"
VID = r"D:\Gallery\VIDEOS"
DOC = r"D:\Documents"
VIDEXT = {".mov", ".mp4", ".m2ts", ".mts", ".avi", ".mkv"}
IMGEXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".bmp", ".gif"}
DOCEXT = {".pdf", ".doc", ".docx", ".txt", ".xls", ".xlsx", ".ppt", ".pptx", ".epub"}
BRANDS = ["APPLE", "SAMSUNG", "OPPO", "VIVO", "XIAOMI", "REALME", "NOKIA",
          "SONY", "CANON", "NIKON", "LAVA", "FUJIFILM"]
TAIL_PAREN = re.compile(r"[\s_]*\(\d+\)\s*$")
TAIL_NUM = re.compile(r"_\d{1,4}$")

branddir = {d.upper(): os.path.join(CAM, d)
            for d in os.listdir(CAM)
            if os.path.isdir(os.path.join(CAM, d))}
c = Counter()


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


for dp, dn, fn in os.walk(DL):
    for f in fn:
        if f in ("LABEL.md", "LABELS.md", "desktop.ini"):
            continue
        src = os.path.join(dp, f)
        fl = f.lower()
        ext = os.path.splitext(fl)[1]
        try:
            if "screenshot" in fl and ext in IMGEXT:
                move(src, os.path.join(SHOT, f))
                c["screenshot"] += 1
            elif ext in VIDEXT:
                d = {}
                move(src, os.path.join(VID, month_of(src, d), f))
                c["video"] += 1
            elif ext in DOCEXT:
                move(src, os.path.join(DOC, f))
                c["doc"] += 1
            elif ext in IMGEXT:
                d = exif_of(src)
                t = brand_target(os.path.splitext(f)[0])
                if t:
                    move(src, os.path.join(t, f))
                    c["brand"] += 1
                else:
                    move(src, os.path.join(PHOTOS, month_of(src, d), f))
                    c["foto"] += 1
            else:
                c["stay"] += 1
        except Exception as e:
            c["error"] += 1
            print("ERR", src, e)

print(dict(c))
# bersih-bersih dir kosong
n = 0
for dp, dn, fn in os.walk(DL, topdown=False):
    if dp == DL:
        continue
    try:
        if not os.listdir(dp):
            os.rmdir(dp)
            n += 1
    except Exception:
        pass
print("empty-dirs:", n)
left = sum(1 for _, _, fs in os.walk(DL) for _ in fs)
print("left-in-Download:", left)
if not os.listdir(DL):
    os.rmdir(DL)
    print("Download removed")
print("uncat-root:", os.listdir(UNC))
