@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
py -3 -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if not errorlevel 1 goto use_py
python -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if not errorlevel 1 goto use_python
echo Python 3.10+ with Tcl/Tk is required.
echo Install Python from python.org and include the Tcl/Tk component.
pause
exit /b 1
:use_py
py -3 main.py %*
goto done
:use_python
python main.py %*
:done
if errorlevel 1 (
  echo.
  echo UE TableDesk failed. Review the message above.
  pause
  exit /b 1
)
exit /b 0
