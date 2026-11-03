"""
CamBridge - notification-area (tray) icon, so the app keeps streaming after its window
is closed. Built on pystray, which runs its own message loop on a background thread.

Menu clicks arrive on that thread; they are handed to the GUI as callbacks on a queue
that the Tk main loop drains (tkinter must only be touched from its own thread).
"""
import theme

try:
    import pystray
    from PIL import Image
except Exception:  # pystray/Pillow missing: the app falls back to quitting on close
    pystray = None


def available():
    return pystray is not None and theme.icon_path() is not None


class Tray:
    def __init__(self, calls, on_show, on_stop, on_quit):
        """calls: queue the Tk thread drains; on_* are put on it when picked in the menu."""
        self.status = "Idle"
        self.running = False
        post = lambda fn: (lambda icon, item: calls.put(fn))
        menu = pystray.Menu(
            pystray.MenuItem("Show CamBridge", post(on_show), default=True),
            pystray.MenuItem(lambda item: f"Status: {self.status}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Stop", post(on_stop), visible=lambda item: self.running),
            pystray.MenuItem("Quit", post(on_quit)),
        )
        self.icon = pystray.Icon("CamBridge", Image.open(theme.icon_path()), "CamBridge", menu)
        self.icon.run_detached()

    def set_status(self, text, running):
        self.status, self.running = text, running
        self.icon.title = f"CamBridge - {text}"
        self.icon.update_menu()

    def notify(self, message):
        try:
            self.icon.notify(message, "CamBridge")
        except Exception:
            pass

    def close(self):
        try:
            self.icon.stop()
        except Exception:
            pass
