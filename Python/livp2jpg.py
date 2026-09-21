import os, zipfile, traceback
import pillow_heif
pillow_heif.register_heif_opener()
from PIL import Image

DST = r"D:\Gallery\PICTURES\RAW\LIVP_TO_JPG"
ok = skip = fail = 0
files = sorted(f for f in os.listdir(DST) if f.lower().endswith(".livp"))
print(f"total livp: {len(files)}", flush=True)
for i, f in enumerate(files, 1):
    base = os.path.splitext(f)[0]
    jpg = os.path.join(DST, base + ".jpg")
    if os.path.isfile(jpg):
        skip += 1
        continue
    try:
        z = zipfile.ZipFile(os.path.join(DST, f))
        names = z.namelist()
        heics = [n for n in names if n.lower().endswith((".heic", ".heif"))]
        jpgs = [n for n in names if n.lower().endswith((".jpg", ".jpeg"))]
        if heics:
            img = Image.open(__import__("io").BytesIO(z.read(heics[0])))
            img.convert("RGB").save(jpg, quality=92)
        elif jpgs:
            with open(jpg, "wb") as o:
                o.write(z.read(jpgs[0]))
        else:
            raise RuntimeError(f"no image inside: {names[:5]}")
        ok += 1
    except Exception as e:
        fail += 1
        print(f"FAIL {f}: {e}")
    if i % 50 == 0:
        print(f"... {i}/{len(files)} ok={ok} skip={skip} fail={fail}", flush=True)
print(f"DONE ok={ok} skip={skip} fail={fail}")
