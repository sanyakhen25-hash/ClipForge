[Setup]
AppName=ClipForge
AppVersion=1.0
DefaultDirName={autopf}\ClipForge
DefaultGroupName=ClipForge
OutputDir=installer
OutputBaseFilename=ClipForge-Setup
Compression=lzma2
SolidCompression=yes

[Files]
Source: "dist\ClipForge\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\ClipForge"; Filename: "{app}\ClipForge.exe"
Name: "{autodesktop}\ClipForge"; Filename: "{app}\ClipForge.exe"

[Run]
Filename: "{app}\ClipForge.exe"; Description: "Open ClipForge"; Flags: nowait postinstall skipifsilent
