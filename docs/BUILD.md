# CamBridge — Building the .exe files

This turns the Python scripts into two standalone Windows apps so employees never
install Python:

- **CamBridge-Sender.exe** — give to LOCAL PCs (the employee's machine).
- **CamBridge-Receiver.exe** — give to REMOTE PCs (the one that joins the meeting).

## You build once, on Windows

PyInstaller is **not** a cross-compiler: a Windows `.exe` can only be produced on a
Windows machine. So run the build on any Windows 11 PC with Python 3.10+ installed
(it can be your own). The resulting `.exe` then runs on other Windows PCs without Python.

### Steps
1. Copy the whole `cam-bridge` folder to a Windows 11 PC that has
   **Python 3.10+** (installed with "Add python.exe to PATH").
2. Double-click **`client\build_exe.bat`**.
   It installs the dependencies + PyInstaller and builds both apps.
3. When it finishes, the executables are in the new **`client\dist\`** folder:
   - `client\dist\CamBridge-Sender.exe`
   - `client\dist\CamBridge-Receiver.exe`

First launch of a onefile exe is a few seconds slower (it unpacks to a temp folder);
after that it's normal.

## Distributing to employees

- **Local PC:** copy `CamBridge-Sender.exe` anywhere and double-click it. Done.
- **Remote PC:** copy `CamBridge-Receiver.exe`, **and** first install the two system
  drivers it depends on (these cannot be baked into an exe):
  - **OBS Studio** (provides the virtual camera), and
  - **VB-Audio Virtual Cable** (provides the virtual mic).
  See `SETUP.md` Part A for those.
- **TLS:** if you enabled encryption, put a copy of **`relay-cert.pem`** next to the exe
  (or anywhere) and point the app's "Cert file" box at it.

## Notes / troubleshooting

- **Antivirus / SmartScreen** may warn on an unsigned exe the first time. It's expected
  for self-built apps; click "More info → Run anyway", or **code-sign** the apps to remove the
  warning — see `SIGNING.md` (the build scripts sign automatically once a cert is configured).
- **64-bit:** build on 64-bit Windows so the exe runs on your (64-bit) employee PCs.
- **Camera/mic not found at runtime** — that's a device/driver issue on the target PC,
  not a build issue; use the app's fields (or the CLI `--list-devices`) to pick the right one.
- **Rebuild after code changes:** just run `build_exe.bat` again; `--clean` refreshes everything.
- The **relay** does not need an exe — it runs as `python3 relay.py` on your Linux VPS.
