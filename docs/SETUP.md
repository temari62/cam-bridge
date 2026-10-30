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
Copy the `relay/` folder (contains `relay.py` and `gen_cert.sh`) to the server. It has no
dependencies — plain Python 3. From inside that folder run:
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

### 5. (Recommended) Turn on encryption (TLS)
Without this, the video/audio crosses the internet unencrypted. To encrypt it, make a certificate
on the VPS (replace the IP with your VPS's public IP):
```
bash gen_cert.sh 203.0.113.10
```
This creates `relay-cert.pem` and `relay-key.pem`. Start the relay with TLS instead of step 3:
```
python3 relay.py --tls --certfile relay-cert.pem --keyfile relay-key.pem
```
Then copy **`relay-cert.pem`** to each PC — you'll point the app at it (the "Cert file" box in the
GUI, or `--cafile relay-cert.pem`). That gives you an encrypted **and** verified connection.
(If you'd rather not bother with the cert file, you can instead tick **"Skip cert check"** / pass
`--insecure`: still encrypted, but it won't detect an impostor relay.)

---

## Part A — REMOTE PC (one-time setup)

### 1. Install Python
Install **Python 3.10 or newer** from https://www.python.org/downloads/ .
On the first installer screen, tick **"Add python.exe to PATH"**.

### 2. Install the virtual **camera** (no OBS Studio needed)
> Using `CamBridge-Setup.exe` (with "virtual camera + microphone" ticked)? It does this step (and
> step 3) for you — skip ahead.

CamBridge only needs OBS's small virtual-camera module, not OBS Studio. On a PC with the repo:
```
python installer\fetch_obs_virtualcam.py
```
then, in a Command Prompt **run as administrator**:
```
tools\virtualcam.bat install
```
This copies two DLLs to `C:\Program Files\CamBridge\virtualcam` and registers the
**"OBS Virtual Camera"** device that CamBridge writes into (`tools\virtualcam.bat uninstall`
removes it). If OBS Studio is already installed you can skip this — it provides the same device.

### 3. Install the virtual **microphone** (VB-CABLE)
Download **VB-Audio Virtual Cable** (free): https://vb-audio.com/Cable/ .
Unzip, right-click **`VBCABLE_Setup_x64.exe` → Run as administrator**, click **Install Driver**,
then **reboot** the PC.
After reboot you'll have two new audio devices: **CABLE Input** and **CABLE Output**.

### 4. Install CamBridge dependencies
Copy the `client/` folder to the remote PC. Open **Command Prompt** in that folder and run:
```
pip install -r requirements.txt
```

No Windows Firewall changes are needed — the remote PC only makes **outbound** connections to the
relay.

---

## Part B — LOCAL PC (one-time setup)

### 1. Install Python 3.10+ (same as above, tick "Add to PATH").

### 2. Install CamBridge dependencies
Copy the `client/` folder to the local PC, open Command Prompt in it, and run:
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

**Easiest way — the CamBridge app (no command line).** Both PCs run the same app
(**CamBridge** from the Start menu, or `start_gui.bat` in the `client` folder). Under **This PC**
choose **Send** or **Receive**, fill in the relay IP and room token, tick **Encrypt (TLS)** (and
point "Cert file" at `relay-cert.pem` from Part 0 step 5), then click **Start**. The window shows a
live status log; click **Stop** when done. It remembers your mode and last entries.

### On the REMOTE PC
1. Open **CamBridge** and choose **Receive into the meeting**. Enter the **relay IP** and **room token**, set TLS,
   click **Start**. Wait for `virtual camera started` / `output ready` in the log.
   (Command-line alternative: `python receiver.py --host <RELAY_IP> --room <TOKEN> --tls --cafile relay-cert.pem`.)
2. Open your meeting app and set devices:
   - **Teams:** Settings → Devices → Camera = **OBS Virtual Camera**, Microphone = **CABLE Output (VB-Audio Virtual Cable)**.
   - **Zoom:** Settings → Video → Camera = **OBS Virtual Camera**; Settings → Audio → Microphone = **CABLE Output**.
   - **Google Meet:** Settings (gear) → Video → Camera = **OBS Virtual Camera**; Audio → Microphone = **CABLE Output**.
3. Join the meeting.

### On the LOCAL PC
1. Open **CamBridge** and choose **Send my camera + mic**. Enter the **same relay IP**, **same room token**, and the
   same TLS settings, then click **Start**.
   (Command-line alternative: `python sender.py --host <RELAY_IP> --room <TOKEN> --tls --cafile relay-cert.pem`.)
2. The webcam light turns on and the remote PC's virtual camera starts showing your face.

That's it — the meeting now shows the employee's **local** camera and mic.

> The old `start_sender.bat` / `start_receiver.bat` (command-line prompts) still work if you
> prefer them, but they don't expose the TLS options — use the GUI or the full command line for that.

---

## Troubleshooting

**"Could not find CABLE Input"** — VB-CABLE isn't installed or the PC wasn't rebooted. Reinstall
and reboot, or run `python receiver.py --list-audio` and pass the right index with `--audio-out N`.

**"OBS Virtual Camera" not listed in the meeting app** — re-run the installer with "virtual camera +
microphone" ticked (or
`tools\virtualcam.bat install` as administrator) and restart the meeting app; some apps only
refresh the camera list after a restart. If OBS Studio was uninstalled after CamBridge was
installed, OBS's uninstaller removes the camera too — re-run the installer.

**Receiver says "OBS Virtual Camera device not found! Did you install OBS?"** — same fix as
above; that message comes from the `pyvirtualcam` library. OBS Studio itself isn't needed.

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

## Packaging as .exe (no Python for employees)
To hand employees double-click apps with no Python install, run **`client\build_exe.bat`** once on
any Windows 11 PC that has Python. It produces `client\dist\CamBridge.exe`, used on both PCs.
Full instructions are in **BUILD.md**. (The virtual camera and VB-CABLE
still need installing on the remote PC — those are system devices, not bundled into the exe; the
installer handles both.)
