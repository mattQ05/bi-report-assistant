; BI Report Assistant — Inno Setup Installer Script
;
; Requirements:
;   - Inno Setup 6.x (https://jrsoftware.org/isinfo.php)
;   - PyInstaller output in ..\dist\bi_report_assistant\
;
; Usage:
;   Open this file in the Inno Setup Compiler and click Build, or:
;   iscc installer\bi_report_assistant.iss

#define AppName      "BI Report Assistant"
#define AppVersion   "1.0.0"
#define AppPublisher "BI Report Assistant"
#define AppURL       "https://github.com/yourusername/bi-report-assistant"
#define AppExeName   "bi_report_assistant.exe"

[Setup]
; Basic identity
AppId={{A3F7C2B1-9E4D-4F8A-B2C5-1D6E3A7F0B9C}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}

; Install location — Program Files by default
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes

; Require admin rights so we can write to the Power BI External Tools folder
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog

; Output
OutputDir={#SourcePath}\installer_output
OutputBaseFilename=BI-Report-Assistant-Setup-{#AppVersion}

; Compression
Compression=lzma2/ultra64
SolidCompression=yes
InternalCompressLevel=ultra64

; Appearance
WizardStyle=modern

; Misc
ShowLanguageDialog=no
LanguageDetectionMethod=none
ChangesAssociations=no
RestartIfNeededByRun=no
CloseApplications=yes
CloseApplicationsFilter=*.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked
Name: "startmenuicon"; Description: "Add to Start Menu"; GroupDescription: "Additional shortcuts:"; Flags: checkedonce

[Files]
; Main app bundle from PyInstaller
Source: "{#SourcePath}\dist\bi_report_assistant\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Copy the bundled pbitool.json (with icon baked in) directly to the External Tools folder
; This is done by Inno Setup which runs as admin, so no permission issues
Source: "{#SourcePath}\BI Report Assistant_bundled.pbitool.json"; \
  DestDir: "{commonpf32}\Common Files\Microsoft Shared\Power BI Desktop\External Tools"; \
  DestName: "BI Report Assistant.pbitool.json"; \
  Flags: ignoreversion skipifsourcedoesntexist

[Icons]
; Start Menu
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: startmenuicon

; Desktop
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

; Start Menu uninstall entry
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"

[Run]
; Run the setup wizard after installation — elevated so it can write to the External Tools folder
Filename: "{app}\{#AppExeName}"; Parameters: "--setup"; Description: "Complete first-time setup (required)"; \
  Flags: nowait postinstall skipifsilent runasoriginaluser

[UninstallDelete]
; Clean up runtime-generated files in the install dir
Type: files; Name: "{app}\powerbi_context.txt"
Type: files; Name: "{app}\powerbi_model_context.txt"

[Code]
// ── Check Power BI Desktop is installed ───────────────────────────────────────
function PowerBIInstalled(): Boolean;
var
  Key: String;
  Path: String;
begin
  Result := False;

  // Standard installer — HKLM 64-bit
  Key := 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Power BI Desktop';
  if RegKeyExists(HKLM, Key) then begin Result := True; exit; end;

  // Standard installer — HKLM 32-bit node
  Key := 'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Power BI Desktop';
  if RegKeyExists(HKLM, Key) then begin Result := True; exit; end;

  // Standard installer — HKCU
  Key := 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Power BI Desktop';
  if RegKeyExists(HKCU, Key) then begin Result := True; exit; end;

  // Microsoft Store version — check WindowsApps folder
  Path := ExpandConstant('{commonpf}\WindowsApps');
  if DirExists(Path) then begin
    // Store installs show up as Microsoft.MicrosoftPowerBIDesktop_x.x.x_x64__*
    // We can't glob in Pascal script easily, so just check if the External Tools
    // folder exists — if Power BI has ever been run, this folder is created
    Path := ExpandConstant('{commonpf32}\Common Files\Microsoft Shared\Power BI Desktop');
    if DirExists(Path) then begin Result := True; exit; end;
  end;

  // Final fallback — check common install paths directly
  if FileExists(ExpandConstant('{commonpf}\Microsoft Power BI Desktop\bin\PBIDesktop.exe')) then begin
    Result := True; exit;
  end;
  if FileExists(ExpandConstant('{commonpf32}\Microsoft Power BI Desktop\bin\PBIDesktop.exe')) then begin
    Result := True; exit;
  end;
end;

// ── Register the External Tool during installation ────────────────────────────
procedure RegisterExternalTool();
var
  ToolsDir: String;
  JsonSrc:  String;
  JsonDest: String;
begin
  ToolsDir := ExpandConstant(
    '{commonpf32}\Common Files\Microsoft Shared\Power BI Desktop\External Tools'
  );
  JsonSrc  := ExpandConstant('{app}\BI Report Assistant.pbitool.json');
  JsonDest := ToolsDir + '\BI Report Assistant.pbitool.json';

  // Create the folder if it doesn't exist
  if not DirExists(ToolsDir) then
    ForceDirectories(ToolsDir);

  // Copy the file
  if FileCopy(JsonSrc, JsonDest, False) then
    Log('External Tool registered at: ' + JsonDest)
  else
    Log('WARNING: Could not register External Tool at: ' + JsonDest);
end;

// ── Remove the External Tool on uninstall ────────────────────────────────────
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  JsonDest: String;
begin
  if CurUninstallStep = usPostUninstall then begin
    JsonDest := ExpandConstant(
      '{commonpf32}\Common Files\Microsoft Shared\Power BI Desktop\External Tools\BI Report Assistant.pbitool.json'
    );
    if FileExists(JsonDest) then
      DeleteFile(JsonDest);
  end;
end;

// ── Main install steps ────────────────────────────────────────────────────────
procedure CurStepChanged(CurStep: TSetupStep);
var
  ToolsDir: String;
  JsonFile: String;
  ExePath:  String;
begin
  if CurStep = ssPostInstall then begin
    // The bundled pbitool.json was already copied with the icon by [Files]
    // Now update the path field to point to the installed exe
    ToolsDir := ExpandConstant('{commonpf32}\Common Files\Microsoft Shared\Power BI Desktop\External Tools');
    JsonFile := ToolsDir + '\BI Report Assistant.pbitool.json';
    ExePath  := ExpandConstant('{app}\{#AppExeName}');
    Log('pbitool.json installed with icon at: ' + JsonFile);
    Log('Exe path: ' + ExePath);
    // The setup wizard (--setup) will update the path/arguments fields
    // while preserving the iconData that was baked in at build time
  end;
end;

// ── Pre-install checks ─────────────────────────────────────────────────────────
function InitializeSetup(): Boolean;
begin
  Result := True;
  // Power BI check is informational only — don't block installation.
  // The user may have the Store version which is harder to detect via registry.
end;
