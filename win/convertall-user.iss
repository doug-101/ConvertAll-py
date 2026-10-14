; convertall-user.iss

; Inno Setup installer script for ConvertAll, a unit converter
; This will install for a single user, no admin rights are required.

[Setup]
AppName=ConvertAll
AppVersion=0.9.3
MinVersion=10.0.17763
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DefaultDirName={userappdata}\ConvertAll
DefaultGroupName=ConvertAll
DisableProgramGroupPage=yes
OutputDir=.
OutputBaseFilename=convertall-0.9.3-install-user
PrivilegesRequired=lowest
SetupIconFile=convertall.ico
Uninstallable=IsTaskSelected('adduninstall')
UninstallDisplayIcon={app}\convertall.exe,0

[Tasks]
Name: "startmenu"; Description: "Add start menu shortcuts"
Name: "deskicon"; Description: "Add a desktop shortcut"
Name: "adduninstall"; Description: "Create an uninstaller"
Name: "translate"; Description: "Include language translations"
Name: "source"; Description: "Include source code"
Name: "portable"; Description: "Use portable config file"; Flags: unchecked

[InstallDelete]
Type: files; Name: "{app}\library.zip"
Type: files; Name: "{app}\python*.zip"
Type: files; Name: "{app}\*.pyd"
Type: files; Name: "{app}\*.dll"
Type: filesandordirs; Name: "{app}\lib"
Type: filesandordirs; Name: "{app}\imageformats"
Type: filesandordirs; Name: "{app}\platforms"
Type: filesandordirs; Name: "{app}\PyQt5"
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "convertall.exe"; DestDir: "{app}"
Source: "base_library.zip"; DestDir: "{app}"
Source: "convertall_dos.exe"; DestDir: "{app}"
Source: "*.dll"; DestDir: "{app}"
Source: "*.pyd"; DestDir: "{app}"
Source: "PyQt6\*"; DestDir: "{app}\PyQt6"; Flags: recursesubdirs createallsubdirs
Source: "PyQt6_sip-13.13.0.dist-info\*"; DestDir: "{app}\PyQt6_sip-13.13.0.dist-info"; Flags: recursesubdirs createallsubdirs
Source: "data\*.dat"; DestDir: "{app}\data"
Source: "doc\*.html"; DestDir: "{app}\doc"
Source: "doc\LICENSE*"; DestDir: "{app}\doc"
Source: "icons\*.png"; DestDir: "{app}\icons"
Source: "translations\*.qm"; DestDir: "{app}\translations"; Tasks: "translate"
Source: "source\*.py"; DestDir: "{app}\source"; Tasks: "source"
Source: "source\convertall.pro"; DestDir: "{app}\source"; Tasks: "source"
Source: "source\convertall.spec"; DestDir: "{app}\source"; Tasks: "source"
Source: "convertall.ico"; DestDir: "{app}"; Tasks: "source"
Source: "*.iss"; DestDir: "{app}"; Tasks: "source"
Source: "convertall.ini"; DestDir: "{app}"; Tasks: "portable"

[Icons]
Name: "{userstartmenu}\ConvertAll"; Filename: "{app}\convertall.exe"; \
      WorkingDir: "{app}"; Tasks: "startmenu"
Name: "{group}\ConvertAll"; Filename: "{app}\convertall.exe"; \
      WorkingDir: "{app}"; Tasks: "startmenu"
Name: "{group}\Uninstall"; Filename: "{uninstallexe}"; Tasks: "startmenu"
Name: "{userdesktop}\ConvertAll"; Filename: "{app}\convertall.exe"; \
      WorkingDir: "{app}"; Tasks: "deskicon"
