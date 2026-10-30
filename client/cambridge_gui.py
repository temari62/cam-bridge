"""
CamBridge - one app for both PCs (Windows 11 / Fluent look).

Pick what this PC does, type the relay address + room token, tick TLS, click Start:
  * Send     - LOCAL PC: stream this PC's camera + mic out to the relay.
  * Receive  - REMOTE PC: feed the stream into the virtual camera + mic, then pick
               "OBS Virtual Camera" and "CABLE Output" in your meeting app.

    python cambridge_gui.py                  # last-used mode
    python cambridge_gui.py --mode receive   # force a mode (send | receive)
"""

import argparse
import json
import os
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import theme

CONFIG = os.path.join(os.path.expanduser("~"), ".cambridge.json")
# Settings files of the old separate Sender/Receiver apps, migrated on first run.
LEGACY_CONFIGS = (("receive", os.path.join(os.path.expanduser("~"), ".cambridge_receiver.json")),
                  ("send", os.path.join(os.path.expanduser("~"), ".cambridge_sender.json")))
_log_queue = queue.Queue()

H1 = ("Segoe UI Semibold", 18)
H2 = ("Segoe UI Semibold", 11)
MONO = ("Cascadia Mono", 9)

SUBTITLES = {
    "send": "Send this PC's camera and microphone to the meeting PC.",
    "receive": "Feed the sender's camera and mic into this PC's virtual devices.",
}


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


class App:
    def __init__(self, root, mode=None):
        self.root = root
        self.threads = []
        self.core = None   # engine module while running
        self.cfg = cfg = load_cfg()

        root.title("CamBridge")
        root.geometry("600x780")
        root.minsize(560, 720)
        self.mode_kind = theme.apply(root)
        theme.set_icon(root)

        outer = ttk.Frame(root, padding=(24, 20))
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="CamBridge", font=H1).pack(anchor="w")
        self.subtitle = ttk.Label(outer, foreground=theme.IDLE_GRAY)
        self.subtitle.pack(anchor="w")

        # --- Mode ---
        section(outer, "This PC")
        self.mode = tk.StringVar(value=mode or cfg.get("mode", "send"))
        modes = ttk.Frame(outer)
        modes.pack(fill="x")
        self.mode_btns = [
            ttk.Radiobutton(modes, text="Send my camera + mic  (the PC I'm at)",
                            value="send", variable=self.mode, command=self._show_mode),
            ttk.Radiobutton(modes, text="Receive into the meeting  (the PC that joins)",
                            value="receive", variable=self.mode, command=self._show_mode),
        ]
        for b in self.mode_btns:
            b.pack(anchor="w", pady=2)

        # --- Connection ---
        section(outer, "Connection")
        conn = ttk.Frame(outer)
        conn.pack(fill="x")
        conn.columnconfigure(1, weight=1)

        ttk.Label(conn, text="Relay server").grid(row=0, column=0, sticky="w", pady=6, padx=(0, 14))
        self.host = ttk.Entry(conn)
        self.host.grid(row=0, column=1, columnspan=2, sticky="we", pady=6)
        self.host.insert(0, cfg.get("host", ""))

        ttk.Label(conn, text="Room token").grid(row=1, column=0, sticky="w", pady=6, padx=(0, 14))
        self.room = ttk.Entry(conn)
        self.room.grid(row=1, column=1, columnspan=2, sticky="we", pady=6)
        self.room.insert(0, cfg.get("room", "default"))

        self.tls = tk.BooleanVar(value=cfg.get("tls", True))
        ttk.Checkbutton(conn, text="Encrypt (TLS)", style="Switch.TCheckbutton",
                        variable=self.tls, command=self._toggle_tls
                        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 2))
        self.insecure = tk.BooleanVar(value=cfg.get("insecure", False))
        self.insecure_cb = ttk.Checkbutton(conn, text="Skip certificate check",
                                            style="Switch.TCheckbutton", variable=self.insecure)
        self.insecure_cb.grid(row=3, column=0, columnspan=2, sticky="w", pady=(0, 4))

        ttk.Label(conn, text="Cert file").grid(row=4, column=0, sticky="w", pady=6, padx=(0, 14))
        self.cafile = ttk.Entry(conn)
        self.cafile.grid(row=4, column=1, sticky="we", pady=6)
        self.cafile.insert(0, cfg.get("cafile", ""))
        self.browse_btn = ttk.Button(conn, text="Browse", width=9, command=self._browse)
        self.browse_btn.grid(row=4, column=2, sticky="e", padx=(8, 0))

        # --- Mode-specific panel (only one is shown) ---
        self.mode_area = ttk.Frame(outer)
        self.mode_area.pack(fill="x")

        # Send: capture settings
        self.send_panel = ttk.Frame(self.mode_area)
        section(self.send_panel, "Advanced")
        adv = ttk.Frame(self.send_panel)
        adv.pack(fill="x")
        ttk.Label(adv, text="Camera #").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.camera = ttk.Entry(adv, width=6)
        self.camera.grid(row=0, column=1, sticky="w", padx=(0, 18))
        self.camera.insert(0, str(cfg.get("camera", 0)))
        ttk.Label(adv, text="Width").grid(row=0, column=2, sticky="w", padx=(0, 8))
        self.width = ttk.Entry(adv, width=7)
        self.width.grid(row=0, column=3, sticky="w", padx=(0, 18))
        self.width.insert(0, str(cfg.get("width", 1280)))
        ttk.Label(adv, text="Height").grid(row=0, column=4, sticky="w", padx=(0, 8))
        self.height = ttk.Entry(adv, width=7)
        self.height.grid(row=0, column=5, sticky="w", padx=(0, 18))
        self.height.insert(0, str(cfg.get("height", 720)))
        ttk.Label(adv, text="FPS").grid(row=0, column=6, sticky="w", padx=(0, 8))
        self.fps = ttk.Entry(adv, width=6)
        self.fps.grid(row=0, column=7, sticky="w")
        self.fps.insert(0, str(cfg.get("fps", 30)))

        # Receive: meeting-app hint
        self.recv_panel = ttk.Frame(self.mode_area)
        section(self.recv_panel, "In your meeting app")
        ttk.Label(self.recv_panel, text="Camera  =  OBS Virtual Camera", font=H2).pack(anchor="w")
        ttk.Label(self.recv_panel, text="Microphone  =  CABLE Output", font=H2
                  ).pack(anchor="w", pady=(2, 0))

        # --- Action bar ---
        bar = ttk.Frame(outer)
        bar.pack(fill="x", pady=(22, 8))
        self.start_btn = ttk.Button(bar, text="Start", style="Accent.TButton", command=self.start)
        self.start_btn.pack(side="left")
        self.stop_btn = ttk.Button(bar, text="Stop", command=self.stop, state="disabled")
        self.stop_btn.pack(side="left", padx=8)
        self.dot = ttk.Label(bar, text="●", foreground=theme.IDLE_GRAY, font=("Segoe UI", 12))
        self.dot.pack(side="right")
        self.status = ttk.Label(bar, text="Idle")
        self.status.pack(side="right", padx=(0, 6))

        # --- Log ---
        ttk.Label(outer, text="Status log", foreground=theme.IDLE_GRAY).pack(anchor="w")
        # tk.Text + ttk.Scrollbar rather than ScrolledText, whose classic scrollbar
        # ignores the theme (a light bar in dark mode).
        logframe = ttk.Frame(outer)
        logframe.pack(fill="both", expand=True, pady=(4, 0))
        self.logbox = tk.Text(logframe, height=8, state="disabled", font=MONO, wrap="word")
        scroll = ttk.Scrollbar(logframe, orient="vertical", command=self.logbox.yview)
        self.logbox.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.logbox.pack(side="left", fill="both", expand=True)
        theme.style_log(self.logbox)

        self._show_mode()
        self._toggle_tls()
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(150, self._drain)

    def _show_mode(self):
        mode = self.mode.get()
        if self.cfg.get("mode") != mode:   # remember the choice even without pressing Start
            self.cfg["mode"] = mode
            save_cfg(self.cfg)
        self.subtitle.configure(text=SUBTITLES[mode])
        self.send_panel.pack_forget()
        self.recv_panel.pack_forget()
        (self.send_panel if mode == "send" else self.recv_panel).pack(fill="x")

    def _toggle_tls(self):
        state = "normal" if self.tls.get() else "disabled"
        self.insecure_cb.configure(state=state)
        self.cafile.configure(state=state)
        self.browse_btn.configure(state=state)

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
        self.status.configure(text=text)
        self.dot.configure(foreground=color)

    def _set_running(self, running):
        self.start_btn.configure(state="disabled" if running else "normal")
        self.stop_btn.configure(state="normal" if running else "disabled")
        for b in self.mode_btns:
            b.configure(state="disabled" if running else "normal")

    def start(self):
        mode = self.mode.get()
        host = self.host.get().strip()
        room = self.room.get().strip() or "default"
        if not host:
            messagebox.showwarning("CamBridge", "Enter the relay server IP or domain.")
            return
        self.cfg.update({
            "mode": mode, "host": host, "room": room, "tls": self.tls.get(),
            "insecure": self.insecure.get(), "cafile": self.cafile.get().strip(),
            "camera": self._int(self.camera, 0), "width": self._int(self.width, 1280),
            "height": self._int(self.height, 720), "fps": self._int(self.fps, 30),
        })
        save_cfg(self.cfg)
        try:
            core = load_engine(mode)
        except Exception as e:  # cv2 / sounddevice / pyvirtualcam missing, etc.
            messagebox.showerror("CamBridge", f"Could not load the {mode} engine:\n\n{e}\n\n"
                                 "Run:  pip install -r requirements.txt")
            return
        tls = dict(use_tls=self.tls.get(), cafile=(self.cafile.get().strip() or None),
                   insecure=self.insecure.get())
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
        self._set_running(True)
        self._set_status("Sending" if mode == "send" else "Receiving", theme.OK_GREEN)
        gui_log(f"--- started ({mode}) ---")

    def stop(self):
        if self.core is not None:
            self.core.stop()
            self.core = None
        self._set_running(False)
        self._set_status("Idle", theme.IDLE_GRAY)
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
    p.add_argument("--mode", choices=("send", "receive"), help="what this PC does")
    args = p.parse_args()
    root = tk.Tk()
    App(root, args.mode)
    root.mainloop()


if __name__ == "__main__":
    main()
