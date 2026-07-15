"""
CamBridge - LOCAL sender.

Runs on the employee's LOCAL PC. Captures the real webcam and microphone and
streams them to the RELAY server, which forwards them to receiver.py on the
remote PC. Both ends connect OUTWARD to the relay, so no port forwarding is
needed on either home PC.

Usage:
    python sender.py --host relay.example.com --room mystandup
    python sender.py --host 203.0.113.10 --room mystandup --tls --cafile relay-cert.pem
    python sender.py --host 203.0.113.10 --room mystandup --tls --insecure
    python sender.py --list-devices                  # show cameras/mics, then exit

--host      = the RELAY server's public IP or domain.
--room      = a shared secret token; the sender and receiver that share a room get paired.
--tls       = encrypt the connection to the relay.
--cafile    = verify the relay against this certificate (PEM). Use for self-signed certs.
--insecure  = with --tls, encrypt but skip certificate verification (less safe).

This module is also imported by sender_gui.py; the GUI overrides `log` and calls
start()/stop().
"""

import argparse
import socket
import ssl
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

# Overridable status sink. The GUI replaces this with its own logger.
log = print


# --- TLS ------------------------------------------------------------------------
def make_client_ssl(use_tls, cafile=None, insecure=False):
    """Return an SSLContext for connecting to the relay, or None for plain TCP."""
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
def send_frame(sock, payload: bytes):
    sock.sendall(struct.pack(">I", len(payload)) + payload)


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


# --- Video thread --------------------------------------------------------------
def video_loop(host, room, ssl_ctx, cam_index, width, height, fps, quality):
    cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)  # DSHOW = fast on Windows
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    if not cap.isOpened():
        log(f"[video] ERROR: could not open camera index {cam_index}")
        _stop.set()
        return

    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    frame_interval = 1.0 / fps

    while not _stop.is_set():
        sock = connect_with_retry(host, VIDEO_PORT, room, "video", ssl_ctx)
        if sock is None:
            break
        try:
            while not _stop.is_set():
                t0 = time.time()
                ok, frame = cap.read()
                if not ok:
                    log("[video] frame grab failed; retrying")
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
            log(f"[video] connection lost ({e}); reconnecting")
            time.sleep(1)
        finally:
            try:
                sock.close()
            except OSError:
                pass

    cap.release()
    log("[video] stopped")


# --- Audio thread --------------------------------------------------------------
def audio_loop(host, room, ssl_ctx, mic_index):
    while not _stop.is_set():
        sock = connect_with_retry(host, AUDIO_PORT, room, "audio", ssl_ctx)
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
                    log("[audio] input overflow")
                send_frame(sock, bytes(data))
        except OSError as e:
            log(f"[audio] connection/stream issue ({e}); reconnecting")
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

    log("[audio] stopped")


# --- Start/stop API (used by CLI main and the GUI) -----------------------------
def start(host, room, use_tls=False, cafile=None, insecure=False,
          camera=0, mic=None, width=1280, height=720, fps=30, quality=80):
    """Start streaming in background threads. Returns the thread list."""
    _stop.clear()
    ssl_ctx = make_client_ssl(use_tls, cafile, insecure)
    vt = threading.Thread(
        target=video_loop,
        args=(host, room, ssl_ctx, camera, width, height, fps, quality),
        daemon=True,
    )
    at = threading.Thread(target=audio_loop, args=(host, room, ssl_ctx, mic), daemon=True)
    vt.start()
    at.start()
    return [vt, at]


def stop():
    _stop.set()


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
    p.add_argument("--tls", action="store_true", help="Encrypt the connection to the relay")
    p.add_argument("--cafile", help="Verify the relay against this certificate (PEM)")
    p.add_argument("--insecure", action="store_true", help="With --tls, skip certificate verification")
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

    enc = "TLS" if args.tls else "plain"
    log(f"CamBridge sender -> relay {args.host} (room '{args.room}', {enc}, "
        f"{args.width}x{args.height} @ {args.fps}fps)")
    log("Press Ctrl+C to stop.\n")

    threads = start(args.host, args.room, use_tls=args.tls, cafile=args.cafile,
                    insecure=args.insecure, camera=args.camera, mic=args.mic,
                    width=args.width, height=args.height, fps=args.fps, quality=args.quality)

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
