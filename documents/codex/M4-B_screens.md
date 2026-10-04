# Codex prompt — M4-B: M4 screens + App extensions + smoke tests

> Wave 7 (needs M4-A merged) · Branch: `feat/m4-screens`.

---

Implement the M4 screens and App extensions described in `documents/CONTEXT.md` §5.11 ("App mở rộng" and "Màn hình"), **and write the tests yourself**.

## Deliverables
- App API additions exactly as listed in §5.11 (`local_config_path`, `start_bot_game`, `open_replay`, `replay_model`, `ranking`, `history`, `sound_enabled`, `set_sound_enabled`, `set_language`, `set_replay_delay`, `reset_ranking`, new `goto` names).
- New screens under `frontend/gui/screens/`: `setup_bots.py`, `history.py`, `replay.py`, `leaderboard.py`, `settings.py`. Extend `game.py` with the bot-vs-bot controls, the series score, the speaker icon and sound playback. Replace the menu's "coming soon" buttons with the real screens.
- Reuse `ReplayModel`, `SoundManager`/`sound_for_move`, `leaderboard_rows` and `GameController.set_bot_move_delay`. Do not re-implement them.
- New UI strings go in **both** `frontend/gui/locales/vi.toml` and `en.toml` (UTF-8 with LF, real Vietnamese diacritics).
- `another/tests/gui/test_app_m4_smoke.py` (headless, `SDL_VIDEODRIVER=dummy`; App gets `data_dir` and `local_config_path` under `tmp_path`). It must at least cover:
  - every screen renders, in `vi` and `en`;
  - `start_bot_game("random", "random", 3)` with `bot_move_delay_ms=0` and small `max_plies` finishes; history holds 3 games; ranking is unchanged (debug bot);
  - `open_replay` on a saved game, then `last()`/`first()`, renders;
  - `set_language`, `set_sound_enabled` and `set_replay_delay` persist to the tmp local TOML;
  - `reset_ranking()` clears a recorded non-debug game;
  - leaving a bot game via `goto("menu")` stops the controller.
- Extend `another/tools/render_previews.py` to also render the new screens (both languages) into `.preview/`, run it, and list the PNG paths in your final message.

## Done
Follow `AGENTS.md`. Existing tests must stay green and unmodified. `pytest -q --basetemp=.pytest-tmp`, `ruff check .`, `ruff format --check .` and `lint-imports` must all be green. No text may overflow or overlap in the previews.
