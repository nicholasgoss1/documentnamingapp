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
