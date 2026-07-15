@echo off
REM ==== CamBridge sender launcher (run on the LOCAL PC) ====
setlocal
cd /d "%~dp0"

set /p REMOTE_IP="Enter the REMOTE PC IP address (e.g. Tailscale 100.x.y.z): "
if "%REMOTE_IP%"=="" (
  echo No IP entered. Exiting.
  pause
  exit /b 1
)

echo.
echo Connecting to %REMOTE_IP% ...
python sender.py --host %REMOTE_IP%

echo.
pause
