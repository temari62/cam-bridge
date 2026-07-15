"""
CamBridge - RELAY server.

Runs on a small cloud VPS with a PUBLIC IP (e.g. a $5/mo Linux box). Both the
local sender and the remote receiver connect OUTWARD to this relay, so neither
home PC needs port forwarding or a public IP of its own.

The relay pairs a sender ('S') and a receiver ('R') that use the same ROOM token,
then pipes the sender's stream to the receiver. Video and audio use separate
ports. Only the standard library is required, so plain `python3 relay.py` works.

Usage (on the VPS):
    python3 relay.py
    python3 relay.py --video-port 50007 --audio-port 50008 --bind 0.0.0.0

Open the two TCP ports in the VPS firewall / security group.

Handshake each client sends immediately on connect:
    MAGIC(4) + role(1: 'S'|'R') + room_len(1) + room(room_len bytes, utf-8)
"""

import argparse
import socket
import threading
import time

MAGIC = b"CBR1"  # CamBridge Relay protocol v1


def recv_exactly(sock, n):
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)


def read_handshake(sock):
    """Return (role, room) or None if malformed/closed."""
    header = recv_exactly(sock, 6)  # MAGIC(4) + role(1) + room_len(1)
    if header is None or header[:4] != MAGIC:
        return None
    role = chr(header[4])
    room_len = header[5]
    room_bytes = recv_exactly(sock, room_len)
    if room_bytes is None:
        return None
    return role, room_bytes.decode("utf-8", "replace")


def pipe(name, room, src, dst):
    """Forward bytes one way (sender -> receiver) until either side closes."""
    print(f"[{name}] room '{room}': paired, streaming")
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass
    finally:
        for s in (src, dst):
            try:
                s.close()
            except OSError:
                pass
        print(f"[{name}] room '{room}': closed")


class Channel:
    """One media channel on one port. Pairs 'S' and 'R' sockets by room token."""

    def __init__(self, name):
        self.name = name
        self.lock = threading.Lock()
        self.waiting = {}  # room -> {'S': sock, 'R': sock}

    def register(self, role, room, sock):
        with self.lock:
            slot = self.waiting.setdefault(room, {})
            old = slot.get(role)
            if old is not None:
                # A reconnect for the same role: drop the stale socket.
                try:
                    old.close()
                except OSError:
                    pass
            slot[role] = sock
            if "S" in slot and "R" in slot:
                s_sock, r_sock = slot["S"], slot["R"]
                del self.waiting[room]
                threading.Thread(
                    target=pipe, args=(self.name, room, s_sock, r_sock), daemon=True
                ).start()


def handle(channel, conn, addr):
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    try:
        hs = read_handshake(conn)
    except OSError:
        hs = None
    if hs is None or hs[0] not in ("S", "R"):
        conn.close()
        return
    role, room = hs
    print(f"[{channel.name}] {role} joined room '{room}' from {addr[0]}")
    channel.register(role, room, conn)


def serve(channel, bind, port):
    ls = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    ls.bind((bind, port))
    ls.listen(50)
    print(f"[{channel.name}] listening on {bind}:{port}")
    while True:
        conn, addr = ls.accept()
        threading.Thread(target=handle, args=(channel, conn, addr), daemon=True).start()


def main():
    p = argparse.ArgumentParser(description="CamBridge relay server (run on a public VPS)")
    p.add_argument("--bind", default="0.0.0.0", help="Listen address (default all interfaces)")
    p.add_argument("--video-port", type=int, default=50007)
    p.add_argument("--audio-port", type=int, default=50008)
    args = p.parse_args()

    video = Channel("video")
    audio = Channel("audio")
    threading.Thread(target=serve, args=(video, args.bind, args.video_port), daemon=True).start()
    threading.Thread(target=serve, args=(audio, args.bind, args.audio_port), daemon=True).start()

    print("CamBridge relay running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping.")


if __name__ == "__main__":
    main()
