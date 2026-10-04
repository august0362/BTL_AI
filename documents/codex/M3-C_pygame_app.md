# Codex prompt — M3-C: Pygame app (MVP screens)

> Wave 5 · Branch: `feat/gui-app-mvp` · One PR. Needs M3-B (`frontend/gui/controller.py`) merged.

---

You are building the Pygame (pygame-ce) GUI MVP of the "Chess AI Tournament" project (Python 3.14).

## Read first
- `documents/CONTEXT.md` §5 (whole GUI spec), especially **§5.10** (App API and MVP scope), §5.8 (logic modules you must reuse), §5.9 (GameController).
- Spec tests (**do not modify anything under `another/tests/`**): `another/tests/gui/test_app_smoke.py` (runs headless with `SDL_VIDEODRIVER=dummy`).
- Reuse, do not re-implement: `gui.scaling.Viewport`, `gui.board_geometry`, `gui.move_input.MoveInput`, `gui.game_info`, `gui.i18n.Translator`, `gui.controller.GameController`, `ai.registry`, `tournament.ranking.Ranking`, `tournament.history.History`, `core.config`.
- UI strings: `frontend/gui/locales/vi.toml` / `en.toml`. If you need a new key, add it to **both** files (CI checks key parity).
- Piece images: `frontend/gui/assets/pieces/rhosgfx/wK.png … bP.png` (256 px).

## Create
- `frontend/gui/app.py`: the `App` class with exactly the public API in §5.10, plus `main()` used by the repo-root `main.py`.
- `frontend/gui/assets_loader.py`: load and scale piece images (cached per size) and pick a font.
- `frontend/gui/widgets/`: `board_view.py` (board, pieces, highlights, flip, legal-target dots, last move, check), `panel.py` (collapsible sections), `eval_bar.py`, `move_list.py`, `button.py`, `promotion_dialog.py`.
- `frontend/gui/screens/`: `base.py` (Screen interface: `handle_click(x, y)`, `update()`, `draw(canvas)`, `on_exit()`), `menu.py`, `setup_human.py`, `game.py`.
- Update `main.py` to call `gui.app.main()`.
- Menu buttons for M4 screens (Bot vs Bot, History, Leaderboard, Settings) may show a "coming soon" state; they must not crash.

## Behaviour notes
- One logical 960×640 canvas. Each frame: draw the current screen onto the canvas, scale it with `Viewport` (smoothscale) onto the window, and fill the letterbox black. Handle `VIDEORESIZE`.
- The game screen accepts board clicks only when `controller.snapshot().waiting_for_human` is True.
- Leaving the game screen (`goto("menu")`, "Back to menu", window close) calls `controller.stop()`.
- Never block the main loop: the bot runs in the controller thread, and the screen reads `snapshot()` each frame.

## Constraints
- `frontend/gui/scaling.py`, `board_geometry.py`, `move_input.py`, `game_info.py`, `i18n.py`, `controller.py` already exist and are tested. Do not change their behaviour.
- Never import `ai.<bot>` packages; use `ai.registry`. Follow `AGENTS.md`. Touch only the files listed above, plus locale files if you need new keys.

## Acceptance criteria
```bash
.venv\Scripts\python -m pytest another/tests/gui -q --basetemp=.pytest-tmp      # all pass, including test_app_smoke.py
.venv\Scripts\python -m pytest -q --basetemp=.pytest-tmp
.venv\Scripts\python -m ruff check . ; .venv\Scripts\python -m ruff format --check . ; .venv\Scripts\lint-imports
```
Also run `SDL_VIDEODRIVER=dummy` and render each screen once to a PNG under `.pytest-tmp/` (do not commit it) so the architect can inspect the layout. Mention the PNG paths in your final message.
