; ============================================================================
;  CamBridge Sender - Inno Setup installer (for the LOCAL PC)
;  Just installs CamBridge-Sender.exe + shortcuts. No drivers needed.
;  Requires, before compiling:  ..\client\dist\CamBridge-Sender.exe
; ============================================================================

#define AppName "CamBridge Sender"
#define AppVersion "1.0"
#define AppPublisher "NovaWave"
#define ExeName "CamBridge-Sender.exe"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\CamBridge
DefaultGroupName=CamBridge
DisableProgramGroupPage=yes
OutputDir=Output
SetupIconFile=..\assets\CamBridge.ico
UninstallDisplayIcon={app}\CamBridge-Sender.exe
OutputBaseFilename=CamBridge-Sender-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\client\dist\{#ExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "vendor\relay-cert.pem"; DestDir: "{app}"; Flags: skipifsourcedoesntexist

[Icons]
Name: "{group}\CamBridge Sender"; Filename: "{app}\{#ExeName}"
Name: "{autodesktop}\CamBridge Sender"; Filename: "{app}\{#ExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#ExeName}"; Description: "Launch CamBridge Sender"; \
  Flags: postinstall nowait skipifsilent
