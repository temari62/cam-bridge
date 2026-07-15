@echo off
REM =====================================================================
REM  CamBridge - build standalone Windows .exe files
REM  Run this ONCE on a Windows 11 PC that has Python 3.10+ installed.
REM  Produces (in the dist\ folder):
REM     dist\CamBridge-Sender.exe    <- give to LOCAL PCs
REM     dist\CamBridge-Receiver.exe  <- give to REMOTE PCs
REM  The .exe includes Python + all libraries; employees need NO Python.
REM  (The REMOTE PC still needs OBS Studio + VB-CABLE installed - those
REM   are system drivers and cannot be bundled into an exe.)
REM =====================================================================
setlocal
cd /d "%~dp0"

echo.
echo [1/3] Installing build dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller
if errorlevel 1 (
  echo ERROR: could not install dependencies. Is Python on PATH?
  pause
  exit /b 1
)

echo.
echo [2/3] Building CamBridge-Sender.exe ...
pyinstaller --noconfirm --clean --onefile --windowed ^
  --name CamBridge-Sender ^
  --collect-all cv2 ^
  --collect-all numpy ^
  --collect-all sounddevice ^
  sender_gui.py
if errorlevel 1 goto :err
call "..\tools\sign.bat" "dist\CamBridge-Sender.exe" || goto :err

echo.
echo [3/3] Building CamBridge-Receiver.exe ...
pyinstaller --noconfirm --clean --onefile --windowed ^
  --name CamBridge-Receiver ^
  --collect-all cv2 ^
  --collect-all numpy ^
  --collect-all sounddevice ^
  --collect-all pyvirtualcam ^
  receiver_gui.py
if errorlevel 1 goto :err
call "..\tools\sign.bat" "dist\CamBridge-Receiver.exe" || goto :err

echo.
echo ============================================================
echo  DONE. Your executables are in the dist\ folder:
echo     dist\CamBridge-Sender.exe
echo     dist\CamBridge-Receiver.exe
echo  Copy relay-cert.pem next to the exe if you use TLS.
echo ============================================================
pause
exit /b 0

:err
echo.
echo BUILD FAILED. Scroll up for the PyInstaller error.
pause
exit /b 1
