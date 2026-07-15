# CamBridge — Code Signing (optional but recommended for a fleet)

Unsigned apps trigger a Windows **SmartScreen** warning ("Windows protected your PC") the first
time each employee runs them. Signing the executables and installers with an **Authenticode code-
signing certificate** removes that warning and shows your company as the verified publisher.

CamBridge's build scripts sign automatically **if** you configure a certificate, and silently skip
signing if you don't — so nothing is required to just build unsigned.

## 1. Get a code-signing certificate

You must obtain this yourself from a certificate authority (Sectigo, DigiCert, SSL.com, etc.); it
can't be generated locally and be trusted by other PCs. Two kinds:

- **OV (Organization Validation)** — delivered as a `.pfx` file (older) or on a hardware/cloud HSM
  (most CAs now require this). Cheaper; SmartScreen reputation builds up over time.
- **EV (Extended Validation)** — always on a hardware token/HSM; grants instant SmartScreen trust.

If your CA gives you a `.pfx`, you can use Option A below. If it's on an HSM/token, the cert lives
in the Windows certificate store — use Option B.

## 2. Tell the build where your cert is

Set these environment variables in the same Command Prompt **before** running `build_exe.bat` /
`build_installer.bat`.

**Option A — PFX file**
```
set CAMBRIDGE_SIGN_PFX=C:\secure\cambridge-cert.pfx
set CAMBRIDGE_SIGN_PASS=your-pfx-password
```

**Option B — certificate already in the Windows store (HSM/EV token)**
```
set CAMBRIDGE_SIGN_SHA1=THUMBPRINTWITHNOSPACES
```
(Find the thumbprint in `certmgr.msc` → your cert → Details → Thumbprint, or
`Get-ChildItem Cert:\CurrentUser\My` in PowerShell. Remove spaces.)

**Optional — timestamp server** (defaults to DigiCert; timestamping keeps signatures valid after
the cert expires):
```
set CAMBRIDGE_SIGN_TS=http://timestamp.sectigo.com
```

## 3. Build as usual

```
client\build_exe.bat          rem signs CamBridge-Sender.exe and CamBridge-Receiver.exe
installer\build_installer.bat rem signs the two Setup.exe installers too
```

You'll see `[sign] signed: ...` lines. Everything the employee runs — the apps and the installers —
is then signed. (Because the exes are signed before the installer packages them, the whole chain is
covered.)

## How it works

Both build scripts call `tools\sign.bat <file>`, which runs the Windows SDK's `signtool.exe` with
`/fd SHA256` and an RFC-3161 timestamp. It needs `signtool.exe`, which comes with the
**Windows SDK** (or Visual Studio "Desktop development with C++"). If it's not on your PATH, the
helper auto-searches `C:\Program Files (x86)\Windows Kits\10\bin\...\x64\`.

## Security notes

- **Never commit your certificate.** `.pfx`, `.p12`, and `.cer` files are git-ignored. Keep the
  password out of scripts; set it as an environment variable at build time only.
- Prefer building signed releases on **one controlled build machine**, not on every employee PC.
