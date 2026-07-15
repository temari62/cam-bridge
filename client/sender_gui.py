"""
CamBridge - LOCAL sender GUI (Windows 11 / Fluent look).

A small window for employees: type the relay address + room token, tick TLS,
click Start. Runs on the LOCAL PC. No command line needed.

    python sender_gui.py
"""

import json
import os
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

import theme

try:
    import sender as core
except Exception as e:  # cv2 / sounddevice missing, etc.
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("CamBridge", f"Could not load the sender engine:\n\n{e}\n\n"
                         "Run:  pip install -r requirements.txt")
    raise SystemExit(1)

CONFIG = os.path.join(os.path.expanduser("~"), ".cambridge_sender.json")
_log_queue = queue.Queue()

H1 = ("Segoe UI Semibold", 18)
H2 = ("Segoe UI Semibold", 11)
MONO = ("Cascadia Mono", 9)


def gui_log(*args):
    _log_queue.put(" ".join(str(a) for a in args))


def load_cfg():
    try:
        with open(CONFIG) as f:
            return json.load(f)
    except Exception:
        return {}


def save_cfg(cfg):
    try:
        with open(CONFIG, "w") as f:
            json.dump(cfg, f)
    except Exception:
        pass


def section(parent, title):
    """A flat section header (bold label + hairline) on the shared background."""
    head = ttk.Frame(parent)
    head.pack(fill="x", pady=(18, 8))
    ttk.Label(head, text=title, font=H2).pack(anchor="w")
    ttk.Separator(head).pack(fill="x", pady=(6, 0))


class App:
    def __init__(self, root):
        self.root = root
        self.threads = []
        cfg = load_cfg()

        root.title("CamBridge Sender")
        root.geometry("600x620")
        root.minsize(560, 580)
        self.mode = theme.apply(root)
        theme.set_icon(root)

        outer = ttk.Frame(root, padding=(24, 20))
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="CamBridge Sender", font=H1).pack(anchor="w")
        ttk.Label(outer, text="Send this PC's camera and microphone to the meeting PC.",
                  foreground=theme.IDLE_GRAY).pack(anchor="w")

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

        # --- Advanced ---
        section(outer, "Advanced")
        adv = ttk.Frame(outer)
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
        self.logbox = scrolledtext.ScrolledText(outer, height=8, state="disabled",
                                                font=MONO, relief="flat", borderwidth=0)
        self.logbox.pack(fill="both", expand=True, pady=(4, 0))
        theme.style_log(self.logbox)

        core.log = gui_log
        self._toggle_tls()
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(150, self._drain)

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

    def start(self):
        host = self.host.get().strip()
        room = self.room.get().strip() or "default"
        if not host:
            messagebox.showwarning("CamBridge", "Enter the relay server IP or domain.")
            return
        cfg = {
            "host": host, "room": room, "tls": self.tls.get(),
            "insecure": self.insecure.get(), "cafile": self.cafile.get().strip(),
            "camera": self._int(self.camera, 0), "width": self._int(self.width, 1280),
            "height": self._int(self.height, 720), "fps": self._int(self.fps, 30),
        }
        save_cfg(cfg)
        try:
            self.threads = core.start(
                host, room, use_tls=self.tls.get(),
                cafile=(self.cafile.get().strip() or None), insecure=self.insecure.get(),
                camera=cfg["camera"], width=cfg["width"], height=cfg["height"], fps=cfg["fps"],
            )
        except Exception as e:
            messagebox.showerror("CamBridge", f"Could not start:\n{e}")
            return
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self._set_status("Running", theme.OK_GREEN)
        gui_log("--- started ---")

    def stop(self):
        core.stop()
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self._set_status("Idle", theme.IDLE_GRAY)
        gui_log("--- stopped ---")

    def _on_close(self):
        try:
            core.stop()
        except Exception:
            pass
        self.root.destroy()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
