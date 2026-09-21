import os
from collections import Counter
from PIL import Image
from PIL.ExifTags import TAGS

ROOT = r"D:\Gallery\PICTURES\Photos"
sw = Counter()
mm = Counter()
gps = 0
dt = 0
tot = 0
n = 0
for dp, dn, fn in os.walk(ROOT):
    for f in fn:
        if f in ("LABEL.md", "LABELS.md", "desktop.ini"):
            continue
        if os.path.splitext(f.lower())[1] not in (".jpg", ".jpeg", ".heic", ".heif"):
            continue
        tot += 1
        try:
            ex = Image.open(os.path.join(dp, f)).getexif()
        except Exception:
            continue
        if not ex:
            continue
        d = {TAGS.get(k, k): v for k, v in ex.items()}
        hit = False
        if d.get("Software"):
            sw[str(d["Software"]).strip()] += 1
            hit = True
        mk = str(d.get("Make", "") or "").strip()
        md = str(d.get("Model", "") or "").strip()
        if mk or md:
            mm[f"{mk} {md}".strip()] += 1
            hit = True
        if d.get("DateTimeOriginal") or d.get("DateTime"):
            dt += 1
        gi = d.get("GPSInfo")
        try:
            if gi is not None and not isinstance(gi, int) and len(gi) > 2:
                gps += 1
                hit = True
        except Exception:
            pass
        n += 1
        if tot % 5000 == 0:
            print(f"...{tot}", flush=True)

print(f"total dicek: {tot}, ada-exif: {n}, datetime: {dt}, gps: {gps}")
print("=== SOFTWARE ===")
for v, c in sw.most_common(25):
    print(f"{c}x :: {v[:110]}")
print("=== MAKE/MODEL ===")
for v, c in mm.most_common(25):
    print(f"{c}x :: {v[:110]}")
if not mm:
    print("(tidak ada Make/Model)")
