@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
py -3 "%SCRIPT_DIR%build_exe.py"
exit /b %errorlevel%
