CamBridge installer - vendor files
==================================

Put the third-party files here BEFORE running build_installer.bat.
They get bundled into CamBridge-Setup.exe and installed silently on remote PCs.

REQUIRED
--------
VBCABLE_Setup_x64.exe   (VB-Audio Virtual Cable - the virtual microphone)
  1. Download the ZIP from https://vb-audio.com/Cable/
  2. Unzip it.
  3. Copy "VBCABLE_Setup_x64.exe" into THIS folder.

obs-virtualcam\   (the virtual camera - fetched automatically)
  build_installer.bat runs ..\fetch_obs_virtualcam.py if this folder is
  missing. It downloads ONLY OBS's virtual-camera DLLs (not OBS Studio) from a
  pinned official OBS release, plus OBS's licence:
      obs-virtualcam-module64.dll, obs-virtualcam-module32.dll,
      COPYING (GPLv2), SOURCE.txt (version, URLs, SHA-256)
  To fetch by hand:  python ..\fetch_obs_virtualcam.py

OPTIONAL
--------
relay-cert.pem   (only if you use TLS encryption)
  - Copy your relay's certificate here to ship it inside the installer;
    it lands next to the app so employees can point "Cert file" at it.

Notes
-----
* File names must match EXACTLY (the .iss scripts reference them by name).
* VB-CABLE is installed with silent flags "-i -h". If a future VB-CABLE
  version changes those flags, edit the [Run] line in CamBridge-Setup.iss.
* These vendor files are intentionally NOT committed to git (.gitignore).
