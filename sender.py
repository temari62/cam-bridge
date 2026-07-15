"""
CamBridge - LOCAL sender.

Runs on the employee's LOCAL PC. Captures the real webcam and microphone and
streams them to the RELAY server, which forwards them to receiver.py on the
remote PC. Both ends connect OUTWARD to the relay, so no port forwarding is
needed on either home PC.

Usage:
    python sender.py --host relay.example.com --room mystandup
    python sender.py --host 203.0.113.10 --room mystandup --width 960 --height 540 --fps 20
    python sender.py --list-devices                  # show cameras/mics, then exit

--host  = the RELAY server's public IP or domain.
--room  = a shared secret token; the sender and receiver that share a room get paired.
"""

import argparse
import socket
import struct
import threading
import time

import cv2
import numpy as np
import sounddevice as sd

# --- Audio format (must match receiver.py) -------------------------------------
SAMPLE_RATE = 48000
CHANNELS = 1
DTYPE = "int16"
BLOCKSIZE = 1024  # samples per audio frame

VIDEO_PORT = 50007
AUDIO_PORT = 50008

MAGIC = b"CBR1"  # CamBridge Relay protocol v1
ROLE = "S"       # this program is the Sender

_stop = threading.Event()


# --- Framing / relay handshake -------------------------------------------------
def send_frame(sock, payload: bytes):
    sock.sendall(struct.pack(">I", len(payload)) + payload)


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


# --- Video thread --------------------------------------------------------------
def video_loop(host, room, cam_index, width, height, fps, quality):
    cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)  # DSHOW = fast on Windows
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    if not cap.isOpened():
        print(f"[video] ERROR: could not open camera index {cam_index}")
        _stop.set()
        return

    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    frame_interval = 1.0 / fps

    while not _stop.is_set():
        sock = connect_with_retry(host, VIDEO_PORT, room, "video")
        if sock is None:
            break
        try:
            while not _stop.is_set():
                t0 = time.time()
                ok, frame = cap.read()
                if not ok:
                    print("[video] frame grab failed; retrying")
                    time.sleep(0.05)
                    continue
                frame = cv2.resize(frame, (width, height))
                ok, buf = cv2.imencode(".jpg", frame, encode_params)
                if not ok:
                    continue
                send_frame(sock, buf.tobytes())
                dt = frame_interval - (time.time() - t0)
                if dt > 0:
                    time.sleep(dt)
        except OSError as e:
            print(f"[video] connection lost ({e}); reconnecting")
            time.sleep(1)
        finally:
            try:
                sock.close()
            except OSError:
                pass

    cap.release()
    print("[video] stopped")


# --- Audio thread --------------------------------------------------------------
def audio_loop(host, room, mic_index):
    while not _stop.is_set():
        sock = connect_with_retry(host, AUDIO_PORT, room, "audio")
        if sock is None:
            break
        stream = None
        try:
            stream = sd.RawInputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype=DTYPE,
                blocksize=BLOCKSIZE,
                device=mic_index,
            )
            stream.start()
            while not _stop.is_set():
                data, overflowed = stream.read(BLOCKSIZE)
                if overflowed:
                    print("[audio] input overflow")
                send_frame(sock, bytes(data))
        except OSError as e:
            print(f"[audio] connection/stream issue ({e}); reconnecting")
            time.sleep(1)
        finally:
            if stream is not None:
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass
            try:
                sock.close()
            except OSError:
                pass

    print("[audio] stopped")


# --- Utilities -----------------------------------------------------------------
def list_devices():
    print("=== CAMERAS (try indexes 0,1,2 ... with --camera) ===")
    for i in range(6):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            print(f"  camera index {i}: available")
            cap.release()
    print("\n=== AUDIO INPUT DEVICES (use --mic <index>) ===")
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            print(f"  [{i}] {d['name']}")


def main():
    p = argparse.ArgumentParser(description="CamBridge local sender")
    p.add_argument("--host", help="Relay server public IP or domain")
    p.add_argument("--room", default="default", help="Shared room token to pair with the receiver")
    p.add_argument("--camera", type=int, default=0, help="Local camera index (default 0)")
    p.add_argument("--mic", type=int, default=None, help="Mic device index (default: system default)")
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=720)
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--quality", type=int, default=80, help="JPEG quality 1-100 (default 80)")
    p.add_argument("--list-devices", action="store_true", help="List cameras/mics and exit")
    args = p.parse_args()

    if args.list_devices:
        list_devices()
        return

    if not args.host:
        p.error("--host is required (the relay server IP). Use --list-devices to inspect devices.")

    print(f"CamBridge sender -> relay {args.host} (room '{args.room}', "
          f"{args.width}x{args.height} @ {args.fps}fps)")
    print("Press Ctrl+C to stop.\n")

    vt = threading.Thread(
        target=video_loop,
        args=(args.host, args.room, args.camera, args.width, args.height, args.fps, args.quality),
        daemon=True,
    )
    at = threading.Thread(target=audio_loop, args=(args.host, args.room, args.mic), daemon=True)
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
