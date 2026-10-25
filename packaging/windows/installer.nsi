; Instalador do Programador de Rádios (NSIS 3).
; Compile depois do PyInstaller, na raiz do projeto:
;   makensis -DVERSION=1.1.0 packaging/windows/installer.nsi

Unicode true
!include "MUI2.nsh"
!include "x64.nsh"

!ifndef VERSION
  !define VERSION "1.1.0"
!endif
!define APPNAME "Programador de Rádios"
!define APPEXE "ProgramadorRadios.exe"
!define REGKEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\ProgramadorRadios"
!define SRCDIR "../../dist/ProgramadorRadios"

Name "${APPNAME} ${VERSION}"
OutFile "../../dist/ProgramadorRadios-${VERSION}-instalador.exe"
InstallDir "$PROGRAMFILES64\Programador de Radios"
InstallDirRegKey HKLM "Software\ProgramadorRadios" "InstallDir"
RequestExecutionLevel admin
SetCompressor /SOLID lzma
BrandingText "${APPNAME} ${VERSION}"

VIProductVersion "${VERSION}.0"
VIAddVersionKey /LANG=1046 "ProductName" "${APPNAME}"
VIAddVersionKey /LANG=1046 "FileDescription" "Instalador do ${APPNAME}"
VIAddVersionKey /LANG=1046 "FileVersion" "${VERSION}"
VIAddVersionKey /LANG=1046 "ProductVersion" "${VERSION}"
VIAddVersionKey /LANG=1046 "LegalCopyright" "GPLv3"

!define MUI_ICON "../../assets/app.ico"
!define MUI_UNICON "../../assets/app.ico"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TEXT "Este assistente instalará o ${APPNAME} ${VERSION}.$\r$\n$\r$\nProgramação do Kenwood TS-2000 (memórias, menus e display em tempo real) e dos Icom ID-51A Plus2 e ID-880H.$\r$\n$\r$\nClique em Próximo para continuar."
!define MUI_FINISHPAGE_RUN "$INSTDIR\${APPEXE}"
!define MUI_FINISHPAGE_RUN_TEXT "Abrir o ${APPNAME}"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "PortugueseBR"

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "Este programa requer o Windows 64 bits."
    Abort
  ${EndIf}
  SetRegView 64
FunctionEnd

Function un.onInit
  SetRegView 64
FunctionEnd

Section "Programa (obrigatório)" SecMain
  SectionIn RO
  SetShellVarContext all
  ; remove arquivos de uma versão anterior antes de copiar
  RMDir /r "$INSTDIR\_internal"
  SetOutPath "$INSTDIR"
  File /r "${SRCDIR}/*.*"
  WriteUninstaller "$INSTDIR\Desinstalar.exe"

  CreateDirectory "$SMPROGRAMS\${APPNAME}"
  CreateShortcut "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk" "$INSTDIR\${APPEXE}"
  CreateShortcut "$SMPROGRAMS\${APPNAME}\Desinstalar.lnk" "$INSTDIR\Desinstalar.exe"

  WriteRegStr HKLM "Software\ProgramadorRadios" "InstallDir" "$INSTDIR"
  WriteRegStr HKLM "${REGKEY}" "DisplayName" "${APPNAME}"
  WriteRegStr HKLM "${REGKEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKLM "${REGKEY}" "DisplayIcon" "$INSTDIR\${APPEXE}"
  WriteRegStr HKLM "${REGKEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "${REGKEY}" "UninstallString" '"$INSTDIR\Desinstalar.exe"'
  WriteRegStr HKLM "${REGKEY}" "QuietUninstallString" '"$INSTDIR\Desinstalar.exe" /S'
  WriteRegDWORD HKLM "${REGKEY}" "NoModify" 1
  WriteRegDWORD HKLM "${REGKEY}" "NoRepair" 1
SectionEnd

Section "Atalho no desktop" SecDesktop
  SetShellVarContext all
  CreateShortcut "$DESKTOP\${APPNAME}.lnk" "$INSTDIR\${APPEXE}"
SectionEnd

Section "Uninstall"
  SetShellVarContext all
  Delete "$DESKTOP\${APPNAME}.lnk"
  RMDir /r "$SMPROGRAMS\${APPNAME}"
  RMDir /r "$INSTDIR\_internal"
  Delete "$INSTDIR\${APPEXE}"
  Delete "$INSTDIR\Desinstalar.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKLM "${REGKEY}"
  DeleteRegKey HKLM "Software\ProgramadorRadios"
SectionEnd

LangString DESC_MAIN ${LANG_PORTUGUESEBR} "Arquivos do programa e atalhos no Menu Iniciar."
LangString DESC_DESKTOP ${LANG_PORTUGUESEBR} "Cria um atalho na área de trabalho (desktop)."
!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecMain} $(DESC_MAIN)
  !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop} $(DESC_DESKTOP)
!insertmacro MUI_FUNCTION_DESCRIPTION_END
