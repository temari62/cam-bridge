@echo off
REM =====================================================================
REM  CamBridge - build the Windows installer with Inno Setup 6
REM  Prereqs:
REM    1) Inno Setup 6 installed  (https://jrsoftware.org/isdl.php)
REM    2) build_exe.bat already run  (so ..\client\dist\CamBridge.exe exists)
REM    3) vendor\VBCABLE_Setup_x64.exe present (see vendor\README.txt)
REM       (vendor\obs-virtualcam\ is fetched automatically if missing)
REM  Output installer lands in:  installer\Output\
REM =====================================================================
setlocal
cd /d "%~dp0"

REM --- locate the Inno Setup compiler (ISCC.exe) ---
set "ISCC="
where iscc >nul 2>&1 && set "ISCC=iscc"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC (
  echo ERROR: Inno Setup 6 not found. Install it from https://jrsoftware.org/isdl.php
  pause & exit /b 1
)

REM --- sanity checks ---
if not exist "..\client\dist\CamBridge.exe" (
  echo ERROR: ..\client\dist\CamBridge.exe missing. Run build_exe.bat first.
  pause & exit /b 1
)
if not exist "vendor\VBCABLE_Setup_x64.exe" (
  echo ERROR: vendor\VBCABLE_Setup_x64.exe missing. See vendor\README.txt.
  pause & exit /b 1
)
if not exist "vendor\obs-virtualcam\obs-virtualcam-module64.dll" (
  echo Fetching the OBS virtual camera DLLs...
  python fetch_obs_virtualcam.py || (
    echo ERROR: could not fetch vendor\obs-virtualcam\. See vendor\README.txt.
    pause & exit /b 1
  )
)

echo Building installer...
"%ISCC%" "CamBridge-Setup.iss" || goto :err
call "..\tools\sign.bat" "Output\CamBridge-Setup.exe" || goto :err

echo.
echo ============================================================
echo  DONE. Installer is in:  installer\Output\
echo     CamBridge-Setup.exe   (give to BOTH PCs; untick "virtual
echo                            camera + microphone" on LOCAL PCs)
echo ============================================================
pause
exit /b 0

:err
echo.
echo BUILD FAILED. Scroll up for the Inno Setup error.
pause
exit /b 1
