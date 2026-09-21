import os
from collections import Counter
from PIL import Image
from PIL.ExifTags import TAGS

PH = r"D:\Gallery\PICTURES\Photos"
SCREENS = {(1170, 2532), (2532, 1170), (1125, 2436), (2436, 1125),
           (828, 1792), (1792, 828), (1284, 2778), (2778, 1284),
           (1179, 2556), (2556, 1179), (1290, 2796), (2796, 1290),
           (1242, 2688), (2688, 1242), (750, 1334), (1334, 750),
           (640, 1136), (1080, 1920), (1080, 2400), (2400, 1080),
           (1080, 2340), (2340, 1080), (1440, 3200), (3200, 1440),
           (720, 1600), (1600, 720), (1080, 2408), (2408, 1080)}
CAMTAGS = {"Make", "Model", "ExposureTime", "FocalLength", "DateTimeOriginal",
           "ISOSpeedRatings", "PhotographicSensitivity"}

found = []
n_png = 0
for dp, dn, fn in os.walk(PH):
    for f in fn:
        if not f.lower().endswith(".png"):
            continue
        if "screenshot" in f.lower():
            continue
        p = os.path.join(dp, f)
        n_png += 1
        try:
            im = Image.open(p)
            im.load()
            w, h = im.size
            if (w, h) not in SCREENS:
                continue
            try:
                tags = {TAGS.get(k, k) for k in im.getexif().keys()}
            except Exception:
                tags = set()
            if tags & CAMTAGS:
                continue
            found.append(os.path.relpath(p, PH))
        except Exception:
            pass

print("png-checked(checks run inside walk), screenshot-candidates:", len(found))
with open(r"C:\Users\Babeh\AppData\Local\Temp\opencode\shot_candidates.txt",
          "w", encoding="utf-8") as o:
    o.write("\n".join(found))
for x in found[:15]:
    print(" ", x[:100])
