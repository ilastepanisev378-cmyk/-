@echo off
setlocal
cd /d "%~dp0"
title Seiko - Puzaty DEBUG
where py >nul 2>&1
if %errorlevel%==0 (set "PY=py") else (set "PY=python")
%PY% -u main.py > seiko_error.log 2>&1
type seiko_error.log
echo.
echo ==========================================
echo Log saved to seiko_error.log
echo ==========================================
pause
