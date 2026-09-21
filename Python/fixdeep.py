import sqlite3
c = sqlite3.connect(r"D:\results\reports\video.db")
c.execute("UPDATE deep SET verdict='ERRORS' WHERE path IN "
          "(SELECT path FROM files WHERE detail='revisi: glitch ringan')")
print("deep updated:", c.total_changes)
c.commit()
print(c.execute("SELECT verdict, COUNT(*) FROM deep GROUP BY verdict").fetchall())
