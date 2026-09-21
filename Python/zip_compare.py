import os
import zipfile
from datetime import datetime

ROOT = r"D:\development\project-coding"


def dir_stats(path):
    n = sz = 0
    for dp, dn, fn in os.walk(path):
        # skip heavy
        dn[:] = [d for d in dn if d not in
                 ("node_modules", ".git", "build", "vendor")]
        for f in fn:
            n += 1
            try:
                sz += os.path.getsize(os.path.join(dp, f))
            except OSError:
                pass
    return n, sz


def find_dirs(name):
    """cari folder bernama 'name' (pruned walk, top 3 level saja)."""
    hits = []
    for y in sorted(os.listdir(ROOT)):
        yp = os.path.join(ROOT, y)
        if not os.path.isdir(yp):
            continue
        for dp, dn, fn in os.walk(yp):
            depth = os.path.relpath(dp, yp).count(os.sep)
            if depth > 2:
                dn[:] = []
                continue
            if name in dn:
                hits.append(os.path.join(dp, name))
    return hits


ZIPS = ["Features-website-master.zip", "belajar-PHP-master.zip",
        "tebak-nada-master.zip", "First-website-master.zip",
        "belajar-css-master.zip", "belajar-navigasi-master.zip",
        "rydhfl-landing-main.zip", "belajar-javascript-master.zip",
        "simple-web-article-master.zip", "belajar-HTML-master.zip",
        "databases-master.zip", "website-portfolio-master.zip",
        "rydhfl-web-master.zip", "latihan-javascript-master.zip"]

for rel in ZIPS:
    p = os.path.join(ROOT, rel)
    z = zipfile.ZipFile(p)
    infos = [i for i in z.infolist() if not i.is_dir()]
    top = infos[0].filename.split("/")[0] if infos else "?"
    zsize = sum(i.file_size for i in infos)
    dates = sorted(i.date_time for i in infos)
    span = f"{dates[0][:3]}..{dates[-1][:3]}" if dates else "?"
    hits = find_dirs(top)
    line = f"{rel} | zip:{len(infos)}f/{zsize//1024}KB/{span} | top={top}"
    for h in hits[:3]:
        n, s = dir_stats(h)
        mark = "SAMA" if (n == len(infos)) else "beda"
        line += f" | {mark} dir={os.path.relpath(h, ROOT)}:{n}f/{s//1024}KB"
    if not hits:
        line += " | TIDAK-ADA -> baru"
    print(line)
