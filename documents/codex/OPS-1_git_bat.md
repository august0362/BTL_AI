# Codex prompt — OPS-1: push / pull .bat scripts

> Runs in parallel with M4-A. Branch: `chore/git-scripts`.

---

Create Windows batch scripts for the team's Git workflow. Read `documents/CONTEXT.md` §8 (Git rules: **no direct push to `main`**, work on branches named `feat/<module>-<desc>` / `fix/...`, merge via Pull Request).
Remote: `https://github.com/august0362/BTL_AI.git`, default branch `main`.

## Deliverables (repo root `another/scripts/`)
1. `another/scripts/pull.bat`: update the local copy.
   - If not a git repo, print how to clone and exit.
   - Otherwise `git fetch origin`. On `main`: `git pull --ff-only origin main`. On a feature branch: pull that branch (if it exists on the remote), then **merge `origin/main` into it**, reporting conflicts clearly and stopping.
   - Refuse to run with uncommitted changes, and say what to do (commit or stash).
2. `another/scripts/push.bat`: save and publish work.
   - **First run** (no `.git`): `git init -b main`, add the remote, make an initial commit, and push `main`. Print that this is the only allowed direct push, and that the admin should enable the Rulesets afterwards (CONTEXT §8.2).
   - **Normal run on `main`:** ask for a short branch description, create `feat/<desc>` and switch to it. Never push to `main`.
   - Show `git status`, ask for a commit message (non-empty), `git add -A`, commit, then `git push -u origin <branch>`.
   - Afterwards print the PR link `https://github.com/august0362/BTL_AI/compare/main...<branch>?expand=1`. If `gh` is installed, offer `gh pr create --fill --base main`.
   - Before committing, run `.venv\Scripts\python -m pytest -q` if the venv exists. On failure, ask whether to continue (default: no).
3. `.gitattributes`: add `*.bat text eol=crlf` (batch files need CRLF; the repo default is LF).
4. Add a short "Git: push / pull" section to `README.md` explaining both scripts.

## Rules
- Keep messages ASCII (Vietnamese **without diacritics** is fine), because cmd.exe mangles UTF-8 in .bat files. Save the .bat files with **CRLF** line endings.
- Use `setlocal EnableDelayedExpansion`, check `errorlevel` after every git command, and exit non-zero on failure.
- Allow overriding the remote URL with the env var `BTL_REMOTE` (for testing).
- **Test both scripts yourself** in a temporary folder **inside this workspace** (e.g. `.pytest-tmp/gitlab/`). Use a local bare repo as the remote via `BTL_REMOTE`, and cover the first run, the normal run (branch creation) and the pull with a merge from main. Do not touch the real GitHub remote. Delete the temp folder afterwards, and report what you tested.
- Follow `AGENTS.md`. Touch only `another/scripts/`, `.gitattributes`, `README.md`.
