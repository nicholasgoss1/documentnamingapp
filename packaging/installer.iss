; Inno Setup Script for ClaimsCo Document Tools
; Download Inno Setup from https://jrsoftware.org/isdl.php

[Setup]
; PERMANENT AppId — never change this GUID across future versions.
; It ensures upgrades silently replace the previous installation.
AppId={{4D574B20-DB46-4E5F-B09B-7F815975303B}
AppName=ClaimsCo Document Tools
AppVersion=2.0.0
AppVerName=ClaimsCo Document Tools v2.0.0
AppPublisher=ClaimsCo Pty Ltd
DefaultDirName={autopf}\ClaimsCo_Tools
DefaultGroupName=ClaimsCo Document Tools
DisableProgramGroupPage=yes
OutputDir=..\installer_output
OutputBaseFilename=ClaimsCo_Tools_Setup_v2.0.0
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
function GetUninstallString(): String;
var
  UninstallKey: String;
  UninstallString: String;
begin
  Result := '';
  UninstallKey := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#SetupSetting("AppId")}_is1';
  if RegQueryStringValue(HKLM, UninstallKey, 'UninstallString', UninstallString) then
    Result := UninstallString
  else if RegQueryStringValue(HKCU, UninstallKey, 'UninstallString', UninstallString) then
    Result := UninstallString;
end;

function GetInstalledVersion(): String;
var
  UninstallKey: String;
  DisplayVersion: String;
begin
  Result := '';
  UninstallKey := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#SetupSetting("AppId")}_is1';
  if RegQueryStringValue(HKLM, UninstallKey, 'DisplayVersion', DisplayVersion) then
    Result := DisplayVersion
  else if RegQueryStringValue(HKCU, UninstallKey, 'DisplayVersion', DisplayVersion) then
    Result := DisplayVersion;
end;

function InitializeSetup(): Boolean;
var
  UninstallString: String;
  ResultCode: Integer;
begin
  Result := True;
  UninstallString := GetUninstallString();
  // If a previous version exists, uninstall it silently before proceeding
  if UninstallString <> '' then
  begin
    Exec(RemoveQuotes(UninstallString), '/SILENT', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    if GetUninstallString() <> '' then
    begin
      MsgBox('The previous version could not be removed. Setup will now exit.', mbError, MB_OK);
      Result := False;
    end;
  end;
end;
