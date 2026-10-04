# Codex prompt — M4-B fix round 1

> Follows M4-B (merged). Branch: `fix/m4-history-speaker`.

---

QA found two bugs in the M4 screens. Fix both and add tests for them.

1. **History shows only 7 games** (`frontend/gui/screens/history.py` slices `self.records[:7]`), so up to 13 of the 20 stored games can never be opened or exported.
   - Make the list scrollable: handle `pygame.MOUSEWHEEL` and add small ▲/▼ buttons drawn with `pygame.draw.polygon`.
   - App currently forwards only left clicks to screens. Add an optional `handle_scroll(dy: int)` to the Screen interface (default no-op), and add `App.scroll_logical(dy)` so tests can inject it.
   - Add a test in `another/tests/gui/test_app_m4_smoke.py`. Save 12 fake records to history, open the history screen, scroll down, click the last visible row, and assert that `open_replay` was reached for one of the older games (`app.replay_model` is not None and refers to that game).
2. **Speaker button shows a tofu box**: the label starts with "♫", which the font lacks. Draw a small speaker icon with `pygame.draw` shapes (and a slash or "x" when muted) instead of a text glyph. Keep the translated label "Bật"/"Tắt" next to it. Then check every other screen for non-ASCII symbol glyphs used as icons (▲▼▶◀♫✓✕ etc.) and replace them the same way. Vietnamese letters are fine.

Then run `another/tools/render_previews.py` (both languages) and list the PNGs.

## Done
Follow `AGENTS.md`. Touch only `frontend/gui/app.py`, `frontend/gui/screens/*.py`, `frontend/gui/widgets/*.py`, `another/tests/gui/test_app_m4_smoke.py`. `pytest -q --basetemp=.pytest-tmp`, `ruff check .`, `ruff format --check .` and `lint-imports` must all be green.
