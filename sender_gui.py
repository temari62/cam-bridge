"""
CamBridge - LOCAL sender GUI.

A tiny window for employees: type the relay address + room token, tick TLS,
click Start. Runs on the LOCAL PC. No command line needed.

    python sender_gui.py
"""

import json
import os
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

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


class App:
    def __init__(self, root):
        self.root = root
        self.threads = []
        self.running = False
        cfg = load_cfg()

        root.title("CamBridge Sender  (local PC)")
        root.geometry("560x520")
        pad = {"padx": 8, "pady": 4}

        frm = ttk.Frame(root)
        frm.pack(fill="x", **pad)

        ttk.Label(frm, text="Relay server IP / domain:").grid(row=0, column=0, sticky="w")
        self.host = ttk.Entry(frm, width=34)
        self.host.grid(row=0, column=1, columnspan=2, sticky="we")
        self.host.insert(0, cfg.get("host", ""))

        ttk.Label(frm, text="Room token:").grid(row=1, column=0, sticky="w")
        self.room = ttk.Entry(frm, width=34)
        self.room.grid(row=1, column=1, columnspan=2, sticky="we")
        self.room.insert(0, cfg.get("room", "default"))

        self.tls = tk.BooleanVar(value=cfg.get("tls", True))
        ttk.Checkbutton(frm, text="Encrypt (TLS)", variable=self.tls,
                        command=self._toggle_tls).grid(row=2, column=0, sticky="w")
        self.insecure = tk.BooleanVar(value=cfg.get("insecure", False))
        self.insecure_cb = ttk.Checkbutton(frm, text="Skip cert check", variable=self.insecure)
        self.insecure_cb.grid(row=2, column=1, sticky="w")

        ttk.Label(frm, text="Cert file (optional):").grid(row=3, column=0, sticky="w")
        self.cafile = ttk.Entry(frm, width=26)
        self.cafile.grid(row=3, column=1, sticky="we")
        self.cafile.insert(0, cfg.get("cafile", ""))
        self.browse_btn = ttk.Button(frm, text="Browse", command=self._browse)
        self.browse_btn.grid(row=3, column=2, sticky="e")

        adv = ttk.LabelFrame(root, text="Advanced (optional)")
        adv.pack(fill="x", **pad)
        ttk.Label(adv, text="Camera #").grid(row=0, column=0, sticky="w")
        self.camera = ttk.Entry(adv, width=6)
        self.camera.grid(row=0, column=1, sticky="w")
        self.camera.insert(0, str(cfg.get("camera", 0)))
        ttk.Label(adv, text="Width").grid(row=0, column=2, sticky="w")
        self.width = ttk.Entry(adv, width=6)
        self.width.grid(row=0, column=3, sticky="w")
        self.width.insert(0, str(cfg.get("width", 1280)))
        ttk.Label(adv, text="Height").grid(row=0, column=4, sticky="w")
        self.height = ttk.Entry(adv, width=6)
        self.height.grid(row=0, column=5, sticky="w")
        self.height.insert(0, str(cfg.get("height", 720)))
        ttk.Label(adv, text="FPS").grid(row=0, column=6, sticky="w")
        self.fps = ttk.Entry(adv, width=5)
        self.fps.grid(row=0, column=7, sticky="w")
        self.fps.insert(0, str(cfg.get("fps", 30)))

        btns = ttk.Frame(root)
        btns.pack(fill="x", **pad)
        self.start_btn = ttk.Button(btns, text="Start", command=self.start)
        self.start_btn.pack(side="left")
        self.stop_btn = ttk.Button(btns, text="Stop", command=self.stop, state="disabled")
        self.stop_btn.pack(side="left", padx=6)
        self.status = ttk.Label(btns, text="Idle")
        self.status.pack(side="right")

        self.logbox = scrolledtext.ScrolledText(root, height=15, state="disabled")
        self.logbox.pack(fill="both", expand=True, **pad)

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
        self.running = True
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.status.configure(text="Running")
        gui_log("--- started ---")

    def stop(self):
        core.stop()
        self.running = False
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.status.configure(text="Idle")
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
