@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0\..\.."
if errorlevel 1 exit /b 1
set "PYTHONPATH=%CD%\backend;%CD%\frontend;%CD%\another;%PYTHONPATH%"

git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
    echo This folder is not a Git repository.
    echo Clone it with: git clone https://github.com/august0362/BTL_AI.git
    exit /b 1
)

git status --porcelain
if errorlevel 1 exit /b 1
for /f "delims=" %%A in ('git status --porcelain') do set "DIRTY=1"
if defined DIRTY (
    echo Uncommitted changes found. Commit or stash them before pulling.
    exit /b 1
)

if defined BTL_REMOTE (
    git remote set-url origin "%BTL_REMOTE%"
    if errorlevel 1 exit /b 1
)
if not defined BTL_REMOTE set "BTL_REMOTE=https://github.com/august0362/BTL_AI.git"
git fetch origin
if errorlevel 1 exit /b 1
for /f "delims=" %%B in ('git branch --show-current') do set "BRANCH=%%B"
if errorlevel 1 exit /b 1
if not defined BRANCH (
    echo Could not determine the current branch.
    exit /b 1
)
if /i "!BRANCH!"=="main" (
    git pull --ff-only origin main
    if errorlevel 1 exit /b 1
    exit /b 0
)

git ls-remote --exit-code --heads origin "!BRANCH!" >nul 2>&1
if errorlevel 2 (
    echo Branch !BRANCH! does not exist on origin; skipping its pull.
) else if errorlevel 1 (
    echo Could not check the remote branch. Check your connection and remote configuration.
    exit /b 1
) else (
    git pull --ff-only origin "!BRANCH!"
    if errorlevel 1 exit /b 1
)

git merge origin/main
if errorlevel 1 (
    echo Merge stopped, possibly due to conflicts. Resolve conflicts, then commit the merge.
    echo To abandon the merge, run: git merge --abort
    exit /b 1
)
exit /b 0
