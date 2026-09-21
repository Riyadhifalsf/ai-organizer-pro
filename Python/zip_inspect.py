import os
import zipfile

ROOT = r"D:\development\project-coding"
ZIPS = [
    "Features-website-master.zip",
    "belajar-PHP-master.zip",
    "tebak-nada-master.zip",
    "First-website-master.zip",
    "belajar-css-master.zip",
    "belajar-navigasi-master.zip",
    "rydhfl-landing-main.zip",
    "belajar-javascript-master.zip",
    "simple-web-article-master.zip",
    "belajar-HTML-master.zip",
    "databases-master.zip",
    "website-portfolio-master.zip",
    "rydhfl-web-master.zip",
    "latihan-javascript-master.zip",
    "project-web-master.zip",
    "__2025\\Coding\\project-web-master.zip",
    "__2024\\project-website-application\\project-web-master.zip",
    "__2025\\Coding\\wordpress.zip",
    "__2024\\project-website-application\\wordpress.zip",
]

for rel in ZIPS:
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        print(f"MISSING {rel}")
        continue
    sz = os.path.getsize(p)
    try:
        z = zipfile.ZipFile(p)
        names = z.namelist()
        tops = sorted({n.split("/")[0] for n in names if "/" in n})
        print(f"{sz//1024}KB {rel} | {len(names)} entries | top: {tops[:3]}")
    except Exception as e:
        print(f"BAD {rel} ({sz} bytes): {e}")
