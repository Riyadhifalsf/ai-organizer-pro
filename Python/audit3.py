import sqlite3
c = sqlite3.connect(r"D:\results\reports\video.db")
rows = c.execute("SELECT path,size,detail FROM deep WHERE verdict='FATAL'").fetchall()
import os
print("fatal:", len(rows))
big = [(p, s, d) for p, s, d in rows if s and s > 500 * 1024 * 1024]
print("di atas 500MB:", len(big))
for p, s, d in rows:
    if "exit" not in d and not any(k in d.lower() for k in ("moov", "invalid data", "could not", "header missing", "unable")):
        print("RAGU n/a %s" % p)
        print("   ", d[:200])
