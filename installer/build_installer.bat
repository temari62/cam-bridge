@echo off
REM =====================================================================
REM  CamBridge - build the Windows installers with Inno Setup 6
REM  Prereqs:
REM    1) Inno Setup 6 installed  (https://jrsoftware.org/isdl.php)
REM    2) build_exe.bat already run  (so ..\client\dist\*.exe exist)
REM    3) vendor\VBCABLE_Setup_x64.exe present (see vendor\README.txt)
REM  Output installers land in:  installer\Output\
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
if not exist "..\client\dist\CamBridge-Receiver.exe" (
  echo ERROR: ..\client\dist\CamBridge-Receiver.exe missing. Run build_exe.bat first.
  pause & exit /b 1
)
if not exist "vendor\VBCABLE_Setup_x64.exe" (
  echo ERROR: vendor\VBCABLE_Setup_x64.exe missing. See vendor\README.txt.
  pause & exit /b 1
)

echo Building Receiver installer...
"%ISCC%" "CamBridge-Receiver.iss" || goto :err

if exist "..\client\dist\CamBridge-Sender.exe" (
  echo Building Sender installer...
  "%ISCC%" "CamBridge-Sender.iss" || goto :err
) else (
  echo (Skipping Sender installer - ..\client\dist\CamBridge-Sender.exe not found.)
)

echo.
echo ============================================================
echo  DONE. Installers are in:  installer\Output\
echo     CamBridge-Receiver-Setup.exe   (give to REMOTE PCs)
echo     CamBridge-Sender-Setup.exe     (give to LOCAL PCs)
echo ============================================================
pause
exit /b 0

:err
echo.
echo BUILD FAILED. Scroll up for the Inno Setup error.
pause
exit /b 1
