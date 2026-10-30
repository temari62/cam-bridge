"""
CamBridge - one app for both PCs (Windows 11 / Fluent look).

Type the relay address + room token, pick the relay's certificate file, then click:
  * Send     - LOCAL PC: stream this PC's camera + mic out to the relay.
  * Receive  - REMOTE PC: feed the stream into the virtual camera + mic, then pick
               "OBS Virtual Camera" and "CABLE Output" in your meeting app.
Click the same button again to stop. The "?" button opens the setup guide and clicking the
status badge opens the log in a side panel.

The connection is always encrypted (TLS) and the relay certificate is required.

    python cambridge_gui.py
"""

import argparse
import json
import os
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import theme
import updater
from version import __version__

CONFIG = os.path.join(os.path.expanduser("~"), ".cambridge.json")
# Settings files of the old separate Sender/Receiver apps, migrated on first run.
LEGACY_CONFIGS = (("receive", os.path.join(os.path.expanduser("~"), ".cambridge_receiver.json")),
                  ("send", os.path.join(os.path.expanduser("~"), ".cambridge_sender.json")))
_log_queue = queue.Queue()

H1 = ("Segoe UI Semibold", 18)
H2 = ("Segoe UI Semibold", 11)
MONO = ("Cascadia Mono", 9)
STATUS = ("Segoe UI Semibold", 13)

SUBTITLE = "Send this PC's camera + mic, or receive them into the meeting PC."
RECEIVE_HINT = "In your meeting app: Camera = OBS Virtual Camera, Microphone = CABLE Output"

# --- Help window text: (style, text). Styles: h1, h2, body, code. ---------------
HELP = [
    ("h1", "How CamBridge works"),
    ("body", "Three pieces: a RELAY server on the internet, the PC you sit at (SEND), and the PC "
             "that joins the meeting (RECEIVE). Both PCs connect out to the relay, so no port "
             "forwarding is needed on either home network. The relay pairs the two PCs that use "
             "the same room token and pipes the camera + mic across."),

    ("h1", "1. Set up the relay server (once)"),
    ("h2", "Rent a small VPS"),
    ("body", "Any provider works (Hetzner, DigitalOcean, Vultr, Lightsail...). The cheapest Ubuntu "
             "plan is enough. Note its public IP address."),
    ("h2", "Open the ports"),
    ("body", "Allow inbound TCP 50007 and 50008 in the provider's firewall / security group. "
             "If ufw is enabled on the server:"),
    ("code", "sudo ufw allow 50007/tcp && sudo ufw allow 50008/tcp"),
    ("h2", "Copy the relay folder and make a certificate"),
    ("body", "Copy the relay/ folder (relay.py + gen_cert.sh) to the server. Then, inside that "
             "folder, create the certificate using the server's public IP:"),
    ("code", "bash gen_cert.sh 203.0.113.10"),
    ("body", "This writes relay-cert.pem (share with every PC) and relay-key.pem (keep on the "
             "server only)."),
    ("h2", "Start the relay"),
    ("code", "python3 relay.py --tls --certfile relay-cert.pem --keyfile relay-key.pem"),
    ("body", "You should see two 'listening on 0.0.0.0:5000x (TLS)' lines. To keep it running "
             "after you log out:"),
    ("code", "nohup python3 relay.py --tls --certfile relay-cert.pem --keyfile relay-key.pem "
             "> relay.log 2>&1 &"),
    ("body", "Only one relay can run at a time. If you see 'Address already in use', an older copy "
             "is still running: find it with 'ss -ltnp | grep 5000' and stop it with "
             "'pkill -f relay.py' before starting again."),

    ("h1", "2. Put the certificate on each PC"),
    ("body", "Download relay-cert.pem from the server to both PCs. In PowerShell on Windows:"),
    ("code", "scp root@203.0.113.10:/root/relay/relay-cert.pem D:\\relay-cert.pem"),
    ("body", "Then click Browse next to 'Cert file' and pick it. The app always encrypts the "
             "connection and uses this file to verify it is talking to your relay, so it is "
             "required on both PCs. Never copy relay-key.pem off the server."),

    ("h1", "3. Relay server and room token"),
    ("body", "Relay server: the VPS public IP (or domain) from step 1. Room token: a hard-to-guess "
             "word or phrase, e.g. jose-standup-7fKq. Both PCs must use the SAME relay and token "
             "to be paired. Treat the token like a password."),

    ("h1", "4. Every meeting"),
    ("h2", "On the meeting PC"),
    ("body", "Open CamBridge, fill in the relay, token and cert file, click Receive. Wait for "
             "'virtual camera started' / 'output ready' in the log. Then in your meeting app pick "
             "Camera = OBS Virtual Camera and Microphone = CABLE Output, and join the meeting. "
             "(Teams: Settings > Devices.  Zoom: Settings > Video / Audio.  Meet: gear icon.)"),
    ("h2", "On the PC you sit at"),
    ("body", "Open CamBridge with the same relay, token and cert file and click Send. The webcam "
             "light turns on and the meeting PC's virtual camera starts showing you. Click the "
             "button again to stop. Order does not matter; whichever starts first waits for the "
             "other and both reconnect automatically."),
    ("body", "The meeting PC also needs the virtual devices installed once: the OBS Virtual Camera "
             "module and VB-CABLE. The CamBridge installer does both when 'virtual camera + "
             "microphone' is ticked."),

    ("h1", "Updates"),
    ("body", "CamBridge checks GitHub for a newer release each time it starts. When one exists "
             "a bar appears at the top of the window; click 'Update now' to download and "
             "install it (one Windows permission prompt), after which the app restarts. "
             "Settings are kept. Use 'Check for updates' below to check by hand."),

    ("h1", "Troubleshooting"),
    ("body", "'waiting for relay ... actively refused / timed out': the relay is not running or "
             "the ports are blocked. Check the relay process and firewall on the VPS."),
    ("body", "'SSL: UNEXPECTED_EOF' or 'forcibly closed by the remote host': the relay was started "
             "without --tls. Restart it with the --tls flags above."),
    ("body", "'certificate verify failed': the cert file does not match this relay, or the relay "
             "address typed here differs from the IP given to gen_cert.sh. Regenerate the cert "
             "with the exact address you type into 'Relay server'."),
    ("body", "Connected but no video/audio: the two PCs use different room tokens, or the other "
             "side is not running yet."),
    ("body", "Choppy: lower Width / Height / FPS under 'Camera' before clicking Send."),
    ("body", "Echo in the meeting: mute the meeting PC's speakers or use headphones there."),
]


def gui_log(*args):
    _log_queue.put(" ".join(str(a) for a in args))


def load_cfg():
    try:
        with open(CONFIG) as f:
            return json.load(f)
    except Exception:
        pass
    # First run after upgrading: merge the old apps' settings. The sender's file is
    # read last, so it wins on shared fields and on the mode if both exist.
    cfg = {}
    for mode, path in LEGACY_CONFIGS:
        try:
            with open(path) as f:
                cfg.update(json.load(f))
            cfg["mode"] = mode
        except Exception:
            pass
    return cfg


def save_cfg(cfg):
    try:
        with open(CONFIG, "w") as f:
            json.dump(cfg, f)
    except Exception:
        pass


def load_engine(mode):
    """Import the sender/receiver engine lazily, so each mode only needs its own libraries."""
    if mode == "send":
        import sender as core
    else:
        import receiver as core
    core.log = gui_log
    return core


def section(parent, title):
    """A flat section header (bold label + hairline) on the shared background."""
    head = ttk.Frame(parent)
    head.pack(fill="x", pady=(18, 8))
    ttk.Label(head, text=title, font=H2).pack(anchor="w")
    ttk.Separator(head).pack(fill="x", pady=(6, 0))


# Field icons: (Segoe Fluent / MDL2 glyph, plain-Unicode fallback).
ICONS = {
    "host":   ("", "☁"),   # cloud
    "room":   ("", "🔑"),  # lock / key
    "cert":   ("", "📄"),  # certificate / page
    "camera": ("", "📷"),  # camera
    "width":  ("↔", "↔"),   # left-right arrow
    "height": ("↕", "↕"),   # up-down arrow
    "fps":    ("", "⏱"),   # stopwatch
}
_icon_font = None


def icon_font():
    """Pick the Windows icon font if installed, else a symbol font for the fallbacks."""
    global _icon_font
    if _icon_font is None:
        import tkinter.font as tkfont
        fams = set(tkfont.families())
        for name in ("Segoe Fluent Icons", "Segoe MDL2 Assets"):
            if name in fams:
                _icon_font = (name, 11, True)
                break
        else:
            _icon_font = ("Segoe UI Symbol", 11, False)
    return _icon_font


def field_label(parent, key, text):
    """A label cell: small icon followed by the field name."""
    name, size, has_glyphs = icon_font()
    glyph, fallback = ICONS[key]
    cell = ttk.Frame(parent)
    ttk.Label(cell, text=glyph if has_glyphs else fallback, font=(name, size),
              foreground=theme.IDLE_GRAY).pack(side="left", padx=(0, 6))
    ttk.Label(cell, text=text).pack(side="left")
    return cell


class StatusBadge(tk.Canvas):
    """A rounded pill with centred text. Tk labels can't round corners, so draw one."""

    RADIUS = 14
    PAD_X = 20
    PAD_Y = 6

    def __init__(self, parent, command=None):
        super().__init__(parent, highlightthickness=0, borderwidth=0,
                         background=theme.SURFACE, cursor="hand2")
        self._font = STATUS
        if command is not None:
            self.bind("<Button-1>", lambda e: command())
        self.set("Idle", theme.IDLE_YELLOW)

    def set(self, text, color):
        self.delete("all")
        fg = "#1a1a1a" if color == theme.IDLE_YELLOW else "#ffffff"
        import tkinter.font as tkfont
        f = tkfont.Font(font=self._font)
        w = f.measure(text) + 2 * self.PAD_X
        h = f.metrics("linespace") + 2 * self.PAD_Y
        self.configure(width=w, height=h)
        r = min(self.RADIUS, h // 2)
        pts = [r, 0, w - r, 0, w, 0, w, r, w, h - r, w, h, w - r, h, r, h,
               0, h, 0, h - r, 0, r, 0, 0]
        self.create_polygon(pts, smooth=True, fill=color, outline=color)
        self.create_text(w / 2, h / 2, text=text, font=self._font, fill=fg)


class App:
    def __init__(self, root, mode=None):   # mode kept for installer compatibility (--mode)
        self.root = root
        self.threads = []
        self.core = None      # engine module while running
        self.running = None   # "send" | "receive" | None
        self.help_win = None
        self.cfg = cfg = load_cfg()

        root.title("CamBridge")
        root.geometry("620x400")
        root.minsize(560, 380)
        self.mode_kind = theme.apply(root)
        theme.set_icon(root)

        outer = ttk.Frame(root, padding=(24, 20))
        outer.pack(fill="both", expand=True)

        # --- Title row with help button ---
        head = ttk.Frame(outer)
        head.pack(fill="x")
        ttk.Label(head, text="CamBridge", font=H1).pack(side="left")
        ttk.Label(head, text=f"v{__version__}", foreground=theme.IDLE_GRAY,
                  font=("Segoe UI", 9)).pack(side="left", anchor="s", padx=(8, 0), pady=(0, 5))
        ttk.Button(head, text="?", width=3, command=self.show_help).pack(side="right")
        self.subtitle = ttk.Label(outer, text=SUBTITLE, foreground=theme.IDLE_GRAY)
        self.subtitle.pack(anchor="w")

        # --- Update banner (hidden until a newer release is found) ---
        self.update_rel = None
        self.banner = ttk.Frame(outer)
        self.banner_text = ttk.Label(self.banner, font=H2)
        self.banner_text.pack(side="left")
        self.banner_later = ttk.Button(self.banner, text="Later", width=7,
                                       command=self._hide_banner)
        self.banner_later.pack(side="right")
        self.banner_btn = ttk.Button(self.banner, text="Update now", style="Accent.TButton",
                                     command=self.update_now)
        self.banner_btn.pack(side="right", padx=(0, 8))

        # --- Connection ---
        # Tabs: Connection | Camera
        tabs = ttk.Notebook(outer)
        tabs.pack(fill="x", pady=(18, 0))
        conn = ttk.Frame(tabs, padding=(12, 14))
        tabs.add(conn, text="  Connection  ")
        conn.columnconfigure(1, weight=3)
        conn.columnconfigure(3, weight=2)

        field_label(conn, "host", "Relay server").grid(row=0, column=0, sticky="w", pady=6, padx=(0, 10))
        self.host = ttk.Entry(conn)
        self.host.grid(row=0, column=1, sticky="we", pady=6)
        self.host.insert(0, cfg.get("host", ""))

        field_label(conn, "room", "Room token").grid(row=0, column=2, sticky="w", pady=6, padx=(16, 10))
        self.room = ttk.Entry(conn)
        self.room.grid(row=0, column=3, columnspan=2, sticky="we", pady=6)
        self.room.insert(0, cfg.get("room", "default"))

        field_label(conn, "cert", "Cert file").grid(row=1, column=0, sticky="w", pady=6, padx=(0, 10))
        self.cafile = ttk.Entry(conn)
        self.cafile.grid(row=1, column=1, columnspan=3, sticky="we", pady=6)
        self.cafile.insert(0, cfg.get("cafile", ""))
        self.browse_btn = ttk.Button(conn, text="Browse", width=9, command=self._browse)
        self.browse_btn.grid(row=1, column=4, sticky="e", padx=(8, 0))

        # --- Camera (used when sending) ---
        adv = ttk.Frame(tabs, padding=(12, 14))
        tabs.add(adv, text="  Camera (when sending)  ")
        adv.columnconfigure(1, weight=1)
        # Camera: a dropdown of detected devices, filled in the background (opening
        # each DirectShow index takes a moment). self.cameras maps label -> index.
        field_label(adv, "camera", "Camera").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.cameras = {}
        self.camera = ttk.Combobox(adv, state="readonly", values=["Detecting cameras..."])
        self.camera.grid(row=0, column=1, columnspan=2, sticky="we", pady=(0, 8))
        self.camera.current(0)
        self.refresh_btn = ttk.Button(adv, text="↻", width=3, command=self._scan_cameras)
        self.refresh_btn.grid(row=0, column=3, sticky="w", padx=(8, 0), pady=(0, 8))

        size = ttk.Frame(adv)
        size.grid(row=1, column=0, columnspan=4, sticky="w")
        field_label(size, "width", "Width").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.width = ttk.Entry(size, width=7)
        self.width.grid(row=0, column=1, sticky="w", padx=(0, 18))
        self.width.insert(0, str(cfg.get("width", 1280)))
        field_label(size, "height", "Height").grid(row=0, column=2, sticky="w", padx=(0, 8))
        self.height = ttk.Entry(size, width=7)
        self.height.grid(row=0, column=3, sticky="w", padx=(0, 18))
        self.height.insert(0, str(cfg.get("height", 720)))
        field_label(size, "fps", "FPS").grid(row=0, column=4, sticky="w", padx=(0, 8))
        self.fps = ttk.Entry(size, width=6)
        self.fps.grid(row=0, column=5, sticky="w")
        self.fps.insert(0, str(cfg.get("fps", 30)))
        self._scan_cameras()

        # --- Action bar: Send / Receive (each doubles as Stop) ---
        bar = ttk.Frame(outer)
        bar.pack(fill="x", pady=(40, 0))
        self.send_btn = ttk.Button(bar, text="Send", width=14, style="Big.Accent.TButton",
                                   command=lambda: self.toggle("send"))
        self.send_btn.pack(side="left")
        self.recv_btn = ttk.Button(bar, text="Receive", width=14, style="Big.Accent.TButton",
                                   command=lambda: self.toggle("receive"))
        self.recv_btn.pack(side="left", padx=10)
        self.buttons = {"send": self.send_btn, "receive": self.recv_btn}
        # Status badge: rounded pill, yellow when idle, green while sending/receiving.
        self.status = StatusBadge(bar, command=self.toggle_log)
        self.status.pack(side="right")
        self._set_status("Idle", theme.IDLE_YELLOW)
        ttk.Label(bar, text="click for log", foreground=theme.IDLE_GRAY,
                  font=("Segoe UI", 8)).pack(side="right", padx=(0, 8))

        self.hint = ttk.Label(outer, text="", foreground=theme.IDLE_GRAY)
        self.hint.pack(anchor="w")

        # --- Log: a side panel next to the main window, toggled by the status badge ---
        self.log_win = log_win = tk.Toplevel(root)
        log_win.withdraw()
        log_win.title("Status log")
        log_win.transient(root)
        log_win.configure(background=theme.SURFACE)
        log_win.protocol("WM_DELETE_WINDOW", self.toggle_log)
        theme.set_icon(log_win)
        logframe = ttk.Frame(log_win, padding=(12, 10))
        logframe.pack(fill="both", expand=True)
        # tk.Text + ttk.Scrollbar rather than ScrolledText, whose classic scrollbar
        # ignores the theme (a light bar in dark mode).
        self.logbox = tk.Text(logframe, state="disabled", font=MONO, wrap="word")
        scroll = ttk.Scrollbar(logframe, orient="vertical", command=self.logbox.yview)
        self.logbox.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.logbox.pack(side="left", fill="both", expand=True)
        theme.style_log(self.logbox)
        root.bind("<Configure>", self._follow_main)

        root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(150, self._drain)
        self.root.after(2000, lambda: self.check_updates(silent=True))

    # --- Updates ------------------------------------------------------------------
    def check_updates(self, silent=False):
        """Ask GitHub for a newer release on a worker thread. silent: no 'up to date' popup."""
        def work():
            try:
                rel = updater.check()
            except Exception as e:
                self.root.after(0, lambda: self._update_result(None, e, silent))
                return
            self.root.after(0, lambda: self._update_result(rel, None, silent))
        threading.Thread(target=work, daemon=True).start()

    def _update_result(self, rel, err, silent):
        if not self.root.winfo_exists():
            return
        if err is not None:
            gui_log(f"update check failed: {err}")
            if not silent:
                messagebox.showwarning("CamBridge", f"Could not check for updates:\n{err}")
            return
        if rel is None:
            gui_log(f"up to date (v{__version__})")
            if not silent:
                messagebox.showinfo("CamBridge", f"You have the latest version (v{__version__}).")
            return
        self.update_rel = rel
        gui_log(f"update available: v{rel.version} (installed v{__version__})")
        self._banner_idle_text()
        self.banner_btn.configure(
            text="Update now" if updater.is_installed_build() else "Download",
            state="normal")
        self.banner_later.configure(state="normal")
        self.banner.pack(fill="x", pady=(14, 0), after=self.subtitle)

    def _banner_idle_text(self):
        self.banner_text.configure(
            text=f"CamBridge v{self.update_rel.version} is available  (you have v{__version__})")

    def _hide_banner(self):
        self.banner.pack_forget()

    def update_now(self):
        rel = self.update_rel
        if rel is None:
            return
        if not updater.is_installed_build():
            # Running from source: the installer can't replace .py files, so just
            # open the release page in the browser.
            updater.open_release_page(rel)
            return
        if self.running is not None:
            if not messagebox.askyesno("CamBridge", "Updating will stop the current session.\n"
                                       "Continue?"):
                return
            self.stop()
        self.banner_btn.configure(state="disabled")
        self.banner_later.configure(state="disabled")
        self.banner_text.configure(text="Downloading update...")

        def progress(done, total):
            pct = f" {done * 100 // total}%" if total else f" {done // 1024} KB"
            self.root.after(0, lambda: self.banner_text.configure(
                text="Downloading update..." + pct))

        def work():
            try:
                path = updater.download(rel, progress)
                self.root.after(0, lambda: self._run_installer(path))
            except Exception as e:
                self.root.after(0, lambda: self._update_failed(e))
        threading.Thread(target=work, daemon=True).start()

    def _run_installer(self, path):
        self.banner_text.configure(text="Installing... CamBridge will restart.")
        gui_log(f"installing update from {path}")
        try:
            updater.install(path)
        except Exception as e:
            self._update_failed(e)
            return
        # The installer replaces this exe and relaunches the app; get out of its way.
        self.root.after(500, self._on_close)

    def _update_failed(self, err):
        gui_log(f"update failed: {err}")
        self._banner_idle_text()
        self.banner_btn.configure(state="normal")
        self.banner_later.configure(state="normal")
        messagebox.showerror("CamBridge", f"Update failed:\n{err}")

    # --- Help -------------------------------------------------------------------
    def show_help(self):
        if self.help_win is not None and self.help_win.winfo_exists():
            self.help_win.lift()
            self.help_win.focus_force()
            return
        win = tk.Toplevel(self.root)
        self.help_win = win
        win.title("CamBridge - Setup guide")
        win.geometry("640x720")
        win.minsize(480, 400)
        win.configure(background=theme.SURFACE)
        theme.set_icon(win)

        frame = ttk.Frame(win, padding=(16, 12))
        frame.pack(fill="both", expand=True)
        text = tk.Text(frame, wrap="word", font=("Segoe UI", 10), padx=12, pady=10,
                       spacing3=6, cursor="arrow")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        foot = ttk.Frame(frame)
        foot.pack(side="bottom", fill="x", pady=(10, 0))
        ttk.Label(foot, text=f"CamBridge v{__version__}", foreground=theme.IDLE_GRAY
                  ).pack(side="left")
        ttk.Button(foot, text="Close", command=win.destroy).pack(side="right")
        ttk.Button(foot, text="Check for updates",
                   command=lambda: self.check_updates(silent=False)
                   ).pack(side="right", padx=(0, 8))
        scroll.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)
        theme.style_log(text)
        text.tag_configure("h1", font=("Segoe UI Semibold", 13), spacing1=14, spacing3=4)
        text.tag_configure("h2", font=("Segoe UI Semibold", 10), spacing1=6, spacing3=2)
        text.tag_configure("body", font=("Segoe UI", 10))
        text.tag_configure("code", font=MONO, lmargin1=16, lmargin2=16,
                           background=theme.SURFACE, spacing1=2, spacing3=8)
        for style, chunk in HELP:
            text.insert("end", chunk + "\n", style)
        text.configure(state="disabled")

    # --- Log side panel -----------------------------------------------------------
    LOG_WIDTH = 440
    LOG_GAP = 8

    def _log_visible(self):
        return self.log_win.state() == "normal"

    def _place_log(self):
        """Dock the log panel to the right edge of the main window, same height."""
        r = self.root
        x = r.winfo_rootx() + r.winfo_width() + self.LOG_GAP
        y = r.winfo_rooty()
        self.log_win.geometry(f"{self.LOG_WIDTH}x{r.winfo_height()}+{x}+{y}")

    def _follow_main(self, event=None):
        if event is not None and event.widget is not self.root:
            return
        if self._log_visible():
            self._place_log()

    def toggle_log(self):
        if self._log_visible():
            self.log_win.withdraw()
        else:
            self._place_log()
            self.log_win.deiconify()
            self.logbox.see("end")
            self.root.focus_force()

    # --- Camera list --------------------------------------------------------------
    def _scan_cameras(self):
        """Detect cameras on a worker thread, then fill the dropdown on the UI thread."""
        self.camera.configure(values=["Detecting cameras..."])
        self.camera.current(0)
        self.refresh_btn.configure(state="disabled")

        def work():
            try:
                import sender
                cams = sender.list_cameras()
            except Exception as e:  # OpenCV missing, etc.
                cams, err = [], e
            else:
                err = None
            self.root.after(0, lambda: self._fill_cameras(cams, err))

        threading.Thread(target=work, daemon=True).start()

    def _fill_cameras(self, cams, err):
        if not self.root.winfo_exists():
            return
        if err is not None:
            gui_log(f"camera detection failed: {err}")
        if not cams:
            # Still let the user try index 0 (or the saved one).
            idx = self.cfg.get("camera", 0)
            cams = [(idx, f"{idx}: Camera (none detected)")]
        self.cameras = {label: idx for idx, label in cams}
        labels = list(self.cameras)
        self.camera.configure(values=labels)
        want = self.cfg.get("camera", 0)
        pick = next((i for i, (idx, _) in enumerate(cams) if idx == want), 0)
        self.camera.current(pick)
        if self.running is None:
            self.refresh_btn.configure(state="normal")

    def _camera_index(self):
        return self.cameras.get(self.camera.get(), self.cfg.get("camera", 0))

    # --- Helpers ----------------------------------------------------------------
    def _browse(self):
        path = filedialog.askopenfilename(title="Relay certificate",
                                          filetypes=[("PEM", "*.pem"), ("All", "*.*")])
        if path:
            self.cafile.delete(0, "end")
            self.cafile.insert(0, path)

    def _drain(self):
        while not _log_queue.empty():
            line = _log_queue.get()
            self.logbox.configure(state="normal")
            self.logbox.insert("end", line + "\n")
            self.logbox.see("end")
            self.logbox.configure(state="disabled")
        self.root.after(150, self._drain)

    def _int(self, entry, default):
        try:
            return int(entry.get())
        except ValueError:
            return default

    def _set_status(self, text, color):
        self.status.set(text, color)

    def _set_running(self, mode):
        """mode = 'send' | 'receive' | None. The active button turns into Stop."""
        self.running = mode
        for name, btn in self.buttons.items():
            if mode is None:
                btn.configure(text=name.capitalize(), state="normal")
            elif name == mode:
                btn.configure(text="Stop", state="normal")
            else:
                btn.configure(state="disabled")
        for w in (self.host, self.room, self.cafile, self.browse_btn, self.refresh_btn,
                  self.width, self.height, self.fps):
            w.configure(state="disabled" if mode else "normal")
        self.camera.configure(state="disabled" if mode else "readonly")
        self.hint.configure(text=RECEIVE_HINT if mode == "receive" else "")

    # --- Actions ----------------------------------------------------------------
    def toggle(self, mode):
        if self.running == mode:
            self.stop()
        elif self.running is None:
            self.start(mode)

    def start(self, mode):
        host = self.host.get().strip()
        room = self.room.get().strip() or "default"
        cafile = self.cafile.get().strip()
        if not host:
            messagebox.showwarning("CamBridge", "Enter the relay server IP or domain.")
            return
        if not cafile:
            messagebox.showwarning("CamBridge", "Pick the relay certificate (relay-cert.pem).\n\n"
                                   "Click ? for how to create and download it.")
            return
        if not os.path.isfile(cafile):
            messagebox.showwarning("CamBridge", f"Cert file not found:\n{cafile}")
            return
        self.cfg.update({
            "mode": mode, "host": host, "room": room, "cafile": cafile,
            "camera": self._camera_index(), "width": self._int(self.width, 1280),
            "height": self._int(self.height, 720), "fps": self._int(self.fps, 30),
        })
        save_cfg(self.cfg)
        try:
            core = load_engine(mode)
        except Exception as e:  # cv2 / sounddevice / pyvirtualcam missing, etc.
            messagebox.showerror("CamBridge", f"Could not load the {mode} engine:\n\n{e}\n\n"
                                 "Run:  pip install -r requirements.txt")
            return
        tls = dict(use_tls=True, cafile=cafile, insecure=False)
        try:
            if mode == "send":
                self.threads = core.start(host, room, camera=self.cfg["camera"],
                                          width=self.cfg["width"], height=self.cfg["height"],
                                          fps=self.cfg["fps"], **tls)
            else:
                self.threads = core.start(host, room, **tls)
        except Exception as e:
            messagebox.showerror("CamBridge", f"Could not start:\n{e}")
            return
        self.core = core
        self._set_running(mode)
        self._set_status("Sending" if mode == "send" else "Receiving", theme.OK_GREEN)
        gui_log(f"--- started ({mode}) ---")
        if mode == "receive":
            gui_log(RECEIVE_HINT)

    def stop(self):
        if self.core is not None:
            self.core.stop()
            self.core = None
        self._set_running(None)
        self._set_status("Idle", theme.IDLE_YELLOW)
        gui_log("--- stopped ---")

    def _on_close(self):
        try:
            if self.core is not None:
                self.core.stop()
        except Exception:
            pass
        self.root.destroy()


def main():
    p = argparse.ArgumentParser(description="CamBridge")
    p.add_argument("--mode", choices=("send", "receive"),
                   help=argparse.SUPPRESS)  # accepted for older installer shortcuts
    args = p.parse_args()
    root = tk.Tk()
    App(root, args.mode)
    root.mainloop()


if __name__ == "__main__":
    main()
