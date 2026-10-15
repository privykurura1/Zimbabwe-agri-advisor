; Murimi Fara - Windows Installer Script
; Build this with Inno Setup (free): https://jrsoftware.org/isinfo.php
;
; HOW TO USE:
; 1. Open this file in Inno Setup Compiler (just double-click it once
;    Inno Setup is installed)
; 2. Check the SourceDir path below matches where your dist\MurimiFara\
;    folder actually is
; 3. Click Build > Compile (or press F9)
; 4. The finished installer appears in an "Output" folder next to this
;    script - that Setup.exe is what you hand to a farmer/extension
;    officer/anyone
;
; NOTE ON SIZE: since this bundles the full offline model, the
; resulting installer will be large (roughly 1-1.5 GB, matching what's
; already in dist\MurimiFara\) - that's expected and correct, not a
; mistake. This is the tradeoff for genuinely zero-setup offline use:
; everything needed is inside this one file.

#define MyAppName "Murimi Fara"
#define MyAppVersion "1.2"
#define MyAppPublisher "MPKCOMTECK Technologies (Private) Limited"
#define MyAppExeName "MurimiFara.exe"

[Setup]
AppId={{8F3B2C1A-4D5E-4A6F-9B7C-1E2F3A4B5C6D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
; Install for the current user only: no administrator prompt (many farmers'
; and extension officers' laptops are locked down), and the app folder stays
; writable. {autopf} then resolves to the user's own Programs folder.
PrivilegesRequired=lowest
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; Lets the person installing pick a different drive/folder if their
; C: drive is short on space - genuinely useful given the install size
DiskSpanning=no
OutputDir=Output
OutputBaseFilename=MurimiFara-Setup-{#MyAppVersion}
; If the app is open when someone installs an update, ask to close it first
; (otherwise Windows locks its files and the update half-fails).
CloseApplications=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=murimifara.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Large files (the model) compress slowly - "fast" compression trades
; a bigger installer file for a much quicker build while you're testing.
; Switch to "lzma2/max" for the final version you actually distribute.
;CompressionThreads=auto

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
; Pulls in EVERYTHING from your built dist\MurimiFara\ folder -
; the exe, index.html, rag.py, corpus, vendor/, llama/, model/, all of it.
; EDIT the Source path below if your folder is somewhere different.
Source: "dist\MurimiFara\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName} now"; Flags: nowait postinstall skipifsilent
