@echo off
REM ==== CamBridge receiver GUI (run on the REMOTE PC) ====
cd /d "%~dp0"
start "" pythonw receiver_gui.py
