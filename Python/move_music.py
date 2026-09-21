import os
import shutil

UNC = r"D:\Gallery\PICTURES\Uncategorized"
MUS = r"C:\Users\Babeh\Music"
MUSEXT = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".wma", ".aac", ".opus"}
c = {"music": 0, "zoom": 0, "collide": 0}


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
    return dst


for dp, dn, fn in os.walk(UNC):
    if "CORRUPT" in os.path.relpath(dp, UNC).split(os.sep):
        continue
    for f in fn:
        if os.path.splitext(f.lower())[1] not in MUSEXT:
            continue
        src = os.path.join(dp, f)
        if "Zoom" in src:
            move(src, os.path.join(MUS, "Zoom", f))
            c["zoom"] += 1
        else:
            move(src, MUS + os.sep + f)
            c["music"] += 1

print(c)
