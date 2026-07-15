@echo off
REM ==== CamBridge receiver launcher (run on the REMOTE PC) ====
setlocal
cd /d "%~dp0"

set /p RELAY_IP="Enter the RELAY server IP or domain (e.g. 203.0.113.10): "
if "%RELAY_IP%"=="" (
  echo No relay entered. Exiting.
  pause
  exit /b 1
)
set /p ROOM="Enter your ROOM token (must match the local PC): "
if "%ROOM%"=="" set ROOM=default

echo.
echo Starting CamBridge receiver via relay %RELAY_IP% (room %ROOM%) ...
echo In your meeting app, pick "OBS Virtual Camera" and "CABLE Output" as camera/mic.
echo.
python receiver.py --host %RELAY_IP% --room %ROOM%

echo.
pause
