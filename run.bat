@echo off
rem Double-click to play. First run: Python (portable if missing) + libraries + AI models.
rem Later runs: only checks, downloads a model again only when a newer release exists.
rem   run.bat --test       install dev tools and run pytest
rem   run.bat --reinstall  reinstall libraries
setlocal EnableDelayedExpansion
cd /d "%~dp0" || goto :fail
title BTL_AI Chess
set "PYTHONPATH=%CD%\backend;%CD%\frontend;%CD%\another"
set "PYTHONIOENCODING=utf-8"
set "PY_URL=https://github.com/astral-sh/python-build-standalone/releases/download/20261110/cpython-3.13.18%%2B20261110-x86_64-pc-windows-msvc-install_only.tar.gz"
set "PY_SHA=7e93813bd362c6413f30788b248590e2f169df2d17dcac81aafbcc7a6eeb542c"
set "VPY=.venv\Scripts\python.exe"

set "FORCE_INSTALL=0"
set "RUN_TESTS=0"
for %%A in (%*) do (
    if /i "%%~A"=="--reinstall" set "FORCE_INSTALL=1"
    if /i "%%~A"=="--test" set "RUN_TESTS=1"
)

set "ARCH=%PROCESSOR_ARCHITECTURE%"
if defined PROCESSOR_ARCHITEW6432 set "ARCH=%PROCESSOR_ARCHITEW6432%"
if /i not "%ARCH%"=="AMD64" if /i not "%ARCH%"=="ARM64" (
    echo LOI: Can Windows 10/11 ban 64-bit. May nay la %ARCH%.
    goto :fail
)

echo [1/4] Kiem tra Python...
if exist "%VPY%" (
    "%VPY%" -c "" >nul 2>&1
    if errorlevel 1 (
        echo   Moi truong .venv bi hong, tao lai...
        rmdir /s /q .venv
    )
)
if not exist "%VPY%" call :create_venv || goto :fail

echo [2/4] Kiem tra thu vien...
call :install_if_needed environments\requirements.txt .venv\.req_hash || goto :fail

if "!RUN_TESTS!"=="1" (
    call :install_if_needed environments\requirements-dev.txt .venv\.dev_req_hash || goto :fail
    "%VPY%" -m pytest -q || goto :fail
    exit /b 0
)

"%VPY%" another\launcher.py || goto :fail
exit /b 0

:create_venv
set "BASE="
py -3.13 -c "" >nul 2>&1 && set "BASE=py -3.13"
if not defined BASE (
    python -c "import sys; sys.exit(sys.version_info[:2] != (3, 13))" >nul 2>&1 && set "BASE=python"
)
if not defined BASE (
    if not exist ".runtime\python\python.exe" call :get_python || exit /b 1
    set "BASE=.runtime\python\python.exe"
)
echo   Tao moi truong .venv bang !BASE!...
!BASE! -m venv .venv || exit /b 1
exit /b 0

:get_python
echo   Khong thay Python 3.13: tai Python portable (~48 MB, chi dung cho du an nay)...
if not exist .runtime mkdir .runtime
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ErrorActionPreference = 'Stop'; [Net.ServicePointManager]::SecurityProtocol = 'Tls12';" ^
    "$f = Join-Path (Get-Location) '.runtime\python.tar.gz';" ^
    "(New-Object Net.WebClient).DownloadFile($env:PY_URL, $f);" ^
    "$s = [IO.File]::OpenRead($f); $h = [Security.Cryptography.SHA256]::Create().ComputeHash($s); $s.Close();" ^
    "if ([BitConverter]::ToString($h).Replace('-', '') -ne $env:PY_SHA) { [IO.File]::Delete($f); throw 'SHA-256 khong khop' }"
if errorlevel 1 (
    echo LOI: Khong tai duoc Python. Kiem tra Internet roi chay lai.
    exit /b 1
)
tar -xzf .runtime\python.tar.gz -C .runtime || exit /b 1
del .runtime\python.tar.gz
exit /b 0

:install_if_needed
set "REQ_FILE=%~1"
set "HASH_FILE=%~2"
set "CURRENT_HASH="
for /f "usebackq delims=" %%H in (`%VPY% -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "%REQ_FILE%"`) do set "CURRENT_HASH=%%H"
if not defined CURRENT_HASH exit /b 1
set "SAVED_HASH="
if exist "%HASH_FILE%" set /p "SAVED_HASH="<"%HASH_FILE%"
if "!FORCE_INSTALL!"=="1" set "SAVED_HASH="
if /i "!CURRENT_HASH!"=="!SAVED_HASH!" exit /b 0
echo   Cai thu vien tu %REQ_FILE% (lan dau mat vai phut vi PyTorch)...
"%VPY%" -m pip install --disable-pip-version-check -r "%REQ_FILE%"
if errorlevel 1 (
    echo LOI: Cai thu vien that bai. Kiem tra Internet roi chay lai run.bat.
    exit /b 1
)
>"%HASH_FILE%" echo !CURRENT_HASH!
exit /b 0

:fail
echo.
echo Co loi xay ra - xem thong bao o tren. Chay lai run.bat sau khi khac phuc.
pause
exit /b 1
