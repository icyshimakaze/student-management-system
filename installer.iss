; Inno Setup script for the Student Management System desktop app.
;
; Prerequisite: build the app first so dist\StudentManagementSystem exists:
;     pyinstaller StudentManagementSystem.spec --noconfirm
; Then compile this script (right-click -> Compile, or):
;     ISCC.exe installer.iss
;
; Output: installer output\StudentManagementSystem-Setup.exe

#define MyAppName "Student Management System"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Student Management System"
#define MyAppExeName "StudentManagementSystem.exe"

[Setup]
AppId={{8F4B6C1E-2A7D-4E93-9B5F-3C8D1A0E7F42}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\StudentManagementSystem
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; Prefer per-user install (no admin needed) but allow machine-wide choice
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=output
OutputBaseFilename=StudentManagementSystem-Setup
SetupIconFile=resources\brand-icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; The whole PyInstaller one-folder build — exe plus its _internal runtime.
Source: "dist\StudentManagementSystem\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Remove settings written next to the exe during use (never deletes user data outside {app}).
Type: files; Name: "{app}\.env"
Type: files; Name: "{app}\student_management.log"
