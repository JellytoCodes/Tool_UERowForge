@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
py -3 -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
  echo First install the optional packaging tool:
  echo py -3 -m pip install pyinstaller
  pause
  exit /b 1
)
py -3 -m PyInstaller --clean --windowed --onedir --name UERowForge --add-data "resources:resources" --add-data "../README.md:." --add-data "../LICENSE.txt:." --add-data "uerowforge/unreal_bridge.py:uerowforge" main.py
if errorlevel 1 (
  echo Packaging failed.
  pause
  exit /b 1
)
echo.
echo Output: dist\UERowForge\UERowForge.exe
echo Distribute the ENTIRE dist\UERowForge directory, not just the EXE.
pause
