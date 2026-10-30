"""CamBridge version - the single source of truth.

Bump __version__ before a release. The installer (build_installer.bat) and the
release script (tools/release.py) read it from here, and the app compares it
against the latest GitHub release to offer updates.
"""

__version__ = "1.1.0"

# GitHub repository that hosts the releases (must be public: the app downloads
# the installer from it without credentials).
GITHUB_REPO = "temari62/cam-bridge"

# Asset names the release script uploads and the updater looks for.
SETUP_ASSET = "CamBridge-Setup.exe"
SHA256_ASSET = "CamBridge-Setup.exe.sha256"
