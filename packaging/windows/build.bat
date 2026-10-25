@echo off
rem Gera o executavel e o instalador no Windows.
rem Requisitos: Python 3.12 64 bits (python.org, com Tcl/Tk) e NSIS 3
rem (https://nsis.sourceforge.io) instalados.
rem Uso: na raiz do projeto, execute  packaging\windows\build.bat

setlocal
cd /d "%~dp0\..\.."
for /f "tokens=2 delims==" %%v in ('findstr /b "__version__" launcher\__init__.py') do set VERSION=%%~v
set VERSION=%VERSION: =%
set VERSION=%VERSION:"=%
echo Versao: %VERSION%

python -m pip install --upgrade "pyinstaller==6.11.1" pyserial || goto :erro
python -m PyInstaller --noconfirm --clean --distpath dist --workpath build\pyinstaller packaging\windows\pt2vhf-prog-tool.spec || goto :erro

set MAKENSIS=makensis
where makensis >nul 2>nul || set MAKENSIS="%ProgramFiles(x86)%\NSIS\makensis.exe"
%MAKENSIS% -DVERSION=%VERSION% packaging\windows\installer.nsi || goto :erro

echo.
echo Pronto: dist\PT2VHFProgTool-%VERSION%-instalador.exe
exit /b 0

:erro
echo Falha no build.
exit /b 1
