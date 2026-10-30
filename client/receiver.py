"""
CamBridge - REMOTE receiver.

Runs on the REMOTE PC (the one that joins Teams/Zoom/Meet). It connects OUTWARD
to the RELAY server, receives the sender's stream, and:
  * writes incoming video frames into the OBS Virtual Camera, and
  * plays incoming audio into the VB-CABLE "CABLE Input" device (virtual mic).

In the meeting app on this PC, select:
  * Camera     -> "OBS Virtual Camera"
  * Microphone -> "CABLE Output (VB-Audio Virtual Cable)"

Prerequisites on this PC (see SETUP.md):
  * OBS virtual camera registered - the installer does this, or
    tools\virtualcam.bat (OBS Studio itself is NOT needed)
  * VB-Audio Virtual Cable installed
  * pip install -r requirements.txt

Usage:
    python receiver.py --host relay.example.com --room mystandup
    python receiver.py --host 203.0.113.10 --room mystandup --tls --cafile relay-cert.pem
    python receiver.py --list-audio          # find the CABLE Input device index

--host      = the RELAY server's public IP or domain.
--room      = the same shared token used by the sender.
--tls/--cafile/--insecure = same meaning as in sender.py.

This module is also imported by cambridge_gui.py (Receive mode); the GUI overrides
`log` and calls start()/stop().
"""

import argparse
import socket
import ssl
import struct
import sys
import threading
import time

import cv2
import numpy as np
import sounddevice as sd
import pyvirtualcam

SAMPLE_RATE = 48000
CHANNELS = 1
DTYPE = "int16"
BLOCKSIZE = 1024

VIDEO_PORT = 50007
AUDIO_PORT = 50008

MAGIC = b"CBR1"  # CamBridge Relay protocol v1
ROLE = "R"       # this program is the Receiver

_stop = threading.Event()

# Overridable status sink. The GUI replaces this with its own logger.
log = print


# --- TLS ------------------------------------------------------------------------
def make_client_ssl(use_tls, cafile=None, insecure=False):
    if not use_tls:
        return None
    if insecure:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    if cafile:
        return ssl.create_default_context(cafile=cafile)
    return ssl.create_default_context()


# --- Framing / relay handshake -------------------------------------------------
def recv_exactly(sock, n):
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)


def recv_frame(sock):
    header = recv_exactly(sock, 4)
    if header is None:
        return None
    (length,) = struct.unpack(">I", header)
    return recv_exactly(sock, length)


def send_handshake(sock, room: str):
    room_b = room.encode("utf-8")[:255]
    sock.sendall(MAGIC + ROLE.encode("ascii") + bytes([len(room_b)]) + room_b)


def connect_with_retry(host, port, room, label, ssl_ctx):
    """Connect to the relay (optionally over TLS) and announce our role/room."""
    while not _stop.is_set():
        try:
            s = socket.create_connection((host, port), timeout=10)
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            if ssl_ctx is not None:
                s = ssl_ctx.wrap_socket(s, server_hostname=host)
            send_handshake(s, room)
            log(f"[{label}] connected to relay {host}:{port} (room '{room}')")
            return s
        except (OSError, ssl.SSLError) as e:
            log(f"[{label}] waiting for relay at {host}:{port} ... ({e})")
            time.sleep(2)
    return None


# --- Audio: play received PCM into CABLE Input ---------------------------------
def find_cable_input():
    for i, d in enumerate(sd.query_devices()):
        name = d["name"].lower()
        if d["max_output_channels"] > 0 and "cable input" in name:
            return i
    return None


def audio_client(host, room, ssl_ctx, out_device):
    # Open the output stream ONCE and keep it across reconnects so the virtual
    # mic stays alive for the whole meeting.
    stream = sd.RawOutputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
        blocksize=BLOCKSIZE,
        device=out_device,
    )
    stream.start()
    log(f"[audio] output ready -> device {out_device}")
    try:
        while not _stop.is_set():
            sock = connect_with_retry(host, AUDIO_PORT, room, "audio", ssl_ctx)
            if sock is None:
                break
            try:
                while not _stop.is_set():
                    data = recv_frame(sock)
                    if data is None:
                        log("[audio] stream ended; reconnecting")
                        break
                    stream.write(data)
            except OSError as e:
                log(f"[audio] connection issue ({e}); reconnecting")
                time.sleep(1)
            finally:
                try:
                    sock.close()
                except OSError:
                    pass
    finally:
        stream.stop()
        stream.close()
    log("[audio] stopped")


# --- Video: push received frames into OBS Virtual Camera -----------------------
def video_client(host, room, ssl_ctx, fps):
    # The virtual camera is created lazily on the first frame (to match its size)
    # and kept open across reconnects so the meeting app never loses the camera.
    cam = None
    try:
        while not _stop.is_set():
            sock = connect_with_retry(host, VIDEO_PORT, room, "video", ssl_ctx)
            if sock is None:
                break
            try:
                while not _stop.is_set():
                    data = recv_frame(sock)
                    if data is None:
                        log("[video] stream ended; reconnecting")
                        break
                    frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
                    if frame is None:
                        continue
                    if cam is None:
                        h, w = frame.shape[:2]
                        cam = pyvirtualcam.Camera(width=w, height=h, fps=fps,
                                                  fmt=pyvirtualcam.PixelFormat.RGB)
                        log(f"[video] virtual camera started: {cam.device} ({w}x{h} @ {fps}fps)")
                    if (frame.shape[1], frame.shape[0]) != (cam.width, cam.height):
                        frame = cv2.resize(frame, (cam.width, cam.height))
                    cam.send(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            except OSError as e:
                log(f"[video] connection issue ({e}); reconnecting")
                time.sleep(1)
            finally:
                try:
                    sock.close()
                except OSError:
                    pass
    finally:
        if cam is not None:
            cam.close()
    log("[video] stopped")


# --- Start/stop API (used by CLI main and the GUI) -----------------------------
def start(host, room, use_tls=False, cafile=None, insecure=False, fps=30, out_device=None):
    """Start receiving in background threads. Returns the thread list.

    Raises RuntimeError if the CABLE Input device can't be found.
    """
    if out_device is None:
        out_device = find_cable_input()
        if out_device is None:
            raise RuntimeError("Could not find 'CABLE Input' device. Install VB-Audio Virtual Cable.")
    _stop.clear()
    ssl_ctx = make_client_ssl(use_tls, cafile, insecure)
    vt = threading.Thread(target=video_client, args=(host, room, ssl_ctx, fps), daemon=True)
    at = threading.Thread(target=audio_client, args=(host, room, ssl_ctx, out_device), daemon=True)
    vt.start()
    at.start()
    return [vt, at]


def stop():
    _stop.set()


def list_audio():
    print("=== AUDIO OUTPUT DEVICES ===")
    print("Pick the one named 'CABLE Input (VB-Audio Virtual Cable)' for --audio-out\n")
    for i, d in enumerate(sd.query_devices()):
        if d["max_output_channels"] > 0:
            print(f"  [{i}] {d['name']}")


def main():
    p = argparse.ArgumentParser(description="CamBridge remote receiver")
    p.add_argument("--host", help="Relay server public IP or domain")
    p.add_argument("--room", default="default", help="Shared room token (same as the sender)")
    p.add_argument("--tls", action="store_true", help="Encrypt the connection to the relay")
    p.add_argument("--cafile", help="Verify the relay against this certificate (PEM)")
    p.add_argument("--insecure", action="store_true", help="With --tls, skip certificate verification")
    p.add_argument("--fps", type=int, default=30, help="Virtual camera fps (default 30)")
    p.add_argument("--audio-out", type=int, default=None,
                   help="Output device index for CABLE Input (auto-detected if omitted)")
    p.add_argument("--list-audio", action="store_true", help="List audio output devices and exit")
    args = p.parse_args()

    if args.list_audio:
        list_audio()
        return

    if not args.host:
        p.error("--host is required (the relay server IP). Use --list-audio to inspect devices.")

    try:
        threads = start(args.host, args.room, use_tls=args.tls, cafile=args.cafile,
                        insecure=args.insecure, fps=args.fps, out_device=args.audio_out)
    except RuntimeError as e:
        print(f"ERROR: {e}")
        print("Or run --list-audio and pass --audio-out <index>.")
        sys.exit(1)

    enc = "TLS" if args.tls else "plain"
    log(f"CamBridge receiver -> relay {args.host} (room '{args.room}', {enc}). Press Ctrl+C to stop.\n")

    try:
        while any(t.is_alive() for t in threads):
            time.sleep(0.5)
    except KeyboardInterrupt:
        log("\nStopping...")
        stop()
        for t in threads:
            t.join(timeout=3)


if __name__ == "__main__":
    main()
