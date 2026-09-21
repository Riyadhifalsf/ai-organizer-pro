# duplicates.ps1 — cari duplikat exact (JSON ringkas).
param([Parameter(Mandatory=$true)][string]$Folder, [long]$MinSize = 1)
. "$PSScriptRoot\common.ps1"
& $CORE_EXE duplicates $Folder --db $env:AIORG_DB --json --min-size $MinSize
