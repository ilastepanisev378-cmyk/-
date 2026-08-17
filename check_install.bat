@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (set "PY=py") else (set "PY=python")
echo Python:
%PY% --version
echo.
echo Kivy:
%PY% -c "import kivy; print(kivy.__version__)"
echo.
echo Files:
%PY% -c "import os; print('main.py:',os.path.isfile('main.py')); print('ui.kv:',os.path.isfile('ui.kv')); print('assets:',len(os.listdir('assets')))"
pause
