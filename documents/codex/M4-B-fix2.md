# Codex prompt — M4-B fix round 2

> Follows M4-B-fix1 (merged). Branch: `fix/m4-topbar-tests`.

---

1. **Overlapping buttons in the game screen top bar (bot vs bot):** the "Speed" button covers the "Pause" button, so only "Tạm" is visible. Lay out the speaker, pause and speed buttons in the 320 px panel so they never overlap and every label fits, in both `vi` and `en`. Shrink the font or widths, or use two rows if needed.
2. **Add the missing tests** (AGENTS.md now allows adding tests; never modify existing ones). Append to `another/tests/gui/test_app_m4_smoke.py`:
   - History scrolling: save 12 fake `GameRecord`s to `app.history`, `goto("history")`, scroll down with `app.scroll_logical`, click the last visible row, and assert that `app.replay_model` is not None and that its game is one of the older records.
   - A layout guard: in the bot-vs-bot game screen, the rects of the speaker, pause and speed buttons do not intersect each other, and each lies inside the canvas. Expose the rects through attributes the test can read.
3. Run `another/tools/render_previews.py` and list the PNGs.

## Done
Follow `AGENTS.md`. Touch only `frontend/gui/screens/*.py`, `frontend/gui/widgets/*.py`, `another/tests/gui/test_app_m4_smoke.py`. `pytest -q --basetemp=.pytest-tmp`, `ruff check .`, `ruff format --check .` and `lint-imports` must all be green.
