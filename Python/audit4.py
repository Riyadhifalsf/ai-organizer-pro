import sqlite3
c = sqlite3.connect(r"D:\results\reports\video.db")
rows = c.execute("SELECT detail, COUNT(*) FROM files WHERE status='HEAVY' GROUP BY detail").fetchall()
print("macam detail heavy:", len(rows))
for d, n in sorted(rows, key=lambda x: -x[1])[:12]:
    print(n, "|", (d or "")[:110])
