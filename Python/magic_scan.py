import os
from collections import Counter

PH = r"D:\Gallery\PICTURES\Photos"
TIFF_LE = b"II*\x00"
TIFF_BE = b"MM\x00*"
magic = Counter()
tiff_files = []
n = 0
for dp, dn, fn in os.walk(PH):
    for f in fn:
        if f in ("LABEL.md", "LABELS.md", "desktop.ini"):
            continue
        p = os.path.join(dp, f)
        n += 1
        try:
            with open(p, "rb") as h:
                head = h.read(16)
        except Exception:
            magic["unreadable"] += 1
            continue
        if head[:4] == b"\xff\xd8\xff\xe0" or head[:4] == b"\xff\xd8\xff\xe1" or head[:2] == b"\xff\xd8":
            magic["jpeg"] += 1
        elif head[:8] == b"\x89PNG\r\n\x1a\n":
            magic["png"] += 1
        elif head[:4] == b"RIFF" and head[8:12] == b"WEBP":
            magic["webp"] += 1
        elif head[4:12] in (b"ftypheic", b"ftypheix", b"ftyphevc", b"ftypmif1"):
            magic["heic"] += 1
        elif head[:4] in (TIFF_LE, TIFF_BE):
            magic["tiff-based"] += 1
            tiff_files.append(os.path.relpath(p, PH))
        else:
            magic["other:" + head[:6].hex()] += 1

print("total:", n)
print(magic.most_common(15))
print("tiff-based files:", len(tiff_files))
for t in tiff_files[:20]:
    print(" ", t[:100])
