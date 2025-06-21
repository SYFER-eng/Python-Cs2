@echo off

cd /d "%~dp0"

pyinstaller --icon=icon.ico --onefile --windowed --name="Syfer-engs External" cs2.py

:: Check if the build was successful
if exist "dist\Syfer-engs External.exe" (
    echo Build successful
) else (
    echo Build failed
)

pause
