"""
CamBridge - fetch the OBS Virtual Camera driver DLLs (without installing OBS).

The receiver only needs OBS's DirectShow virtual-camera module, not OBS Studio
itself. This script downloads JUST these files from an official OBS release
into installer\\vendor\\obs-virtualcam\\ :

    obs-virtualcam-module64.dll   (64-bit apps: Teams, Zoom, browsers)
    obs-virtualcam-module32.dll   (32-bit apps)
    COPYING                       (OBS's GPLv2 licence - ship it with the DLLs)
    SOURCE.txt                    (where the files came from + SHA-256)

It reads only the needed bytes out of the ~200 MB release zip using HTTP range
requests, so it takes seconds rather than a full download. Standard library only.

Usage:
    python fetch_obs_virtualcam.py              # pinned version (below)
    python fetch_obs_virtualcam.py 33.0.0       # a specific OBS release tag
"""

import hashlib
import json
import os
import sys
import urllib.request
import zipfile

OBS_VERSION = "33.0.0"   # bump deliberately; re-test the camera after changing
WANTED = ("obs-virtualcam-module64.dll", "obs-virtualcam-module32.dll")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor", "obs-virtualcam")
UA = {"User-Agent": "CamBridge-fetch"}


def http(url, headers=None, method="GET"):
    return urllib.request.urlopen(urllib.request.Request(url, headers={**UA, **(headers or {})},
                                                         method=method))


class RemoteFile:
    """Read-only, seekable file over HTTP range requests (with a small read-ahead cache)."""
    BLOCK = 512 * 1024

    def __init__(self, url):
        with http(url, method="HEAD") as r:          # follows GitHub's redirect to the CDN
            self.url, self.size = r.url, int(r.headers["Content-Length"])
        self.pos, self.cache_start, self.cache = 0, 0, b""

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = offset if whence == 0 else self.pos + offset if whence == 1 else self.size + offset
        return self.pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        n = min(n, self.size - self.pos)
        if n <= 0:
            return b""
        start, end = self.pos, self.pos + n
        if not (self.cache_start <= start and end <= self.cache_start + len(self.cache)):
            fetch_end = min(max(end, start + self.BLOCK), self.size) - 1
            with http(self.url, {"Range": f"bytes={start}-{fetch_end}"}) as r:
                self.cache_start, self.cache = start, r.read()
        off = start - self.cache_start
        data = self.cache[off:off + n]
        self.pos += len(data)
        return data


def find_zip_url(version):
    with http(f"https://api.github.com/repos/obsproject/obs-studio/releases/tags/{version}") as r:
        release = json.load(r)
    for asset in release["assets"]:
        name = asset["name"]
        if name.endswith("-x64.zip") and "PDB" not in name and "arm64" not in name:
            return asset["browser_download_url"]
    sys.exit(f"ERROR: no Windows x64 .zip found in OBS release {version}")


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else OBS_VERSION
    os.makedirs(OUT_DIR, exist_ok=True)

    url = find_zip_url(version)
    print(f"OBS {version}: {url}")
    zf = zipfile.ZipFile(RemoteFile(url))

    lines = [f"OBS Virtual Camera module from OBS Studio {version} (GPLv2).",
             f"Binary source : {url}",
             f"Source code   : https://github.com/obsproject/obs-studio/tree/{version}",
             f"                (plugins/win-dshow/virtualcam-module)", ""]
    for wanted in WANTED:
        member = next((n for n in zf.namelist() if n.lower().endswith("/" + wanted)), None)
        if member is None:
            sys.exit(f"ERROR: {wanted} not found in the OBS {version} zip")
        data = zf.read(member)
        with open(os.path.join(OUT_DIR, wanted), "wb") as f:
            f.write(data)
        digest = hashlib.sha256(data).hexdigest()
        lines.append(f"{wanted}  sha256={digest}")
        print(f"  {wanted}  ({len(data):,} bytes)  sha256={digest}")

    with http(f"https://raw.githubusercontent.com/obsproject/obs-studio/{version}/COPYING") as r:
        with open(os.path.join(OUT_DIR, "COPYING"), "wb") as f:
            f.write(r.read())
    with open(os.path.join(OUT_DIR, "SOURCE.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Done -> {OUT_DIR}")


if __name__ == "__main__":
    main()
