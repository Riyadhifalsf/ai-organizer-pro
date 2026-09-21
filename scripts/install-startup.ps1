# install-startup.ps1 / uninstall-startup.ps1 — autostart HKCU (tanpa admin).
# Dipakai: .\install-startup.ps1  |  .\uninstall-startup.ps1
param([switch]$Uninstall)
. "$PSScriptRoot\common.ps1"
$key = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$exe = Join-Path $PRO "AIOrganizerPro.exe"
if ($Uninstall) {
  Remove-ItemProperty -Path $key -Name "AIOrganizerPro" -ErrorAction SilentlyContinue
  Write-Host "Autostart dimatikan."
} else {
  Set-ItemProperty -Path $key -Name "AIOrganizerPro" -Value "`"$exe`""
  Write-Host "Autostart aktif -> $exe"
}
