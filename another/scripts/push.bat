@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0\..\.."
if errorlevel 1 exit /b 1
set "PYTHONPATH=%CD%\backend;%CD%\frontend;%CD%\another;%PYTHONPATH%"
if not defined BTL_REMOTE set "BTL_REMOTE=https://github.com/august0362/BTL_AI.git"

git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 goto first_run

if defined BTL_REMOTE (
    git remote set-url origin "%BTL_REMOTE%"
    if errorlevel 1 exit /b 1
)

for /f "delims=" %%B in ('git branch --show-current') do set "BRANCH=%%B"
if errorlevel 1 exit /b 1
if /i "!BRANCH!"=="main" (
    set /p "DESC=Short branch description (use letters, numbers, and hyphens): "
    if not defined DESC (
        echo Branch description cannot be empty.
        exit /b 1
    )
    echo(!DESC!| findstr /r /c:"^[a-zA-Z0-9][a-zA-Z0-9-]*$" >nul
    if errorlevel 1 (
        echo Use only letters, numbers, and hyphens in the description.
        exit /b 1
    )
    git switch -c "feat/!DESC!"
    if errorlevel 1 exit /b 1
    set "BRANCH=feat/!DESC!"
)
if not defined BRANCH (
    echo Detached HEAD is not supported. Switch to a branch first.
    exit /b 1
)
if /i "!BRANCH!"=="main" (
    echo Refusing to push directly to main.
    exit /b 1
)

git status
if errorlevel 1 exit /b 1
call :run_tests
if errorlevel 1 exit /b 1
set /p "MESSAGE=Commit message: "
if not defined MESSAGE (
    echo Commit message cannot be empty.
    exit /b 1
)
git add -A
if errorlevel 1 exit /b 1
git commit -m "!MESSAGE!"
if errorlevel 1 exit /b 1
git push -u origin "!BRANCH!"
if errorlevel 1 exit /b 1
echo.
echo Create a pull request: https://github.com/august0362/BTL_AI/compare/main...!BRANCH!?expand=1
where gh >nul 2>&1
if not errorlevel 1 (
    set /p "CREATE_PR=Create the PR now with gh? [y/N]: "
    if /i "!CREATE_PR!"=="y" (
        gh pr create --fill --base main
        if errorlevel 1 exit /b 1
    )
)
exit /b 0

:first_run
echo Bootstrapping a new repository. This is the only allowed direct push to main.
echo Admin: enable the GitHub Rulesets afterwards, as described in documents/CONTEXT.md section 8.2.
git init -b main
if errorlevel 1 exit /b 1
git remote add origin "%BTL_REMOTE%"
if errorlevel 1 exit /b 1
git status
if errorlevel 1 exit /b 1
call :run_tests
if errorlevel 1 exit /b 1
set /p "MESSAGE=Initial commit message: "
if not defined MESSAGE set "MESSAGE=Initial commit"
git add -A
if errorlevel 1 exit /b 1
git commit -m "!MESSAGE!"
if errorlevel 1 exit /b 1
git push -u origin main
if errorlevel 1 exit /b 1
echo Bootstrap complete. This was the only allowed direct push to main.
echo Admin: enable the GitHub Rulesets afterwards, as described in documents/CONTEXT.md section 8.2.
exit /b 0

:run_tests
if not exist ".venv\Scripts\python.exe" exit /b 0
echo Running pytest before commit...
.venv\Scripts\python -m pytest -q
if not errorlevel 1 exit /b 0
set /p "CONTINUE=Tests failed. Continue anyway? [y/N]: "
if /i "!CONTINUE!"=="y" exit /b 0
echo Stopping because tests failed.
exit /b 1
