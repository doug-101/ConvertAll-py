; convertall-all.iss

; Inno Setup installer script for ConvertAll, an RPN calculator
; This will install for all users, admin rights are required.

[Setup]
AppName=ConvertAll
AppVersion=0.7.3
DefaultDirName={pf}\ConvertAll
DefaultGroupName=ConvertAll
DisableProgramGroupPage=yes
OutputDir=.
OutputBaseFilename=convertall-0.7.3-install-all
PrivilegesRequired=poweruser
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

[Files]
Source: "convertall.exe"; DestDir: "{app}"
Source: "python35.zip"; DestDir: "{app}"
Source: "*.dll"; DestDir: "{app}"
Source: "*.pyd"; DestDir: "{app}"
Source: "imageformats\*.dll"; DestDir: "{app}\imageformats"
Source: "platforms\*.dll"; DestDir: "{app}\platforms"
Source: "data\*.dat"; DestDir: "{app}\data"
Source: "doc\*.html"; DestDir: "{app}\doc"
Source: "doc\LICENSE"; DestDir: "{app}\doc"
Source: "icons\*.png"; DestDir: "{app}\icons"
Source: "translations\*.ts"; DestDir: "{app}\translations"; Tasks: "translate"
Source: "translations\*.qm"; DestDir: "{app}\translations"; Tasks: "translate"
Source: "source\*.py"; DestDir: "{app}\source"; Tasks: "source"
Source: "convertall.ico"; DestDir: "{app}"; Tasks: "source"
Source: "*.iss"; DestDir: "{app}"; Tasks: "source"
Source: "convertall.ini"; DestDir: "{app}"; Tasks: "portable"

[Icons]
Name: "{commonstartmenu}\ConvertAll"; Filename: "{app}\convertall.exe"; \
      WorkingDir: "{app}"; Tasks: "startmenu"
Name: "{group}\ConvertAll"; Filename: "{app}\convertall.exe"; \
      WorkingDir: "{app}"; Tasks: "startmenu"
Name: "{group}\Uninstall"; Filename: "{uninstallexe}"; Tasks: "startmenu"
Name: "{commondesktop}\ConvertAll"; Filename: "{app}\convertall.exe"; \
      WorkingDir: "{app}"; Tasks: "deskicon"
