import os
from PIL import Image
from PIL.ExifTags import TAGS

ROOT = r"D:\Gallery\PICTURES\Uncategorized"
PER_FOLDER = 12
total = with_exif = with_model = with_gps = with_dt = 0
folders_with = []
checked_folders = 0
for folder in sorted(os.listdir(ROOT)):
    fp = os.path.join(ROOT, folder)
    if not os.path.isdir(fp):
        continue
    # kumpulkan file gambar sampai kuota
    cands = []
    for dp, dn, fn in os.walk(fp):
        for f in fn:
            if f == "LABEL.md":
                continue
            if os.path.splitext(f)[1].lower() in (".jpg", ".jpeg", ".heic", ".heif", ".png", ".webp"):
                cands.append(os.path.join(dp, f))
                if len(cands) >= 60:
                    break
        if len(cands) >= 60:
            break
    if not cands:
        continue
    step = max(1, len(cands) // PER_FOLDER)
    sample = cands[::step][:PER_FOLDER]
    checked_folders += 1
    f_with = 0
    for p in sample:
        total += 1
        try:
            im = Image.open(p)
            ex = im.getexif()
            if not ex:
                continue
            with_exif += 1
            f_with += 1
            d = {TAGS.get(k, k): v for k, v in ex.items()}
            if d.get("DateTimeOriginal"):
                with_dt += 1
            if d.get("Model") or d.get("Make"):
                with_model += 1
            if d.get("GPSInfo"):
                g = d["GPSInfo"]
                try:
                    has_coord = len(g) >= 4 if hasattr(g, "__len__") else True
                except Exception:
                    has_coord = False
                if has_coord and not (isinstance(g, int)):
                    with_gps += 1
        except Exception:
            pass
    if f_with:
        folders_with.append((folder, f_with, len(sample)))
print(f"folder dicek: {checked_folders}, file dicek: {total}")
print(f"ada EXIF: {with_exif}, DateTimeOriginal: {with_dt}, Model/Make: {with_model}, GPS: {with_gps}")
print("folder berisi metadata:")
for f, w, s in folders_with:
    print(f"  {f}: {w}/{s}")
