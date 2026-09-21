import os
import shutil
import zipfile

ROOT = r"D:\development\project-coding"
WEB2021 = os.path.join(ROOT, "__2021", "project-website-application")
WEB2024 = os.path.join(ROOT, "__2024", "project-website-application")
freed = 0


def ex(ziprel, destdir):
    src = os.path.join(ROOT, ziprel)
    with zipfile.ZipFile(src) as z:
        bad = z.testzip()
        assert bad is None, f"corrupt: {bad}"
        z.extractall(destdir)
    top = zipfile.ZipFile(src).namelist()[0].split("/")[0]
    print(f"extracted {ziprel} -> {os.path.relpath(destdir, ROOT)}/{top}")


def rm(rel):
    global freed
    p = os.path.join(ROOT, rel)
    freed += os.path.getsize(p)
    os.remove(p)
    print(f"deleted {rel}")


# 1. extract baru
ex("Features-website-master.zip", WEB2021)
ex("tebak-nada-master.zip", WEB2024)
ex("First-website-master.zip", WEB2021)
ex("belajar-navigasi-master.zip", WEB2021)
ex("website-portfolio-master.zip", WEB2021)
ex("__2024\\project-website-application\\wordpress.zip",
   os.path.join(WEB2024, "Wordpress-temp"))
# rapikan hasil extract wordpress 94MB (zip berisi folder 'wordpress')
tmp = os.path.join(WEB2024, "Wordpress-temp")
inner = os.listdir(tmp)
if inner == ["wordpress"]:
    shutil.move(os.path.join(tmp, "wordpress"),
                os.path.join(WEB2024, "Wordpress"))
    os.rmdir(tmp)
    print("wordpress-2024 placed")
else:
    print("wordpress-temp content:", inner)
ex("project-web-master.zip", WEB2024)

# 2. hapus duplikat root (isi sudah ada)
for z in ["belajar-PHP-master.zip", "belajar-css-master.zip",
          "rydhfl-landing-main.zip", "belajar-javascript-master.zip",
          "simple-web-article-master.zip", "belajar-HTML-master.zip",
          "databases-master.zip", "rydhfl-web-master.zip",
          "latihan-javascript-master.zip"]:
    rm(z)

# 3. hapus zip hasil extract
for z in ["Features-website-master.zip", "tebak-nada-master.zip",
          "First-website-master.zip", "belajar-navigasi-master.zip",
          "website-portfolio-master.zip",
          "__2024\\project-website-application\\wordpress.zip",
          "project-web-master.zip",
          "__2025\\Coding\\project-web-master.zip",
          "__2024\\project-website-application\\project-web-master.zip"]:
    rm(z)

# 4. hapus arsip WP 220/201MB (folder sudah ada)
for z in ["__2025\\Coding\\Wordpress\\wordpress.zip",
          "__2025\\Coding\\2023\\Wordpress\\wordpress.zip",
          "__2023\\project-website-application\\Wordpress\\wordpress.zip",
          "__2025\\Coding\\Wordpress\\wordpress.rar",
          "__2025\\Coding\\2023\\Wordpress\\wordpress.rar",
          "__2023\\project-website-application\\Wordpress\\wordpress.rar"]:
    rm(z)

print(f"FREED {freed/1e9:.2f} GB")
