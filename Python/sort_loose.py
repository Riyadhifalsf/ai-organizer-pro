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
VIDEXT = {".mov", ".mp4", ".m2ts", ".mts", ".avi", ".mkv"}

branddir = {d.upper(): os.path.join(CAM, d)
            for d in os.listdir(CAM)
            if os.path.isdir(os.path.join(CAM, d))}

c = Counter()
errs = []


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


def move(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        return False
    shutil.move(src, dst)
    return True


for f in sorted(os.listdir(UNC)):
    src = os.path.join(UNC, f)
    if not os.path.isfile(src):
        continue
    ext = os.path.splitext(f.lower())[1]
    try:
        d = exif_of(src) if ext not in VIDEXT else {}
        m = month_of(src, d)
        done = False
        if ext in VIDEXT:
            done = move(src, os.path.join(VID, m, f))
            c["video" if done else "collide"] += 1
        elif ext == ".png":
            done = move(src, os.path.join(SHOT, m, f))
            c["screenshot" if done else "collide"] += 1
        else:
            mk = re.sub(r"\s+", "_", str(d.get("Make", "") or "").strip().upper())
            md = re.sub(r"\s+", "_", str(d.get("Model", "") or "").strip().upper())
            for cand_dir in ([mk + "_" + md] if mk and md else []) + ([md] if md else []):
                hit = None
                for bdir in branddir.values():
                    t = os.path.join(bdir, cand_dir)
                    if os.path.isdir(t):
                        hit = t
                        break
                if hit:
                    done = move(src, os.path.join(hit, f))
                    c["brand:" + cand_dir if done else "collide"] += 1
                    break
            if not done and (mk or md):
                c["brand-nomatch"] += 1
            if not done and not (mk or md):
                done = move(src, os.path.join(TM, m, f))
                c["foto" if done else "collide"] += 1
            if not done and (mk or md):
                done = move(src, os.path.join(TM, m, f))
                c["foto-nomatch" if done else "collide"] += 1
    except Exception as e:
        c["error"] += 1
        errs.append(f"{f}: {e}")

print(dict(c))
for e in errs[:15]:
    print(e)
