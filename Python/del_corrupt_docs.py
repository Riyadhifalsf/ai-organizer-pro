import os
import csv
from datetime import datetime

UNC = r"D:\Gallery\PICTURES\Uncategorized"
COR = os.path.join(UNC, "CORRUPT")
TARGETS = {".pdf", ".doc", ".docx", ".txt", ".xls", ".xlsx", ".ppt", ".pptx",
           ".epub", ".csv", ".rtf", ".mp3", ".wav", ".flac", ".m4a", ".ogg",
           ".wma", ".aac", ".opus"}
LOG = r"D:\Gallery\REPORTS\opencode_corrupt_docs_delete_20260921.csv"

rows = [["path", "bytes", "result"]]
deleted = kept = 0
for dp, dn, fn in os.walk(COR):
    for f in fn:
        if os.path.splitext(f.lower())[1] not in TARGETS:
            continue
        p = os.path.join(dp, f)
        try:
            with open(p, "rb") as h:
                data = h.read()
            if len(data) == 0 or all(b == 0 for b in data):
                os.remove(p)
                rows.append([os.path.relpath(p, UNC), str(len(data)), "deleted-zero"])
                deleted += 1
            else:
                rows.append([os.path.relpath(p, UNC), str(len(data)), "KEPT-has-data"])
                kept += 1
        except Exception as e:
            rows.append([os.path.relpath(p, UNC), "?", f"error:{e}"])
            kept += 1

with open(LOG, "w", newline="", encoding="utf-8") as o:
    csv.writer(o).writerows(rows)
print(f"deleted={deleted} kept={kept} log={LOG}")
