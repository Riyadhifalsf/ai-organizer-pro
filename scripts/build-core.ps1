# build-core.ps1 — configure + build Release + ctest.
. "$PSScriptRoot\common.ps1"
cmd /c ('"' + $VCVARS + '" >nul && cmake -S "' + $PRO + '" -B "' + $PRO + '\build" -G Ninja -DCMAKE_BUILD_TYPE=Release')
if (-not $?) { exit 1 }
cmd /c ('"' + $VCVARS + '" >nul && cmake --build "' + $PRO + '\build" --config Release')
if (-not $?) { exit 1 }
& (Join-Path $PRO "build\tests\aiorg_tests.exe")
if (-not $?) { exit 1 }
Copy-Item -Force (Join-Path $PRO "build\src\aiorganizer.exe") (Join-Path $PRO "aiorganizer.exe")
Write-Host "OK: aiorganizer.exe diperbarui."
