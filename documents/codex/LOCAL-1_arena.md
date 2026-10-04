# Codex prompt — LOCAL-1: personal round-robin arena (local only, never pushed)

> Runs in parallel with UI-3 and DOC-1. `another/local_tools/` is **gitignored** (CONTEXT §4.7, OI-3): it stays on the owner's machine.

---

Build a command-line round-robin arena for the owner to compare bot strength.

## Deliverables (all under `another/local_tools/`)
- `another/local_tools/__init__.py`
- `another/local_tools/arena.py`, run from PowerShell after `$env:PYTHONPATH = "backend;frontend;another"` as `python -m local_tools.arena [options]`:
  - Options:
    - `--bots` (default: every bot from `ai.registry.list_bots(include_debug=True)` that can be created; skip `BotUnavailableError` with a notice);
    - `--games-per-pair N` (default 4; colours alternate);
    - `--random-opening-plies` (default from config);
    - `--max-plies`;
    - `--seed`;
    - `--out DIR` (default `database/data/local_arena/`).
  - Use `tournament.match_runner.MatchRunner` (no GUI), with a fresh bot instance per game via `ai.registry.create_bot` and the bot config from `core.config`.
  - Show progress in the console: pair, game i/N, result, plies, seconds.
  - Write:
    - `games.csv` (one row per game: white, black, result, termination, plies, avg think time per side, opening);
    - `table.csv` + a printed table (bot, games, W/D/L, points, Elo);
    - PGNs into `pgn/`.
  - Elo uses a **separate** `tournament.ranking.Ranking(out/"elo.json", debug_ids=())`. It must never touch `database/data/ranking.json`. Random is allowed here.
  - Ctrl+C stops gracefully, keeping the results written so far.
- `another/local_tools/README.md` (Vietnamese): usage examples.
- `another/local_tools/test_arena.py` (pytest, kept inside `another/local_tools/` so it stays local): run the arena with `random` vs `random`, 2 games per pair, small `max_plies`, into `tmp_path`; assert the CSV columns and row counts, that `elo.json` is separate, and that `database/data/ranking.json` is untouched.

## Constraints
- Do not modify anything outside `another/local_tools/` (it may import `ai.registry`, `core`, `tournament`).
- Follow `AGENTS.md` code style; `ruff check local_tools` and `ruff format --check local_tools` must be clean (it is excluded from the repo-wide lint config, so pass the path explicitly).
- Run `pytest local_tools -q --basetemp=.pytest-tmp` and report the results.
