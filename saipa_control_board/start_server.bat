@echo off
rem ============================================================
rem  Saipa Mashayekh - control board server (run on ONE computer)
rem  Double-click. Keep the window open while the board is used.
rem  Uses Windows PowerShell only - nothing needs to be installed.
rem ============================================================
cd /d "%~dp0"
title Saipa Mashayekh Board Server
set PORT=8080

if not exist "%~dp0server.ps1" goto notextracted
if not exist "%~dp0board.html" goto notextracted

rem One-time: let other computers on the network connect to this port.
netsh advfirewall firewall show rule name=SaipaMashayekhBoard >nul 2>nul
if errorlevel 1 (
  echo Allowing other computers to connect - click YES if Windows asks...
  powershell -NoProfile -Command "Start-Process netsh -ArgumentList 'advfirewall firewall add rule name=SaipaMashayekhBoard dir=in action=allow protocol=TCP localport=%PORT%' -Verb RunAs -Wait" >nul 2>nul
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0server.ps1" -Port %PORT%

echo.
echo ============================================================
echo  The server is NOT running now.
echo  If there is a red error above, send a photo of this window.
echo ============================================================
pause
exit /b

:notextracted
echo.
echo ============================================================
echo  The files are not extracted.
echo  You opened this file directly inside the ZIP / WinRAR window.
echo.
echo  1. Close this window.
echo  2. In WinRAR click "Extract To" and extract to a folder,
echo     for example  D:\SaipaBoard
echo  3. Open that folder and double-click start_server.bat there.
echo ============================================================
pause
