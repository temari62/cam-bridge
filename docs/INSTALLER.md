# CamBridge — One-Click Installers (Inno Setup)

This wraps the apps into Windows installers so setup is a single wizard. The **receiver
installer** also **silently installs VB-Audio Virtual Cable** (and optionally OBS Studio), so
the remote PC is ready without the separate driver steps.

Two installers get produced:

- **CamBridge-Receiver-Setup.exe** → REMOTE PCs. Installs the app **+ virtual mic driver**
  (+ optional virtual camera), makes shortcuts, and prompts a restart to finish the driver.
- **CamBridge-Sender-Setup.exe** → LOCAL PCs. Just the app + shortcuts (no drivers needed).

## Build order (all on Windows)

Inno Setup, like PyInstaller, compiles **only on Windows** — there's no way to produce the
`Setup.exe` from Linux. On a Windows 11 PC:

1. **Build the exes:** run `client\build_exe.bat` (see BUILD.md). This creates `client\dist\CamBridge-*.exe`.
2. **Install Inno Setup 6:** https://jrsoftware.org/isdl.php .
3. **Add the driver installer(s):** follow `installer\vendor\README.txt` — at minimum drop
   `VBCABLE_Setup_x64.exe` into `installer\vendor\`. Optionally add the OBS installer and your
   `relay-cert.pem`.
4. **Build the installers:** run `installer\build_installer.bat`.
   The finished installers appear in `installer\Output\`.

## What the receiver installer does, in order

1. Copies `CamBridge-Receiver.exe` into `C:\Program Files\CamBridge`.
2. Runs `VBCABLE_Setup_x64.exe -i -h` silently → creates the **CABLE Input/Output** devices.
3. If bundled, runs the OBS installer `/S` silently → registers the **OBS Virtual Camera**.
4. Creates Start-menu (and optional desktop) shortcuts.
5. Prompts a **restart** (VB-CABLE needs one to finish registering the audio device).

After the restart, the employee opens CamBridge Receiver, enters the relay + room, and picks
**OBS Virtual Camera** / **CABLE Output** in their meeting app — same as before, just no manual
driver installs.

## Notes & caveats

- **Admin required:** installing a driver needs elevation; the installer requests it automatically.
- **OBS bundling is optional.** If you don't include the OBS installer, install OBS on the remote
  PC yourself (SETUP.md Part A). It's left optional because OBS is large and you may prefer to
  manage it via your own software deployment.
- **VB-CABLE silent flags** are `-i -h` (verified against VB-Audio's current reference manual;
  uninstall is `-u -h`). If a future VB-CABLE changes them, edit the `[Run]` line in
  `installer\CamBridge-Receiver.iss`.
- **One prompt may still appear.** Even with `-i -h`, Windows can still show its "Would you like to
  install this device software?" driver-trust dialog the first time. To make it *fully* silent
  across a fleet, pre-trust VB-Audio's publisher certificate on the target PC before installing —
  export the certificate from `VBCABLE_Setup_x64.exe` (right-click → Properties → Digital
  Signatures → Details → View Certificate → Copy to File) and import it into the machine's
  Trusted Publishers store, e.g. `certutil -addstore TrustedPublisher vbaudio.cer` (run as admin,
  e.g. via Group Policy or your MDM). This is optional — without it the employee just clicks
  "Install" once.
- **Code signing:** by default the installer and exes are unsigned, so Windows SmartScreen may warn
  on first run. For a fleet rollout, configure a code-signing certificate and the build scripts sign
  the apps **and** the installers automatically — see `SIGNING.md`.
- **Redistribution:** make sure your use of the bundled VB-CABLE / OBS installers complies with
  their licenses. For internal company deployment this is normally fine; confirm for your case.
