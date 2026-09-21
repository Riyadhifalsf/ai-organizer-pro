@echo off
REM PRO.cmd — dispatcher cepat: PRO <perintah> [args]
REM   gui | stats | scan FOLDER | dup FOLDER | doctor | migrate | db "SQL" | build
set PRO=%~dp0
if "%1"=="" goto help
if "%1"=="gui" powershell -NoProfile -ExecutionPolicy Bypass -File "%PRO%scripts\run-server.ps1" & goto :eof
if "%1"=="stats" powershell -NoProfile -ExecutionPolicy Bypass -File "%PRO%scripts\db-stats.ps1" & goto :eof
if "%1"=="scan" powershell -NoProfile -ExecutionPolicy Bypass -File "%PRO%scripts\scan.ps1" -Folder "%2" & goto :eof
if "%1"=="dup" powershell -NoProfile -ExecutionPolicy Bypass -File "%PRO%scripts\duplicates.ps1" -Folder "%2" & goto :eof
if "%1"=="doctor" powershell -NoProfile -ExecutionPolicy Bypass -File "%PRO%scripts\doctor.ps1" & goto :eof
if "%1"=="migrate" powershell -NoProfile -ExecutionPolicy Bypass -File "%PRO%scripts\migrate.ps1" & goto :eof
if "%1"=="db" call :rundb %* & goto :eof
if "%1"=="build" powershell -NoProfile -ExecutionPolicy Bypass -File "%PRO%scripts\build-core.ps1" & goto :eof
:help
echo pakai: PRO gui ^| stats ^| scan FOLDER ^| dup FOLDER ^| doctor ^| migrate ^| db "SQL" ^| build
goto :eof
:rundb
powershell -NoProfile -ExecutionPolicy Bypass -File "%PRO%scripts\db-query.ps1" %2 %3 %4 %5 %6 %7 %8 %9
goto :eof
