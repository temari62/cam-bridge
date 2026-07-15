# CamBridge

Attend a meeting on a **remote PC** while it shows the **camera and microphone of your
local PC**. Built for employees joining an in-company standup where the meeting runs on one
machine and the person sits at another. Works with Teams, Zoom, and Google Meet because it
feeds a system-wide virtual camera + virtual mic that any app can select.

The local PC streams its webcam/mic out to a small **relay** server on the internet, which
forwards it to the remote PC, where it appears as "OBS Virtual Camera" and "CABLE Output".

## Folder layout

```
cam-bridge/
├─ README.md            <- you are here
├─ client/              <- runs on the employee PCs (local + remote)
│   ├─ sender.py            local PC: capture + stream out       (CLI)
│   ├─ receiver.py          remote PC: stream in -> virtual devices (CLI)
│   ├─ sender_gui.py        friendly window for the local PC (Windows 11 look)
│   ├─ receiver_gui.py      friendly window for the remote PC (Windows 11 look)
│   ├─ theme.py             shared Fluent theme + auto light/dark
│   ├─ requirements.txt     Python dependencies
│   ├─ build_exe.bat        build standalone .exe files (PyInstaller)
│   └─ start_*.bat          double-click launchers (GUI + CLI)
├─ relay/               <- runs on a public VPS (Linux)
│   ├─ relay.py             pairs local+remote by room token, forwards the stream
│   └─ gen_cert.sh          make a TLS certificate for the relay
├─ installer/           <- optional one-click Windows installers (Inno Setup)
│   ├─ CamBridge-Receiver.iss   installs receiver + silently installs VB-CABLE/OBS
│   ├─ CamBridge-Sender.iss     installs sender
│   ├─ build_installer.bat      compiles the installers
│   └─ vendor/                  drop VBCABLE_Setup_x64.exe here (see its README)
├─ assets/
│   ├─ CamBridge.ico       app icon (multi-size: 16–256px) for the window, exe, installer
│   ├─ CamBridge.png       1024px master icon
│   └─ make_icon.py        regenerates the icon
├─ tools/
│   └─ sign.bat            optional Authenticode signing helper (used by the build scripts)
└─ docs/
    ├─ SETUP.md          step-by-step setup for every meeting (start here)
    ├─ DESIGN.md         architecture, tech choices, limitations
    ├─ BUILD.md          building the .exe files
    ├─ INSTALLER.md      building the one-click installers
    └─ SIGNING.md        optional code signing to remove SmartScreen warnings
```

## Quick start

1. **Relay:** on a cheap Linux VPS, run `relay/relay.py` (see `docs/SETUP.md` Part 0).
2. **Remote PC:** install OBS Studio + VB-CABLE, then run `client/receiver_gui.py`.
3. **Local PC:** run `client/sender_gui.py`, point both at the relay with the same room token.

Full instructions: **`docs/SETUP.md`**.
