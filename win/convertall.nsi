; convertall.nsi

; Created       : 2004-03-09
; By            : Doug Bell
; License       : Free to use, modify and distribute, but with no warranty.
; Last modified : 2011-03-30

; ConvertAll is a versatile unit conversion program
; Please check the website for details and updates <http://www.bellz.org/>.

;--------------------------------

!include "MUI.nsh"


; The name of the installer

!define NAME "ConvertAll"
!define VERSION "0.5.1"

; Uncomment next line to include pyQt libraries in the installer
!define PYQT

!ifdef PYQT
	!define SUFFIX "-install"
!else
	!define SUFFIX "-upgrade"
!endif

Name "${NAME} ${VERSION} by Doug Bell"


; The file to write
OutFile "convertall-${VERSION}${SUFFIX}.exe"
SetCompressor lzma

!define MUI_ICON "install.ico"
!define MUI_UNICON "uninstall.ico"

XPStyle on

; The default installation directory
InstallDir "$PROGRAMFILES\${NAME}"

; Registry key to check for directory (so if you install again, it will
; overwrite the old one automatically)
InstallDirRegKey HKLM "Software\${NAME}" "Install_Dir"

;--------------------------------

!define MUI_COMPONENTSPAGE
!define MUI_COMPONENTSPAGE_SMALLDESC
!define MUI_LICENSEPAGE_TEXT_BOTTOM "Press Continue to install."
!define MUI_LICENSEPAGE_BUTTON "Continue"

!insertmacro MUI_PAGE_LICENSE ".\doc\LICENSE"
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

;--------------------------------
;Languages

!insertmacro MUI_LANGUAGE "English"


;--------------------------------

AutoCloseWindow false
ShowInstDetails show

InstType Typical
SetOverwrite ifnewer


; The stuff to install
Section "${NAME} (required)" convertall

	SectionIn 1 RO

	; Set output path to the installation directory.
	SetOutPath "$INSTDIR\lib"

	; Put files there
	File ".\lib\convertall.exe"
        File ".\lib\convertall_dos.exe"
        File ".\lib\library.zip"
        File ".\lib\units.dat"
	File ".\convertall.ico"

        ; Set output path to the doc install directory.
        SetOutPath "$INSTDIR\doc"

        ; Put files there
        File ".\doc\LICENSE"
        File ".\doc\README.html"

        ; Create an icons directory.
        SetOutPath "$INSTDIR\icons"

        ; Put files there
        File ".\icons\convertall_lg.png"
        File ".\icons\convertall_med.png"
        File ".\icons\convertall_sm.png"
        File ".\icons\helpback.png"
        File ".\icons\helpforward.png"
        File ".\icons\helphome.png"

SectionEnd

!ifdef PYQT

	Section "PyQt libraries (required)" py_qt

		SectionIn 1 RO

                Delete "$INSTDIR\lib\libgcc_s_dw2-1.dll"
                Delete "$INSTDIR\lib\mingwm10.dll"
                Delete "$INSTDIR\lib\msvcp71.dll"
                Delete "$INSTDIR\lib\MSVCR71.dll"
		Delete "$INSTDIR\lib\python25.dll"

                SetOutPath "$INSTDIR\lib"

                File ".\lib\_hashlib.pyd"
		File ".\lib\_socket.pyd"
		File ".\lib\_ssl.pyd"
                File ".\lib\bz2.pyd"
                File ".\lib\Microsoft.VC90.CRT.manifest"
                File ".\lib\msvcp90.dll"
                File ".\lib\msvcr90.dll"
                File ".\lib\PyQt4.QtCore.pyd"
                File ".\lib\PyQt4.QtGui.pyd"
                File ".\lib\python27.dll"
                File ".\lib\QtCore4.dll"
                File ".\lib\QtGui4.dll"
                File ".\lib\select.pyd"
                File ".\lib\sip.pyd"
                File ".\lib\unicodedata.pyd"
                File ".\lib\w9xpopen.exe"

	SectionEnd
!endif

Section "Start menu shortcuts" startmenu
	; Optional section (can be disabled by the user)
  SectionIn 1
  CreateDirectory "$SMPROGRAMS\${NAME}"
  CreateShortCut "$SMPROGRAMS\${NAME}\Uninstall.lnk" "$INSTDIR\uninstall.exe" "" "$INSTDIR\uninstall.exe" 0
  CreateShortCut "$SMPROGRAMS\${NAME}\Readme.lnk" "$INSTDIR\doc\Readme.html"
  CreateShortCut "$SMPROGRAMS\${NAME}\${NAME}.lnk" "$INSTDIR\lib\convertall.exe" "" "$INSTDIR\lib\convertall.exe" 0

SectionEnd

Section "Desktop shortcut" deskicon
	; Optional section (can be disabled by the user)
  SectionIn 1
  CreateShortCut "$DESKTOP\${NAME}.lnk" "$INSTDIR\lib\convertall.exe" "" "$INSTDIR\lib\convertall.exe" 0

SectionEnd

Section "Install and uninstall registry keys" reg_keys
        ; Optional section (can be disabled by the user)
        SectionIn 1

	; Write the installation path into the registry
	WriteRegStr HKLM "SOFTWARE\${NAME}" "Install_Dir" "$INSTDIR"

	; Write the uninstall keys for Windows
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${NAME}" "DisplayName" "${NAME}"
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${NAME}" "UninstallString" '"$INSTDIR\uninstall.exe"'
	WriteUninstaller "uninstall.exe"

SectionEnd

Section /o "${NAME} source code" source
	; Optional section (can be disabled by the user)
        SectionIn 1

        SetOutPath "$INSTDIR\source"

	File ".\convertall.nsi"
	File ".\install.ico"
	File ".\uninstall.ico"

        File ".\source\cmdline.py"
        File ".\source\convertall.py"
        File ".\source\convertdlg.py"
        File ".\source\finddlg.py"
        File ".\source\helpview.py"
        File ".\source\icondict.py"
        File ".\source\modbutton.py"
        File ".\source\numedit.py"
        File ".\source\option.py"
        File ".\source\optiondefaults.py"
        File ".\source\optiondlg.py"
        File ".\source\recentunits.py"
        File ".\source\setup.py"
        File ".\source\unitatom.py"
        File ".\source\unitdata.py"
        File ".\source\unitedit.py"
        File ".\source\unitgroup.py"
        File ".\source\unitlistview.py"
        File ".\source\convertall.pro"

SectionEnd

;--------------------------------
;Descriptions

LangString DESC_convertall ${LANG_ENGLISH} "ConvertAll program and help files."
LangString DESC_pyqt ${LANG_ENGLISH} "Required PyQt library files."
LangString DESC_startmenu ${LANG_ENGLISH} "Add ConvertAll to the Start menu."
LangString DESC_deskicon ${LANG_ENGLISH} "Add a ConvertAll shortcut to the desktop."
LangString DESC_reg_keys ${LANG_ENGLISH} "Write install and uninstall information."
LangString DESC_source ${LANG_ENGLISH} "ConvertAll source code (for developers)."

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
	!insertmacro MUI_DESCRIPTION_TEXT ${convertall} $(DESC_convertall)

	!ifdef PYQT
		!insertmacro MUI_DESCRIPTION_TEXT ${py_qt} $(DESC_pyqt)
	!endif

	!insertmacro MUI_DESCRIPTION_TEXT ${startmenu} $(DESC_startmenu)
	!insertmacro MUI_DESCRIPTION_TEXT ${deskicon} $(DESC_deskicon)
        !insertmacro MUI_DESCRIPTION_TEXT ${reg_keys} $(DESC_reg_keys)
	!insertmacro MUI_DESCRIPTION_TEXT ${source} $(DESC_source)
!insertmacro MUI_FUNCTION_DESCRIPTION_END


;--------------------------------

; Uninstaller

Section "Uninstall"

	; Remove registry keys
	DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${NAME}"
	DeleteRegKey HKLM "SOFTWARE\${NAME}"

	; Remove files and uninstaller

	Delete "$INSTDIR\lib\convertall.exe"
        Delete "$INSTDIR\lib\convertall_dos.exe"
        Delete "$INSTDIR\lib\library.zip"
        Delete "$INSTDIR\lib\units.dat"
	Delete "$INSTDIR\lib\convertall.ico"

        Delete "$INSTDIR\doc\LICENSE"
        Delete "$INSTDIR\doc\README.html"

        Delete "$INSTDIR\icons\convertall_lg.png"
        Delete "$INSTDIR\icons\convertall_med.png"
        Delete "$INSTDIR\icons\convertall_sm.png"
        Delete "$INSTDIR\icons\helpback.png"
        Delete "$INSTDIR\icons\helpforward.png"
        Delete "$INSTDIR\icons\helphome.png"

        Delete "$INSTDIR\lib\_hashlib.pyd"
	Delete "$INSTDIR\lib\_socket.pyd"
	Delete "$INSTDIR\lib\_ssl.pyd"
        Delete "$INSTDIR\lib\bz2.pyd"
        Delete "$INSTDIR\lib\libgcc_s_dw2-1.dll"
        Delete "$INSTDIR\lib\mingwm10.dll"
        Delete "$INSTDIR\lib\msvcp71.dll"
        Delete "$INSTDIR\lib\MSVCR71.dll"
        Delete "$INSTDIR\lib\Microsoft.VC90.CRT.manifest"
        Delete "$INSTDIR\lib\msvcp90.dll"
        Delete "$INSTDIR\lib\msvcr90.dll"
        Delete "$INSTDIR\lib\PyQt4.QtCore.pyd"
        Delete "$INSTDIR\lib\PyQt4.QtGui.pyd"
	Delete "$INSTDIR\lib\python24.dll"
	Delete "$INSTDIR\lib\python25.dll"
        Delete "$INSTDIR\lib\python27.dll"
        Delete "$INSTDIR\lib\QtCore4.dll"
        Delete "$INSTDIR\lib\QtGui4.dll"
        Delete "$INSTDIR\lib\sip.pyd"
        Delete "$INSTDIR\lib\unicodedata.pyd"
        Delete "$INSTDIR\lib\w9xpopen.exe"
        Delete "$INSTDIR\lib\zlib.pyd"

        Delete "$INSTDIR\lib\_qt.pyd"
        Delete "$INSTDIR\lib\_sre.pyd"
        Delete "$INSTDIR\lib\libqtc.pyd"
        Delete "$INSTDIR\lib\libsip.dll"
        Delete "$INSTDIR\lib\python23.dll"
        Delete "$INSTDIR\lib\qt.pyd"
        Delete "$INSTDIR\lib\qt-mt230nc.dll"
        Delete "$INSTDIR\lib\QtCore.pyd"
        Delete "$INSTDIR\lib\QtGui.pyd"

	Delete "$INSTDIR\source\convertall.nsi"
	Delete "$INSTDIR\source\install.ico"
	Delete "$INSTDIR\source\uninstall.ico"

        Delete "$INSTDIR\source\cmdline.py"
        Delete "$INSTDIR\source\convertall.py"
        Delete "$INSTDIR\source\convertdlg.py"
        Delete "$INSTDIR\source\finddlg.py"
        Delete "$INSTDIR\source\helpview.py"
        Delete "$INSTDIR\source\icondict.py"
        Delete "$INSTDIR\source\icons.py"
        Delete "$INSTDIR\source\modbutton.py"
        Delete "$INSTDIR\source\numedit.py"
        Delete "$INSTDIR\source\numeval1.py"
        Delete "$INSTDIR\source\numeval2.py"
        Delete "$INSTDIR\source\option.py"
        Delete "$INSTDIR\source\optiondefaults.py"
        Delete "$INSTDIR\source\optiondlg.py"
        Delete "$INSTDIR\source\recentunits.py"
        Delete "$INSTDIR\source\setup.py"
        Delete "$INSTDIR\source\tmpcontrol.py"
        Delete "$INSTDIR\source\unit.py"
        Delete "$INSTDIR\source\unitatom.py"
        Delete "$INSTDIR\source\unitdata.py"
        Delete "$INSTDIR\source\unitedit.py"
        Delete "$INSTDIR\source\unitgroup.py"
        Delete "$INSTDIR\source\unitlistview.py"
        Delete "$INSTDIR\source\convertall.pro"

	Delete "$INSTDIR\lib\convertall.ini"

	Delete "$INSTDIR\uninstall.exe"

	; Remove shortcuts, if any
	RMDir /r "$SMPROGRAMS\${NAME}"

	; Remove directories used
        RMDir "$INSTDIR\lib"
        RMDir "$INSTDIR\doc"
        RMDir "$INSTDIR\icons"
        RMDir "$INSTDIR\source"
	RMDir "$INSTDIR" ;remove if empty
	; RMDir /r "$INSTDIR" ;remove even if not empty

SectionEnd
