import sqlite3
c = sqlite3.connect(r"D:\results\reports\video.db")
for s in ("NORMAL", "LIGHT", "HEAVY", "SLOW"):
    print(s, c.execute("SELECT COUNT(*) FROM files WHERE status=?", (s,)).fetchone()[0])
print("deep", c.execute("SELECT COUNT(*) FROM deep").fetchone()[0])
print("verdicts", c.execute("SELECT verdict, COUNT(*) FROM deep GROUP BY verdict").fetchall())
