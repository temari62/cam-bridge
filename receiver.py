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
  * OBS Studio installed (registers the virtual camera)
  * VB-Audio Virtual Cable installed
  * pip install -r requirements.txt

Usage:
    python receiver.py --host relay.example.com --room mystandup
    python receiver.py --host 203.0.113.10 --room mystandup --audio-out 7
    python receiver.py --list-audio          # find the CABLE Input device index

--host  = the RELAY server's public IP or domain.
--room  = the same shared token used by the sender.
"""

import argparse
import socket
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


def connect_with_retry(host, port, room, label):
    """Connect to the relay and announce our role/room. Retry until it's up."""
    while not _stop.is_set():
        try:
            s = socket.create_connection((host, port), timeout=10)
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            send_handshake(s, room)
            print(f"[{label}] connected to relay {host}:{port} (room '{room}')")
            return s
        except OSError as e:
            print(f"[{label}] waiting for relay at {host}:{port} ... ({e})")
            time.sleep(2)
    return None


# --- Audio: play received PCM into CABLE Input ---------------------------------
def find_cable_input():
    for i, d in enumerate(sd.query_devices()):
        name = d["name"].lower()
        if d["max_output_channels"] > 0 and "cable input" in name:
            return i
    return None


def audio_client(host, room, out_device):
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
    print(f"[audio] output ready -> device {out_device}")
    try:
        while not _stop.is_set():
            sock = connect_with_retry(host, AUDIO_PORT, room, "audio")
            if sock is None:
                break
            try:
                while not _stop.is_set():
                    data = recv_frame(sock)
                    if data is None:
                        print("[audio] stream ended; reconnecting")
                        break
                    stream.write(data)
            except OSError as e:
                print(f"[audio] connection issue ({e}); reconnecting")
                time.sleep(1)
            finally:
                try:
                    sock.close()
                except OSError:
                    pass
    finally:
        stream.stop()
        stream.close()
    print("[audio] stopped")


# --- Video: push received frames into OBS Virtual Camera -----------------------
def video_client(host, room, fps):
    # The virtual camera is created lazily on the first frame (to match its size)
    # and kept open across reconnects so the meeting app never loses the camera.
    cam = None
    try:
        while not _stop.is_set():
            sock = connect_with_retry(host, VIDEO_PORT, room, "video")
            if sock is None:
                break
            try:
                while not _stop.is_set():
                    data = recv_frame(sock)
                    if data is None:
                        print("[video] stream ended; reconnecting")
                        break
                    frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
                    if frame is None:
                        continue
                    if cam is None:
                        h, w = frame.shape[:2]
                        cam = pyvirtualcam.Camera(width=w, height=h, fps=fps,
                                                  fmt=pyvirtualcam.PixelFormat.RGB)
                        print(f"[video] virtual camera started: {cam.device} ({w}x{h} @ {fps}fps)")
                    if (frame.shape[1], frame.shape[0]) != (cam.width, cam.height):
                        frame = cv2.resize(frame, (cam.width, cam.height))
                    cam.send(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            except OSError as e:
                print(f"[video] connection issue ({e}); reconnecting")
                time.sleep(1)
            finally:
                try:
                    sock.close()
                except OSError:
                    pass
    finally:
        if cam is not None:
            cam.close()
    print("[video] stopped")


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

    out_device = args.audio_out
    if out_device is None:
        out_device = find_cable_input()
        if out_device is None:
            print("ERROR: Could not find 'CABLE Input' device.")
            print("Install VB-Audio Virtual Cable, or run --list-audio and pass --audio-out <index>.")
            sys.exit(1)
        print(f"[audio] auto-detected CABLE Input at device index {out_device}")

    print(f"CamBridge receiver -> relay {args.host} (room '{args.room}'). Press Ctrl+C to stop.\n")

    vt = threading.Thread(target=video_client, args=(args.host, args.room, args.fps), daemon=True)
    at = threading.Thread(target=audio_client, args=(args.host, args.room, out_device), daemon=True)
    vt.start()
    at.start()

    try:
        while vt.is_alive() or at.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping...")
        _stop.set()
        vt.join(timeout=3)
        at.join(timeout=3)


if __name__ == "__main__":
    main()
