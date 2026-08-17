@echo off
setlocal
cd /d "%~dp0"
title Seiko - Puzaty

where py >nul 2>&1
if %errorlevel%==0 (
  set "PY=py"
) else (
  set "PY=python"
)

%PY% -c "import kivy" >nul 2>&1
if errorlevel 1 (
  echo [1/2] Kivy not found. Installing Kivy 2.3.1...
  %PY% -m pip install --upgrade pip
  %PY% -m pip install -r requirements.txt
  if errorlevel 1 goto :error
)

echo [2/2] Starting Seiko...
%PY% main.py
if errorlevel 1 goto :error
exit /b 0

:error
echo.
echo ==========================================
echo GAME FAILED TO START.
echo See seiko_error.log in this folder.
echo ==========================================
pause
exit /b 1
