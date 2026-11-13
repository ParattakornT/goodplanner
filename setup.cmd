@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  call :create_venv
  if errorlevel 1 goto failed
  goto install_packages
)
".venv\Scripts\python.exe" -c "import sys" >nul 2>nul
if errorlevel 1 (
  echo Existing virtual environment is invalid. Recreating it...
  py -3 -m venv --clear .venv
  if errorlevel 1 (
    python -m venv --clear .venv
    if errorlevel 1 goto failed
  )
)
:install_packages
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo Setup complete. Open start.cmd to launch GoodPlanner.
exit /b 0
:create_venv
py -3 -m venv .venv
if errorlevel 1 python -m venv .venv
exit /b %errorlevel%
:failed
echo Setup failed. Install Python 3.10 or newer, then retry setup.cmd.
exit /b 1
