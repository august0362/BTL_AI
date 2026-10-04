@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0\..\.."
if errorlevel 1 (
    echo FAIL: Could not change to the project folder.
    pause
    exit /b 1
)
set "PYTHONPATH=%CD%\backend;%CD%\frontend;%CD%\another;%PYTHONPATH%"

if not exist ".venv\Scripts\python.exe" (
    echo FAIL: Virtual environment not found. Run run.bat first to create it.
    pause
    exit /b 1
)

set "DEV_HASH="
for /f "usebackq delims=" %%H in (`.venv\Scripts\python.exe -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" environments\requirements-dev.txt`) do set "DEV_HASH=%%H"
if errorlevel 1 set "DEV_HASH="
set "SAVED_HASH="
if exist ".venv\.dev_req_hash" set /p "SAVED_HASH="<".venv\.dev_req_hash"
if not defined DEV_HASH (
    echo FAIL: Could not calculate the requirements hash.
    set "FAILED=1"
) else if /i not "!DEV_HASH!"=="!SAVED_HASH!" (
    echo Installing development dependencies. The first install, especially torch, can take several minutes.
    .venv\Scripts\python.exe -m pip install -r environments\requirements-dev.txt
    if errorlevel 1 (
        echo FAIL: Dependency installation failed. Check your internet connection and Python/pip installation.
        set "FAILED=1"
    ) else (
        >".venv\.dev_req_hash" echo !DEV_HASH!
        if errorlevel 1 (
            echo FAIL: Could not save the requirements hash.
            set "FAILED=1"
        ) else echo PASS: Install development dependencies
    )
) else echo PASS: Development dependencies are up to date

if not defined FAILED (
    echo Running pytest -q...
    .venv\Scripts\python.exe -m pytest -q
    if errorlevel 1 (echo FAIL: pytest -q & set "FAILED=1") else echo PASS: pytest -q

    echo Running ruff check ....
    .venv\Scripts\python.exe -m ruff check .
    if errorlevel 1 (echo FAIL: ruff check . & set "FAILED=1") else echo PASS: ruff check .

    echo Running ruff format --check ....
    .venv\Scripts\python.exe -m ruff format --check .
    if errorlevel 1 (echo FAIL: ruff format --check . & set "FAILED=1") else echo PASS: ruff format --check .

    echo Running lint-imports...
    .venv\Scripts\lint-imports
    if errorlevel 1 (echo FAIL: lint-imports & set "FAILED=1") else echo PASS: lint-imports
)

if defined FAILED (
    echo One or more steps failed.
    pause
    exit /b 1
)
echo All checks passed.
pause
exit /b 0
