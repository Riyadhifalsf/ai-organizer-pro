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
SHOT = r"D:\Gallery\PICTURES\Screenshots"
CAM = r"D:\Gallery\PICTURES\Camera"
VID = r"D:\Gallery\PICTURES\Videos"
COR = os.path.join(UNC, "CORRUPT")
DCIM = os.path.join(UNC, "DCIM")
VIDEXT = {".mov", ".mp4", ".m2ts", ".mts", ".avi", ".mkv"}

branddir = {d.upper(): os.path.join(CAM, d)
            for d in os.listdir(CAM)
            if os.path.isdir(os.path.join(CAM, d))}

c = Counter()
errs = []


def move(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        return False
    shutil.move(src, dst)
    return True


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


def brand_target(f, d):
    mk = re.sub(r"\s+", "_", str(d.get("Make", "") or "").strip().upper())
    md = re.sub(r"\s+", "_", str(d.get("Model", "") or "").strip().upper())
    for cand in ([mk + "_" + md] if mk and md else []) + ([md] if md else []):
        for bdir in branddir.values():
            t = os.path.join(bdir, cand)
            if os.path.isdir(t):
                return t
    return None


# 1. DCIM/Screenshots -> Screenshots/YYYY-MM (dari nama file)
sd = os.path.join(DCIM, "Screenshots")
if os.path.isdir(sd):
    for f in os.listdir(sd):
        src = os.path.join(sd, f)
        if not os.path.isfile(src):
            continue
        m = re.search(r"IMG_(\d{4})(\d{2})\d{2}_", f)
        month = f"{m.group(1)}-{m.group(2)}" if m else month_of(src, exif_of(src))
        c["shot" if move(src, os.path.join(SHOT, month, f)) else "collide"] += 1

# 2. DCIM/Camera + file root DCIM -> brand/month
for base in [os.path.join(DCIM, "Camera"), DCIM]:
    if not os.path.isdir(base):
        continue
    for f in os.listdir(base):
        src = os.path.join(base, f)
        if not os.path.isfile(src):
            continue
        ext = os.path.splitext(f.lower())[1]
        d = exif_of(src) if ext not in VIDEXT else {}
        t = brand_target(f, d)
        if t and ext not in VIDEXT:
            c["brand" if move(src, os.path.join(t, f)) else "collide"] += 1
        elif ext in VIDEXT:
            c["video" if move(src, os.path.join(VID, month_of(src, d), f)) else "collide"] += 1
        else:
            c["foto" if move(src, os.path.join(TM, month_of(src, d), f)) else "collide"] += 1

# 3. DCIM/ScreenRecorder -> Videos/YYYY-MM (dari nama)
rd = os.path.join(DCIM, "ScreenRecorder")
if os.path.isdir(rd):
    for f in os.listdir(rd):
        src = os.path.join(rd, f)
        if not os.path.isfile(src):
            continue
        m = re.search(r"(\d{4})-(\d{2})-\d{2}", f)
        month = f"{m.group(1)}-{m.group(2)}" if m else month_of(src, {})
        c["rec" if move(src, os.path.join(VID, month, f)) else "collide"] += 1


def is_zero(p):
    try:
        with open(p, "rb") as h:
            head = h.read(4096)
        if not head:
            return "empty"
        if all(b == 0 for b in head):
            sz = os.path.getsize(p)
            with open(p, "rb") as h:
                h.seek(sz // 2)
                mid = h.read(4096)
            return "zero" if all(b == 0 for b in mid) else "headzero"
        return None
    except Exception as e:
        return f"err:{e}"


# 4. Download zero/empty + Documents.rar corrupt -> CORRUPT
for base in [os.path.join(UNC, "Download"),
             os.path.join(UNC, "Documents", "Documents.rar")]:
    if os.path.isfile(base):
        bases = [base]
    elif os.path.isdir(base):
        bases = [os.path.join(dp, f)
                 for dp, _, fs in os.walk(base) for f in fs]
    else:
        continue
    for src in bases:
        z = is_zero(src)
        if z in ("zero", "empty"):
            rel = os.path.relpath(src, UNC)
            c["corrupt" if move(src, os.path.join(COR, rel)) else "collide"] += 1

print(dict(c))
for e in errs[:10]:
    print(e)
