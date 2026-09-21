import os, shutil
import pillow_heif
pillow_heif.register_heif_opener()
from PIL import Image
from PIL.ExifTags import TAGS

UNC = r"D:\Gallery\PICTURES\Uncategorized"
TM = os.path.join(UNC, "Tanpa-Metadata")
R6 = r"D:\Gallery\PICTURES\Camera\REALME\REALME_6"
R6S = r"D:\Gallery\PICTURES\Camera\REALME\REALME_6S_6I"
IMG = {".jpg", ".jpeg", ".heic", ".heif"}

os.makedirs(TM, exist_ok=True)
c_r6 = c_r6s = c_tm = c_err = 0
errs = []

def move(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        return False
    shutil.move(src, dst)
    return True

for folder in sorted(os.listdir(UNC)):
    fp = os.path.join(UNC, folder)
    if not os.path.isdir(fp) or folder in ("Tanpa-Metadata",):
        continue
    for dp, dn, fn in os.walk(fp):
        for f in fn:
            if f in ("LABEL.md", "LABELS.md"):
                continue
            src = os.path.join(dp, f)
            rel = os.path.relpath(src, UNC)
            try:
                dest = None
                if os.path.splitext(f)[1].lower() in IMG:
                    try:
                        ex = Image.open(src).getexif()
                        d = {TAGS.get(k, k): v for k, v in ex.items()} if ex else {}
                        sw = str(d.get("Software", "") or "")
                    except Exception:
                        sw = ""
                    if "RMX2001" in sw:
                        dest = os.path.join(R6, folder, f)
                        c_r6 += 1
                    elif "RMX2002" in sw:
                        dest = os.path.join(R6S, folder, f)
                        c_r6s += 1
                if dest is None:
                    dest = os.path.join(TM, rel)
                    c_tm += 1
                if not move(src, dest):
                    c_err += 1
                    errs.append(f"EXISTS: {rel}")
            except Exception as e:
                c_err += 1
                errs.append(f"ERR {rel}: {e}")
    print(f"{folder} done", flush=True)

print(f"REALME_6={c_r6} REALME_6S_6I={c_r6s} TANPA={c_tm} ERR={c_err}")
for e in errs[:20]:
    print(e)
