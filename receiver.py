"""
CamBridge - REMOTE receiver.

Runs on the REMOTE PC (the one that joins Teams/Zoom/Meet). It listens for the
sender, then:
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
    python receiver.py
    python receiver.py --list-audio          # find the CABLE Input device index
    python receiver.py --audio-out 7         # force a specific output device index
    python receiver.py --bind 0.0.0.0        # listen address (default all interfaces)
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

_stop = threading.Event()


# --- Framing helpers -----------------------------------------------------------
def recv_exactly(sock, n):
    """Read exactly n bytes or return None if the connection closes."""
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)


def recv_frame(sock):
    """Read one length-prefixed message, or None on disconnect."""
    header = recv_exactly(sock, 4)
    if header is None:
        return None
    (length,) = struct.unpack(">I", header)
    return recv_exactly(sock, length)


def make_listener(bind, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((bind, port))
    s.listen(1)
    return s


# --- Audio: play received PCM into CABLE Input ---------------------------------
def find_cable_input():
    """Return the device index whose name looks like VB-CABLE's playback endpoint."""
    for i, d in enumerate(sd.query_devices()):
        name = d["name"].lower()
        if d["max_output_channels"] > 0 and "cable input" in name:
            return i
    return None


def audio_server(bind, out_device):
    listener = make_listener(bind, AUDIO_PORT)
    print(f"[audio] listening on {bind}:{AUDIO_PORT} -> output device {out_device}")
    while not _stop.is_set():
        try:
            listener.settimeout(1.0)
            try:
                conn, addr = listener.accept()
            except socket.timeout:
                continue
            print(f"[audio] sender connected from {addr}")
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            stream = sd.RawOutputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype=DTYPE,
                blocksize=BLOCKSIZE,
                device=out_device,
            )
            stream.start()
            try:
                while not _stop.is_set():
                    data = recv_frame(conn)
                    if data is None:
                        print("[audio] sender disconnected")
                        break
                    stream.write(data)
            finally:
                stream.stop()
                stream.close()
                conn.close()
        except OSError as e:
            print(f"[audio] error: {e}")
            time.sleep(1)
    listener.close()
    print("[audio] stopped")


# --- Video: push received frames into OBS Virtual Camera -----------------------
def video_server(bind, fps):
    listener = make_listener(bind, VIDEO_PORT)
    print(f"[video] listening on {bind}:{VIDEO_PORT}")
    while not _stop.is_set():
        try:
            listener.settimeout(1.0)
            try:
                conn, addr = listener.accept()
            except socket.timeout:
                continue
            print(f"[video] sender connected from {addr}")
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            _serve_video_conn(conn, fps)
            conn.close()
        except OSError as e:
            print(f"[video] error: {e}")
            time.sleep(1)
    listener.close()
    print("[video] stopped")


def _serve_video_conn(conn, fps):
    cam = None
    try:
        # Wait for the first frame so we can size the virtual camera to match.
        first = recv_frame(conn)
        if first is None:
            return
        frame = cv2.imdecode(np.frombuffer(first, np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            print("[video] could not decode first frame")
            return
        h, w = frame.shape[:2]
        cam = pyvirtualcam.Camera(width=w, height=h, fps=fps,
                                  fmt=pyvirtualcam.PixelFormat.RGB)
        print(f"[video] virtual camera started: {cam.device} ({w}x{h} @ {fps}fps)")
        cam.send(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

        while not _stop.is_set():
            data = recv_frame(conn)
            if data is None:
                print("[video] sender disconnected")
                break
            frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                continue
            if (frame.shape[1], frame.shape[0]) != (w, h):
                frame = cv2.resize(frame, (w, h))
            cam.send(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    finally:
        if cam is not None:
            cam.close()


def list_audio():
    print("=== AUDIO OUTPUT DEVICES ===")
    print("Pick the one named 'CABLE Input (VB-Audio Virtual Cable)' for --audio-out\n")
    for i, d in enumerate(sd.query_devices()):
        if d["max_output_channels"] > 0:
            print(f"  [{i}] {d['name']}")


def main():
    p = argparse.ArgumentParser(description="CamBridge remote receiver")
    p.add_argument("--bind", default="0.0.0.0", help="Address to listen on (default all)")
    p.add_argument("--fps", type=int, default=30, help="Virtual camera fps (default 30)")
    p.add_argument("--audio-out", type=int, default=None,
                   help="Output device index for CABLE Input (auto-detected if omitted)")
    p.add_argument("--list-audio", action="store_true", help="List audio output devices and exit")
    args = p.parse_args()

    if args.list_audio:
        list_audio()
        return

    out_device = args.audio_out
    if out_device is None:
        out_device = find_cable_input()
        if out_device is None:
            print("ERROR: Could not find 'CABLE Input' device.")
            print("Install VB-Audio Virtual Cable, or run --list-audio and pass --audio-out <index>.")
            sys.exit(1)
        print(f"[audio] auto-detected CABLE Input at device index {out_device}")

    print("CamBridge receiver starting. Press Ctrl+C to stop.\n")

    vt = threading.Thread(target=video_server, args=(args.bind, args.fps), daemon=True)
    at = threading.Thread(target=audio_server, args=(args.bind, out_device), daemon=True)
    vt.start()
    at.start()

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping...")
        _stop.set()
        vt.join(timeout=3)
        at.join(timeout=3)


if __name__ == "__main__":
    main()
