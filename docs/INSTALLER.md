# CamBridge — One-Click Installer (Inno Setup)

This wraps the app into a single Windows installer, **CamBridge-Setup.exe**, used on **both** PCs.
Its wizard has one choice:

- **"Set up the virtual camera + microphone"** — *ticked by default; keep it on the REMOTE PC.*
  Also sets up the **virtual camera** (just OBS's virtual-camera module — OBS Studio is *not*
  installed) and **silently installs VB-Audio Virtual Cable**, then prompts a restart to finish
  the audio driver.
- **Unticked** — *for the LOCAL PC.* Just the app + shortcuts: no drivers, no restart.

Upgrading from the old separate *CamBridge Sender* / *CamBridge Receiver* installers: the new
installer silently uninstalls them first, so only **CamBridge** remains. Settings carry over.

## Build order (all on Windows)

Inno Setup, like PyInstaller, compiles **only on Windows** — there's no way to produce the
`Setup.exe` from Linux. On a Windows 11 PC:

1. **Build the exe:** run `client\build_exe.bat` (see BUILD.md). This creates `client\dist\CamBridge.exe`.
2. **Install Inno Setup 6:** https://jrsoftware.org/isdl.php .
3. **Add the vendor files:** follow `installer\vendor\README.txt` — drop
   `VBCABLE_Setup_x64.exe` into `installer\vendor\` (and optionally your `relay-cert.pem`).
   The virtual-camera DLLs are fetched automatically by the next step
   (`installer\fetch_obs_virtualcam.py`; needs Python and internet).
4. **Build the installer:** run `installer\build_installer.bat`.
   The finished `CamBridge-Setup.exe` appears in `installer\Output\`.

## What the installer does, in order

Steps 2, 3 and 5 only happen with "Set up the virtual camera + microphone" ticked (remote PC).

1. Copies `CamBridge.exe` into `C:\Program Files\CamBridge`, and the virtual-camera
   DLLs into `C:\Program Files\CamBridge\virtualcam`.
2. Runs `VBCABLE_Setup_x64.exe -i -h` silently → creates the **CABLE Input/Output** devices.
3. Registers the DLLs with `regsvr32 /i /s` (64- and 32-bit) → creates the **OBS Virtual Camera**
   device. Skipped if OBS Studio is already installed, since it provides the same device.
4. Creates Start-menu (and optional desktop) shortcuts.
5. Prompts a **restart** (VB-CABLE needs one to finish registering the audio device).

After the restart, the employee opens CamBridge, chooses **Receive**, enters the relay + room,
and picks **OBS Virtual Camera** / **CABLE Output** in their meeting app. (The app opens in the
right mode the first time when launched from the installer's finish page.)

## Silent / fleet install

```
CamBridge-Setup.exe /VERYSILENT /TASKS="remotepc"     rem remote PC (add ,desktopicon for a shortcut)
CamBridge-Setup.exe /VERYSILENT /TASKS="!remotepc"    rem local PC
```
Add `/NORESTART` to postpone the reboot the remote-PC install needs.

## Notes & caveats

- **Admin required:** installing a driver needs elevation; the installer requests it automatically.
- **Virtual camera without OBS.** The receiver only talks to OBS's DirectShow virtual-camera
  module (`obs-virtualcam-module64/32.dll`, ~0.4 MB, signed by OBS Project, no dependencies
  beyond Windows itself), so the installer ships just that instead of the ~190 MB OBS Studio. The
  device is still named **"OBS Virtual Camera"**. The OBS version is pinned in
  `fetch_obs_virtualcam.py`; bump it deliberately and re-test.
- **Coexisting with OBS Studio:** if OBS is already installed, the installer leaves OBS's camera
  registration alone; uninstalling CamBridge only unregisters the camera if it's still CamBridge's.
  Uninstalling OBS *after* CamBridge removes the camera — re-run the installer to fix.
- **VB-CABLE silent flags** are `-i -h` (verified against VB-Audio's current reference manual;
  uninstall is `-u -h`). If a future VB-CABLE changes them, edit the `[Run]` line in
  `installer\CamBridge-Setup.iss`.
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
  the app **and** the installer automatically — see `SIGNING.md`.
- **Redistribution:** make sure your use of the bundled VB-CABLE and OBS files complies with
  their licenses. The OBS virtual-camera module is **GPLv2**: the installer ships OBS's `COPYING`
  and a `SOURCE.txt` (exact version + source link) next to the DLLs. VB-Audio requires a licence
  to bundle VB-CABLE in a distributed product. For internal company deployment this is normally
  fine; confirm for your case.
