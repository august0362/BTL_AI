# Codex prompt — M3-A: pure-logic GUI modules

> Wave 1 (no dependencies) · Branch: `feat/gui-logic` · One PR. Runs in parallel with M1-A / M1-B.

---

You are implementing the display-independent logic of the Pygame GUI for the "Chess AI Tournament" project (Python 3.14, `python-chess`).

## Read first
- `documents/CONTEXT.md` §5 (GUI spec), especially **§5.8**, which has the exact signatures and click rules.
- Spec tests (**do not modify anything under `another/tests/`**):
  `another/tests/gui/test_scaling.py`, `another/tests/gui/test_board_geometry.py`, `another/tests/gui/test_move_input.py`,
  `another/tests/gui/test_game_info.py`, `another/tests/gui/test_i18n_translator.py`, `another/tests/architecture/test_i18n.py`.
- UI strings already exist in `frontend/gui/locales/vi.toml` and `frontend/gui/locales/en.toml`. Do not rename the keys.

## Create exactly these files
1. `frontend/gui/scaling.py`: `LOGICAL_SIZE`, frozen dataclass `Viewport` with `fit`, `to_logical`, `to_window`. Use a half-open canvas area: a point at `offset_x + width` is outside.
2. `frontend/gui/board_geometry.py`: `BOARD_SIZE = 640`, `SQUARE_SIZE = 80`, `square_at`, `square_origin`. Check bounds before flooring, so negative fractions return `None`.
3. `frontend/gui/move_input.py`: `InputResult` (frozen dataclass) and `MoveInput`, following the click rules in §5.8 exactly.
4. `frontend/gui/game_info.py`: `captured_pieces`, `think_time_summary`. `think_time_summary` accepts any objects with `ply`, `think_time_s` and `is_random_opening`.
5. `frontend/gui/i18n.py`: `SUPPORTED_LANGUAGES`, `LOCALES_DIR`, `Translator`.
   - Load TOML with `tomllib` and flatten nested tables into dotted keys.
   - Format parameters with `str.format_map` and a dict subclass whose `__missing__` returns `"{" + key + "}"`.

## Constraints
- These 5 modules must **not** import `pygame` (they are tested headless).
- They may import only stdlib, `chess`, and each other. Never import `ai.<bot>` packages.
- Full type hints, short docstrings, line length 100, ruff clean. Touch only the five files above.

## Acceptance criteria
```bash
pytest another/tests/gui another/tests/architecture -q        # all gui tests pass
pytest -q
ruff check . && ruff format --check . && lint-imports
```
