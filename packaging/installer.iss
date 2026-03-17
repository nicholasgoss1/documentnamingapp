; Inno Setup Script for Claim File Renamer
; Download Inno Setup from https://jrsoftware.org/isdl.php

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName=Claim File Renamer
AppVersion=1.0.0
AppVerName=Claim File Renamer 1.0.0
AppPublisher=ClaimFileRenamer
DefaultDirName={autopf}\ClaimFileRenamer
DefaultGroupName=Claim File Renamer
DisableProgramGroupPage=yes
OutputDir=..\installer_output
OutputBaseFilename=ClaimFileRenamer_Setup_1.0.0
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
Source: "..\dist\ClaimFileRenamer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Claim File Renamer"; Filename: "{app}\ClaimFileRenamer.exe"
Name: "{group}\{cm:UninstallProgram,Claim File Renamer}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Claim File Renamer"; Filename: "{app}\ClaimFileRenamer.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\ClaimFileRenamer.exe"; Description: "{cm:LaunchProgram,Claim File Renamer}"; Flags: nowait postinstall skipifsilent

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
  InstalledVersion: String;
  ResultCode: Integer;
begin
  Result := True;
  UninstallString := GetUninstallString();
  if UninstallString <> '' then
  begin
    InstalledVersion := GetInstalledVersion();
    if MsgBox('Claim File Renamer version ' + InstalledVersion + ' is already installed.' + #13#10 + #13#10 +
              'The previous version must be uninstalled before installing this version.' + #13#10 + #13#10 +
              'Would you like to uninstall it now?',
              mbConfirmation, MB_YESNO) = IDYES then
    begin
      Exec(RemoveQuotes(UninstallString), '/SILENT', '', SW_SHOW, ewWaitUntilTerminated, ResultCode);
      // Verify uninstall succeeded
      if GetUninstallString() <> '' then
      begin
        MsgBox('The previous version could not be uninstalled. Setup will now exit.', mbError, MB_OK);
        Result := False;
      end;
    end
    else
    begin
      MsgBox('The previous version must be uninstalled before installing this version.' + #13#10 +
             'Setup will now exit.', mbInformation, MB_OK);
      Result := False;
    end;
  end;
end;
