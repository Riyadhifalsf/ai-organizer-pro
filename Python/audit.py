import sqlite3
c = sqlite3.connect(r"D:\results\reports\video.db")
rows = c.execute("SELECT path,detail FROM deep WHERE verdict='FATAL'").fetchall()
print("fatal:", len(rows))
from collections import Counter
kinds = Counter()
for p, d in rows:
    kinds[d[:80]] += 1
for k, n in kinds.most_common(10):
    print(n, "|", k)
