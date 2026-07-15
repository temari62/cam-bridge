@echo off
REM =====================================================================
REM  sign.bat <file>  -  Authenticode-sign a file, IF signing is set up.
REM  If no signing certificate is configured, it silently skips so that
REM  ordinary (unsigned) builds keep working.
REM
REM  Configure by setting environment variables before you build:
REM    Option 1 - PFX file:
REM       set CAMBRIDGE_SIGN_PFX=C:\path\to\your-cert.pfx
REM       set CAMBRIDGE_SIGN_PASS=your-pfx-password       (omit if none)
REM    Option 2 - certificate already in the Windows store:
REM       set CAMBRIDGE_SIGN_SHA1=THUMBPRINT_WITH_NO_SPACES
REM    Optional (defaults to DigiCert):
REM       set CAMBRIDGE_SIGN_TS=http://timestamp.sectigo.com
REM =====================================================================
setlocal
set "TARGET=%~1"
if "%TARGET%"=="" exit /b 0
if not exist "%TARGET%" (
  echo [sign] file not found: %TARGET%
  exit /b 1
)

if not defined CAMBRIDGE_SIGN_PFX if not defined CAMBRIDGE_SIGN_SHA1 (
  echo [sign] skipped ^(no signing cert configured^): %TARGET%
  exit /b 0
)

REM --- locate signtool.exe (on PATH, or newest Windows 10/11 SDK) ---
set "SIGNTOOL="
where signtool >nul 2>&1 && set "SIGNTOOL=signtool"
if not defined SIGNTOOL (
  for /f "delims=" %%I in ('dir /b /s "%ProgramFiles(x86)%\Windows Kits\10\bin\*\x64\signtool.exe" 2^>nul') do set "SIGNTOOL=%%I"
)
if not defined SIGNTOOL (
  echo [sign] ERROR: signtool.exe not found. Install the Windows SDK, or add signtool to PATH.
  exit /b 1
)

set "TS=%CAMBRIDGE_SIGN_TS%"
if not defined TS set "TS=http://timestamp.digicert.com"

if defined CAMBRIDGE_SIGN_PFX goto :pfx
goto :store

:pfx
if defined CAMBRIDGE_SIGN_PASS (
  "%SIGNTOOL%" sign /fd SHA256 /f "%CAMBRIDGE_SIGN_PFX%" /p "%CAMBRIDGE_SIGN_PASS%" /tr "%TS%" /td SHA256 "%TARGET%"
) else (
  "%SIGNTOOL%" sign /fd SHA256 /f "%CAMBRIDGE_SIGN_PFX%" /tr "%TS%" /td SHA256 "%TARGET%"
)
goto :checkres

:store
"%SIGNTOOL%" sign /fd SHA256 /sha1 "%CAMBRIDGE_SIGN_SHA1%" /tr "%TS%" /td SHA256 "%TARGET%"
goto :checkres

:checkres
if errorlevel 1 (
  echo [sign] ERROR signing %TARGET%
  exit /b 1
)
echo [sign] signed: %TARGET%
exit /b 0
