import os
import csv

UNC = r"D:\Gallery\PICTURES\Uncategorized"
COR = os.path.join(UNC, "CORRUPT")
TARGETS = {".pdf", ".doc", ".docx", ".txt", ".xls", ".xlsx", ".ppt", ".pptx",
           ".epub", ".csv", ".rtf", ".mp3", ".wav", ".flac", ".m4a", ".ogg",
           ".wma", ".aac", ".opus"}
LOG = r"D:\Gallery\REPORTS\opencode_corrupt_docs_delete_20260921.csv"
BLK = 4096


def points(sz):
    if sz <= BLK:
        return [0]
    return [0, sz // 4, sz // 2, 3 * sz // 4, max(0, sz - BLK)]


def all_zero(p):
    try:
        sz = os.path.getsize(p)
        if sz == 0:
            return "empty"
        with open(p, "rb") as h:
            for off in points(sz):
                h.seek(off)
                if any(h.read(BLK)):
                    return None
        return "zero"
    except Exception as e:
        return f"err:{e}"


rows = [["path", "bytes", "result"]]
deleted = kept = 0
n = 0
for dp, dn, fn in os.walk(COR):
    for f in fn:
        if os.path.splitext(f.lower())[1] not in TARGETS:
            continue
        p = os.path.join(dp, f)
        r = all_zero(p)
        n += 1
        if r in ("zero", "empty"):
            sz = os.path.getsize(p)
            try:
                os.remove(p)
                rows.append([os.path.relpath(p, UNC), str(sz), f"deleted-{r}"])
                deleted += 1
            except Exception as e:
                rows.append([os.path.relpath(p, UNC), "?", f"del-fail:{e}"])
                kept += 1
        else:
            rows.append([os.path.relpath(p, UNC), "?", "KEPT-has-data" if r is None else r])
            kept += 1
        if n % 20 == 0:
            print(f"...{n} del={deleted} kept={kept}", flush=True)

with open(LOG, "w", newline="", encoding="utf-8") as o:
    csv.writer(o).writerows(rows)
print(f"DONE deleted={deleted} kept={kept}")
