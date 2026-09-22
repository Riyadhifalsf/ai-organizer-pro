# common.ps1 — dimuat semua script Pro. Menentukan PRO root + path alat.
$PRO = Split-Path -Parent $PSScriptRoot
$env:AIORG_DB = if ($env:AIORG_DB) { $env:AIORG_DB } else { Join-Path $PRO "data\aiorganizer.db" }
$CORE_EXE = if (Test-Path (Join-Path $PRO "aiorganizer.exe")) { Join-Path $PRO "aiorganizer.exe" } else { Join-Path $PRO "build\src\aiorganizer.exe" }
# Toolchain VS Build Tools (pindah dari D:\tools).
$TOOLS_VS = "D:\development\environment-files\VS_BuildTools\VS"
$VCVARS = Join-Path $TOOLS_VS "VC\Auxiliary\Build\vcvars64.bat"
