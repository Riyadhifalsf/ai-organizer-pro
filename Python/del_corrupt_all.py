import os
import csv

COR = r"D:\Gallery\PICTURES\Uncategorized\CORRUPT"
UNC = r"D:\Gallery\PICTURES\Uncategorized"
LOG = r"D:\Gallery\REPORTS\opencode_corrupt_delete_20260921.csv"
BLK = 65536
NPTS = 64

rows = [["path", "bytes", "result"]]
deleted = kept = freed_logic = 0
n = 0
for dp, dn, fn in os.walk(COR):
    for f in fn:
        p = os.path.join(dp, f)
        n += 1
        try:
            sz = os.path.getsize(p)
            verdict = None
            with open(p, "rb") as h:
                head = h.read(4096)
                if not head:
                    verdict = "empty"
                elif any(head):
                    verdict = "has-head"
                else:
                    bad = False
                    for i in range(NPTS):
                        h.seek(sz * i // NPTS)
                        if any(h.read(BLK)):
                            bad = True
                            break
                    verdict = "has-body" if bad else None
            if verdict in ("empty", None):
                os.remove(p)
                rows.append([os.path.relpath(p, UNC), str(sz),
                             "deleted-empty" if verdict == "empty" else "deleted-zero"])
                deleted += 1
                freed_logic += sz
            else:
                rows.append([os.path.relpath(p, UNC), str(sz), f"KEPT-{verdict}"])
                kept += 1
        except Exception as e:
            rows.append([os.path.relpath(p, UNC), "?", f"error:{e}"])
            kept += 1
        if n % 200 == 0:
            print(f"...{n} del={deleted} kept={kept}", flush=True)

# bersihkan dir kosong
gone = 0
for dp, dn, fn in os.walk(COR, topdown=False):
    if dp == COR:
        continue
    try:
        if not os.listdir(dp):
            os.rmdir(dp)
            gone += 1
    except Exception:
        pass
try:
    if os.path.isdir(COR) and not os.listdir(COR):
        os.rmdir(COR)
        print("CORRUPT folder removed (empty)")
except Exception as e:
    print("CORRUPT kept:", e)

with open(LOG, "w", newline="", encoding="utf-8") as o:
    csv.writer(o).writerows(rows)
print(f"DONE checked={n} deleted={deleted} kept={kept} freed-logical={freed_logic/1e9:.1f}GB")
