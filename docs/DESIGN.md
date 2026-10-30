# CamBridge — Design Document

A Windows 11 tool that lets an employee join a meeting **on a remote PC** while the
meeting shows **the camera and microphone of their local PC**.

- **Local PC** = the machine physically in front of the employee (real webcam + mic).
- **Remote PC** = the machine that actually runs Teams / Zoom / Meet and joins the standup.

The two PCs are in different places on the internet, so they connect through a small **relay
server** on a public VPS — both dial *out* to it, which sidesteps home NAT/firewalls entirely
(no port forwarding on either PC). The relay pairs them by a shared **room token** and forwards
the stream. The remote PC exposes a **virtual camera** and a **virtual microphone**, and any
meeting app on it simply picks "OBS Virtual Camera" and "CABLE Output" like a normal
webcam/headset — so this works the same for Teams, Zoom, Google Meet, or anything else.

---

## 1. How it works (data flow)

```
  LOCAL PC (employee)              RELAY (public VPS)            REMOTE PC (joins the meeting)
 ┌────────────────────┐          ┌──────────────────┐         ┌──────────────────────────────┐
 │ Real webcam ─►      │  video   │  pairs S and R   │  video  │  ─► Virtual Camera (OBS Cam)  │
 │ Real mic    ─► sender├────────►│  by room token,  ├────────►│      receiver.py             │
 │             sender.py│  audio   │  forwards bytes  │  audio  │  ─► Virtual Mic (VB-CABLE)    │
 └────────────────────┘  (out)    └──────────────────┘  (out)  └───────────────┬──────────────┘
                                                                                │ selected as
                                                                                ▼ camera + mic
                                                                    Teams / Zoom / Google Meet
```

1. `sender.py` on the local PC captures the webcam and microphone.
2. Both `sender.py` and `receiver.py` connect *outward* to `relay.py` on the VPS, each announcing
   the same room token. The relay pairs them and forwards the sender's stream to the receiver
   (video and audio on two separate TCP connections).
3. `receiver.py` on the remote PC writes:
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
| `sender.py` | Local PC | Capture webcam (OpenCV) + mic (sounddevice), encode, connect out to relay |
| `receiver.py` | Remote PC | Connect out to relay, push video → virtual camera, audio → virtual mic |
| `relay.py` | Public VPS | Pair sender+receiver by room token, forward the stream; optional TLS (stdlib only) |
| `cambridge_gui.py` | Both PCs | One tkinter app: Send/Receive mode, relay + room fields, TLS toggle, Start/Stop, live log |
| `gen_cert.sh` | Public VPS | One-command self-signed TLS certificate generator for the relay |
| Virtual camera driver | Remote PC | OBS Virtual Camera (system-wide camera device) |
| Virtual audio driver | Remote PC | VB-Audio Virtual Cable (system-wide mic device) |
| Network transport | All | Two outbound TCP connections (video + audio), length-prefixed frames |

---

## 3. Tech stack and why

**Language: Python 3.10+.** Fastest path to a working, cross-tested prototype, and packages
into a standalone `.exe` with PyInstaller so employees don't need Python installed.

**Video capture:** `opencv-python` — reliable webcam access and JPEG encode/decode.

**Audio capture/playback:** `sounddevice` (PortAudio) — simple blocking read/write and easy
device selection by name.

**Video virtual camera:** `pyvirtualcam` driving the **OBS Virtual Camera** backend — a
system-wide DirectShow camera that Teams, Zoom, and browsers (Google Meet) all recognize.
`pyvirtualcam` writes frames into it through shared memory and only checks that the camera's COM
class is registered, so CamBridge ships **just OBS's virtual-camera DLLs** (~0.4 MB, GPLv2, signed
by OBS Project) and registers them with `regsvr32` — **OBS Studio itself is not installed**.

**Audio virtual mic:** **VB-Audio Virtual Cable** (VB-CABLE) — a free, Microsoft-signed audio
driver. It creates a `CABLE Input` playback endpoint and a `CABLE Output` recording endpoint.
`receiver.py` plays the received audio into `CABLE Input`; the meeting app selects `CABLE Output`
as its microphone. Windows has no user-mode "virtual mic" API, so a signed driver like this is
the standard, safe approach — and you confirmed admin rights, so installing it is fine.

**Transport:** plain TCP with 4-byte length-prefixed frames. Video and audio each get their own
connection so audio stays smooth and isn't blocked behind large video frames. Both PCs connect
*outward* to the relay; on connect each sends a tiny handshake (`role` + `room token`) so the
relay can pair the right sender with the right receiver. The relay is a **dumb byte pipe** once
paired — it never parses the media, so framing is preserved end-to-end.

### Why not a fully native driver?
A "proper" productized version would ship one signed Windows driver package (a Media Foundation
virtual camera + a virtual audio driver) so there are no third-party installs. That requires C++
driver development and code-signing certificates — weeks of work and out of scope for a prototype.
The OBS virtual-camera module + VB-CABLE combination gives you the **same end result today**,
set up by one installer.
See §6 for the productization path.

---

## 4. Networking

The two PCs are far apart on the internet, both behind home NAT, so neither can accept an incoming
connection reliably (home routers block it, and CGNAT — common on 5G/fibre — makes it impossible
even with port forwarding). The fix is a **relay server**:

- Rent a small Linux VPS with a **public IP** (any provider; the cheapest ~$5/mo tier is plenty).
- Run `relay.py` on it and open TCP ports **50007** and **50008** in the VPS firewall / security group.
- Both `sender.py` and `receiver.py` connect *outward* to the VPS. Outbound connections pass
  through home NAT with no router changes, so nothing needs configuring on either home network.

The relay pairs a sender and receiver using a shared **room token** (`--room`), so multiple
employees can share one relay at the same time — each pair just uses its own token. The token also
acts as lightweight access control, so pick something unguessable.

Default ports: **50007** (video), **50008** (audio). Configurable on all three programs.

---

## 5. Deployment overview

On the **VPS** (one-time): run `relay.py` and open ports 50007/50008. Best run as an always-on
service so it's ready for every meeting.

On the **remote PC** (one-time): run the CamBridge installer with "virtual camera + microphone"
ticked (it registers the virtual camera and installs VB-CABLE). Then each meeting: open CamBridge in
**Receive** mode (pointing at the relay + room), open Teams/Zoom/Meet,
pick "OBS Virtual Camera" and "CABLE Output" as camera/mic, and join.

On the **local PC** (one-time): run the same installer with that option unticked. Each meeting:
open CamBridge in **Send** mode pointing at the same relay + room.

Full click-by-click steps are in **SETUP.md**.

---

## 6. Limitations and productization path

**Prototype limitations (be aware):**
- Latency on a good connection is roughly 150–400 ms — fine for a standup, not for music.
- Video/audio are only loosely synced (separate streams); acceptable for talking heads.
- Requires the OBS virtual-camera module and VB-CABLE on the remote PC (the installer
  sets up both; no OBS Studio), plus a VPS running the relay.
- Someone must start the receiver on the remote PC (e.g. via Remote Desktop) before joining.
- **Encryption is now available via TLS** (`--tls` on all three programs, `gen_cert.sh` to make a
  certificate). When enabled with a verified certificate, media is encrypted client↔relay in both
  directions. Note the relay still *terminates* TLS, so the VPS you operate sees plaintext in the
  middle — fine since you control it, but it is not zero-knowledge end-to-end. Still use a strong,
  unguessable room token. If TLS is left off, the media crosses the internet in the clear.

**Path to a polished product, in order of value:**
1. **[Done] Encrypt the relay link** — TLS is implemented (client↔relay). Next step for true
   end-to-end secrecy: terminate TLS at the endpoints instead of the relay (receiver acts as TLS
   server through the relay's byte pipe), so the VPS never sees plaintext.
2. **[Done] Simple GUI** — one app, `cambridge_gui.py`, with a Send/Receive mode, relay+room form, TLS toggle,
   and Start/Stop. Could still add an in-GUI camera/mic picker.
3. **One-click installer** (Inno Setup) that bundles the `.exe` files and silently installs VB-CABLE.
4. **Run the relay as a managed service** (systemd on the VPS) and auto-start the receiver as a
   Windows service so both are always ready.
5. **Opus/H.264 encoding + WebRTC** to cut bandwidth and latency and add encryption natively.
6. **Native virtual camera + signed virtual-audio driver** to remove the OBS-module/VB-CABLE
   dependency (Windows 11's `MFCreateVirtualCamera` API needs no kernel driver for the camera).

---

## 7. A note on appropriate use

This is built for the stated purpose: employees joining an internal company standup where the
meeting runs on one PC and the person is at another. It relays a live camera and mic transparently.
Keep its use consistent with your company's policies and with participants' awareness — it should
represent a real person who is genuinely present, not misrepresent who is attending.
