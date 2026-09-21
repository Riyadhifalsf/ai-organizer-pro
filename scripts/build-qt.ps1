# build-qt.ps1 — configure + build Release aplikasi Qt + windeployqt.
. "$PSScriptRoot\common.ps1"
$QT = if ($env:QT_PREFIX) { $env:QT_PREFIX } else { "D:\Qt\6.8.3\msvc2022_64" }
if (-not (Test-Path (Join-Path $QT "bin\qmake.exe"))) {
  Write-Error "Qt tidak ditemukan di $QT (set env QT_PREFIX bila beda)."
  exit 1
}
cmd /c ('"' + $VCVARS + '" >nul && cmake -S "' + (Join-Path $PRO "qt") + '" -B "' + (Join-Path $PRO "qt\build") + '" -DCMAKE_PREFIX_PATH=' + $QT.Replace('\','/') + ' -DCMAKE_BUILD_TYPE=Release')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
cmd /c ('"' + $VCVARS + '" >nul && cmake --build "' + (Join-Path $PRO "qt\build") + '"')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& (Join-Path $QT "bin\windeployqt.exe") --release --no-translations --no-system-d3d-compiler (Join-Path $PRO "qt\build\AIOrganizerPro.exe")
Write-Host "Qt OK: qt\build\AIOrganizerPro.exe"
