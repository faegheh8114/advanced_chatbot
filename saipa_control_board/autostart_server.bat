@echo off
rem Starts the board server automatically when this computer is turned on.
set "LNK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Saipa Mashayekh Board Server.lnk"
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:LNK);$s.TargetPath='%~dp0start_server.bat';$s.WorkingDirectory='%~dp0';$s.WindowStyle=7;$s.Save()"
if exist "%LNK%" (echo Done: the server will start automatically with Windows.) else (echo Failed to create the startup shortcut.)
pause
