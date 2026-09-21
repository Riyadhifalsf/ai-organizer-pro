# migrate.ps1 — impor data lama (behavior.db + doc CSV) ke DB terpadu.
. "$PSScriptRoot\common.ps1"
python (Join-Path $PRO "tools\migrate_unified.py")
