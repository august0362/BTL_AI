# Codex prompt — UI-2: 18 Color Hunt themes + derivation algorithm + theme picker

> Wave after UI-1-fix1 is merged. Branch: `feat/ui-colorhunt-themes`.

---

Implement `documents/CONTEXT.md` **§5.13** and write the tests yourself.

## Deliverables
- In `frontend/gui/theme.py` (or a new `frontend/gui/theme_derive.py`):
  - WCAG helpers: `relative_luminance` and `contrast_ratio`.
  - Colour adjustment helpers: lighten/darken that keep the hue (HLS).
  - `derive_theme(palette: list[str]) -> Theme`, following the 6 steps exactly.
  - Discovery of `frontend/resource/theme/Color Hunt Palette <hex>.png` from filenames, with duplicate skipping, ids `ch_<hex6>`, and the vi/en names from the table (stored in both locale files under `themes.<id>`, falling back to "Color Hunt #<hex>").
- Every theme, including the 6 existing ones, must pass the §5.12/§5.13 contrast thresholds. Adjust the hand-picked values if needed.
- Settings theme picker for 24 themes:
  - "Tối" and "Sáng" groups;
  - scrollable via `handle_scroll` and drawn ▲/▼;
  - selected tile with an `accent` border;
  - hover shows a live preview on the Settings screen; click applies and persists via `App.set_theme`.
- `another/tests/gui/test_theme_derive.py`:
  - contrast math against known values (black/white = 21, #777777 on white ≈ 4.48);
  - every discovered theme passes every threshold, including piece-outline visibility on both board squares;
  - the dark/light classification;
  - the duplicate palette is skipped;
  - an unknown new palette file (create one in `tmp_path` with a patched theme dir) yields a valid theme with a fallback name.
- Extend `another/tests/gui/test_app_m4_smoke.py` **by appending only**: render every screen once under every theme (24 × screens, headless, small window) without errors.
- `another/tools/render_previews.py`:
  - render the menu and game for all 24 themes;
  - render Settings scrolled to the top and to the bottom;
  - save as `.preview/themes/<id>_<screen>.png`;
  - also build a single contact sheet `.preview/themes/_all.png` (a grid of the 24 game screenshots, each with its name) for quick QA. List the paths.

## Done
Follow `AGENTS.md`. Keep existing tests unchanged, except for appending to the smoke test as stated. `pytest -q --basetemp=.pytest-tmp`, `ruff check .`, `ruff format --check .` and `lint-imports` must all be green. Touch only `frontend/gui/**`, `another/tests/gui/`, `another/tools/render_previews.py`.
