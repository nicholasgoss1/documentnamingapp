; Inno Setup Script for ClaimsCo Document Tools
; Download Inno Setup from https://jrsoftware.org/isdl.php

[Setup]
; PERMANENT AppId — never change this GUID across future versions.
; It ensures upgrades silently replace the previous installation.
AppId={{4D574B20-DB46-4E5F-B09B-7F815975303B}
AppName=ClaimsCo Document Tools
AppVersion=2.0.7
AppVerName=ClaimsCo Document Tools v2.0.7
AppPublisher=ClaimsCo Pty Ltd
DefaultDirName={autopf}\ClaimsCo_Tools
DefaultGroupName=ClaimsCo Document Tools
DisableProgramGroupPage=yes
OutputDir=..\installer_output
OutputBaseFilename=ClaimsCo_Tools_Setup_v2.0.7
SetupIconFile=..\assets\icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\ClaimsCo_Tools\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\ClaimsCo Document Tools"; Filename: "{app}\ClaimsCo_Tools.exe"
Name: "{group}\{cm:UninstallProgram,ClaimsCo Document Tools}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\ClaimsCo Document Tools"; Filename: "{app}\ClaimsCo_Tools.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\ClaimsCo_Tools.exe"; Description: "{cm:LaunchProgram,ClaimsCo Document Tools}"; Flags: nowait postinstall skipifsilent

[Code]
// ────────────────────────────────────────────────────────────────────────
// Silent uninstall of ANY previous version by display name.
//
// Searches HKLM, HKCU, and WOW6432Node uninstall registry paths for
// entries whose DisplayName starts with "Claim File Renamer" (old app)
// or "ClaimsCo Document Tools" (current app, any version).
//
// This ensures v1.0 through v1.6 of the old app AND any prior v2.x
// of the new app are silently removed before installing the new version.
// ────────────────────────────────────────────────────────────────────────

procedure UninstallByDisplayNamePrefix(RootKey: Integer; const BasePath: String; const Prefix: String);
var
  SubKeys: TArrayOfString;
  I: Integer;
  KeyPath: String;
  DisplayName: String;
  UninstallCmd: String;
  ResultCode: Integer;
begin
  if not RegGetSubkeyNames(RootKey, BasePath, SubKeys) then
    Exit;

  for I := 0 to GetArrayLength(SubKeys) - 1 do
  begin
    KeyPath := BasePath + '\' + SubKeys[I];

    if not RegQueryStringValue(RootKey, KeyPath, 'DisplayName', DisplayName) then
      Continue;

    // Check if DisplayName starts with the target prefix (case-insensitive)
    if Pos(Lowercase(Prefix), Lowercase(DisplayName)) <> 1 then
      Continue;

    // Found a match — try QuietUninstallString first, then UninstallString
    if RegQueryStringValue(RootKey, KeyPath, 'QuietUninstallString', UninstallCmd) then
    begin
      Exec('>', '/C ' + UninstallCmd, '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    end
    else if RegQueryStringValue(RootKey, KeyPath, 'UninstallString', UninstallCmd) then
    begin
      Exec(RemoveQuotes(UninstallCmd), '/SILENT /NORESTART', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    end;
  end;
end;

procedure RemoveAllPreviousVersions();
var
  BasePaths: array[0..2] of String;
  Prefixes: array[0..1] of String;
  RootKeys: array[0..1] of Integer;
  I, J, K: Integer;
begin
  // Registry base paths to search
  BasePaths[0] := 'Software\Microsoft\Windows\CurrentVersion\Uninstall';
  BasePaths[1] := 'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall';
  BasePaths[2] := 'Software\Microsoft\Windows\CurrentVersion\Uninstall';

  // Display name prefixes to match (old app name + current app name)
  Prefixes[0] := 'Claim File Renamer';
  Prefixes[1] := 'ClaimsCo Document Tools';

  // Root keys: HKLM and HKCU
  RootKeys[0] := HKLM;
  RootKeys[1] := HKCU;

  for I := 0 to 1 do              // Each root key
    for J := 0 to 2 do            // Each base path (native + WOW6432Node)
      for K := 0 to 1 do          // Each display name prefix
        UninstallByDisplayNamePrefix(RootKeys[I], BasePaths[J], Prefixes[K]);
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  // Silently remove ALL previous versions of both old and new app names
  RemoveAllPreviousVersions();
end;
