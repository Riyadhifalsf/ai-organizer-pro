# retry-locked.ps1 — ulangi karantina grup duplikat yang kemarin terkunci sistem.
# Jalankan SETELAH restart (saat lock sudah lepas). Aman: hanya memindah file
# yang pasangannya masih ada, terverifikasi + rollback tercatat seperti biasa.
. "$PSScriptRoot\common.ps1"
$DB = Join-Path $PRO "data\dupfind.db"
if (-not (Test-Path $DB)) { Write-Error "DB tidak ada: $DB"; exit 1 }

Write-Host "Mencari grup duplikat yang tersisa..."
$raw = & $CORE_EXE duplicates "D:\results\Images" --db $DB --json --actor cli | Out-String
$line = ($raw -split "`r?`n" | Where-Object { $_.TrimStart().StartsWith("{") } | Select-Object -Last 1)
$d = $line | ConvertFrom-Json
$groups = @($d.groups | Where-Object {
  ($_.paths | ForEach-Object { Test-Path -LiteralPath $_ }) -notcontains $false
})
Write-Host ("Sisa {0} grup (kedua file masih ada)." -f $groups.Count)
if ($groups.Count -eq 0) { Write-Host "Beres - tidak ada sisa."; exit 0 }

New-Item -ItemType Directory -Force -Path "D:\results\duplicate" | Out-Null
$ok = 0; $fail = @()
foreach ($g in $groups) {
  $keep = ($g.paths | Sort-Object)[0]
  $out = & $CORE_EXE move-approved --db $DB --group $g.id --keep $keep --to "D:\results\duplicate" --json --actor cli | Out-String
  $o = ($out -split "`r?`n" | Where-Object { $_.TrimStart().StartsWith("{") } | Select-Object -Last 1) | ConvertFrom-Json
  if ($o.ok -and $o.moved.Count -gt 0) { $ok++; Write-Host ("OK grup {0}: {1}" -f $g.id, $o.moved[0]) }
  else { $fail += $g.id; Write-Host ("MASIH TERKUNCI grup {0}" -f $g.id) }
}
Write-Host ("Selesai: {0} pindah, {1} masih terkunci: {2}" -f $ok, $fail.Count, ($fail -join ","))
