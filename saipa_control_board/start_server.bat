@echo off
rem ============================================================
rem  Saipa Mashayekh - control board server (run on ONE computer)
rem  Double-click. Keep the window open while the board is used.
rem  Uses Windows PowerShell only - nothing needs to be installed.
rem ============================================================
cd /d "%~dp0"
title Saipa Mashayekh Board Server
set PORT=8080

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
