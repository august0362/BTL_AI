# Codex prompt — M3-C fix round 1: layout issues found in QA

> Follows M3-C (merged). Branch: `fix/gui-layout-1` · One PR.

---

QA rendered the MVP screens headless and found the layout bugs below. Fix all of them. Do not change behaviour that the tests cover.

## Bugs
1. **Setup screen: bot button text overflows.** "Alpha-Beta + Hồi quy" and "Alpha-Beta + Di truyền" are wider than their buttons and overlap the neighbouring button. Make labels fit: use a single-column list of full-width buttons, or shrink the font until the text fits. Never draw text outside its button.
2. **Setup screen: duplicated info column.** A right-hand column repeats "Chọn bot" and every bot name with "Không khả dụng: …", and it overlaps the colour buttons. Remove that column. Show the unavailable reason inside or directly under the disabled bot's own button (small, muted text), and keep the colour row inside the canvas without overlapping anything.
3. **Game panel: collapse/expand arrow renders as a tofu box (□)** for expanded sections, because the font lacks the glyph. Draw the arrow as a small filled triangle with `pygame.draw.polygon` (▶ collapsed, ▼ expanded) instead of a text glyph.
4. **Game panel "score" section:**
   - "White" and "Black" are hard-coded English. Use `t("setup.color_white")` and `t("setup.color_black")`.
   - The "your turn" / "thinking" line is clipped by the next section header. Compute each section's height from its content so that nothing overlaps.
5. **General:** no text may overflow its widget or overlap another widget on any MVP screen, in either `vi` or `en`.

## How to verify (required)
- Write a small dev script `another/tools/render_previews.py`. With `SDL_VIDEODRIVER=dummy`, it renders menu, setup_human, and game (after 3 human moves vs the random bot, with a piece selected) in **both languages**, and saves PNGs to `.preview/` at the repo root. That directory is gitignored and is not cleaned by pytest. Run it and list the PNG paths in your final message.
- Run `.venv\Scripts\python -m pytest -q --basetemp=.pytest-tmp`, `ruff check .`, `ruff format --check .` and `lint-imports`, all green.

## Constraints
- Follow `AGENTS.md` (write files as UTF-8 with LF via apply_patch).
- Touch only `frontend/gui/screens/`, `frontend/gui/widgets/`, `frontend/gui/app.py`, `frontend/gui/assets_loader.py`, `frontend/gui/locales/*.toml` (only if you need a key; add it to both files) and the new `another/tools/render_previews.py`.
