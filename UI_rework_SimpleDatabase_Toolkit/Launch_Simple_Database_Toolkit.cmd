@echo off
setlocal

set "SDT_VENV=%USERPROFILE%\.venvs\sdt"
set "SDT_PYTHON=%SDT_VENV%\Scripts\pythonw.exe"

if not exist "%SDT_PYTHON%" (
    echo The Simple Database Toolkit environment is not installed.
    echo Run Setup_Environment.cmd first.
    pause
    exit /b 1
)

start "Simple Database Toolkit" "%SDT_PYTHON%" "%~dp0app.py"
exit /b 0
