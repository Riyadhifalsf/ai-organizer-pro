import os, re
from collections import Counter

ROOT = r"D:\Gallery\PICTURES\Uncategorized"
IMG = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".bmp", ".gif", ".psd", ".ico"}
VID = {".mov", ".mp4", ".m2ts", ".mts", ".avi", ".mkv"}
HEX32 = re.compile(r"^[0-9a-f]{32}(\.jpg)?$", re.I)
APPS = ["whatsapp", "instagram", "genshin", "hoyolab", "shopee", "discord",
        "chrome", "youtube", "docs", "trill", "tiktok", "facebook", "telegram",
        "browser", "mihoyo", "kmikbiihsaidnv"]

index = []
for folder in sorted(os.listdir(ROOT)):
    fp = os.path.join(ROOT, folder)
    if not os.path.isdir(fp):
        continue
    files = []
    for dp, dn, fn in os.walk(fp):
        for f in fn:
            if f == "LABEL.md":
                continue
            p = os.path.join(dp, f)
            try:
                files.append((f, os.path.getsize(p)))
            except OSError:
                pass
    n = len(files)
    mb = sum(s for _, s in files) / 1e6
    cats = Counter()
    apps = Counter()
    for f, s in files:
        fl = f.lower()
        ext = os.path.splitext(fl)[1]
        if ext in VID:
            cats["video"] += 1
        elif ext == ".livp":
            cats["live-photo"] += 1
        elif "screenshot" in fl:
            cats["screenshot"] += 1
        elif fl.startswith("com.") or "@2x" in fl or "@3x" in fl or HEX32.match(os.path.splitext(f)[0]):
            cats["cache-aplikasi"] += 1
        elif ext in IMG:
            cats["foto"] += 1
        else:
            cats["lain"] += 1
        for a in APPS:
            if a in fl:
                apps[a] += 1
    parts = [f"{v} {k}" for k, v in cats.most_common()]
    ringkas = ", ".join(parts) if parts else "kosong"
    appline = ""
    if apps:
        appline = "\nSinyal aplikasi: " + ", ".join(f"{k} ({v})" for k, v in apps.most_common(5)) + "."
    label = (f"# {folder}\n\n{n} file, {mb:.1f} MB.\n\nRincian: {ringkas}.{appline}\n\n"
             f"> Label otomatis — edit baris di bawah untuk nama momen:\n> **Momen:** \n")
    with open(os.path.join(fp, "LABEL.md"), "w", encoding="utf-8") as o:
        o.write(label)
    index.append((folder, n, mb, ringkas))
    print(f"{folder}: {n} file, {mb:.0f}MB | {ringkas}", flush=True)

with open(os.path.join(ROOT, "LABELS.md"), "w", encoding="utf-8") as o:
    o.write("# Label Uncategorized\n\n| Folder | File | Ukuran | Isi |\n|---|---|---|---|\n")
    for folder, n, mb, ringkas in index:
        o.write(f"| {folder} | {n} | {mb:.0f} MB | {ringkas} |\n")
print("INDEX DONE")
