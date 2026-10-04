@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
if errorlevel 1 (
    echo FAIL: Could not change to the project folder.
    pause
    exit /b 1
)
set "PYTHONPATH=%CD%\backend;%CD%\frontend;%CD%\another;%PYTHONPATH%"

set "FORCE_INSTALL=0"
set "RUN_TESTS=0"
for %%A in (%*) do (
    if /i "%%~A"=="--reinstall" set "FORCE_INSTALL=1"
    if /i "%%~A"=="--test" set "RUN_TESTS=1"
)

if not exist ".venv\Scripts\python.exe" call :create_venv
if errorlevel 1 exit /b 1

call :install_if_needed environments\requirements.txt .venv\.req_hash
if errorlevel 1 exit /b 1

if "!RUN_TESTS!"=="1" (
    call :install_if_needed environments\requirements-dev.txt .venv\.dev_req_hash
    if errorlevel 1 exit /b 1
    .venv\Scripts\python.exe -m pytest -q
    if errorlevel 1 (
        echo FAIL: Tests failed.
        pause
        exit /b 1
    )
    exit /b 0
)

if defined BTL_RUN_SMOKE (
    if "!BTL_RUN_SMOKE!"=="1" (
        set "SDL_VIDEODRIVER=dummy"
        .venv\Scripts\python.exe -c "import gui.app"
    ) else (
        .venv\Scripts\python.exe main.py
    )
) else (
    .venv\Scripts\python.exe main.py
)
if errorlevel 1 (
    echo FAIL: The game exited with an error.
    pause
    exit /b 1
)
exit /b 0

:create_venv
set "PYTHON_EXE="
py -3.13 -c "import sys; sys.exit(0 if sys.version_info >= (3,13) else 1)" >nul 2>&1
if not errorlevel 1 set "PYTHON_EXE=py -3.13"
if not defined PYTHON_EXE (
    py -3.14 -c "import sys; sys.exit(0 if sys.version_info >= (3,13) else 1)" >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=py -3.14"
)
if not defined PYTHON_EXE (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3,13) else 1)" >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=python"
)
if not defined PYTHON_EXE (
    echo Python 3.13 or newer was not found. Install it from https://www.python.org/downloads/ and try again.
    pause
    exit /b 1
)
echo Creating virtual environment...
!PYTHON_EXE! -m venv .venv
if errorlevel 1 (
    echo FAIL: Could not create the virtual environment.
    pause
    exit /b 1
)
exit /b 0

:install_if_needed
set "REQ_FILE=%~1"
set "HASH_FILE=%~2"
set "CURRENT_HASH="
for /f "usebackq delims=" %%H in (`.venv\Scripts\python.exe -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "%REQ_FILE%"`) do set "CURRENT_HASH=%%H"
if errorlevel 1 (
    echo FAIL: Could not calculate the requirements hash for %REQ_FILE%.
    pause
    exit /b 1
)
if not defined CURRENT_HASH (
    echo FAIL: Could not calculate the requirements hash for %REQ_FILE%.
    pause
    exit /b 1
)
set "SAVED_HASH="
if exist "%HASH_FILE%" set /p "SAVED_HASH="<"%HASH_FILE%"
if "!FORCE_INSTALL!"=="1" set "SAVED_HASH="
if /i "!CURRENT_HASH!"=="!SAVED_HASH!" exit /b 0

echo Installing dependencies from %REQ_FILE%. The first install, especially torch, can take several minutes.
.venv\Scripts\python.exe -m pip install -r "%REQ_FILE%"
if errorlevel 1 (
    echo FAIL: Dependency installation failed. Check your internet connection and Python/pip installation, then try again.
    pause
    exit /b 1
)
>"%HASH_FILE%" echo !CURRENT_HASH!
if errorlevel 1 (
    echo FAIL: Could not save the requirements hash.
    pause
    exit /b 1
)
exit /b 0
