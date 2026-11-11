@echo off
setlocal DisableDelayedExpansion
set "BTL_STOP_ROOT=%~dp0"

rem Match executable paths so other projects using Python are left running.
powershell.exe -NoLogo -NoProfile -NonInteractive -Command ^
    "$ErrorActionPreference = 'Stop';" ^
    "try {" ^
    "    $root = [IO.Path]::GetFullPath($env:BTL_STOP_ROOT);" ^
    "    $targets = @(Get-CimInstance Win32_Process | Where-Object {" ^
    "        $_.ExecutablePath -and $_.ExecutablePath.StartsWith(" ^
    "            $root, [StringComparison]::OrdinalIgnoreCase)" ^
    "    });" ^
    "    if ($targets.Count -eq 0) {" ^
    "        Write-Host 'No running project processes found.';" ^
    "        exit 0;" ^
    "    }" ^
    "    $failed = $false;" ^
    "    foreach ($target in $targets) {" ^
    "        if (-not (Get-Process -Id $target.ProcessId -ErrorAction SilentlyContinue)) {" ^
    "            continue;" ^
    "        }" ^
    "        & $env:SystemRoot\System32\taskkill.exe /PID $target.ProcessId /T /F;" ^
    "        if ($LASTEXITCODE -ne 0 -and (Get-Process -Id $target.ProcessId -ErrorAction SilentlyContinue)) {" ^
    "            $failed = $true;" ^
    "        }" ^
    "    }" ^
    "    if ($failed) { throw 'Some project processes could not be stopped.'; }" ^
    "    Write-Host 'Stopped all project processes and their child processes.';" ^
    "} catch {" ^
    "    Write-Host ('FAIL: ' + $_.Exception.Message);" ^
    "    exit 1;" ^
    "}"
if errorlevel 1 (
    echo FAIL: Could not stop the program. See the error above.
    pause
    exit /b 1
)
exit /b 0
