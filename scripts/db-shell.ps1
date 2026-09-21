# db-shell.ps1 — shell interaktif SQLite (stdlib Python, tanpa install).
. "$PSScriptRoot\common.ps1"
Write-Host "DB: $($env:AIORG_DB)  (ketik .tables / .quit)"
python -c "import sqlite3,code;c=sqlite3.connect(r'''$($env:AIORG_DB)''');c.execute('PRAGMA journal_mode=WAL');print('tabel:',sorted(r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type=''table''\")));code.interact(local={'c':c,'db':c},banner='db-shell: objek koneksi = c / db')"
