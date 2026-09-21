# db-stats.ps1 — ringkasan database terpadu.
. "$PSScriptRoot\common.ps1"
& $CORE_EXE stats --db $env:AIORG_DB
