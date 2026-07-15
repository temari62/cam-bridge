# CamBridge — Setup Guide

Follow this once per machine. It takes ~15 minutes. You need **admin rights on the remote PC**.

Two roles:
- **LOCAL PC** = where the employee sits (real webcam + mic).
- **REMOTE PC** = the machine that joins Teams/Zoom/Meet.

---

## Part A — REMOTE PC (one-time setup)

### 1. Install Python
Install **Python 3.10 or newer** from https://www.python.org/downloads/ .
On the first installer screen, tick **"Add python.exe to PATH"**.

### 2. Install the virtual **camera** (OBS Studio)
Download and install **OBS Studio** (free): https://obsproject.com/ .
You do **not** need to configure OBS — just installing it registers the
"OBS Virtual Camera" device that CamBridge writes into.
(Optional: open OBS once, click **Start Virtual Camera**, then close it, to confirm it works.)

### 3. Install the virtual **microphone** (VB-CABLE)
Download **VB-Audio Virtual Cable** (free): https://vb-audio.com/Cable/ .
Unzip, right-click **`VBCABLE_Setup_x64.exe` → Run as administrator**, click **Install Driver**,
then **reboot** the PC.
After reboot you'll have two new audio devices: **CABLE Input** and **CABLE Output**.

### 4. Install CamBridge dependencies
Copy the `CamBridge` folder to the remote PC. Open **Command Prompt** in that folder and run:
```
pip install -r requirements.txt
```

### 5. Allow the network ports through Windows Firewall
In an **admin** Command Prompt:
```
netsh advfirewall firewall add rule name="CamBridge Video" dir=in action=allow protocol=TCP localport=50007
netsh advfirewall firewall add rule name="CamBridge Audio" dir=in action=allow protocol=TCP localport=50008
```
(If you use Tailscale — see Part C — this is usually unnecessary, but it doesn't hurt.)

---

## Part B — LOCAL PC (one-time setup)

### 1. Install Python 3.10+ (same as above, tick "Add to PATH").

### 2. Install CamBridge dependencies
Copy the `CamBridge` folder to the local PC, open Command Prompt in it, and run:
```
pip install -r requirements.txt
```
(The local PC doesn't strictly need `pyvirtualcam`, but installing everything is simplest.)

---

## Part C — Networking (do this on BOTH PCs)

Because both are personal PCs, the easiest reliable option is **Tailscale**:
1. Install Tailscale on both PCs: https://tailscale.com/download .
2. Sign in with the **same account** on both.
3. On the **remote PC**, note its Tailscale IP (looks like `100.x.y.z`) — run `tailscale ip -4`
   or check the Tailscale admin page. This is the IP the local PC will connect to.

If both PCs are on the same office LAN/VPN instead, just use the remote PC's local IP
(e.g. `192.168.1.50`) and make sure Part A step 5 (firewall) is done.

---

## Part D — Running it (every meeting)

### On the REMOTE PC
1. Double-click **`start_receiver.bat`** (or run `python receiver.py`).
   You should see `listening on 0.0.0.0:50007` and `auto-detected CABLE Input`.
2. Open your meeting app and set devices:
   - **Teams:** Settings → Devices → Camera = **OBS Virtual Camera**, Microphone = **CABLE Output (VB-Audio Virtual Cable)**.
   - **Zoom:** Settings → Video → Camera = **OBS Virtual Camera**; Settings → Audio → Microphone = **CABLE Output**.
   - **Google Meet:** Settings (gear) → Video → Camera = **OBS Virtual Camera**; Audio → Microphone = **CABLE Output**.
3. Join the meeting.

### On the LOCAL PC
1. Double-click **`start_sender.bat`**, enter the remote PC's IP (Tailscale `100.x.y.z`), press Enter.
   (Or run `python sender.py --host 100.x.y.z`.)
2. The webcam light turns on and the remote PC's virtual camera starts showing your face.

That's it — the meeting now shows the employee's **local** camera and mic.

---

## Troubleshooting

**"Could not find CABLE Input"** — VB-CABLE isn't installed or the PC wasn't rebooted. Reinstall
and reboot, or run `python receiver.py --list-audio` and pass the right index with `--audio-out N`.

**"OBS Virtual Camera" not listed in the meeting app** — install OBS Studio, open it once, and
try again. Some apps only refresh the camera list after a restart.

**Camera is black / wrong camera on the local PC** — run `python sender.py --list-devices` and
pass the right one, e.g. `python sender.py --host <ip> --camera 1`.

**Wrong microphone captured on the local PC** — run `--list-devices`, then
`python sender.py --host <ip> --mic <index>`.

**Choppy or laggy** — lower quality/size: `python sender.py --host <ip> --width 960 --height 540 --fps 20 --quality 65`.

**Sender says "waiting for receiver"** — start the receiver on the remote PC first, and confirm
the IP is reachable (`ping <ip>` from the local PC).

**Echo in the meeting** — make sure the remote PC's *speakers* are muted or use headphones on the
remote side; the audio only needs to flow into CABLE, not out of the remote PC's speakers.

---

## Packaging as a real .exe (optional, later)
To hand employees a double-click app with no Python install, build standalone executables:
```
pip install pyinstaller
pyinstaller --onefile sender.py
pyinstaller --onefile receiver.py
```
The `.exe` files appear in the `dist/` folder. (OBS and VB-CABLE still need installing on the
remote PC — those are drivers, not bundled with the exe.)
