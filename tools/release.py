r"""
CamBridge - build and publish a release to GitHub (so installed apps auto-update).

    python tools\release.py                 # build exe + installer, then publish
    python tools\release.py --skip-build    # publish the installer already in installer\Output
    python tools\release.py --notes-file CHANGELOG-1.2.0.md
    python tools\release.py --draft         # create the release as a draft (publish by hand)

Needs: Windows, Python 3.10+, Inno Setup 6 (for the build), and a GitHub token with
"contents: write" on the repo in the GITHUB_TOKEN environment variable (or --token).
Create one at https://github.com/settings/tokens  (fine-grained, this repo only).

Steps:
  1. Read the version from client\version.py (bump it first!) -> tag v<version>.
  2. Build client\dist\CamBridge.exe and installer\Output\CamBridge-Setup.exe.
  3. Write CamBridge-Setup.exe.sha256 next to the installer.
  4. Create the GitHub release (tag at the current branch's pushed HEAD) and upload
     both files. Installed apps see it on their next start and offer to update.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT = os.path.join(ROOT, "client")
INSTALLER = os.path.join(ROOT, "installer")
sys.path.insert(0, CLIENT)
from version import __version__, GITHUB_REPO, SETUP_ASSET, SHA256_ASSET  # noqa: E402

API = "https://api.github.com"


def run(cmd, cwd):
    print(f"\n>>> {' '.join(cmd)}  (in {cwd})")
    env = dict(os.environ, NOPAUSE="1")
    r = subprocess.run(cmd, cwd=cwd, env=env)
    if r.returncode != 0:
        sys.exit(f"step failed with exit code {r.returncode}")


def build():
    run(["cmd", "/c", "build_exe.bat"], CLIENT)
    run(["cmd", "/c", "build_installer.bat"], INSTALLER)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def api(token, method, url, data=None, content_type="application/json"):
    body = None
    if data is not None:
        body = data if isinstance(data, bytes) else json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "CamBridge-release",
        "Content-Type": content_type,
    })
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r) if r.status != 204 else None
    except urllib.error.HTTPError as e:
        sys.exit(f"GitHub API {method} {url} failed: {e.code} {e.read().decode(errors='replace')[:500]}")


def upload(token, upload_url, path, name):
    base = upload_url.split("{", 1)[0]
    url = f"{base}?{urllib.parse.urlencode({'name': name})}"
    with open(path, "rb") as f:
        data = f.read()
    print(f"uploading {name} ({len(data) / 1e6:.1f} MB) ...")
    return api(token, "POST", url, data, content_type="application/octet-stream")


def main():
    p = argparse.ArgumentParser(description="Build + publish a CamBridge release")
    p.add_argument("--skip-build", action="store_true", help="use the existing installer\\Output")
    p.add_argument("--notes", default="", help="release notes text")
    p.add_argument("--notes-file", help="file with release notes (Markdown)")
    p.add_argument("--draft", action="store_true", help="create a draft release")
    p.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"), help="GitHub token")
    args = p.parse_args()

    tag = f"v{__version__}"
    setup = os.path.join(INSTALLER, "Output", SETUP_ASSET)
    sums = os.path.join(INSTALLER, "Output", SHA256_ASSET)
    print(f"CamBridge {__version__}  ->  release {tag} on {GITHUB_REPO}")

    if git("status", "--porcelain"):
        print("WARNING: working tree has uncommitted changes.")
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    if git("rev-parse", "HEAD") != git("rev-parse", f"origin/{branch}"):
        print(f"WARNING: local {branch} differs from origin/{branch}; push first so the tag "
              "points at the released code.")

    if not args.skip_build:
        build()
    if not os.path.isfile(setup):
        sys.exit(f"missing {setup}")

    digest = sha256_file(setup)
    with open(sums, "w", newline="\n") as f:
        f.write(f"{digest}  {SETUP_ASSET}\n")
    print(f"sha256 {digest}")

    notes = args.notes
    if args.notes_file:
        notes = open(args.notes_file, encoding="utf-8").read()
    if not notes:
        notes = f"CamBridge {__version__}"

    if not args.token:
        print("\nNo GitHub token (GITHUB_TOKEN). Publish by hand:\n"
              f"  1. https://github.com/{GITHUB_REPO}/releases/new  -> tag {tag}\n"
              f"  2. attach {setup}\n"
              f"             {sums}\n"
              "  3. Publish. Installed apps will offer the update on their next start.")
        return

    existing = None
    try:
        existing = api(args.token, "GET", f"{API}/repos/{GITHUB_REPO}/releases/tags/{tag}")
    except SystemExit:
        pass
    if existing:
        sys.exit(f"release {tag} already exists: {existing.get('html_url')}\n"
                 "Bump __version__ in client\\version.py for a new release.")

    rel = api(args.token, "POST", f"{API}/repos/{GITHUB_REPO}/releases", {
        "tag_name": tag, "target_commitish": branch, "name": f"CamBridge {__version__}",
        "body": notes, "draft": args.draft, "prerelease": False,
    })
    upload(args.token, rel["upload_url"], setup, SETUP_ASSET)
    upload(args.token, rel["upload_url"], sums, SHA256_ASSET)
    print(f"\nDONE: {rel['html_url']}")
    if args.draft:
        print("Draft release: open the link and click Publish to make apps see it.")


if __name__ == "__main__":
    main()
