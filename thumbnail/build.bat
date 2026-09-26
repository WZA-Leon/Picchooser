@echo off
REM Build the thumbnail DLL with MinGW g++.
REM Output: thumbnail.dll (same folder as this script)
REM Usage: double-click this script, or run build.bat in a terminal.

setlocal
cd /d "%~dp0"

echo [1/2] Compiling thumbnail.dll ...
g++ -O2 -shared -o thumbnail.dll thumbnail.cpp -lole32 -loleaut32 -luuid -lgdi32 -lshlwapi -static-libgcc -static-libstdc++ -Wl,--kill-at

if errorlevel 1 (
    echo [ERROR] Build failed. Make sure g++ is in PATH.
    exit /b 1
)

echo [2/2] Build OK: %cd%\thumbnail.dll
endlocal
