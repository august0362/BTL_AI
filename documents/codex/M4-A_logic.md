# Codex prompt — M4-A: M4 logic modules + their tests

> Wave 6 · Branch: `feat/m4-logic` · Runs in parallel with OPS-1.

---

Implement the M4 logic described in `documents/CONTEXT.md` §5.11 ("Module logic mới"), **and write the tests for it yourself**.

## Deliverables
1. `frontend/gui/replay_model.py` (`ReplayModel`, no pygame) + `another/tests/gui/test_replay_model.py`.
2. `frontend/gui/sound.py` (`SOUND_EVENTS`, `sound_for_move`, `SoundManager` that never raises) + `another/tests/gui/test_sound.py`. Test with `SDL_AUDIODRIVER=dummy`, and also cover a missing sounds dir and disabled mode.
3. `frontend/gui/leaderboard_view.py` (`LeaderboardRow`, `leaderboard_rows`, no pygame) + `another/tests/gui/test_leaderboard_view.py`.
4. `GameController.set_bot_move_delay(ms)` in `frontend/gui/controller.py`. It takes effect immediately, even during an ongoing wait. Add tests to `another/tests/gui/test_controller.py`, appending only and keeping existing tests unchanged. Example: start with a 10 s delay, call `set_bot_move_delay(0)`, and the game must finish within a few seconds.
5. `another/tools/make_sounds.py`: generate `frontend/gui/assets/sounds/{move,capture,check,game_end}.wav` (short sine tones, stdlib `wave` + `math`, each < 50 KB). Run it, keep the WAVs, delete `frontend/gui/assets/sounds/.gitkeep`, and add a line to `frontend/gui/assets/CREDITS.md` (self-generated, CC0).

## Test requirements
- Cover every rule written in §5.11 for these modules: clamping, auto-pause at the end, `play()` at the end restarting from the start, check beating capture, en passant counting as a capture, and rank order following `ranking.table()`.
- Do not modify existing tests except appending to `test_controller.py`.

## Done
Follow `AGENTS.md`. `pytest -q --basetemp=.pytest-tmp` (run controller tests 3× to check for flakes), `ruff check .`, `ruff format --check .` and `lint-imports` must all be green.
