import os
from collections import Counter
from PIL import Image
from PIL.ExifTags import TAGS

ROOT = r"D:\Gallery\PICTURES\Uncategorized"
sw = Counter()
mm = Counter()
tot = 0
for folder in sorted(os.listdir(ROOT)):
    fp = os.path.join(ROOT, folder)
    if not os.path.isdir(fp):
        continue
    for dp, dn, fn in os.walk(fp):
        for f in fn:
            if f == "LABEL.md":
                continue
            if os.path.splitext(f)[1].lower() not in (".jpg", ".jpeg", ".heic", ".heif"):
                continue
            tot += 1
            try:
                ex = Image.open(os.path.join(dp, f)).getexif()
            except Exception:
                continue
            if not ex:
                continue
            d = {TAGS.get(k, k): v for k, v in ex.items()}
            if d.get("Software"):
                sw[str(d["Software"]).strip()] += 1
            mk = str(d.get("Make", "") or "").strip()
            md = str(d.get("Model", "") or "").strip()
            if mk or md:
                mm[f"{mk} {md}".strip()] += 1
print(f"total dicek: {tot}")
print("=== SOFTWARE distinct ===")
for v, c in sw.most_common():
    print(f"{c}x :: {v[:120]}")
print("=== MAKE/MODEL distinct ===")
for v, c in mm.most_common():
    print(f"{c}x :: {v[:120]}")
if not mm:
    print("(tidak ada Make/Model sama sekali)")
