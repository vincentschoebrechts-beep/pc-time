@echo off
rem Construit dist\TempsPC.exe a partir de temps_pc.pyw (a lancer depuis le dossier du depot).
cd /d "%~dp0.."
py -m pip install --upgrade pyinstaller || goto :erreur
py -m PyInstaller --noconfirm --clean --onefile --windowed --name TempsPC ^
  --icon construction\tempspc.ico --version-file construction\version.txt temps_pc.pyw || goto :erreur
echo.
echo Termine : dist\TempsPC.exe
pause
exit /b 0

:erreur
echo.
echo La construction a echoue.
pause
exit /b 1
