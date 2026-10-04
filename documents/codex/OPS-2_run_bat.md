# Codex prompt — OPS-2: one-click run script

> Branch: `chore/run-script`.

---

Create `run.bat` at the repo root so that anyone on Windows can double-click it to set up and launch the game. Also create `another/scripts/test.bat`.

## `run.bat`
1. `cd /d "%~dp0"`.
2. If `.venv\Scripts\python.exe` is missing, create the venv:
   - Prefer `py -3.14`, then `py -3.13`, then `python`, checking that the version is >= 3.13.
   - If none is found, print a clear message with the python.org download link, `pause`, and exit 1.
3. Install dependencies only when needed. Store a hash of `environments/requirements.txt` in `.venv\.req_hash`. When it changes or is missing, run `python -m pip install -r environments/requirements.txt`. `torch` is large, so print a note that the first install can take several minutes.
   - If pip fails, print the error hint, `pause`, and exit 1.
4. Launch the game: `.venv\Scripts\python main.py`. If the game exits with a non-zero code, keep the window open (`pause`) so the error is readable.
5. Options:
   - `run.bat --test`: run `pytest -q` instead of the game (installing `environments/requirements-dev.txt` if needed).
   - `run.bat --reinstall`: force the reinstall.

## `another/scripts/test.bat`
Runs the full gate locally, the same as CI: `pytest -q`, `ruff check .`, `ruff format --check .`, `lint-imports` (installing `environments/requirements-dev.txt` if needed). Print PASS/FAIL per step, exit non-zero if any step fails, and `pause` at the end when double-clicked.

## Rules
- ASCII-only messages (Vietnamese without diacritics is fine) and **CRLF** line endings (`.gitattributes` already forces `*.bat` to CRLF).
- `setlocal EnableDelayedExpansion`. Check `errorlevel` after each step.
- Add a short "Chạy nhanh" section at the top of `README.md` (Vietnamese) with "double-click `run.bat`" and the two options.
- **Test it yourself** in this workspace without the GUI blocking: set `SDL_VIDEODRIVER=dummy` and use an env var `BTL_RUN_SMOKE=1` that makes `run.bat` run `python -c "import gui.app"` instead of opening the window. Also test `--test`. You may not be able to create a fresh venv in the sandbox; if so, say so.
- Follow `AGENTS.md`. Touch only `run.bat`, `another/scripts/test.bat`, `README.md`.
