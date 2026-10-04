# Codex prompt — M3-B: `frontend/gui/controller.py`

> Wave 4 · Branch: `feat/gui-controller` · One PR. Needs M2 merged (done).

---

You are implementing the bridge between the Pygame screens and the tournament engine in the "Chess AI Tournament" project (Python 3.14).

## Read first
- `documents/CONTEXT.md` §4.6 (MatchRunner/SeriesRunner), §5.9 (GameController — the exact spec).
- Spec tests (**do not modify anything under `another/tests/`**): `another/tests/gui/test_controller.py`. Test doubles are in `another/tests/tournament/fakes.py`.

## Create exactly this file
`frontend/gui/controller.py`:
- `ControllerSnapshot` (frozen dataclass) and `GameController`, as in §5.9.
- Run the game in one `threading.Thread(daemon=True)`. Use `MatchRunner` for `human_vs_bot` and `SeriesRunner` for `bot_vs_bot`.
  - Get `max_plies`, `claim_draw` and `random_opening_plies` from `config["game"]`, `scale` from `config["eval_bar"]` and `bot_move_delay_ms` from `config["ui"]`. Use `.get` with the defaults from `backend/config/default.toml`.
  - `human_vs_bot` with `n_games != 1` raises `ValueError`. Random openings only apply to `bot_vs_bot`.
- Protect all shared state with a `threading.Lock`. `snapshot()` returns copies, including `board.copy()`.
- Wrap any `tournament.players.HumanPlayer` in a small proxy that sets a "waiting" flag around `select_move`. It must forward `bot_id`, `display_name`, `reset` and `cancel`, and `submit_human_move` must reach the real `HumanPlayer`.
- The `on_move` callback updates the current board and move list. For `bot_vs_bot`, after a non-opening move, wait `bot_move_delay_ms` using `threading.Event.wait(timeout)` so that `stop()` interrupts it immediately.
- On each game end, call `history.save` and then `ranking.record_game` (if provided), and reset the per-game board and moves for the next game. Use the series `on_game_end` hook for bot vs bot; in human vs bot, handle it after `MatchRunner.play()` returns.
- `pause()` before `start()` must apply once the runner exists.
- Any exception in the worker thread must be caught. The controller then ends with `finished=True` and does not crash the GUI.

## Constraints
- Must **not** import `pygame`. May import stdlib, `chess`, `core`, `tournament`, `ai.registry`/`ai.base_bot`. Never import `ai.<bot>` packages directly.
- Follow `AGENTS.md`. Touch only `frontend/gui/controller.py`.

## Acceptance criteria
```bash
.venv\Scripts\python -m pytest another/tests/gui/test_controller.py -q --basetemp=.pytest-tmp   # all pass, run it 3 times: no flakes
.venv\Scripts\python -m pytest -q --basetemp=.pytest-tmp
.venv\Scripts\python -m ruff check . ; .venv\Scripts\python -m ruff format --check . ; .venv\Scripts\lint-imports
```
