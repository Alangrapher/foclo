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

; Only launch the app if WebView2 is confirmed present.
; If the bootstrapper failed, the launch is silently skipped
; and the user gets a Start Menu shortcut to retry manually.
Filename: "{app}\{#AppExeName}"; \
  Description: "{cm:LaunchProgram,{#AppName}}"; \
  Flags: nowait postinstall skipifsilent; \
  Check: HasWebView2

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\Alangrapher"

[Code]
// Robust WebView2 detection — checks multiple registry locations.
// The Evergreen Runtime registers under HKLM with this GUID.
// Used by [Run] Check parameter to skip app launch if WebView2 is missing.
function HasWebView2: Boolean;
var
  KeyPaths: array of String;
  i: Integer;
begin
  SetArrayLength(KeyPaths, 5);
  KeyPaths[0] := 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  KeyPaths[1] := 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  KeyPaths[2] := 'SOFTWARE\WOW6432Node\Microsoft\EdgeWebView\';
  KeyPaths[3] := 'SOFTWARE\Microsoft\EdgeWebView\';
  KeyPaths[4] := 'SOFTWARE\Classes\CLSID\{26C7A6A1-C9E3-4E9A-A09C-3F1D7F0A2D5B}\';

  for i := 0 to 4 do
  begin
    if RegKeyExists(HKLM, KeyPaths[i]) then
    begin
      Result := True;
      Exit;
    end;
  end;
  Result := False;
end;
