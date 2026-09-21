import sqlite3
c = sqlite3.connect(r"D:\results\reports\video.db")
rows = c.execute("SELECT path,detail FROM files WHERE status='HEAVY' AND dest LIKE '%broken%heavy%Videos%MVI%'").fetchall()
print(len(rows))
for r in rows[:5]:
    print(r[0])
    print("   ", r[1][:200])
