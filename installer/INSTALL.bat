@echo off
rem Double-click to install SimRCL into Cinema 4D. The work is done by install.ps1 next to this file.
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
echo.
pause
