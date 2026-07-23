; Inno Setup script for Foclo Windows installer.
;
; Usage:
;   iscc /DVersion=%VERSION% installer.iss
;
; Prerequisites: dist\Foclo.exe must exist (built by PyInstaller first).

#define AppName "Foclo"
#define AppPublisher "Foclo"
#define AppURL "https://github.com/Alangrapher/foclo"
#define AppExeName "Foclo.exe"

#ifndef Version
  #define Version "0.0.0-dev"
#endif

[Setup]
AppId={{3E1D9A5B-7C8F-4A2E-9D1F-6B3C8A4E7D2F}
AppName={#AppName}
AppVersion={#Version}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputBaseFilename=Foclo-Setup-{#Version}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "dist\Foclo.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch Foclo"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\Foclo"
