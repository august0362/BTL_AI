# Codex prompt — UI-1: crisp rendering + themes + design pass

> Branch: `feat/ui-v2`. Product-code change across `frontend/gui/`.

---

Implement `documents/CONTEXT.md` **§5.12 (Giao diện v2)** completely, and write the tests yourself.

## Context
The owner reported that the UI is **blurry** (Windows DPI scaling at ~150%, combined with our own smoothscale upscaling of a 960×640 canvas) and **ugly**. The app name must be **"Chess"**.

## Deliverables
1. **Crisp rendering:**
   - Set DPI awareness before `pygame.init()` (Windows only, guarded).
   - Use a DPI-based default window size.
   - Add a new `frontend/gui/render.py` drawing layer. It takes logical coordinates and draws at physical resolution: scaled rects, line widths, radii, fonts at their real pixel size (cached), and piece images scaled from 256 px. Refactor all screens and widgets to draw through it.
   - Remove the "draw at 960×640, then smoothscale up" path.
   - Expose `app.render_scale` and `app.canvas_size`.
2. **Themes:**
   - `frontend/gui/theme.py` with the 6 themes and all role tokens from §5.12. Start from the suggested `dark_winter` values, and derive the others from their palettes by the stated rules.
   - Load the theme from `config["ui"]["theme"]`, and add `App.set_theme(theme_id)` (applies immediately and persists to the local config).
   - Remove every hard-coded colour from `frontend/gui/screens` and `frontend/gui/widgets`, including the old `config["board"]` lookups in `game.py` and `replay.py`. Board colours come from the theme.
3. **Design pass on every screen**, following §5.12:
   - 8 px grid, type scale, radius 10;
   - one primary button per screen;
   - button states (hover, pressed, disabled, selected) plus a hand cursor over buttons via `handle_hover`;
   - `attention` used only for the last move and "your turn"; `danger` used only for check, Reset and Stop;
   - menu with a "Chess" title and the rhosgfx king as logo, without the decorative circle;
   - Settings: a theme picker with 4-colour swatches.
4. **Strings:** set `app.title = "Chess"` in both locales. Add theme names (vi/en from §5.12) and any new keys to **both** locale files (UTF-8, LF, real diacritics).
5. **Tests you write** (new files only; never modify existing tests):
   - `another/tests/gui/test_theme.py`: every theme defines every role; WCAG contrast ratios as required by §5.12, computed with the standard relative-luminance formula; ids match the config whitelist; no role is a duplicate of `bg` where that would make it invisible.
   - `another/tests/gui/test_render_scale.py` (headless): with windows 960×640, 1440×960 and 1920×1080, `canvas_size == (viewport.width, viewport.height)` and `render_scale == viewport.scale`; clicks via `click_window` still hit the right square at each size; `set_theme` persists and changes the board colours.
   - A guard test that greps `frontend/gui/screens` and `frontend/gui/widgets` for colour literals (`(r, g, b)` tuples or `#rrggbb`) and fails if any remain outside `frontend/gui/theme.py`.
6. Extend `another/tools/render_previews.py` to render every screen for **every theme** (vi) plus the menu in en, at window 1440×960, into `.preview/`. Run it and list the paths.

## Done
Follow `AGENTS.md`. All existing tests stay green and unmodified. `pytest -q --basetemp=.pytest-tmp`, `ruff check .`, `ruff format --check .` and `lint-imports` must all be green. Touch only `frontend/gui/**`, `another/tests/gui/` (new files), `another/tools/render_previews.py`, `main.py`.
