# Codex prompt — UI-4: speed button works after the game ends + bot speed in Settings

---

Bug in `frontend/gui/screens/game.py` (bot vs bot): at "Tốc độ: 0" the series finishes almost
instantly. Once `snapshot.finished` is true, `GameScreen.handle_click` only handles
`result_again` / `result_menu` and then `return`s, so the top bar (speed, sound, pause) and the
panel stop responding. The player cannot switch the speed back away from 0.

## What to change
1. In `GameScreen.handle_click`, when `snapshot.finished`, still handle these clicks (after
   `result_again` / `result_menu`):
   - the speed button (bot games): cycles `0 → 150 → 300 → 800 → 0` as today;
   - the sound button;
   - the bottom "Về menu" button (`menu_button`);
   - the panel section headers (expand/collapse).
   The pause button and "Dừng ván" do nothing once the game is finished.
2. Persist the speed: replace the direct `self.app.config[...]` write with a new
   `App.set_bot_move_delay(ms: int)` in `frontend/gui/app.py` that calls
   `self._save_ui("bot_move_delay_ms", ms)` and `self.controller.set_bot_move_delay(ms)`.
   The chosen speed therefore carries over to "Chơi lại" and to the next bot game.
3. Move the speed-cycling logic into a small helper in `GameScreen` so the in-game and
   finished-game paths share it.
4. **Bot speed in Settings** (`frontend/gui/screens/settings.py`): add a button
   `self.bot_speed` labelled `"{settings.bot_speed}: {delay} ms"` that reads
   `config["ui"]["bot_move_delay_ms"]` (default 300) and, on click, cycles
   `0 → 150 → 300 → 800 → 0` through `App.set_bot_move_delay`. Put the cycle order in one
   shared place (e.g. a `BOT_DELAY_STEPS` tuple plus a `next_bot_delay(current)` function in
   `frontend/gui/app.py`) and use it from both `GameScreen` and `SettingsScreen`; an unknown
   value goes to `0`.
   - Layout: bottom row at `y=518`, height 38, left to right: sound `(80, 518, 180, 38)`,
     replay speed `(270, 518, 260, 38)`, bot speed `(540, 518, 170, 38)`, back
     `(720, 518, 160, 38)`. Labels must fit inside their buttons in both languages
     (shrink the font to 12 if needed, no overlap or clipping).
   - Add the hand cursor on hover, like the other buttons.
   - Locale keys: `settings.bot_speed` = `"Tốc độ bot"` (vi) / `"Bot speed"` (en).
   - `App.set_bot_move_delay` must work when no game is running (the controller may be idle
     or `None` — guard accordingly).

## Tests you add (new tests only; keep existing ones unchanged)
`another/tests/gui/test_speed_button.py` (headless, same fixtures as the other GUI tests):
- Bot game finished with delay 0: clicking the centre of `speed_button_rect` changes the delay
  to 150, updates the label, and calls `controller.set_bot_move_delay(150)`.
- Clicking it again while finished keeps cycling (150 → 300).
- Sound button still toggles while finished.
- `App.set_bot_move_delay` writes `bot_move_delay_ms` to the local config (use a tmp path).
- While finished, clicking the pause button does not call `pause()` / `resume()`.
- Settings: clicking `bot_speed` cycles 300 → 800 → 0 → 150, updates the label and persists
  `bot_move_delay_ms`; it works with no game started.
- Settings: the four bottom buttons do not overlap, and `next_bot_delay(999) == 0`.
- A new `GameScreen` created after changing the speed in Settings shows the new value.

Run `another/tools/render_previews.py` for the Settings screen (vi and en, 1440×960) and list
the PNGs.

## Done
Follow `AGENTS.md`. `pytest -q --basetemp=.pytest-tmp`, `ruff check .`, `ruff format --check .`
and `lint-imports` must all be green. Touch only `frontend/gui/screens/game.py`,
`frontend/gui/screens/settings.py`, `frontend/gui/app.py`, `frontend/gui/locales/vi.toml`,
`frontend/gui/locales/en.toml` and the new test file.
