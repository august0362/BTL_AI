# Codex prompt — OPS-2 fix round 1

> Follows OPS-2 (merged). Branch: `fix/run-bat-hash`.

---

QA ran `run.bat` from PowerShell 7 (the VS Code terminal) and got:
`Get-FileHash : The term 'Get-FileHash' is not recognized` → `FAIL: Could not calculate the requirements hash for environments/requirements.txt.`
The child `powershell` inherits the PowerShell 7 `PSModulePath` and cannot load the module, so the script is fragile depending on where it is launched from.

Fix in `run.bat` and in `another/scripts/test.bat` if it uses the same approach:
- Compute the hash with the venv's Python, which always exists at that point:
  `.venv\Scripts\python.exe -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" environments/requirements.txt`
  Do not call `powershell` at all.
- Keep everything else unchanged.

Verify by running `run.bat` from **both** `cmd.exe` and `pwsh`, with `BTL_RUN_SMOKE=1`, as far as the sandbox allows. If no network is available, verify at least that the hash step succeeds and that the "already installed" path (hash file present and matching) skips pip.

Follow `AGENTS.md`. Touch only `run.bat` and `another/scripts/test.bat`.
