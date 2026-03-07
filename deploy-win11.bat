@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%deploy-win11.ps1" %*
exit /b %ERRORLEVEL%
