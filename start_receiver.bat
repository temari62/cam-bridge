@echo off
REM ==== CamBridge receiver launcher (run on the REMOTE PC) ====
setlocal
cd /d "%~dp0"

echo Starting CamBridge receiver...
echo In your meeting app, pick "OBS Virtual Camera" and "CABLE Output" as camera/mic.
echo.
python receiver.py

echo.
pause
