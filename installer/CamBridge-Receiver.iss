; ============================================================================
;  CamBridge Receiver - Inno Setup installer (for the REMOTE PC)
;  Installs CamBridge-Receiver.exe AND silently installs the system drivers
;  it needs: VB-Audio Virtual Cable (required) and OBS Studio (optional).
;
;  Build with Inno Setup 6:  see build_installer.bat
;  Requires, before compiling:
;    ..\dist\CamBridge-Receiver.exe        (run build_exe.bat first)
;    vendor\VBCABLE_Setup_x64.exe          (download - see vendor\README.txt)
;    vendor\OBS-Studio-Full-Installer-x64.exe   (optional; auto-skipped if absent)
; ============================================================================

#define AppName "CamBridge Receiver"
#define AppVersion "1.0"
#define AppPublisher "NovaWave"
#define ExeName "CamBridge-Receiver.exe"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\CamBridge
DefaultGroupName=CamBridge
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=CamBridge-Receiver-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; VB-CABLE is 64-bit and requires admin to install a driver.
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
; VB-CABLE needs a reboot to finish registering the audio device.
AlwaysRestart=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist\{#ExeName}"; DestDir: "{app}"; Flags: ignoreversion
; Bundled driver installers, copied to a temp dir and removed after install:
Source: "vendor\VBCABLE_Setup_x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall
Source: "vendor\OBS-Studio-Full-Installer-x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall skipifsourcedoesntexist
; Optionally ship your relay certificate next to the app (place it here before building):
Source: "vendor\relay-cert.pem"; DestDir: "{app}"; Flags: skipifsourcedoesntexist

[Icons]
Name: "{group}\CamBridge Receiver"; Filename: "{app}\{#ExeName}"
Name: "{autodesktop}\CamBridge Receiver"; Filename: "{app}\{#ExeName}"; Tasks: desktopicon

[Run]
; 1) Install VB-Audio Virtual Cable silently (installer is elevated, so this is too).
Filename: "{tmp}\VBCABLE_Setup_x64.exe"; Parameters: "-i -h"; \
  StatusMsg: "Installing VB-Audio Virtual Cable (virtual microphone)..."; \
  Flags: waituntilterminated
; 2) Install OBS Studio silently IF it was bundled (provides the virtual camera).
Filename: "{tmp}\OBS-Studio-Full-Installer-x64.exe"; Parameters: "/S"; \
  StatusMsg: "Installing OBS Studio (virtual camera)..."; \
  Flags: waituntilterminated skipifdoesntexist
; 3) Offer to launch the app after the (post-reboot) install.
Filename: "{app}\{#ExeName}"; Description: "Launch CamBridge Receiver"; \
  Flags: postinstall nowait skipifsilent

[Messages]
; Friendly note shown on the final page.
FinishedLabel=Setup installed CamBridge Receiver and the virtual devices.%n%nA restart is required to finish installing the virtual microphone. After restarting, open CamBridge Receiver, then choose "OBS Virtual Camera" and "CABLE Output" in your meeting app.
