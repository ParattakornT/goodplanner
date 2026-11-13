@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  call setup.cmd
  if errorlevel 1 goto failed
  goto environment_ready
)
".venv\Scripts\python.exe" -c "import sys" >nul 2>nul
if errorlevel 1 (
  call setup.cmd
  if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -c "import django, whitenoise" >nul 2>nul
if errorlevel 1 (
  call setup.cmd
  if errorlevel 1 goto failed
)
:environment_ready
".venv\Scripts\python.exe" manage.py migrate --noinput
if errorlevel 1 goto failed
".venv\Scripts\python.exe" manage.py collectstatic --noinput >nul
if errorlevel 1 goto failed
".venv\Scripts\python.exe" manage.py import_legacy
if errorlevel 1 goto failed
echo.
echo Open http://localhost:3000/login.html in your browser.
echo Keep this window open. Press Ctrl+C to stop Django.
".venv\Scripts\python.exe" manage.py runserver 127.0.0.1:3000
pause
exit /b 0
:failed
echo GoodPlanner could not start. Read the error above.
pause
exit /b 1
