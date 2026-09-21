import sqlite3
c = sqlite3.connect(r"D:\results\reports\video.db")
rows = c.execute("SELECT path,errcount,detail FROM deep WHERE verdict='FATAL'").fetchall()
for p, n, d in rows:
    print("n=%d %s" % (n, p))
    print("   ", d[:250])
