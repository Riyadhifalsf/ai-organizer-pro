"""Perbaiki FATAL palsu: tanpa kata fatal & exit 0 -> LIGHT (heavy->light)."""
import os
import shutil
import sqlite3

FATAL_KEYS = ("moov", "invalid data found", "could not find", "header missing",
              "not found", "unable to", "could not open", "no such file")

c = sqlite3.connect(r"D:\results\reports\video.db")
rows = c.execute("SELECT path,dest,detail FROM files WHERE status='HEAVY' AND dest<>''").fetchall()
print("heavy terpindah:", len(rows))
fixed = 0
for src, dst, detail in rows:
    d = (detail or "").lower().replace("deep: ", "")
    if d.startswith("exit") or any(k in d for k in FATAL_KEYS):
        continue  # FATAL asli
    if not os.path.isfile(dst):
        print("HILANG:", dst)
        continue
    light = dst.replace(os.sep + "heavy" + os.sep, os.sep + "light" + os.sep)
    os.makedirs(os.path.dirname(light), exist_ok=True)
    if os.path.exists(light):
        stem, ext = os.path.splitext(light)
        i = 1
        while os.path.exists("%s (%d)%s" % (stem, i, ext)):
            i += 1
        light = "%s (%d)%s" % (stem, i, ext)
    os.rename(dst, light)
    c.execute("UPDATE files SET status='LIGHT', dest=?, detail=? WHERE path=?",
              (light, "revisi: glitch ringan", src))
    fixed += 1
c.commit()
print("dikoreksi ke LIGHT:", fixed)
