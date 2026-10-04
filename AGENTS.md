# AGENTS.md — rules for Codex agents

Architecture, interface contracts and rules live in `documents/CONTEXT.md`. Read the sections your task references before coding.

## Hard rules
- **Never modify or delete existing tests** — they are the spec. If you believe one is wrong, stop and explain why in your final message.
- **Do add new tests** when your task asks for them (new test files, or new test functions appended to an existing file).
- Edit **only** the files listed in your task. Other agents work in parallel on other files.
- Respect module boundaries (`documents/CONTEXT.md` §3.1): bot packages never import each other; `backend/tournament/` and `frontend/gui/` load bots only via `ai.registry`.
- Do not commit, push or create branches unless the task says so.
- No new dependencies unless the task says so.

## Environment (Windows)
- Use the project virtualenv: `.venv\Scripts\python -m pytest`, `.venv\Scripts\python -m ruff`; run `lint-imports` through `another\scripts\test.bat` so the relocated packages are on `PYTHONPATH`.
- Target is **Python 3.13** (annotations are evaluated eagerly: a class referring to itself in annotations needs `from __future__ import annotations`).
- Format only your own files (`ruff format <files>`). `ruff format --check .` is fine.
- Write files as **UTF-8 with LF** (use apply_patch, not PowerShell `Set-Content`/`Out-File`, which corrupts Vietnamese text into `?`).
- The sandbox cannot write to the Windows temp dir: run pytest with `--basetemp=.pytest-tmp` (gitignored).

## Code style
- Full type hints, short docstrings on public classes and functions, line length 100.
- Keep it simple: implement exactly what the spec asks, with no extra features.

## Done means
`pytest -q`, `ruff check .`, `ruff format --check .` and `lint-imports` are all green. Your final message lists the files you changed, the test summary and any concerns.
