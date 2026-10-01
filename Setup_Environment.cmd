@echo off
setlocal

set "SDT_VENV=%USERPROFILE%\.venvs\sdt"
set "SDT_PYTHON=%SDT_VENV%\Scripts\python.exe"

echo Setting up Simple Database Toolkit...

if not exist "%SDT_PYTHON%" (
    py -3.13 -m venv "%SDT_VENV%"
    if errorlevel 1 goto :failure
)

"%SDT_PYTHON%" -m pip install --upgrade pip
if errorlevel 1 goto :failure

pushd "%~dp0"
"%SDT_PYTHON%" -m pip install -e ".[dev,build]"
set "INSTALL_RESULT=%ERRORLEVEL%"
popd

if not "%INSTALL_RESULT%"=="0" goto :failure

"%SDT_PYTHON%" -m pip check
if errorlevel 1 goto :failure

echo.
echo Setup completed successfully.
echo Run Launch_Simple_Database_Toolkit.cmd to open the application.
pause
exit /b 0

:failure
echo.
echo Setup failed. Review the messages above.
pause
exit /b 1
