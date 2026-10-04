# Codex prompt — M1-A: `backend/core/` package

> Tasks: X1-01, X1-02, X1-03, X1-04 · Branch: `feat/core-game-state` · One PR.
> Copy everything below the line into Codex.

---

You are implementing the `backend/core/` package of the "Chess AI Tournament" project (Python 3.14, `python-chess`).

## Read first
- `documents/CONTEXT.md` §3.1 (dependency rules), §4.3 (core API), §4.4 (end-of-game rules + implementation order), §4.5 (material), §6 (config API).
- The tests are the specification. They already exist — **do not modify any file under `another/tests/`**:
  - `another/tests/core/test_types.py`
  - `another/tests/core/test_game_state.py`
  - `another/tests/core/test_material.py`
  - `another/tests/core/test_config.py`

## Create exactly these files
1. `backend/core/types.py`: `Termination` (StrEnum, values exactly as in the tests), `IllegalMoveError(ValueError)`, `GameOverError(RuntimeError)`, frozen dataclasses `GameResult` (with `score_for`) and `MoveRecord`.
2. `backend/core/game_state.py`: `GameState(fen=None, max_plies=300, claim_draw=True)`.
   - Properties: `board` (returns `self._board.copy()`, keeping the move stack), `turn`, `fen`, `starting_fen`, `ply_count`.
   - Methods: `legal_moves() -> list[chess.Move]`, `push(move) -> str` (returns SAN computed before pushing), `is_over()`, `result() -> GameResult | None`, `to_pgn(headers) -> str`.
   - `push` raises `GameOverError` if the game is over and `IllegalMoveError` if the move is not legal. The state must be unchanged after an exception.
   - `result()` must check conditions in the exact order given in CONTEXT §4.4. **Do NOT use `board.outcome(claim_draw=True)`**; use `board.is_repetition(3)` and `board.halfmove_clock >= 100`.
   - No `undo`/`pop` methods. This is a product requirement and is tested.
   - `to_pgn`: use `chess.pgn.Game.from_board`, apply the given headers, and set the `Result` header to `1-0` / `0-1` / `1/2-1/2` / `*` from `result()`.
3. `backend/core/material.py`: `PIECE_VALUES`, `material_diff(board) -> int` (white − black), `eval_bar_value(board, scale=8.0) -> float` = `math.tanh(material_diff / scale)`.
4. `backend/core/config.py`: `DEFAULT_CONFIG_PATH`, `LOCAL_CONFIG_PATH` (resolved relative to the repo root: `Path(__file__).resolve().parents[1] / "config"`), `load_config(default_path=DEFAULT_CONFIG_PATH, local_path=LOCAL_CONFIG_PATH)`, `deep_merge(base, override)` (returns a new dict, never mutates the inputs), `save_local_config(updates, local_path=LOCAL_CONFIG_PATH)` (reads the existing local file, deep-merges, writes with `tomli_w`), `get_bot_config(config, bot_id)`. Read with `tomllib`, using UTF-8. `local_path=None` or a missing file means "defaults only".

## Constraints
- `backend/core/` may import only the standard library, `chess` and `tomli_w`. Never import `ai`, `tournament` or `gui` (enforced by `lint-imports`).
- Full type hints and a short docstring per public class/function. Keep it simple; no extra features.
- Line length 100. Must pass `ruff check .` and `ruff format --check .`.
- Do not touch files outside `backend/core/`.

## Acceptance criteria (all must pass)
```bash
pytest another/tests/core -q                 # all tests pass, none skipped
pytest --cov -q                      # coverage of backend/core/ >= 80%
ruff check . && ruff format --check .
lint-imports                         # 3 contracts KEPT
```
