"""
CamBridge - self-update via GitHub Releases (standard library only).

Flow (driven by the GUI):
    info = check()                       # None, or a Release newer than this build
    path = download(info, progress_cb)   # fetch the installer, verify SHA-256
    install(path)                        # run it silently and relaunch the app

The installer is Inno Setup with a fixed AppId, so it upgrades in place and keeps
the user's settings. It is started with the remote-PC driver task deselected, so
an update never re-runs the VB-CABLE / virtual-camera setup (no reboot prompt).
"""

import hashlib
import json
import os
import re
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass

from version import __version__, GITHUB_REPO, SETUP_ASSET, SHA256_ASSET

API_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{GITHUB_REPO}/releases/latest"
TIMEOUT = 15
# Installer switches: silent, no reboot, no re-running the driver task, and
# "/UPDATE=1" makes the [Run] section relaunch the app afterwards.
INSTALL_ARGS = ('/VERYSILENT /NORESTART /SUPPRESSMSGBOXES /CLOSEAPPLICATIONS '
                '/MERGETASKS="!remotepc" /UPDATE=1')


@dataclass
class Release:
    version: str
    setup_url: str
    sha256_url: str | None
    page_url: str
    notes: str = ""


def version_tuple(v):
    """'v1.2.3' -> (1, 2, 3); missing parts compare as 0."""
    return tuple(int(x) for x in re.findall(r"\d+", v or "")) or (0,)


def is_newer(remote, local=__version__):
    return version_tuple(remote) > version_tuple(local)


def _open(url, binary=False):
    req = urllib.request.Request(url, headers={
        "User-Agent": f"CamBridge/{__version__}",
        "Accept": "application/octet-stream" if binary else "application/vnd.github+json",
    })
    return urllib.request.urlopen(req, timeout=TIMEOUT, context=ssl.create_default_context())


def check():
    """Return a Release if GitHub has a newer version than this build, else None.

    Raises on network errors so the caller can decide whether to show them."""
    try:
        with _open(API_LATEST) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:   # repo has no releases yet
            return None
        raise
    tag = data.get("tag_name", "")
    if not is_newer(tag):
        return None
    assets = {a.get("name"): a.get("browser_download_url") for a in data.get("assets", [])}
    if SETUP_ASSET not in assets:
        return None  # release without an installer attached (e.g. source-only)
    return Release(version=tag.lstrip("vV"), setup_url=assets[SETUP_ASSET],
                   sha256_url=assets.get(SHA256_ASSET),
                   page_url=data.get("html_url", RELEASES_PAGE),
                   notes=data.get("body") or "")


def is_installed_build():
    """True when running as the packaged exe (the installer can replace it)."""
    return bool(getattr(sys, "frozen", False))


def download(release, progress=None):
    """Download the installer to a temp folder, verify its SHA-256, return its path.

    progress(done_bytes, total_bytes_or_None) is called as data arrives."""
    folder = os.path.join(tempfile.gettempdir(), "CamBridge-Update")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, SETUP_ASSET)

    expected = None
    if release.sha256_url:
        with _open(release.sha256_url, binary=True) as r:
            text = r.read(4096).decode("utf-8", "replace")
        m = re.search(r"\b[0-9a-fA-F]{64}\b", text)
        expected = m.group(0).lower() if m else None
    if expected is None:
        raise RuntimeError("Release has no SHA-256 checksum file; refusing to install it.")

    h = hashlib.sha256()
    done = 0
    with _open(release.setup_url, binary=True) as r, open(path, "wb") as f:
        total = r.headers.get("Content-Length")
        total = int(total) if total and total.isdigit() else None
        while True:
            chunk = r.read(256 * 1024)
            if not chunk:
                break
            f.write(chunk)
            h.update(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    if h.hexdigest() != expected:
        try:
            os.remove(path)
        except OSError:
            pass
        raise RuntimeError("Downloaded installer failed its checksum; not installing.")
    return path


def install(path):
    """Launch the installer (UAC prompt appears). The caller should exit right after."""
    if not sys.platform.startswith("win"):
        raise RuntimeError("Self-update is only supported on Windows.")
    # Inno's installer is marked requireAdministrator, so it must be started via
    # ShellExecute (os.startfile) for Windows to show the elevation prompt.
    os.startfile(path, arguments=INSTALL_ARGS)


def open_release_page(release=None):
    import webbrowser
    webbrowser.open((release.page_url if release else None) or RELEASES_PAGE)


if __name__ == "__main__":  # quick manual test: python updater.py
    print(f"installed: {__version__}")
    rel = check()
    print("latest is newer:" if rel else "up to date", rel or "")
