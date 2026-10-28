; Instalador do PT2VHF Prog Tool (NSIS 3).
; Compile depois do PyInstaller, na raiz do projeto, sem trocar de pasta:
;   makensis -NOCD -DVERSION=X.Y.Z packaging/windows/installer.nsi
; (no Windows: makensis /NOCD ...). Opcional: -DROOT=<raiz do projeto>.

Unicode true
!include "MUI2.nsh"
!include "x64.nsh"
!include "FileFunc.nsh"

!ifndef VERSION
  !define VERSION "1.3.0"
!endif
!define APPNAME "PT2VHF Prog Tool"
!define APPEXE "PT2VHFProgTool.exe"
!define REGKEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\PT2VHFProgTool"
!ifndef ROOT
  !define ROOT "${__FILEDIR__}/../.."
!endif
!define SRCDIR "${ROOT}/dist/PT2VHFProgTool"

Name "${APPNAME} ${VERSION}"
OutFile "${ROOT}/dist/PT2VHFProgTool-${VERSION}-instalador.exe"
InstallDir "$PROGRAMFILES64\PT2VHF Prog Tool"
InstallDirRegKey HKLM "Software\PT2VHFProgTool" "InstallDir"
RequestExecutionLevel admin
SetCompressor /SOLID lzma
BrandingText "${APPNAME} ${VERSION}"

VIProductVersion "${VERSION}.0"
VIAddVersionKey /LANG=1046 "ProductName" "${APPNAME}"
VIAddVersionKey /LANG=1046 "FileDescription" "Instalador do ${APPNAME}"
VIAddVersionKey /LANG=1046 "FileVersion" "${VERSION}"
VIAddVersionKey /LANG=1046 "ProductVersion" "${VERSION}"
VIAddVersionKey /LANG=1046 "LegalCopyright" "GPLv3"

!define MUI_ICON "${ROOT}/assets/app.ico"
!define MUI_UNICON "${ROOT}/assets/app.ico"
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

!define OLDKEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\ProgramadorRadios"

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "Este programa requer o Windows 64 bits."
    Abort
  ${EndIf}
  SetRegView 64
FunctionEnd

; Remove a versão 1.1.0, que se chamava "Programador de Rádios"
Section "-RemoverVersaoAntiga"
  ReadRegStr $R0 HKLM "${OLDKEY}" "InstallLocation"
  StrCmp $R0 "" fim
  IfFileExists "$R0\Desinstalar.exe" 0 fim
    DetailPrint "Removendo a versão anterior (Programador de Rádios)..."
    ExecWait '"$R0\Desinstalar.exe" /S _?=$R0'
    Delete "$R0\Desinstalar.exe"
    RMDir "$R0"
  fim:
SectionEnd

; atualização automática: "instalador.exe /S /AUTOSTART" reabre o programa
Function .onInstSuccess
  ${GetParameters} $R0
  ClearErrors
  ${GetOptions} $R0 "/AUTOSTART" $R1
  IfErrors +2
    Exec '"$INSTDIR\${APPEXE}"'
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
  File "/oname=LICENCA.txt" "${ROOT}/LICENSE"
  WriteUninstaller "$INSTDIR\Desinstalar.exe"

  CreateDirectory "$SMPROGRAMS\${APPNAME}"
  CreateShortcut "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk" "$INSTDIR\${APPEXE}"
  CreateShortcut "$SMPROGRAMS\${APPNAME}\Desinstalar.lnk" "$INSTDIR\Desinstalar.exe"

  WriteRegStr HKLM "Software\PT2VHFProgTool" "InstallDir" "$INSTDIR"
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
  Delete "$INSTDIR\LICENCA.txt"
  RMDir "$INSTDIR"
  DeleteRegKey HKLM "${REGKEY}"
  DeleteRegKey HKLM "Software\PT2VHFProgTool"
SectionEnd

LangString DESC_MAIN ${LANG_PORTUGUESEBR} "Arquivos do programa e atalhos no Menu Iniciar."
LangString DESC_DESKTOP ${LANG_PORTUGUESEBR} "Cria um atalho na área de trabalho (desktop)."
!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecMain} $(DESC_MAIN)
  !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop} $(DESC_DESKTOP)
!insertmacro MUI_FUNCTION_DESCRIPTION_END
