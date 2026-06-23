; Inno Setup script for Alangrapher Windows installer.
;
; Usage:
;   iscc /DVersion=%VERSION% installer.iss
;
; Prerequisites: dist\Alangrapher.exe must exist (built by PyInstaller first).

#define AppName "Alangrapher"
#define AppPublisher "Alangrapher"
#define AppURL "https://github.com/Alangrapher/foclo"
#define AppExeName "Alangrapher.exe"

#ifndef Version
  #define Version "0.0.0-dev"
#endif

[Setup]
AppId={{B4E3F1A2-8C5D-4E9B-A7F0-2D1C6E8A3B95}}
AppName={#AppName}
AppVersion={#Version}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DisableProgramGroupPage=yes
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=dist
OutputBaseFilename=Alangrapher-Setup-{#Version}
SetupIconFile=
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#AppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Main application
Source: "dist\Alangrapher.exe"; DestDir: "{app}"; Flags: ignoreversion
; WebView2 Evergreen Bootstrapper (downloaded by CI before iscc)
Source: "MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
; Install WebView2 Runtime if missing (Evergreen bootstrapper — no-op if already installed).
; /silent suppresses all UI; /install triggers the install path (not just download).
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; \
  Parameters: "/silent /install"; \
  StatusMsg: "Installing Microsoft Edge WebView2 Runtime..."; \
  Flags: runhidden waituntilterminated

; Optionally launch after install
Filename: "{app}\{#AppExeName}"; \
  Description: "{cm:LaunchProgram,{#AppName}}"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\Alangrapher"

[Code]
// Check if WebView2 Evergreen Runtime is already installed.
// The bootstrapper is still always run (it's a no-op if already installed),
// but this gives us a chance to skip the progress message if unnecessary.
function HasWebView2: Boolean;
begin
  Result := RegKeyExists(
    HKLM,
    'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
  );
end;
