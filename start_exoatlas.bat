@echo off
setlocal
set "ROOT=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\start_exoatlas.ps1"
if errorlevel 1 (
    echo.
    echo ExoAtlas could not be started. Review the message above.
    pause
    exit /b 1
)
endlocal
