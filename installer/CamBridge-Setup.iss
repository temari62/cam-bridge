; ============================================================================
;  CamBridge - Inno Setup installer (for BOTH PCs)
;  Installs CamBridge.exe. With the "remotepc" task (ticked by default) it also
;  sets up the system devices the REMOTE PC needs:
;    * virtual camera - OBS's virtual-camera DLLs only (no OBS Studio install)
;    * virtual mic    - VB-Audio Virtual Cable, installed silently
;  Untick it on the LOCAL PC for a plain app install (no drivers, no restart).
;
;  Build with Inno Setup 6:  see build_installer.bat
;  Requires, before compiling:
;    ..\client\dist\CamBridge.exe          (run build_exe.bat first)
;    vendor\VBCABLE_Driver_Pack45\*        (download - see vendor\README.txt)
;    vendor\obs-virtualcam\*               (run fetch_obs_virtualcam.py)
;
;  Silent install:  CamBridge-Setup.exe /VERYSILENT /TASKS="remotepc"   (remote PC)
;                   CamBridge-Setup.exe /VERYSILENT /TASKS="!remotepc"  (local PC)
; ============================================================================

#define AppName "CamBridge"
; Version comes from ..\client\version.py via build_installer.bat (/DAppVersion=x.y.z).
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppPublisher "NovaWave"
#define ExeName "CamBridge.exe"
#define VBCablePack "VBCABLE_Driver_Pack45"

[Setup]
; Fixed AppId so upgrades find this install; never change it.
AppId={{15DC1DF5-8BAA-47FE-B097-B4E77B3B95AD}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\CamBridge
DefaultGroupName=CamBridge
DisableProgramGroupPage=yes
OutputDir=Output
SetupIconFile=..\assets\CamBridge.ico
UninstallDisplayIcon={app}\{#ExeName}
OutputBaseFilename=CamBridge-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; VB-CABLE is 64-bit and requires admin to install a driver.
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin

[Tasks]
Name: "remotepc"; Description: "Set up the virtual camera + microphone (needed on the REMOTE PC that joins the meeting; untick on the PC you sit at)"; GroupDescription: "This PC:"
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\client\dist\{#ExeName}"; DestDir: "{app}"; Flags: ignoreversion
; Bundled VB-CABLE driver pack (the setup exe needs the .inf/.sys/.cat files beside it),
; copied to a temp dir and removed after install:
Source: "vendor\{#VBCablePack}\*"; DestDir: "{tmp}\vbcable"; Flags: deleteafterinstall; Tasks: remotepc
; OBS Virtual Camera module (GPLv2, signed by OBS Project) - registered in [Run] below.
; restartreplace/uninsrestartdelete: a meeting app may have the DLL loaded.
Source: "vendor\obs-virtualcam\obs-virtualcam-module64.dll"; DestDir: "{app}\virtualcam"; Flags: ignoreversion restartreplace uninsrestartdelete; Tasks: remotepc
Source: "vendor\obs-virtualcam\obs-virtualcam-module32.dll"; DestDir: "{app}\virtualcam"; Flags: ignoreversion restartreplace uninsrestartdelete; Tasks: remotepc
Source: "vendor\obs-virtualcam\COPYING"; DestDir: "{app}\virtualcam"; Flags: ignoreversion; Tasks: remotepc
Source: "vendor\obs-virtualcam\SOURCE.txt"; DestDir: "{app}\virtualcam"; Flags: ignoreversion; Tasks: remotepc
; Optionally ship your relay certificate next to the app (place it here before building):
Source: "vendor\relay-cert.pem"; DestDir: "{app}"; Flags: skipifsourcedoesntexist

[Icons]
Name: "{group}\CamBridge"; Filename: "{app}\{#ExeName}"
Name: "{autodesktop}\CamBridge"; Filename: "{app}\{#ExeName}"; Tasks: desktopicon

[Run]
; 1) Install VB-Audio Virtual Cable silently (installer is elevated, so this is too).
Filename: "{tmp}\vbcable\VBCABLE_Setup_x64.exe"; Parameters: "-i -h"; WorkingDir: "{tmp}\vbcable"; \
  StatusMsg: "Installing VB-Audio Virtual Cable (virtual microphone)..."; \
  Flags: waituntilterminated; Tasks: remotepc
; 2) Register the virtual camera (64-bit and 32-bit), as OBS's virtualcam-install.bat does.
;    Skipped if a real OBS Studio install already provides it (see ShouldRegisterVCam).
Filename: "{sys}\regsvr32.exe"; Parameters: "/i /s ""{app}\virtualcam\obs-virtualcam-module64.dll"""; \
  StatusMsg: "Registering virtual camera..."; \
  Flags: runhidden waituntilterminated; Tasks: remotepc; Check: ShouldRegisterVCam
Filename: "{syswow64}\regsvr32.exe"; Parameters: "/i /s ""{app}\virtualcam\obs-virtualcam-module32.dll"""; \
  StatusMsg: "Registering virtual camera..."; \
  Flags: runhidden waituntilterminated; Tasks: remotepc; Check: ShouldRegisterVCam
; 3) Self-update (the app runs setup with /VERYSILENT /UPDATE=1): relaunch the app
;    as the logged-on user once the new files are in place.
Filename: "{app}\{#ExeName}"; Flags: nowait runasoriginaluser; Check: IsUpdateRun
; 4) Offer to launch the app, opened in the mode that fits this PC.
Filename: "{app}\{#ExeName}"; Parameters: "--mode receive"; Description: "Launch CamBridge"; \
  Flags: postinstall nowait skipifsilent; Tasks: remotepc
Filename: "{app}\{#ExeName}"; Parameters: "--mode send"; Description: "Launch CamBridge"; \
  Flags: postinstall nowait skipifsilent; Tasks: not remotepc

[Messages]
; Friendly note shown on the final page.
FinishedLabel=Setup installed CamBridge.%n%nOn the PC you sit at, choose "Send" in the app. On the meeting PC, choose "Receive", then pick "OBS Virtual Camera" and "CABLE Output" in your meeting app.
FinishedRestartLabel=Setup installed CamBridge and the virtual devices. A restart is required to finish installing the virtual microphone.%n%nAfter restarting, open CamBridge, choose "Receive", then pick "OBS Virtual Camera" and "CABLE Output" in your meeting app.

[Code]
// True when started by the app's self-updater (CamBridge.exe passes /UPDATE=1).
function IsUpdateRun: Boolean;
begin
  Result := ExpandConstant('{param:UPDATE|0}') = '1';
end;

const
  // CLSID of the OBS Virtual Camera DirectShow filter (pyvirtualcam checks for this key).
  VCamKey = 'SOFTWARE\Classes\CLSID\{A3FCE0F5-3493-419F-958A-ABA1250EC20B}\InprocServer32';
  UninstallKey = 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\';

function OurVCamDll: String;
begin
  Result := ExpandConstant('{app}\virtualcam\obs-virtualcam-module64.dll');
end;

// Path of the DLL currently registered as the virtual camera, or '' if none.
function RegisteredVCamDll: String;
begin
  if not RegQueryStringValue(HKLM64, VCamKey, '', Result) then
    Result := '';
end;

// Register ours unless a working OBS Studio install already owns the camera:
// re-pointing it would break OBS, and our uninstall would then remove it.
function ShouldRegisterVCam: Boolean;
var
  Current: String;
begin
  Current := RegisteredVCamDll;
  Result := (Current = '') or (CompareText(Current, OurVCamDll) = 0) or not FileExists(Current);
  if not Result then
    Log('Virtual camera already provided by ' + Current + '; not registering ours.');
end;

// VB-CABLE needs a reboot to finish registering the audio device.
function NeedRestart: Boolean;
begin
  Result := WizardIsTaskSelected('remotepc');
end;

// The separate "CamBridge Sender" / "CamBridge Receiver" apps of earlier versions
// are replaced by this one: uninstall them silently so they don't linger.
procedure RemoveLegacyApp(const Name: String);
var
  Key, UninstallExe: String;
  ResultCode, Waited: Integer;
begin
  Key := UninstallKey + Name + '_is1';
  if RegQueryStringValue(HKLM64, Key, 'UninstallString', UninstallExe) then
  begin
    Log('Removing legacy ' + Name);
    Exec(RemoveQuotes(UninstallExe), '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART', '',
         SW_HIDE, ewWaitUntilTerminated, ResultCode);
    // Inno uninstallers relaunch from a temp copy and return at once, so wait
    // (up to 30 s) for the real uninstall to finish before copying our files.
    Waited := 0;
    while RegKeyExists(HKLM64, Key) and (Waited < 30000) do
    begin
      Sleep(250);
      Waited := Waited + 250;
    end;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  RemoveLegacyApp('CamBridge Sender');
  RemoveLegacyApp('CamBridge Receiver');
  Result := '';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
begin
  // Only unregister if the camera is still ours (OBS may have taken it over since).
  if (CurUninstallStep = usUninstall) and (CompareText(RegisteredVCamDll, OurVCamDll) = 0) then
  begin
    Exec(ExpandConstant('{sys}\regsvr32.exe'), '/u /s "' + OurVCamDll + '"',
         '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Exec(ExpandConstant('{syswow64}\regsvr32.exe'),
         '/u /s "' + ExpandConstant('{app}\virtualcam\obs-virtualcam-module32.dll') + '"',
         '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;
