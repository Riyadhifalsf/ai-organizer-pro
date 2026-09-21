import os
import csv

UNC = r"D:\Gallery\PICTURES\Uncategorized"
COR = os.path.join(UNC, "CORRUPT")
TARGETS = {".pdf", ".doc", ".docx", ".txt", ".xls", ".xlsx", ".ppt", ".pptx",
           ".epub", ".csv", ".rtf", ".mp3", ".wav", ".flac", ".m4a", ".ogg",
           ".wma", ".aac", ".opus"}
LOG = r"D:\Gallery\REPORTS\opencode_corrupt_docs_delete_20260921.csv"
BLK = 65536
NPTS = 64

rows = [["path", "bytes", "result"]]
deleted = kept = 0
n = 0
for dp, dn, fn in os.walk(COR):
    for f in fn:
        if os.path.splitext(f.lower())[1] not in TARGETS:
            continue
        p = os.path.join(dp, f)
        n += 1
        try:
            sz = os.path.getsize(p)
            bad = None
            with open(p, "rb") as h:
                head = h.read(4096)
                if not head:
                    bad = "empty"
                elif any(head):
                    bad = "has-head"
                else:
                    for i in range(NPTS):
                        h.seek(sz * i // NPTS)
                        if any(h.read(BLK)):
                            bad = "has-body"
                            break
            if bad in ("empty", None):
                os.remove(p)
                rows.append([os.path.relpath(p, UNC), str(sz),
                             "deleted-zero" if bad is None else "deleted-empty"])
                deleted += 1
            else:
                rows.append([os.path.relpath(p, UNC), str(sz), f"KEPT-{bad}"])
                kept += 1
        except Exception as e:
            rows.append([os.path.relpath(p, UNC), "?", f"error:{e}"])
            kept += 1
        if n % 20 == 0:
            print(f"...{n} del={deleted} kept={kept}", flush=True)

with open(LOG, "w", newline="", encoding="utf-8") as o:
    csv.writer(o).writerows(rows)
print(f"DONE deleted={deleted} kept={kept}")
