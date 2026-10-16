@echo off
rem ============================================================
rem  Saipa Mashayekh - control board server (run on ONE computer)
rem  Double-click. Keep the window open while the board is used.
rem ============================================================
cd /d "%~dp0"
title Saipa Mashayekh Board Server
set PORT=8080

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY ( python --version >nul 2>nul && set "PY=python" )
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Launcher\py.exe" set "PY="%LOCALAPPDATA%\Programs\Python\Launcher\py.exe" -3"
if not defined PY if exist "%WINDIR%\py.exe" set "PY="%WINDIR%\py.exe" -3"
if not defined PY (
  echo Python is not installed. Installing it now - one time only...
  winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
  if exist "%LOCALAPPDATA%\Programs\Python\Launcher\py.exe" set "PY="%LOCALAPPDATA%\Programs\Python\Launcher\py.exe" -3"
  if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY="%LOCALAPPDATA%\Programs\Python\Python312\python.exe""
)
if not defined PY (
  echo.
  echo Could not install Python automatically.
  echo Install it from https://www.python.org/downloads/ then run this file again.
  pause
  exit /b 1
)

rem Allow other computers to connect (works when run as administrator; otherwise
rem Windows asks once - click "Allow access").
netsh advfirewall firewall show rule name="Saipa Mashayekh Board" >nul 2>nul || netsh advfirewall firewall add rule name="Saipa Mashayekh Board" dir=in action=allow protocol=TCP localport=%PORT% >nul 2>nul

start "" /min cmd /c "timeout /t 3 >nul & start http://localhost:%PORT%"
%PY% server.py %PORT%
echo.
echo The server stopped.
pause
