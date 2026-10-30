@echo off
REM ==== CamBridge app (run on BOTH PCs - pick Send or Receive in the window) ====
cd /d "%~dp0"
start "" pythonw cambridge_gui.py %*
