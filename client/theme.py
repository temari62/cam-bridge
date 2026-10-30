"""
CamBridge - shared UI theming (Windows 11 / Fluent look).

Applies the Sun Valley (sv-ttk) theme and matches the PC's light/dark setting.
Also forces every control's backing colour to match the window surface so the
rounded buttons / toggles / entries don't show a mismatched rectangle behind
their rounded corners. Everything degrades gracefully: if sv-ttk isn't installed,
the GUI still runs with the default ttk theme.

After apply(), these module values are set for callers to reuse:
    theme.SURFACE   - window/background colour
    theme.LOG_BG    - background for the (tk) log Text widget
    theme.LOG_FG    - foreground for the log Text widget
"""

from tkinter import ttk

# Accent color used for the primary "Start" button and status dot.
ACCENT = "#0067C0"
OK_GREEN = "#2EA043"
IDLE_GRAY = "#8A8A8A"
IDLE_YELLOW = "#F2B705"
ERR_RED = "#D13438"

# Filled in by apply(); safe defaults for import-time use.
SURFACE = "#f3f3f3"
LOG_BG = "#ffffff"
LOG_FG = "#1a1a1a"

# Control styles whose rectangular backing must match the surface.
_BACKING_STYLES = (
    "TFrame", "TLabel", "TButton", "Accent.TButton", "Toolbutton",
    "TCheckbutton", "Switch.TCheckbutton", "TRadiobutton",
    "TSeparator", "TEntry", "TLabelframe", "TLabelframe.Label",
    "TNotebook", "TNotebook.Tab",
)


def windows_is_dark():
    """True if Windows apps are set to dark mode (reads the registry)."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return value == 0
    except Exception:
        return False


def _set_titlebar_dark(root, dark):
    """Best-effort: paint the window title bar dark on Windows 11 (no dependency)."""
    try:
        import ctypes
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        val = ctypes.c_int(1 if dark else 0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(val), ctypes.sizeof(val)
        )
    except Exception:
        pass


def _match_backgrounds(root, dark):
    """Force control backings, the root window, and log colours to the surface."""
    global SURFACE, LOG_BG, LOG_FG
    style = ttk.Style()
    bg = style.lookup("TFrame", "background")
    if not bg:
        bg = "#1c1c1c" if dark else "#fafafa"
    SURFACE = bg
    LOG_BG = "#2b2b2b" if dark else "#ffffff"
    LOG_FG = "#e6e6e6" if dark else "#1a1a1a"

    # The rounded sv-ttk controls composite their corners against -background;
    # setting it to the surface makes the halo disappear. The coloured button
    # faces and toggle tracks are separate element images, so they stay intact.
    for name in _BACKING_STYLES:
        try:
            style.configure(name, background=bg)
        except Exception:
            pass
    try:
        root.configure(background=bg)
    except Exception:
        pass


def apply(root):
    """Apply the modern theme to a Tk root. Returns 'dark' or 'light'.

    Safe to call even if sv-ttk is missing.
    """
    dark = windows_is_dark()
    mode = "dark" if dark else "light"
    try:
        import sv_ttk
        sv_ttk.set_theme(mode)
        # sv-ttk sets the base text/background colours in a <<ThemeChanged>>
        # handler on the root, but Tk doesn't deliver that event to a root that
        # isn't mapped yet - leaving every label black. Fire it ourselves.
        root.event_generate("<<ThemeChanged>>")
        style = ttk.Style()
        if not style.lookup(".", "foreground"):
            style.configure(".", foreground="#fafafa" if dark else "#1c1c1c")
    except Exception:
        pass  # fall back to default ttk theme
    _match_backgrounds(root, dark)
    _fix_text_fields(dark)
    _set_titlebar_dark(root, dark)
    return mode


def _fix_text_fields(dark):
    """Visible caret + selection in entries (dark mode otherwise draws them black),
    and a larger primary-button style for the Send / Receive buttons."""
    style = ttk.Style()
    fg = "#fafafa" if dark else "#1c1c1c"
    try:
        style.configure("TEntry", insertcolor=fg, selectbackground=ACCENT,
                        selectforeground="#ffffff")
        style.configure("TCombobox", insertcolor=fg, selectbackground=ACCENT,
                        selectforeground="#ffffff")
    except Exception:
        pass
    try:
        style.configure("Big.Accent.TButton", font=("Segoe UI Semibold", 12),
                        padding=(24, 10))
    except Exception:
        pass


def style_log(text_widget):
    """Theme a tk Text/ScrolledText log widget to match the current mode."""
    try:
        text_widget.configure(background=LOG_BG, foreground=LOG_FG,
                              insertbackground=LOG_FG, selectbackground=ACCENT,
                              selectforeground="#ffffff", highlightthickness=0,
                              borderwidth=0, relief="flat")
    except Exception:
        pass


def set_icon(root):
    """Best-effort: set the window/taskbar icon from assets/CamBridge.ico."""
    import os
    import sys
    candidates = []
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", "")
        candidates += [os.path.join(base, "assets", "CamBridge.ico"),
                       os.path.join(base, "CamBridge.ico")]
    here = os.path.dirname(os.path.abspath(__file__))
    candidates += [os.path.join(here, "..", "assets", "CamBridge.ico"),
                   os.path.join(here, "assets", "CamBridge.ico")]
    for p in candidates:
        try:
            if os.path.exists(p):
                root.iconbitmap(p)
                return
        except Exception:
            pass
