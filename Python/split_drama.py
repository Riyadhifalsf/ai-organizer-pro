import os
D = r"D:\Gallery\PICTURES\Drama"
R = r"D:\Gallery\PICTURES\RAW\Drama"
JPG = {".jpg", ".jpeg"}
del_d = del_r = skip = 0
# 1. non-JPG keluar dari Drama (hapus bila kembaran identik ada di RAW)
for dp, dn, fn in os.walk(D):
    for f in fn:
        ext = os.path.splitext(f)[1].lower()
        if ext in JPG:
            continue
        src = os.path.join(dp, f)
        rel = os.path.relpath(src, D)
        twin = os.path.join(R, rel)
        if os.path.isfile(twin) and os.path.getsize(twin) == os.path.getsize(src):
            os.remove(src)
            del_d += 1
        else:
            skip += 1
            print("SKIP (no identical twin):", rel)
# 2. JPG keluar dari RAW/Drama (hapus bila kembaran identik ada di Drama)
for dp, dn, fn in os.walk(R):
    for f in fn:
        ext = os.path.splitext(f)[1].lower()
        if ext not in JPG:
            continue
        src = os.path.join(dp, f)
        rel = os.path.relpath(src, R)
        twin = os.path.join(D, rel)
        if os.path.isfile(twin) and os.path.getsize(twin) == os.path.getsize(src):
            os.remove(src)
            del_r += 1
        else:
            skip += 1
            print("SKIP (no identical twin):", rel)
print(f"deleted-from-Drama={del_d} deleted-from-RAW={del_r} skipped={skip}")
# 3. struktur RAW/Wedding
os.makedirs(r"D:\Gallery\PICTURES\RAW\Wedding\04-03-2024", exist_ok=True)
print("RAW/Wedding ready")
