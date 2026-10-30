@echo off
REM =====================================================================
REM  CamBridge - install / remove the virtual camera WITHOUT OBS Studio
REM  For manual setups only; the installer does this for you.
REM  Run as Administrator:
REM     virtualcam.bat install      copy the DLLs to Program Files + register
REM     virtualcam.bat uninstall    unregister + delete
REM  Needs installer\vendor\obs-virtualcam\ (python installer\fetch_obs_virtualcam.py)
REM =====================================================================
setlocal
set "SRC=%~dp0..\installer\vendor\obs-virtualcam"
set "DEST=%ProgramFiles%\CamBridge\virtualcam"

net session >nul 2>&1 || (
  echo ERROR: run this as Administrator.
  exit /b 1
)

if /i "%~1"=="install" goto install
if /i "%~1"=="uninstall" goto uninstall
echo Usage: %~nx0 install ^| uninstall
exit /b 1

:install
if not exist "%SRC%\obs-virtualcam-module64.dll" (
  echo ERROR: %SRC% missing. Run:  python installer\fetch_obs_virtualcam.py
  exit /b 1
)
reg query "HKLM\SOFTWARE\Classes\CLSID\{A3FCE0F5-3493-419F-958A-ABA1250EC20B}" >nul 2>&1 && (
  echo Note: a virtual camera is already registered ^(OBS Studio?^) - re-pointing it to CamBridge's copy.
)
if not exist "%DEST%" mkdir "%DEST%"
copy /y "%SRC%\*" "%DEST%\" >nul || exit /b 1
"%SystemRoot%\System32\regsvr32.exe" /i /s "%DEST%\obs-virtualcam-module64.dll" || exit /b 1
"%SystemRoot%\SysWOW64\regsvr32.exe" /i /s "%DEST%\obs-virtualcam-module32.dll" || exit /b 1
echo Virtual camera installed: "OBS Virtual Camera"
exit /b 0

:uninstall
if exist "%DEST%\obs-virtualcam-module64.dll" "%SystemRoot%\System32\regsvr32.exe" /u /s "%DEST%\obs-virtualcam-module64.dll"
if exist "%DEST%\obs-virtualcam-module32.dll" "%SystemRoot%\SysWOW64\regsvr32.exe" /u /s "%DEST%\obs-virtualcam-module32.dll"
rmdir /s /q "%DEST%" 2>nul
echo Virtual camera removed.
exit /b 0
