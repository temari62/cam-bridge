# CamBridge — Setup Guide

Follow this once per machine. It takes ~20 minutes. You need **admin rights on the remote PC**.

Three pieces:
- **RELAY** = a small cloud server (VPS) with a public IP that both PCs connect out to.
- **LOCAL PC** = where the employee sits (real webcam + mic).
- **REMOTE PC** = the machine that joins Teams/Zoom/Meet.

Because both PCs are on the open internet behind home routers, they can't reach each other
directly — they meet in the middle at the relay. Set up the relay once (Part 0); it can serve all
your employees at the same time.

---

## Part 0 — RELAY SERVER (one-time, serves everyone)

### 1. Rent a small VPS
Any provider works (DigitalOcean, Hetzner, Vultr, AWS Lightsail, etc.). The cheapest tier
(~$4–6/month, 1 shared CPU) is plenty. Choose **Ubuntu 22.04+** and note its **public IP**.

### 2. Open the ports
In the provider's firewall / security group, allow inbound **TCP 50007** and **TCP 50008**.
On the server itself (if `ufw` is on):
```
sudo ufw allow 50007/tcp && sudo ufw allow 50008/tcp
```

### 3. Run the relay
Copy `relay.py` to the server (no dependencies — plain Python 3). Then:
```
python3 relay.py
```
You should see `listening on 0.0.0.0:50007` and `...50008`. Leave it running.

To keep it running after you log out, use `tmux`/`screen`, or install it as a service:
```
# quick-and-dirty always-on:
nohup python3 relay.py > relay.log 2>&1 &
```
(For production, run it under `systemd` — see DESIGN.md §6.)

### 4. Pick a room token
Choose a hard-to-guess shared word/phrase per employee (e.g. `jose-standup-7fKq`). The local and
remote PC must use the **same** token to be paired. Anyone who knows the relay IP *and* the token
could connect, so treat it like a password.

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

No Windows Firewall changes are needed — the remote PC only makes **outbound** connections to the
relay.

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

## Part C — What each PC needs to connect

Both PCs point at the **same relay IP** and use the **same room token** (from Part 0). There is no
per-PC IP to look up and no router setup — the relay handles the meeting-in-the-middle. Order
doesn't matter; whichever starts first waits for the other, and either will reconnect
automatically if the connection drops.

---

## Part D — Running it (every meeting)

### On the REMOTE PC
1. Double-click **`start_receiver.bat`**. Enter the **relay IP** and the **room token**.
   (Or run `python receiver.py --host <RELAY_IP> --room <TOKEN>`.)
   You should see `connected to relay ...` and `auto-detected CABLE Input`.
2. Open your meeting app and set devices:
   - **Teams:** Settings → Devices → Camera = **OBS Virtual Camera**, Microphone = **CABLE Output (VB-Audio Virtual Cable)**.
   - **Zoom:** Settings → Video → Camera = **OBS Virtual Camera**; Settings → Audio → Microphone = **CABLE Output**.
   - **Google Meet:** Settings (gear) → Video → Camera = **OBS Virtual Camera**; Audio → Microphone = **CABLE Output**.
3. Join the meeting.

### On the LOCAL PC
1. Double-click **`start_sender.bat`**. Enter the **same relay IP** and the **same room token**, press Enter.
   (Or run `python sender.py --host <RELAY_IP> --room <TOKEN>`.)
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

**Sender/receiver says "waiting for relay"** — the relay isn't reachable. Confirm `relay.py` is
running on the VPS, the VPS firewall allows TCP 50007/50008, and the relay IP is correct
(`ping <relay_ip>`).

**Connected to relay but no video/audio** — the two sides are using **different room tokens**, or
the other side isn't running yet. Make sure both use the exact same `--room` value.

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
