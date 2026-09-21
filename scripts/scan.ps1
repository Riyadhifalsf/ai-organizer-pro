# scan.ps1 — scan cepat core C++ (baca saja, aman).
param([Parameter(Mandatory=$true)][string]$Folder)
. "$PSScriptRoot\common.ps1"
& $CORE_EXE scan $Folder --db $env:AIORG_DB
