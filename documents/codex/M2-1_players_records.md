# Codex prompt — M2-1: `backend/tournament/players.py` + `backend/tournament/records.py`

> Wave 2 (needs M1-A merged) · Branch: `feat/tournament-records` · One PR.

---

You are implementing part of the `backend/tournament/` package of the "Chess AI Tournament" project (Python 3.14, `python-chess`).

## Read first
- `documents/CONTEXT.md` §4.6, the `players.py` and `records.py` code blocks.
- Spec tests (**do not modify anything under `another/tests/`**): `another/tests/tournament/test_players.py`. `records.py` is exercised by later waves; implement it exactly as specified.

## Create exactly these files
1. `backend/tournament/players.py`
   - `HUMAN_ID = "human"`, `class MatchAborted(Exception)`, `Player` as a `typing.Protocol` (`bot_id`, `display_name`, `select_move`, `reset`).
   - `HumanPlayer(display_name="Human")` with `bot_id = HUMAN_ID`. It is thread-safe and uses `queue.Queue`:
     - `submit_move(move)` puts the move on the queue.
     - `select_move(board)` blocks until it receives a move that is legal on `board`, discarding illegal ones.
     - `cancel()` makes a waiting (or the next) `select_move` raise `MatchAborted`; use a sentinel object on the queue.
     - `reset()` empties the queue and clears the cancelled state.
2. `backend/tournament/records.py`
   - `@dataclass class GameRecord` with exactly the fields, order and defaults in CONTEXT §4.6.
   - `to_json() -> dict`: plain JSON types only. `result` becomes `{"winner": "white" | "black" | None, "termination": <Termination.value>}`. `moves` becomes a list of dicts (`dataclasses.asdict`).
   - `from_json(d)` (classmethod): exact inverse, so `GameRecord.from_json(r.to_json()) == r`. Rebuild `GameResult`, `Termination` and `MoveRecord` from `core.types`.

## Constraints
- May import only stdlib, `chess` and `core`. Never import `ai.<bot>` packages or `gui` (`lint-imports` enforces this).
- Full type hints, short docstrings, line length 100, ruff clean. Touch only the two files above.

## Acceptance criteria
```bash
pytest another/tests/tournament/test_players.py -q    # all pass
pytest -q                                     # whole suite still green
ruff check . && ruff format --check . && lint-imports
```
