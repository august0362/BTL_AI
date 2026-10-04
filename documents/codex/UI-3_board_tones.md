# Codex prompt — UI-3: calmer board colours for all themes

> Branch: `fix/ui-board-tones`. Runs in parallel with DOC-1 and LOCAL-1.

---

QA of `.preview/themes/_all.png` found that several themes have board squares that are too saturated for long viewing: `ch_499a13` (Spring Leaf: lime), `cold` (Sky) and `dark_cold` (Deep Sea: vivid blue), `ch_ffeecc` (Cotton Candy) and `ch_ffdcdc` (Strawberry Milk: strong orange/amber).

Colour-psychology and design rule: board squares are a **background** for the pieces, so they must be calm. The palette hue is kept, but the board is muted.

## Change (in the theme derivation, `frontend/gui/theme.py`)
- After choosing `board_light`/`board_dark` for **every** theme (hand-picked ones included), clamp them in HLS:
  - saturation: `board_light` ≤ 0.35, `board_dark` ≤ 0.45;
  - lightness: `board_light` in [0.78, 0.94], `board_dark` in [0.38, 0.62].
- Keep the existing thresholds: light/dark contrast ≥ 1.6:1, and piece outline (black) ≥ 3:1 on both squares.
- `board_select`, `board_last` and `board_hint` must stay clearly visible on both squares (≥ 1.3:1 against the square colour).
- UI colours (`primary`, `accent`, …) keep their vividness. Only the board is muted.

## Tests (new tests only)
- `another/tests/gui/test_board_tones.py`: for every theme, the HLS saturation and lightness bounds above, plus the visibility of the overlay colours.

## Verify
Regenerate `.preview/themes/` (incl. `_all.png`) and list the paths.

Follow `AGENTS.md`. Touch only `frontend/gui/theme.py` (and a helper module if needed), `another/tests/gui/test_board_tones.py`. `pytest -q --basetemp=.pytest-tmp`, `ruff check .`, `ruff format --check .` and `lint-imports` must all be green.
