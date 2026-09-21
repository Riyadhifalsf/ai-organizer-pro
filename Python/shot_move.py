import os
import shutil
from collections import Counter

PH = r"D:\Gallery\PICTURES\Photos"
SHOT = r"D:\Gallery\PICTURES\Screenshots"
Q = os.path.join(PH, "_corrupt")
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


# a. 427 screenshot -> Screenshots flat
with open(r"C:\Users\Babeh\AppData\Local\Temp\opencode\shot_candidates.txt",
          encoding="utf-8") as o:
    cands = [l.strip() for l in o if l.strip()]
for rel in cands:
    src = os.path.join(PH, rel)
    if os.path.isfile(src):
        move(src, os.path.join(SHOT, os.path.basename(src)))
        c["screenshot"] += 1
    else:
        c["gone"] += 1

# b. fake-jpg + fragmen -> karantina jika sampah
from PIL import Image

suspects = [r"2024-08\2024_08_01_21_49_IMG_9346.JPG"]
for dp, dn, fn in os.walk(os.path.join(PH, "2026-09")):
    for f in fn:
        if f.startswith(".") and f.lower().endswith(".jpg"):
            suspects.append(os.path.relpath(os.path.join(dp, f), PH))
for rel in suspects:
    src = os.path.join(PH, rel)
    if not os.path.isfile(src):
        continue
    try:
        with open(src, "rb") as h:
            data = h.read()
        if len(data) == 0 or all(b == 0 for b in data):
            move(src, os.path.join(Q, os.path.basename(src)))
            c["quar-zero"] += 1
            continue
        try:
            im = Image.open(src)
            im.load()
            c["keep-opens"] += 1
        except Exception:
            move(src, os.path.join(Q, os.path.basename(src)))
            c["quar-broken"] += 1
    except Exception as e:
        c["error"] += 1
        print("ERR", rel, e)

print(dict(c))
