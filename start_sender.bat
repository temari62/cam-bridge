@echo off
REM ==== CamBridge sender launcher (run on the LOCAL PC) ====
setlocal
cd /d "%~dp0"

set /p RELAY_IP="Enter the RELAY server IP or domain (e.g. 203.0.113.10): "
if "%RELAY_IP%"=="" (
  echo No relay entered. Exiting.
  pause
  exit /b 1
)
set /p ROOM="Enter your ROOM token (must match the remote PC): "
if "%ROOM%"=="" set ROOM=default

echo.
echo Connecting to relay %RELAY_IP% (room %ROOM%) ...
python sender.py --host %RELAY_IP% --room %ROOM%

echo.
pause
