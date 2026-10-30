@echo off
REM =====================================================================
REM  CamBridge - build standalone Windows .exe files
REM  Run this ONCE on a Windows 11 PC that has Python 3.10+ installed.
REM  Produces (in the dist\ folder):
REM     dist\CamBridge.exe   <- give to BOTH PCs (pick Send / Receive in the app)
REM  The .exe includes Python + all libraries; employees need NO Python.
REM  (The REMOTE PC also needs the virtual camera + VB-CABLE - those are
REM   system devices; the installer sets both up.)
REM =====================================================================
setlocal
cd /d "%~dp0"

echo.
echo [1/2] Installing build dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller
if errorlevel 1 (
  echo ERROR: could not install dependencies. Is Python on PATH?
  pause
  exit /b 1
)

echo.
echo [2/2] Building CamBridge.exe ...
pyinstaller --noconfirm --clean --onefile --windowed ^
  --name CamBridge ^
  --icon "..\assets\CamBridge.ico" ^
  --add-data "..\assets\CamBridge.ico;assets" ^
  --collect-all cv2 ^
  --collect-all numpy ^
  --collect-all sounddevice ^
  --collect-all pyvirtualcam ^
  --collect-all sv_ttk ^
  cambridge_gui.py
if errorlevel 1 goto :err
call "..\tools\sign.bat" "dist\CamBridge.exe" || goto :err

echo.
echo ============================================================
echo  DONE. Your executable is in the dist\ folder:
echo     dist\CamBridge.exe
echo  Copy relay-cert.pem next to the exe if you use TLS.
echo ============================================================
pause
exit /b 0

:err
echo.
echo BUILD FAILED. Scroll up for the PyInstaller error.
pause
exit /b 1
