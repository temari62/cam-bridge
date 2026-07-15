# CamBridge — Design Document

A Windows 11 tool that lets an employee join a meeting **on a remote PC** while the
meeting shows **the camera and microphone of their local PC**.

- **Local PC** = the machine physically in front of the employee (real webcam + mic).
- **Remote PC** = the machine that actually runs Teams / Zoom / Meet and joins the standup.

The remote PC exposes a **virtual camera** and a **virtual microphone**. CamBridge streams
the local PC's real camera and mic to the remote PC and feeds them into those virtual devices.
Any meeting app on the remote PC then simply picks "CamBridge Camera" and "CamBridge Mic"
like it would any normal webcam/headset — so this works the same for Teams, Zoom, Google Meet,
or anything else.

---

## 1. How it works (data flow)

```
   LOCAL PC (employee)                         REMOTE PC (joins the meeting)
 ┌─────────────────────┐                     ┌───────────────────────────────────┐
 │  Real webcam  ──►    │   video (TCP)       │  ──►  Virtual Camera (OBS Cam)     │
 │  sender.py    ──────────────────────────► │       receiver.py                 │
 │  Real mic     ──►    │   audio (TCP)       │  ──►  Virtual Mic (VB-CABLE)       │
 └─────────────────────┘                     └───────────────┬───────────────────┘
                                                              │ selected as
                                                              ▼ camera + mic
                                                  Teams / Zoom / Google Meet
```

1. `sender.py` on the local PC captures the webcam and microphone.
2. It streams the video and audio over the network to the remote PC (two TCP connections).
3. `receiver.py` on the remote PC receives the streams and writes:
   - video frames into a **virtual camera** device, and
   - audio samples into a **virtual audio input** (virtual mic) device.
4. In Teams/Zoom/Meet on the remote PC, the employee picks the virtual camera and virtual mic.
   The meeting now shows the employee's local face and voice.

Because the virtual devices look like ordinary hardware to Windows, **no meeting app needs any
special support** — this is what makes it platform-agnostic across Teams, Zoom, and Meet.

---

## 2. Components

| Component | Runs on | Responsibility |
|-----------|---------|----------------|
| `sender.py` | Local PC | Capture webcam (OpenCV) + mic (sounddevice), encode, stream out |
| `receiver.py` | Remote PC | Receive streams, push video → virtual camera, audio → virtual mic |
| Virtual camera driver | Remote PC | OBS Virtual Camera (system-wide camera device) |
| Virtual audio driver | Remote PC | VB-Audio Virtual Cable (system-wide mic device) |
| Network transport | Both | Two TCP connections (video + audio), length-prefixed frames |

---

## 3. Tech stack and why

**Language: Python 3.10+.** Fastest path to a working, cross-tested prototype, and packages
into a standalone `.exe` with PyInstaller so employees don't need Python installed.

**Video capture:** `opencv-python` — reliable webcam access and JPEG encode/decode.

**Audio capture/playback:** `sounddevice` (PortAudio) — simple blocking read/write and easy
device selection by name.

**Video virtual camera:** `pyvirtualcam` driving the **OBS Virtual Camera** backend.
Installing OBS Studio (free) registers a system-wide DirectShow camera that Teams, Zoom, and
browsers (Google Meet) all recognize. `pyvirtualcam` writes frames straight into it.

**Audio virtual mic:** **VB-Audio Virtual Cable** (VB-CABLE) — a free, Microsoft-signed audio
driver. It creates a `CABLE Input` playback endpoint and a `CABLE Output` recording endpoint.
`receiver.py` plays the received audio into `CABLE Input`; the meeting app selects `CABLE Output`
as its microphone. Windows has no user-mode "virtual mic" API, so a signed driver like this is
the standard, safe approach — and you confirmed admin rights, so installing it is fine.

**Transport:** plain TCP with 4-byte length-prefixed frames. Video and audio each get their own
connection so audio stays smooth and isn't blocked behind large video frames. The **receiver is
the server** (it listens); the **sender connects** to the remote PC's IP.

### Why not a fully native driver?
A "proper" productized version would ship one signed Windows driver package (a Media Foundation
virtual camera + a virtual audio driver) so there are no third-party installs. That requires C++
driver development and code-signing certificates — weeks of work and out of scope for a prototype.
The OBS + VB-CABLE combination gives you the **same end result today** with two quick installs.
See §6 for the productization path.

---

## 4. Networking

Both machines are personal PCs, so they are probably **not** on the same LAN and sit behind home
routers. Three options, easiest first:

1. **Tailscale (recommended).** Install the free [Tailscale](https://tailscale.com) on both PCs
   and sign in with the same account. Each PC gets a stable private IP (e.g. `100.x.y.z`) that
   works from anywhere with no port-forwarding and encrypted end-to-end. Point the sender at the
   remote PC's Tailscale IP. This is by far the simplest for remote/home machines.
2. **Same LAN / office VPN.** If both are on the same network or company VPN, just use the remote
   PC's local IP (e.g. `192.168.1.50`) and open the two TCP ports in Windows Firewall.
3. **Port forwarding.** Possible but discouraged — exposes ports to the internet.

Default ports: **50007** (video), **50008** (audio). Configurable.

---

## 5. Deployment overview

On the **remote PC** (one-time): install OBS Studio, install VB-CABLE, install the CamBridge
receiver, allow the two ports through the firewall. Then each meeting: run the receiver, open
Teams/Zoom/Meet, pick "OBS Virtual Camera" and "CABLE Output" as camera/mic, and join.

On the **local PC** (one-time): install the CamBridge sender. Each meeting: run the sender with
the remote PC's IP.

Full click-by-click steps are in **SETUP.md**.

---

## 6. Limitations and productization path

**Prototype limitations (be aware):**
- Latency on a good connection is roughly 150–400 ms — fine for a standup, not for music.
- Video/audio are only loosely synced (separate streams); acceptable for talking heads.
- Requires OBS and VB-CABLE installed on the remote PC.
- Someone must start the receiver on the remote PC (e.g. via Remote Desktop) before joining.
- No encryption on the raw TCP itself — **run it over Tailscale** (encrypted) or a VPN, not the
  open internet.

**Path to a polished product, in order of value:**
1. **One-click installer** (Inno Setup) that bundles the sender/receiver `.exe`, silently
   installs VB-CABLE, and sets firewall rules.
2. **Simple GUI** with a device picker, connection status, and a big Start/Stop button.
3. **Auto-start receiver** as a Windows service so the remote PC is always ready.
4. **Opus/H.264 encoding + WebRTC** to cut bandwidth and latency and add encryption natively.
5. **Native signed virtual-camera + virtual-audio driver** to remove the OBS/VB-CABLE dependency.

---

## 7. A note on appropriate use

This is built for the stated purpose: employees joining an internal company standup where the
meeting runs on one PC and the person is at another. It relays a live camera and mic transparently.
Keep its use consistent with your company's policies and with participants' awareness — it should
represent a real person who is genuinely present, not misrepresent who is attending.
