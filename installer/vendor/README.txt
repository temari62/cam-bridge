CamBridge installer - vendor files
==================================

Put the third-party driver installers here BEFORE running build_installer.bat.
They get bundled into CamBridge-Receiver-Setup.exe and run silently on install.

REQUIRED
--------
VBCABLE_Setup_x64.exe   (VB-Audio Virtual Cable - the virtual microphone)
  1. Download the ZIP from https://vb-audio.com/Cable/
  2. Unzip it.
  3. Copy "VBCABLE_Setup_x64.exe" into THIS folder.

OPTIONAL
--------
OBS-Studio-Full-Installer-x64.exe   (OBS Studio - the virtual camera)
  - Download from https://obsproject.com/download
  - Rename it to exactly:  OBS-Studio-Full-Installer-x64.exe
  - Copy it into THIS folder.
  If you leave it out, the installer simply skips it and you install OBS
  separately on the remote PC (see SETUP.md Part A).

relay-cert.pem   (only if you use TLS encryption)
  - Copy your relay's certificate here to ship it inside the installer;
    it lands next to the app so employees can point "Cert file" at it.

Notes
-----
* File names must match EXACTLY (the .iss scripts reference them by name).
* VB-CABLE is installed with silent flags "-i -h". If a future VB-CABLE
  version changes those flags, edit the [Run] line in CamBridge-Receiver.iss.
* These vendor files are intentionally NOT committed to git (.gitignore).
