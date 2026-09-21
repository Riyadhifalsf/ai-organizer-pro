# db-query.ps1 — jalankan query baca ke DB terpadu (SELECT saja).
# Contoh: .\db-query.ps1 "SELECT kind,COUNT(*) FROM behavior_events GROUP BY kind"
param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Rest)
. "$PSScriptRoot\common.ps1"
$Sql = ($Rest -join ' ').Trim().Trim('"').Trim("'")
if ($Sql -notmatch '^\s*(SELECT|PRAGMA|EXPLAIN)\b') { Write-Error "Hanya query baca (SELECT/PRAGMA/EXPLAIN)."; exit 2 }
python -c "import sqlite3,sys;db=r'''$($env:AIORG_DB)''';c=sqlite3.connect('file:'+db+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;[print(dict(r)) for r in c.execute(sys.argv[1])]" $Sql
