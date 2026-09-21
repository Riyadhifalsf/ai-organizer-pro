# run-server.ps1 — jalankan GUI modern (server Node + browser).
. "$PSScriptRoot\common.ps1"
if (-not (Test-Path $CORE_EXE)) { Write-Warning "core belum dibuild. Jalankan scripts\build-core.ps1 dulu." }
Start-Process -FilePath "node" -ArgumentList "`"$SERVER`"" -WorkingDirectory (Split-Path $SERVER) -WindowStyle Minimized
Start-Sleep -Seconds 2
Start-Process "http://127.0.0.1:$PORT/"
Write-Host "GUI: http://127.0.0.1:$PORT/  DB=$($env:AIORG_DB)"
