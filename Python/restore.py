"""Kembalikan file yang salah pindah akibat bug WinError 2 (detail cocok)."""
import os
import shutil
import sqlite3

c = sqlite3.connect(r"D:\results\reports\video.db")
rows = c.execute("SELECT path,dest FROM files WHERE detail LIKE '%WinError 2%' AND dest<>''").fetchall()
print("kandidat restore:", len(rows))
ok, gagal = 0, []
for src, dst in rows:
    # src = lokasi asal (Videos), dst = lokasi broken. Kembalikan dst -> src.
    if not os.path.isfile(dst):
        gagal.append((src, "dest hilang: %s" % dst))
        continue
    os.makedirs(os.path.dirname(src), exist_ok=True)
    try:
        if os.path.exists(src):
            stem, ext = os.path.splitext(src)
            i = 1
            while os.path.exists("%s (%d)%s" % (stem, i, ext)):
                i += 1
            src = "%s (%d)%s" % (stem, i, ext)
        os.rename(dst, src)
        ok += 1
    except OSError:
        try:
            shutil.move(dst, src)
            ok += 1
        except Exception as e:
            gagal.append((src, str(e)))
print("kembali:", ok, "gagal:", len(gagal))
for g in gagal[:10]:
    print("  ", g)
# tandai ulang agar di-scan ulang deep berikutnya
c.execute("DELETE FROM deep WHERE path IN (SELECT path FROM files WHERE detail LIKE '%WinError 2%')")
c.execute("UPDATE files SET status='STALE', dest='' WHERE detail LIKE '%WinError 2%'")
c.commit()
print("DB ditandai ulang.")
