@echo off
rem Construit dist\PCTime.exe a partir de pc_time.pyw (a lancer depuis le dossier du depot).
cd /d "%~dp0.."
py -m pip install --upgrade pyinstaller || goto :erreur
py -m PyInstaller --noconfirm --clean --onefile --windowed --name PCTime ^
  --icon construction\tempspc.ico --version-file construction\version.txt pc_time.pyw || goto :erreur
echo.
echo Termine : dist\PCTime.exe
pause
exit /b 0

:erreur
echo.
echo La construction a echoue.
pause
exit /b 1
