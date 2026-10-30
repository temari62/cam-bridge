# CamBridge — Releasing an update

Installed copies of CamBridge (v1.1.0 and later) check GitHub Releases on every start. When a
newer release exists, a bar appears at the top of the app with **Update now**. Clicking it
downloads `CamBridge-Setup.exe`, verifies its SHA-256 against the `.sha256` file attached to the
same release, runs the installer silently (one UAC prompt) and relaunches the app. Settings are
kept. The update never re-runs the virtual-camera / VB-CABLE driver steps, so there is no reboot.

> Copies installed **before** v1.1.0 have no updater: install the new version over them once by
> hand. Every version after that updates itself.

## One-time setup

1. The repo must be **public** (the app downloads without credentials). `temari62/cam-bridge` is.
2. Create a GitHub token with **Contents: read and write** on this repo
   (https://github.com/settings/tokens → fine-grained) and put it in the `GITHUB_TOKEN`
   environment variable on the PC you release from. Never commit it or put it in the git remote URL.
3. Inno Setup 6 and Python 3.10+ installed (same as for `BUILD.md` / `INSTALLER.md`).

## Publishing a release

1. Bump `__version__` in **`client\version.py`** (e.g. `1.1.0` → `1.2.0`). This is the only place.
2. Commit and **push** (the release tag is created from the pushed branch head).
3. Run:
   ```
   python tools\release.py --notes "What changed in this version"
   ```
   It builds `CamBridge.exe`, builds `CamBridge-Setup.exe` (stamped with the version), writes
   `CamBridge-Setup.exe.sha256`, creates release `v<version>` and uploads both files.

   Useful flags: `--skip-build` (reuse `installer\Output`), `--notes-file notes.md`,
   `--draft` (review on GitHub, then click Publish).

Without a token the script still builds and prints the two files to attach by hand at
https://github.com/temari62/cam-bridge/releases/new with tag `v<version>`.

## How the app decides

- It calls `https://api.github.com/repos/temari62/cam-bridge/releases/latest`.
- The tag is compared numerically to its own version (`v1.10.0` > `v1.9.0`).
- A release is offered only if it has a `CamBridge-Setup.exe` asset, and installed only if the
  `.sha256` asset matches the download. A release missing the checksum is refused.
- Pre-releases and drafts are not returned by the `latest` endpoint, so they are never offered.
- When run from source (`python cambridge_gui.py`), the button opens the release page instead.

## Manual check

In the app, click **?** → **Check for updates**. The status log (click the status badge) shows
`up to date`, `update available`, or the error from the check.
