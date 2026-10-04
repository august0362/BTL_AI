# Codex prompt — M2-2: `backend/tournament/match_runner.py` + `backend/tournament/series.py`

> Wave 3 (needs M1-A and M2-1 merged) · Branch: `feat/tournament-match` · One PR. Runs in parallel with M2-3.

---

You are implementing the game orchestration of the "Chess AI Tournament" project (Python 3.14, `python-chess`).

## Read first
- `documents/CONTEXT.md` §4.4 (end-of-game rules), §4.6. Follow the numbered list "Hành vi `play()`" step by step.
- Spec tests (**do not modify anything under `another/tests/`**): `another/tests/tournament/test_match_runner.py`, `another/tests/tournament/test_series.py`. Test doubles are in `another/tests/tournament/fakes.py`.

## Create exactly these files
1. `backend/tournament/match_runner.py`
   - `generate_random_opening(plies, rng) -> list[str]`: random legal UCI moves from the standard position. Pick from the moves sorted by UCI string, so a given seed always gives the same result. Retry (max 100 attempts, then `RuntimeError`) if the position becomes game-over. `plies <= 0` returns `[]`.
   - `MatchRunner` with the exact constructor in CONTEXT §4.6.
     - `play()` uses `core.game_state.GameState` and `core.material.eval_bar_value`.
     - Use `threading.Event` for stop and pause. `pause()` blocks before the next move; `request_stop()` also releases a paused runner and calls `cancel()` on any player that has it.
     - Never let a player's exception escape `play()`. Bot exceptions and illegal moves produce an ABORTED record with `error` set to `"<bot_id>: <description>"`. `MatchAborted` and stop requests produce ABORTED with `error=None`.
     - `game_id = uuid.uuid4().hex`, `started_at = datetime.now(UTC).isoformat()`.
     - Fill `pgn` via `GameState.to_pgn({"White": white.display_name, "Black": black.display_name, "Date": "YYYY.MM.DD"})`.
2. `backend/tournament/series.py`
   - `series_colors`, `SeriesResult` and `SeriesRunner` as in CONTEXT §4.6.
   - Generate the random opening once and pass it as `opening_moves` to every game. Always play all games unless one is aborted, which stops the series with `aborted=True, winner=None`.
   - `n_games` not in `{1, 3}` raises `ValueError`.
   - Call `on_game_end(record)` after each game, including an aborted one.
   - `request_stop`/`pause`/`resume` are forwarded to the current `MatchRunner`.

## Constraints
- May import only stdlib, `chess`, `core` and `tournament`. **Never** import `ai.<bot>` packages or `gui`.
- Full type hints, short docstrings, line length 100, ruff clean. Touch only the two files above.

## Acceptance criteria
```bash
pytest another/tests/tournament -q                    # match_runner + series tests pass (ranking/history may skip)
pytest --cov -q                               # suite green, coverage core+tournament >= 80%
ruff check . && ruff format --check . && lint-imports
```
