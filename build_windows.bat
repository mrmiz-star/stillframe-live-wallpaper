@echo off
setlocal
cd /d "%~dp0"
py -m pip install --upgrade pip
py -m pip install -r requirements.txt pyinstaller
py -m PyInstaller --noconfirm --clean --windowed --name Stillframe --onedir --collect-all PySide6 app.py
if errorlevel 1 exit /b %errorlevel%
echo.
echo Build complete: %CD%\dist\Stillframe\Stillframe.exe
echo Distribute the full dist\Stillframe folder, not just the executable.
pause
