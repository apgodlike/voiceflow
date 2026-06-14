; Inno Setup script for VoiceFlow.
; Build the app folder first:   pyinstaller VoiceFlow.spec --noconfirm
; Then compile this with the Inno Setup Compiler (ISCC.exe installer.iss)
; or open it in the Inno Setup IDE and press F9. Output: dist\VoiceFlow-Setup.exe
;
; Keep MyAppVersion in sync with voiceflow/__init__.py __version__.

#define MyAppName "VoiceFlow"
#define MyAppVersion "0.2.7"
#define MyAppPublisher "Praveen"
#define MyAppExeName "VoiceFlow.exe"

[Setup]
AppId={{8F2B6C41-2D4E-4F1A-9C3B-1A2B3C4D5E6F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=VoiceFlow-Setup
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Per-user install — no admin prompt, matches the per-user data dir.
PrivilegesRequired=lowest

[Tasks]
Name: "startupicon"; Description: "Start {#MyAppName} when I sign in"; GroupDescription: "Startup:"
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "dist\VoiceFlow\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; Start-on-login (per-user Run key). The app's Settings dialog manages the same
; value, so the two stay consistent. Removed on uninstall.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "{#MyAppName}"; ValueData: """{app}\{#MyAppExeName}"""; \
    Tasks: startupicon; Flags: uninsdeletevalue

[Run]
; Launch after install so the user sees the window + how-to immediately.
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName} now"; \
    Flags: nowait postinstall skipifsilent
