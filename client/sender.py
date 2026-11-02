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
    python sender.py --host relay.example.com --room mystandup --background blur --blur strong
    python sender.py --host relay.example.com --room mystandup --background image --background-image office.jpg
    python sender.py --list-devices                  # show cameras/mics, then exit

--host        = the RELAY server's public IP or domain.
--room        = a shared secret token; the sender and receiver that share a room get paired.
--tls         = encrypt the connection to the relay.
--cafile      = verify the relay against this certificate (PEM). Use for self-signed certs.
--insecure    = with --tls, encrypt but skip certificate verification (less safe).
--background  = off | blur | image: blur the room behind you or replace it with a picture
                (--background-image FILE); --blur light|medium|strong sets the blur amount.

This module is also imported by cambridge_gui.py (Send mode); the GUI overrides `log`
and calls start()/stop().
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


# --- Camera opening ------------------------------------------------------------
# Virtual cameras such as NVIDIA Broadcast only stream at the resolution chosen in
# their own app; asked for any other size they deliver one black frame per second.
# So after opening a camera we measure its real frame rate and, if it is stalled,
# retry at the usual native sizes. The frames are scaled to the requested size anyway.
NATIVE_SIZES = ((1920, 1080), (1280, 720), (640, 480), (2560, 1440), (3840, 2160), (1024, 576))
MIN_LIVE_FPS = 4          # below this the camera is considered stalled
PROBE_SECONDS = 1.0       # how long the frame rate is measured after the first frame


def _stream_fps(cap, seconds=PROBE_SECONDS):
    """Frames per second the camera really delivers, measured after its first frame."""
    deadline = time.time() + seconds + 2.0   # allow 2 s for the first frame to show up
    first = None
    n = 0
    while time.time() < deadline and not _stop.is_set():
        ok, _ = cap.read()
        if not ok:
            time.sleep(0.02)
            continue
        if first is None:
            first = time.time()
            deadline = first + seconds
            continue
        n += 1
    return n / seconds if first is not None else 0.0


def open_camera(cam_index, width, height, fps):
    """Open camera cam_index streaming at width x height, or at a native size if it
    only runs there. Returns an opened cv2.VideoCapture, or None (reason is logged)."""
    sizes = ((width, height),) + tuple(s for s in NATIVE_SIZES if s != (width, height))
    for w, h in sizes:
        cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)  # DSHOW = fast on Windows
        if not cap.isOpened():
            log(f"[video] ERROR: could not open camera index {cam_index}")
            return None
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        cap.set(cv2.CAP_PROP_FPS, fps)
        rate = _stream_fps(cap)
        got = f"{cap.get(cv2.CAP_PROP_FRAME_WIDTH):.0f}x{cap.get(cv2.CAP_PROP_FRAME_HEIGHT):.0f}"
        if rate >= MIN_LIVE_FPS:
            if (w, h) != (width, height):
                log(f"[video] camera streams at its native {got}; scaling to {width}x{height}")
            return cap
        cap.release()
        if _stop.is_set():
            return None
        log(f"[video] camera gives only {rate:.0f} fps at {got}; trying another size")
    log(f"[video] ERROR: camera index {cam_index} does not stream at any size "
        "(a virtual camera may need its own app running)")
    return None


# --- Video thread --------------------------------------------------------------
def video_loop(host, room, ssl_ctx, cam_index, width, height, fps, quality, background=None):
    cap = open_camera(cam_index, width, height, fps)
    if cap is None:
        _stop.set()
        return

    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    frame_interval = 1.0 / fps
    if background is not None:
        log(f"[video] virtual background: {background.describe()}")

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
                if background is not None:
                    try:
                        frame = background.apply(frame)
                    except Exception as e:  # keep streaming the plain picture
                        log(f"[video] virtual background failed ({e}); continuing without it")
                        background = None
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
          camera=0, mic=None, width=1280, height=720, fps=30, quality=80, background=None):
    """Start streaming in background threads. Returns the thread list.

    background: a background.VirtualBackground (blur / picture behind you) or None."""
    _stop.clear()
    ssl_ctx = make_client_ssl(use_tls, cafile, insecure)
    vt = threading.Thread(
        target=video_loop,
        args=(host, room, ssl_ctx, camera, width, height, fps, quality, background),
        daemon=True,
    )
    at = threading.Thread(target=audio_loop, args=(host, room, ssl_ctx, mic), daemon=True)
    vt.start()
    at.start()
    return [vt, at]


def stop():
    _stop.set()


# --- Utilities -----------------------------------------------------------------
def _dshow_camera_names():
    """Names of the DirectShow video capture devices, in DirectShow's own order.

    OpenCV's CAP_DSHOW backend numbers cameras by walking the same system device
    enumerator (CLSID_VideoInputDeviceCategory), so position i in this list is exactly
    camera index i. Talks COM through ctypes only; raises on non-Windows or COM errors."""
    import ctypes
    from ctypes import POINTER, Structure, byref, c_ubyte, c_ulong, c_ushort, c_void_p, c_wchar_p

    class GUID(Structure):
        _fields_ = [("Data1", c_ulong), ("Data2", c_ushort), ("Data3", c_ushort),
                    ("Data4", c_ubyte * 8)]

        def __init__(self, text):
            super().__init__()
            p = text.strip("{}").split("-")
            self.Data1, self.Data2, self.Data3 = int(p[0], 16), int(p[1], 16), int(p[2], 16)
            self.Data4 = (c_ubyte * 8)(*bytes.fromhex(p[3] + p[4]))

    class VARIANT(Structure):
        _fields_ = [("vt", c_ushort), ("r1", c_ushort), ("r2", c_ushort), ("r3", c_ushort),
                    ("bstr", c_void_p), ("pad", c_void_p)]

    CLSID_SystemDeviceEnum = GUID("{62BE5D10-60EB-11d0-BD3B-00A0C911CE86}")
    IID_ICreateDevEnum = GUID("{29840822-5B84-11D0-BD3B-00A0C911CE86}")
    CLSID_VideoInputDeviceCategory = GUID("{860BB310-5D01-11d0-BD3B-00A0C911CE86}")
    IID_IPropertyBag = GUID("{55272A00-42CB-11CE-8135-00AA004BB851}")
    CLSCTX_INPROC_SERVER, VT_BSTR, HRESULT = 1, 8, ctypes.HRESULT
    ole32, oleaut32 = ctypes.windll.ole32, ctypes.windll.oleaut32

    def method(obj, index, restype, *argtypes):
        """Bind COM vtable slot `index` of interface pointer `obj`."""
        vtbl = ctypes.cast(obj, POINTER(POINTER(c_void_p)))[0]
        return ctypes.WINFUNCTYPE(restype, c_void_p, *argtypes)(vtbl[index])

    def release(obj):
        method(obj, 2, c_ulong)(obj)

    names = []
    uninit = ole32.CoInitializeEx(None, 0) in (0, 1)  # S_OK / S_FALSE: we must uninit
    try:
        dev_enum = c_void_p()
        hr = ole32.CoCreateInstance(byref(CLSID_SystemDeviceEnum), None, CLSCTX_INPROC_SERVER,
                                    byref(IID_ICreateDevEnum), byref(dev_enum))
        if hr != 0 or not dev_enum:
            raise OSError(f"CoCreateInstance(SystemDeviceEnum) failed: 0x{hr & 0xFFFFFFFF:08X}")
        try:
            enum_mon = c_void_p()
            # ICreateDevEnum::CreateClassEnumerator(REFCLSID, IEnumMoniker**, DWORD) = slot 3
            hr = method(dev_enum, 3, HRESULT, POINTER(GUID), POINTER(c_void_p), c_ulong)(
                dev_enum, byref(CLSID_VideoInputDeviceCategory), byref(enum_mon), 0)
            if hr != 0 or not enum_mon:   # S_FALSE: the category is empty
                return names
            try:
                # IEnumMoniker::Next(ULONG, IMoniker**, ULONG*) = slot 3
                next_ = method(enum_mon, 3, HRESULT, c_ulong, POINTER(c_void_p), POINTER(c_ulong))
                while True:
                    mon, fetched = c_void_p(), c_ulong(0)
                    if next_(enum_mon, 1, byref(mon), byref(fetched)) != 0 or not fetched.value:
                        break
                    try:
                        name = ""
                        bag = c_void_p()
                        # IMoniker::BindToStorage(IBindCtx*, IMoniker*, REFIID, void**) = slot 9
                        hr = method(mon, 9, HRESULT, c_void_p, c_void_p, POINTER(GUID),
                                    POINTER(c_void_p))(mon, None, None, byref(IID_IPropertyBag),
                                                       byref(bag))
                        if hr == 0 and bag:
                            try:
                                var = VARIANT()
                                # IPropertyBag::Read(LPCOLESTR, VARIANT*, IErrorLog*) = slot 3
                                hr = method(bag, 3, HRESULT, c_wchar_p, POINTER(VARIANT),
                                            c_void_p)(bag, "FriendlyName", byref(var), None)
                                if hr == 0 and var.vt == VT_BSTR and var.bstr:
                                    name = ctypes.wstring_at(var.bstr)
                                oleaut32.VariantClear(byref(var))
                            finally:
                                release(bag)
                        names.append(name or f"Camera {len(names)}")
                    finally:
                        release(mon)
            finally:
                release(enum_mon)
        finally:
            release(dev_enum)
    finally:
        if uninit:
            ole32.CoUninitialize()
    return names


def list_cameras(max_index=6):
    """Return [(index, label)] for the PC's cameras, e.g. (0, '0: Logitech C920').

    OpenCV only knows cameras by DirectShow index, and Windows' DirectShow enumerator
    is the ground truth for that order, so the names are read straight from it (no
    camera is opened, so nothing flickers). If that fails (not Windows, COM error),
    fall back to probing indexes with OpenCV under generic labels."""
    try:
        names = _dshow_camera_names()
        if names:
            return [(i, f"{i}: {n}") for i, n in enumerate(names)]
    except Exception as e:
        log(f"[video] DirectShow camera names unavailable ({e}); probing indexes")
    found = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            found.append(i)
        cap.release()
    return [(i, f"{i}: Camera {i}") for i in found]


def list_devices():
    print("=== CAMERAS (use --camera <index>) ===")
    for i, label in list_cameras():
        print(f"  {label}")
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
    p.add_argument("--background", choices=("off", "blur", "image"), default="off",
                   help="Virtual background: blur the room or replace it with a picture")
    p.add_argument("--background-image", metavar="FILE",
                   help="Picture for --background image (jpg/png)")
    p.add_argument("--blur", choices=("light", "medium", "strong"), default="medium",
                   help="Blur strength for --background blur (default medium)")
    p.add_argument("--list-devices", action="store_true", help="List cameras/mics and exit")
    args = p.parse_args()

    if args.list_devices:
        list_devices()
        return

    if not args.host:
        p.error("--host is required (the relay server IP). Use --list-devices to inspect devices.")
    if args.background == "image" and not args.background_image:
        p.error("--background image needs --background-image FILE")

    bg = None
    if args.background != "off":
        import background
        try:
            bg = background.create(args.background, image=args.background_image, blur=args.blur)
        except (OSError, ValueError) as e:
            p.error(f"virtual background: {e}")

    enc = "TLS" if args.tls else "plain"
    log(f"CamBridge sender -> relay {args.host} (room '{args.room}', {enc}, "
        f"{args.width}x{args.height} @ {args.fps}fps)")
    log("Press Ctrl+C to stop.\n")

    threads = start(args.host, args.room, use_tls=args.tls, cafile=args.cafile,
                    insecure=args.insecure, camera=args.camera, mic=args.mic,
                    width=args.width, height=args.height, fps=args.fps, quality=args.quality,
                    background=bg)

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
