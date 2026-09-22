# doctor.ps1 — cek kesehatan lingkungan + DB (bacaan saja).
. "$PSScriptRoot\common.ps1"
function ok($n, $c) { if ($c) { Write-Host "[OK] $n" } else { Write-Host "[!!] $n" } }
ok "python+PIL+watchdog" ((python -c "import PIL,watchdog;print(1)" 2>$null) -eq '1')
ok "cmake" ((cmake --version) -match 'cmake version')
ok "VS BuildTools" (Test-Path $VCVARS)
ok "core exe" (Test-Path $CORE_EXE)
ok "aplikasi Qt" (Test-Path (Join-Path $PRO "AIOrganizerPro.exe"))
ok "ffmpeg" (Test-Path (Join-Path $PRO "bin\ffmpeg\ffprobe.exe"))
ok "icon" (Test-Path (Join-Path $PRO "assets\icon.ico"))
if (Test-Path $env:AIORG_DB) {
  $v = python -c "import sqlite3;c=sqlite3.connect(r'''$($env:AIORG_DB)''');print(c.execute('PRAGMA user_version').fetchone()[0])"
  ok "DB v4 ($v)" ($v -eq '4')
} else { Write-Host "[--] DB belum ada (dibuat otomatis saat scan/migrate)" }
& $CORE_EXE stats --db $env:AIORG_DB 2>$null | Select-Object -First 3
