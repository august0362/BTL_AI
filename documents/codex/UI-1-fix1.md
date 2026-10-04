# Codex prompt — UI-1 fix round 1: finish crisp rendering + selection states

> Follows UI-1 (merged). Branch: `fix/ui-crisp`.

---

QA review of UI-1 (see `.preview/` at 1440×960) found:

1. **Still blurry/pixelated — the main complaint is NOT fixed.** Screens still draw on a 960×640 surface that is scaled to the window (now nearest-neighbour, which gives jagged text and pieces). Finish §5.12 "Độ nét":
   - Refactor **every** screen and widget to draw through `frontend/gui/render.py` directly onto a surface of size `(viewport.width, viewport.height)`.
   - Logical coordinates stay for layout and hit-testing; rendering multiplies by `render_scale`.
   - Fonts are created at `round(size * scale)` px; piece images are smoothscaled from the 256 px PNG to the physical square size (cached per size).
   - Line widths and radii are scaled.
   - **No `pygame.transform.scale`/`smoothscale` of a full-screen surface anywhere.**
2. **Selection states are inverted or unclear** (seen in Settings with the `fall` theme: the selected "Tiếng Việt" looks dimmer than the unselected "English", and every button is the primary colour).
   - Selected option in a group: `accent` fill, `on_accent` text, plus a 2 px border.
   - Unselected options: `secondary`.
   - Only one `primary` button per screen (Settings: none; the menu: "Người vs Bot"; setup screens: "Bắt đầu").
   - Add `accent`/`on_accent` contrast to the theme tests if missing.
3. **Speaker button:** the label "Tắt"/"Bật" is tiny and overlaps the icon. Give the icon its own area, use at least the 13 px type size, and leave an 8 px gap.

## Tests you add (new tests only; keep existing ones unchanged)
- `another/tests/gui/test_crisp_render.py` (headless, window 1440×960):
  - Monkeypatch `pygame.transform.scale` and `pygame.transform.smoothscale` to record the sizes they are called with. Render one frame of each screen, and assert that no call has a source surface of size ≥ 900×600 (i.e. no full-canvas scaling).
  - Assert that the surface blitted to the display has the viewport size.
  - Assert that the font used for body text has pixel height ≥ 1.4× its height at scale 1.
- A test that, for every theme, the selected button colour differs from the unselected one with contrast ≥ 1.5:1 (so selection is visible).

Run `another/tools/render_previews.py` (all themes, 1440×960) and list the PNGs.

## Done
Follow `AGENTS.md`. `pytest -q --basetemp=.pytest-tmp`, `ruff check .`, `ruff format --check .` and `lint-imports` must all be green. Touch only `frontend/gui/**`, new files in `another/tests/gui/`, and `another/tools/render_previews.py`.
