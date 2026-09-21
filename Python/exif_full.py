import os
from PIL import Image
from PIL.ExifTags import TAGS

ROOT = r"D:\Gallery\PICTURES\Uncategorized"
tot = dt = sw = gps = withex = 0
per = {}
for folder in sorted(os.listdir(ROOT)):
    fp = os.path.join(ROOT, folder)
    if not os.path.isdir(fp):
        continue
    t = d = s = g = 0
    for dp, dn, fn in os.walk(fp):
        for f in fn:
            if f == "LABEL.md":
                continue
            if os.path.splitext(f)[1].lower() not in (".jpg", ".jpeg", ".heic", ".heif"):
                continue
            t += 1
            try:
                ex = Image.open(os.path.join(dp, f)).getexif()
            except Exception:
                continue
            if not ex:
                continue
            dd = {TAGS.get(k, k): v for k, v in ex.items()}
            hit = False
            if dd.get("DateTime"):
                d += 1; hit = True
            if dd.get("Software"):
                s += 1; hit = True
            gi = dd.get("GPSInfo")
            try:
                if gi is not None and not isinstance(gi, int) and len(gi) > 2:
                    g += 1; hit = True
            except Exception:
                pass
            if hit:
                withex += 1
    tot += t; dt += d; sw += s; gps += g
    per[folder] = (t, d, s, g)
print(f"TOTAL jpg dicek: {tot}")
print(f"DateTime: {dt} | Software: {sw} | GPS-koordinat: {gps}")
print("per folder (hanya yg ada metadata):")
for f, (t, d, s, g) in per.items():
    if d or s or g:
        print(f"  {f}: {t} file -> DateTime={d} Software={s} GPS={g}")
